#!/usr/bin/env python3

from __future__ import annotations

import argparse
import queue
import sys
from pathlib import Path

import grpc
from google.rpc import code_pb2
from p4.v1 import p4runtime_pb2

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from p4rt import (
    ArbitrationError,
    P4RuntimeClient,
    P4RuntimeWriteError,
    TableEntryBuilder,
    decode_packet_in,
    parse_election_id,
    update,
)


PORT_BY_MAC = {
    bytes.fromhex("000000000001"): 1,
    bytes.fromhex("000000000002"): 2,
}
PROBE_MAC = "00:00:00:00:00:99"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Packet I/O 与主备切换 controller")
    parser.add_argument("--grpc-addr", default="127.0.0.1:9559")
    parser.add_argument("--device-id", type=int, default=1)
    parser.add_argument("--election-id", type=parse_election_id, default=(0, 1))
    parser.add_argument("--p4info", type=Path, required=True)
    parser.add_argument("--device-config", type=Path, required=True)
    parser.add_argument("--name", default="controller")
    parser.add_argument("--install-pipeline", action="store_true")
    parser.add_argument("--promote-election-id", type=parse_election_id)
    return parser.parse_args()


def probe_update(index, update_type: int):
    entry = (
        TableEntryBuilder(index, "punt_policy")
        .exact("dst_addr", PROBE_MAC)
        .action("drop")
        .build()
    )
    return update(update_type, entry)


def verify_backup_write_is_denied(client: P4RuntimeClient, index) -> None:
    request = client.build_write_request(
        [probe_update(index, p4runtime_pb2.Update.INSERT)]
    )
    try:
        client.stub.Write(request, timeout=client.timeout)
    except grpc.RpcError as error:
        if error.code() != grpc.StatusCode.PERMISSION_DENIED:
            raise
        print("backup 的 Write 被 server 拒绝：PERMISSION_DENIED", flush=True)
        return
    raise RuntimeError("backup 的 Write 不应成功")


def verify_primary_write(client: P4RuntimeClient, index) -> None:
    client.write([probe_update(index, p4runtime_pb2.Update.INSERT)])
    client.write([probe_update(index, p4runtime_pb2.Update.DELETE)])
    print("接管后的 Write 已成功，测试表项也已清理。", flush=True)


def relay_packet(client: P4RuntimeClient, response, index) -> None:
    packet = response.packet
    fields = decode_packet_in(index, packet)
    if len(packet.payload) < 14:
        print("忽略过短的 PacketIn", flush=True)
        return

    egress_port = PORT_BY_MAC.get(packet.payload[:6])
    if egress_port is None:
        return

    client.send_packet_out(packet.payload, egress_port=egress_port)
    print(
        f"PacketIn port {fields['ingress_port']} -> PacketOut port {egress_port}, "
        f"reason={fields['reason']}",
        flush=True,
    )


def run(client: P4RuntimeClient, index, args: argparse.Namespace) -> None:
    active = client.is_primary
    takeover_verified = False
    while True:
        try:
            event = client.wait_for_arbitration(timeout=0 if active else 0.5)
        except queue.Empty:
            event = None

        if event is not None:
            status_name = code_pb2.Code.Name(event.status.code)
            print(f"arbitration 通知：{status_name}", flush=True)
            active = event.status.code == code_pb2.OK
            can_take_over = event.status.code in (code_pb2.NOT_FOUND, code_pb2.OK)
            if not can_take_over or args.promote_election_id is None:
                continue

            if client.election_id != args.promote_election_id:
                print(f"将 election_id 更新为 {args.promote_election_id}", flush=True)
                if not client.update_election_id(args.promote_election_id):
                    raise ArbitrationError("新的 election ID 仍未取得 primary 权限")
                active = True
            if not takeover_verified:
                print(f"{args.name} 已成为 primary", flush=True)
                verify_primary_write(client, index)
                takeover_verified = True
            continue

        if not active:
            continue
        try:
            response = client.receive_stream(timeout=0.5)
        except queue.Empty:
            continue
        if response.HasField("packet"):
            relay_packet(client, response, index)
        elif response.HasField("error"):
            print(f"StreamError：{response.error.message}", flush=True)


def main() -> int:
    args = parse_args()
    try:
        with P4RuntimeClient(
            args.grpc_addr,
            device_id=args.device_id,
            election_id=args.election_id,
            require_primary=False,
        ) as client:
            state = "primary" if client.is_primary else "backup"
            status = code_pb2.Code.Name(client.last_arbitration.status.code)
            print(
                f"{args.name} 已连接：election_id={args.election_id}, "
                f"state={state}, status={status}",
                flush=True,
            )

            if args.install_pipeline:
                if not client.is_primary:
                    raise ArbitrationError("只有 primary 能安装 pipeline")
                index = client.set_pipeline(args.p4info, args.device_config)
                print("pipeline 已安装", flush=True)
            else:
                client.get_p4info()
                index = client.p4info_index

            if not client.is_primary:
                verify_backup_write_is_denied(client, index)

            run(client, index, args)
    except KeyboardInterrupt:
        print("\ncontroller 已退出")
    except grpc.RpcError as error:
        print(f"gRPC 失败：{error.code().name}: {error.details()}", file=sys.stderr)
        return 1
    except (
        ArbitrationError,
        OSError,
        P4RuntimeWriteError,
        RuntimeError,
        TimeoutError,
        ValueError,
    ) as error:
        print(f"controller 失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
