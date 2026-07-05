#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import grpc
from p4.v1 import p4runtime_pb2

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from p4rt import (
    ArbitrationError,
    P4RuntimeClient,
    TableEntryBuilder,
    parse_election_id,
    update,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Counter 与 meter 实验")
    parser.add_argument("--grpc-addr", default="127.0.0.1:9559")
    parser.add_argument("--device-id", type=int, default=1)
    parser.add_argument("--election-id", type=parse_election_id, default=(0, 1))
    parser.add_argument("--p4info", type=Path, required=True)
    parser.add_argument("--device-config", type=Path, required=True)
    parser.add_argument("--no-wait", action="store_true", help="不等待手工发包")
    return parser.parse_args()


def route(index, address: str, src_mac: str, dst_mac: str, port: int):
    return (
        TableEntryBuilder(index, "route_v4")
        .lpm("dst_addr", address, 32)
        .action(
            "rewrite_and_forward",
            src_mac=src_mac,
            dst_mac=dst_mac,
            port=port,
        )
        .build()
    )


def print_resources(client: P4RuntimeClient) -> None:
    print("\nindirect counter（按输出端口索引）：")
    for index in (1, 2):
        entry = next(client.read_counter("port_packets", index))
        print(
            f"  index {index}: packets={entry.data.packet_count}, "
            f"bytes={entry.data.byte_count}"
        )

    print("direct counter（绑定 route_v4 entry）：")
    for entry in client.read_direct_counters("route_v4"):
        match = entry.table_entry.match[0].lpm
        address = ".".join(str(byte) for byte in match.value.rjust(4, b"\x00"))
        print(
            f"  {address}/{match.prefix_len}: packets={entry.data.packet_count}, "
            f"bytes={entry.data.byte_count}"
        )

    print("meter 配置：")
    for index in (1, 2):
        entry = next(client.read_meter("port_meter", index))
        config = entry.config
        print(
            f"  index {index}: cir={config.cir}, cburst={config.cburst}, "
            f"pir={config.pir}, pburst={config.pburst}"
        )


def main() -> int:
    args = parse_args()
    try:
        with P4RuntimeClient(
            args.grpc_addr,
            device_id=args.device_id,
            election_id=args.election_id,
        ) as client:
            index = client.set_pipeline(args.p4info, args.device_config)
            for meter_index in (1, 2):
                client.configure_meter(
                    "port_meter",
                    meter_index,
                    cir=1000,
                    cburst=100,
                    pir=1000,
                    pburst=100,
                )

            entries = (
                route(
                    index,
                    "10.0.1.1",
                    "00:aa:00:00:00:01",
                    "00:00:00:00:01:01",
                    1,
                ),
                route(
                    index,
                    "10.0.1.2",
                    "00:aa:00:00:00:02",
                    "00:00:00:00:01:02",
                    2,
                ),
            )
            client.write(
                [update(p4runtime_pb2.Update.INSERT, entry) for entry in entries]
            )
            print("pipeline、两条路由和两个 meter cell 已配置。")
            if not args.no_wait:
                input("请在 Mininet 中执行 h1 ping -c 5 h2，然后回车读取资源：")
            print_resources(client)
    except grpc.RpcError as error:
        print(f"gRPC 失败：{error.code().name}: {error.details()}", file=sys.stderr)
        return 1
    except (ArbitrationError, EOFError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"实验失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
