"""PacketIn / PacketOut metadata 编解码。"""

from __future__ import annotations

from p4.v1 import p4runtime_pb2

from .entities import encode
from .p4info import P4InfoIndex


def _metadata_info(index: P4InfoIndex, header_name: str):
    header = index.resolve("controller_packet_metadata", header_name)
    return {item.name: item for item in header.message.metadata}


def packet_out(
    index: P4InfoIndex,
    payload: bytes,
    **metadata: str | int,
) -> p4runtime_pb2.StreamMessageRequest:
    expected = _metadata_info(index, "packet_out")
    if set(metadata) != set(expected):
        raise ValueError(
            f"PacketOut metadata 不匹配，期望 {sorted(expected)}，"
            f"收到 {sorted(metadata)}"
        )

    request = p4runtime_pb2.StreamMessageRequest()
    request.packet.payload = payload
    for name, value in metadata.items():
        info = expected[name]
        request.packet.metadata.add(
            metadata_id=info.id,
            value=encode(value, info.bitwidth),
        )
    return request


def decode_packet_in(
    index: P4InfoIndex,
    packet: p4runtime_pb2.PacketIn,
) -> dict[str, int]:
    expected = _metadata_info(index, "packet_in")
    names_by_id = {item.id: item for item in expected.values()}
    result = {}
    for field in packet.metadata:
        info = names_by_id.get(field.metadata_id)
        if info is None:
            raise ValueError(f"未知 PacketIn metadata ID：{field.metadata_id}")
        if info.name in result:
            raise ValueError(f"PacketIn metadata 重复：{info.name}")
        result[info.name] = int.from_bytes(field.value, "big")

    if set(result) != set(expected):
        raise ValueError(
            f"PacketIn metadata 不完整，期望 {sorted(expected)}，"
            f"收到 {sorted(result)}"
        )
    return result
