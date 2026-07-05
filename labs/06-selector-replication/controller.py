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
    entity_update,
    multicast_group,
    parse_election_id,
    profile_group,
    profile_member,
    update,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Action selector 与 multicast 实验")
    parser.add_argument("--grpc-addr", default="127.0.0.1:9559")
    parser.add_argument("--device-id", type=int, default=1)
    parser.add_argument("--election-id", type=parse_election_id, default=(0, 1))
    parser.add_argument("--p4info", type=Path, required=True)
    parser.add_argument("--device-config", type=Path, required=True)
    parser.add_argument("--no-wait", action="store_true")
    return parser.parse_args()


def table_to_group(index, address: str, group_id: int):
    return (
        TableEntryBuilder(index, "service_route")
        .exact("dst_addr", address)
        .group_id(group_id)
        .build()
    )


def table_to_member(index, address: str, member_id: int):
    return (
        TableEntryBuilder(index, "service_route")
        .exact("dst_addr", address)
        .member_id(member_id)
        .build()
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

            members = [
                profile_member(
                    index,
                    "backend_selector",
                    1,
                    "set_nhop",
                    src_mac="00:aa:00:00:00:02",
                    dst_mac="00:00:00:00:00:02",
                    port=2,
                ),
                profile_member(
                    index,
                    "backend_selector",
                    2,
                    "set_nhop",
                    src_mac="00:aa:00:00:00:03",
                    dst_mac="00:00:00:00:00:03",
                    port=3,
                ),
                profile_member(
                    index,
                    "backend_selector",
                    3,
                    "set_nhop",
                    src_mac="00:aa:00:00:00:01",
                    dst_mac="00:00:00:00:00:01",
                    port=1,
                ),
                profile_member(
                    index,
                    "backend_selector",
                    4,
                    "multicast",
                    group_id=1,
                ),
            ]
            client.write(
                [
                    entity_update(p4runtime_pb2.Update.INSERT, member)
                    for member in members
                ]
            )

            group = profile_group(
                index,
                "backend_selector",
                100,
                [(1, 1), (2, 1)],
                max_size=2,
            )
            multicast = multicast_group(1, [(2, 1), (3, 2)])
            client.write(
                [
                    entity_update(p4runtime_pb2.Update.INSERT, group),
                    entity_update(p4runtime_pb2.Update.INSERT, multicast),
                ]
            )

            table_entries = (
                table_to_group(index, "10.0.0.100", 100),
                table_to_member(index, "10.0.0.1", 3),
                table_to_member(index, "239.1.1.1", 4),
            )
            client.write(
                [
                    update(p4runtime_pb2.Update.INSERT, entry)
                    for entry in table_entries
                ]
            )

            print("4 个 member、group 100、multicast group 1 和 3 条表项已安装。")
            if not args.no_wait:
                input("请在 Mininet 中完成 VIP 与组播测试，然后回车读取状态：")

            print("\nselector 成员：", len(list(client.read_profile_members("backend_selector"))))
            groups = list(client.read_profile_groups("backend_selector"))
            print("selector groups：", len(groups))
            print("group 100 member IDs：", [item.member_id for item in groups[0].members])
            for port in (2, 3):
                counter = next(client.read_counter("output_packets", port))
                print(f"output port {port}: {counter.data.packet_count} packets")
            replicas = list(client.read_multicast_groups(1))[0].replicas
            print("multicast group 1 ports：", [int.from_bytes(item.port, "big") for item in replicas])
    except grpc.RpcError as error:
        print(f"gRPC 失败：{error.code().name}: {error.details()}", file=sys.stderr)
        return 1
    except (ArbitrationError, EOFError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"实验失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
