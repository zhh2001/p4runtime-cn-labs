"""P4Runtime 1.5 gRPC session 与 pipeline 配置。"""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from pathlib import Path

import grpc
from google.protobuf import text_format
from p4.config.v1 import p4info_pb2
from p4.v1 import p4runtime_pb2, p4runtime_pb2_grpc

from .p4info import P4InfoIndex
from .errors import P4RuntimeWriteError


class ArbitrationError(RuntimeError):
    pass


def parse_election_id(value: str) -> tuple[int, int]:
    try:
        high_text, low_text = value.split(",", maxsplit=1)
        high, low = int(high_text, 0), int(low_text, 0)
    except (TypeError, ValueError) as error:
        raise ValueError("election ID 应写成 <high>,<low>") from error

    limit = (1 << 64) - 1
    if not 0 <= high <= limit or not 0 <= low <= limit:
        raise ValueError("election ID 的 high 和 low 必须是 uint64")
    return high, low


def load_p4info(path: str | Path) -> p4info_pb2.P4Info:
    p4info = p4info_pb2.P4Info()
    text_format.Parse(Path(path).read_text(encoding="utf-8"), p4info)
    return p4info


class P4RuntimeClient:
    def __init__(
        self,
        grpc_addr: str = "127.0.0.1:9559",
        *,
        device_id: int = 1,
        election_id: tuple[int, int] = (0, 1),
        role_name: str = "",
        timeout: float = 5.0,
    ) -> None:
        if device_id == 0:
            raise ValueError("P4Runtime v1.5.0 不允许 device_id=0")
        if device_id < 0 or device_id >= 1 << 64:
            raise ValueError("device_id 必须是 uint64")

        high, low = election_id
        limit = (1 << 64) - 1
        if not 0 <= high <= limit or not 0 <= low <= limit:
            raise ValueError("election ID 的 high 和 low 必须是 uint64")

        self.grpc_addr = grpc_addr
        self.device_id = device_id
        self.election_id = election_id
        self.role_name = role_name
        self.timeout = timeout

        self.channel = None
        self.stub = None
        self.is_primary = False
        self.p4info = None
        self.p4info_index = None

        self._requests = queue.Queue()
        self._arbitration_events = queue.Queue()
        self._stream_messages = queue.Queue()
        self._receiver = None
        self._responses = None
        self._closing = threading.Event()

    def __enter__(self) -> "P4RuntimeClient":
        return self.connect()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def connect(self) -> "P4RuntimeClient":
        if self.channel is not None:
            return self

        self._closing.clear()
        self._requests = queue.Queue()
        self._arbitration_events = queue.Queue()
        self._stream_messages = queue.Queue()
        self.channel = grpc.insecure_channel(self.grpc_addr)
        try:
            grpc.channel_ready_future(self.channel).result(timeout=self.timeout)
        except grpc.FutureTimeoutError as error:
            self.close()
            raise TimeoutError(f"连接 P4Runtime server 超时：{self.grpc_addr}") from error

        self.stub = p4runtime_pb2_grpc.P4RuntimeStub(self.channel)
        self._responses = self.stub.StreamChannel(self._request_iterator())
        self._receiver = threading.Thread(
            target=self._receive_stream,
            name=f"p4runtime-{self.device_id}-stream",
            daemon=True,
        )
        self._receiver.start()

        self.send_stream(self._arbitration_request())
        try:
            event = self._arbitration_events.get(timeout=self.timeout)
        except queue.Empty as error:
            self.close()
            raise TimeoutError("等待 arbitration response 超时") from error

        if isinstance(event, grpc.RpcError):
            self.close()
            raise ArbitrationError(f"StreamChannel 失败：{event.code().name}") from event

        self.is_primary = event.status.code == 0
        if not self.is_primary:
            message = event.status.message or "server 未授予 primary 权限"
            self.close()
            raise ArbitrationError(message)
        return self

    def _arbitration_request(self) -> p4runtime_pb2.StreamMessageRequest:
        request = p4runtime_pb2.StreamMessageRequest()
        update = request.arbitration
        update.device_id = self.device_id
        update.election_id.high, update.election_id.low = self.election_id
        if self.role_name:
            update.role.name = self.role_name
        return request

    def _request_iterator(self) -> Iterator[p4runtime_pb2.StreamMessageRequest]:
        while True:
            request = self._requests.get()
            if request is None:
                return
            yield request

    def _receive_stream(self) -> None:
        try:
            for response in self._responses:
                if response.HasField("arbitration"):
                    self._arbitration_events.put(response.arbitration)
                else:
                    self._stream_messages.put(response)
        except grpc.RpcError as error:
            if not self._closing.is_set():
                self._arbitration_events.put(error)
                self._stream_messages.put(error)

    def send_stream(self, request: p4runtime_pb2.StreamMessageRequest) -> None:
        if self.stub is None:
            raise RuntimeError("client 尚未连接")
        self._requests.put(request)

    def receive_stream(self, timeout: float | None = None):
        message = self._stream_messages.get(timeout=timeout)
        if isinstance(message, grpc.RpcError):
            raise message
        return message

    def capabilities(self) -> p4runtime_pb2.CapabilitiesResponse:
        self._require_connected()
        request = p4runtime_pb2.CapabilitiesRequest(device_id=self.device_id)
        return self.stub.Capabilities(request, timeout=self.timeout)

    def build_pipeline_request(
        self,
        p4info_path: str | Path,
        device_config_path: str | Path,
    ) -> p4runtime_pb2.SetForwardingPipelineConfigRequest:
        request = p4runtime_pb2.SetForwardingPipelineConfigRequest(
            device_id=self.device_id,
            action=p4runtime_pb2.SetForwardingPipelineConfigRequest.VERIFY_AND_COMMIT,
        )
        request.election_id.high, request.election_id.low = self.election_id
        if self.role_name:
            request.role = self.role_name
        request.config.p4info.CopyFrom(load_p4info(p4info_path))
        request.config.p4_device_config = Path(device_config_path).read_bytes()
        return request

    def set_pipeline(
        self,
        p4info_path: str | Path,
        device_config_path: str | Path,
    ) -> P4InfoIndex:
        self._require_primary()
        request = self.build_pipeline_request(p4info_path, device_config_path)
        self.stub.SetForwardingPipelineConfig(request, timeout=self.timeout)
        self.p4info = request.config.p4info
        self.p4info_index = P4InfoIndex(self.p4info)
        return self.p4info_index

    def get_p4info(self) -> p4info_pb2.P4Info:
        self._require_connected()
        request = p4runtime_pb2.GetForwardingPipelineConfigRequest(
            device_id=self.device_id,
            response_type=p4runtime_pb2.GetForwardingPipelineConfigRequest.P4INFO_AND_COOKIE,
        )
        response = self.stub.GetForwardingPipelineConfig(request, timeout=self.timeout)
        self.p4info = response.config.p4info
        self.p4info_index = P4InfoIndex(self.p4info)
        return self.p4info

    def write(
        self,
        updates,
        *,
        atomicity: int = p4runtime_pb2.WriteRequest.CONTINUE_ON_ERROR,
    ) -> None:
        self._require_primary()
        request = p4runtime_pb2.WriteRequest(
            device_id=self.device_id,
            atomicity=atomicity,
        )
        request.election_id.high, request.election_id.low = self.election_id
        if self.role_name:
            request.role = self.role_name
        request.updates.extend(updates)
        try:
            self.stub.Write(request, timeout=self.timeout)
        except grpc.RpcError as error:
            raise P4RuntimeWriteError(error) from None

    def read(self, entities):
        self._require_connected()
        request = p4runtime_pb2.ReadRequest(device_id=self.device_id)
        if self.role_name:
            request.role = self.role_name
        request.entities.extend(entities)
        for response in self.stub.Read(request, timeout=self.timeout):
            yield from response.entities

    def read_table(self, table_name_or_id: str | int):
        if self.p4info_index is None:
            raise RuntimeError("尚未读取 P4Info")
        table_id = self.p4info_index.table(table_name_or_id).id
        query = p4runtime_pb2.Entity()
        query.table_entry.table_id = table_id
        for result in self.read([query]):
            yield result.table_entry

    def read_counter(self, counter_name_or_id: str | int, index: int | None = None):
        if self.p4info_index is None:
            raise RuntimeError("尚未读取 P4Info")
        counter_id = self.p4info_index.resolve("counter", counter_name_or_id).id
        query = p4runtime_pb2.Entity()
        query.counter_entry.counter_id = counter_id
        if index is not None:
            query.counter_entry.index.index = index
        for result in self.read([query]):
            yield result.counter_entry

    def read_direct_counters(self, table_name_or_id: str | int):
        if self.p4info_index is None:
            raise RuntimeError("尚未读取 P4Info")
        table_id = self.p4info_index.table(table_name_or_id).id
        query = p4runtime_pb2.Entity()
        query.direct_counter_entry.table_entry.table_id = table_id
        for result in self.read([query]):
            yield result.direct_counter_entry

    def configure_meter(
        self,
        meter_name_or_id: str | int,
        index: int,
        *,
        cir: int,
        cburst: int,
        pir: int,
        pburst: int,
    ) -> None:
        if self.p4info_index is None:
            raise RuntimeError("尚未读取 P4Info")
        meter_id = self.p4info_index.resolve("meter", meter_name_or_id).id
        entry = p4runtime_pb2.MeterEntry(meter_id=meter_id)
        entry.index.index = index
        entry.config.cir = cir
        entry.config.cburst = cburst
        entry.config.pir = pir
        entry.config.pburst = pburst
        request = p4runtime_pb2.Update(type=p4runtime_pb2.Update.MODIFY)
        request.entity.meter_entry.CopyFrom(entry)
        self.write([request])

    def read_meter(self, meter_name_or_id: str | int, index: int | None = None):
        if self.p4info_index is None:
            raise RuntimeError("尚未读取 P4Info")
        meter_id = self.p4info_index.resolve("meter", meter_name_or_id).id
        query = p4runtime_pb2.Entity()
        query.meter_entry.meter_id = meter_id
        if index is not None:
            query.meter_entry.index.index = index
        for result in self.read([query]):
            yield result.meter_entry

    def read_profile_members(self, profile_name_or_id: str | int):
        if self.p4info_index is None:
            raise RuntimeError("尚未读取 P4Info")
        profile_id = self.p4info_index.resolve("action_profile", profile_name_or_id).id
        query = p4runtime_pb2.Entity()
        query.action_profile_member.action_profile_id = profile_id
        for result in self.read([query]):
            yield result.action_profile_member

    def read_profile_groups(self, profile_name_or_id: str | int):
        if self.p4info_index is None:
            raise RuntimeError("尚未读取 P4Info")
        profile_id = self.p4info_index.resolve("action_profile", profile_name_or_id).id
        query = p4runtime_pb2.Entity()
        query.action_profile_group.action_profile_id = profile_id
        for result in self.read([query]):
            yield result.action_profile_group

    def read_multicast_groups(self, group_id: int = 0):
        query = p4runtime_pb2.Entity()
        query.packet_replication_engine_entry.multicast_group_entry.multicast_group_id = group_id
        for result in self.read([query]):
            yield result.packet_replication_engine_entry.multicast_group_entry

    def _require_connected(self) -> None:
        if self.stub is None:
            raise RuntimeError("client 尚未连接")

    def _require_primary(self) -> None:
        self._require_connected()
        if not self.is_primary:
            raise ArbitrationError("当前 controller 不是 primary")

    def close(self) -> None:
        self._closing.set()
        self._requests.put(None)
        if self._responses is not None:
            self._responses.cancel()
        if self._receiver is not None and self._receiver is not threading.current_thread():
            self._receiver.join(timeout=1)
        if self.channel is not None:
            self.channel.close()

        self.channel = None
        self.stub = None
        self._responses = None
        self._receiver = None
        self.is_primary = False
