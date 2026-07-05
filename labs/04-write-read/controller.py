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
    P4RuntimeWriteError,
    TableEntryBuilder,
    parse_election_id,
    update,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TableEntry batch 与错误解析实验")
    parser.add_argument("--grpc-addr", default="127.0.0.1:9559")
    parser.add_argument("--device-id", type=int, default=1)
    parser.add_argument("--election-id", type=parse_election_id, default=(0, 1))
    parser.add_argument("--p4info", type=Path, required=True)
    parser.add_argument("--device-config", type=Path, required=True)
    return parser.parse_args()


def allow_entry(index, address: str):
    return (
        TableEntryBuilder(index, "allow_src")
        .exact("src_addr", address)
        .action("permit")
        .build()
    )


def route_entry(index, address: str, src_mac: str, dst_mac: str, port: int):
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


def count(client: P4RuntimeClient, table_name: str) -> int:
    return len(list(client.read_table(table_name)))


def main() -> int:
    args = parse_args()

    try:
        with P4RuntimeClient(
            args.grpc_addr,
            device_id=args.device_id,
            election_id=args.election_id,
        ) as client:
            index = client.set_pipeline(args.p4info, args.device_config)

            allow_h1 = allow_entry(index, "10.0.1.1")
            allow_h2 = allow_entry(index, "10.0.1.2")
            route_h1 = route_entry(
                index,
                "10.0.1.1",
                "00:aa:00:00:00:01",
                "00:00:00:00:01:01",
                1,
            )
            route_h2 = route_entry(
                index,
                "10.0.1.2",
                "00:aa:00:00:00:02",
                "00:00:00:00:01:02",
                2,
            )

            inserts = [
                update(p4runtime_pb2.Update.INSERT, entry)
                for entry in (allow_h1, allow_h2, route_h1, route_h2)
            ]
            client.write(inserts)
            print("batch INSERT：4 条 update 全部成功")
            print(f"wildcard Read：allow_src={count(client, 'allow_src')}")
            print(f"wildcard Read：route_v4={count(client, 'route_v4')}")

            try:
                client.write(
                    [
                        update(p4runtime_pb2.Update.INSERT, allow_h1),
                        update(p4runtime_pb2.Update.INSERT, route_h2),
                    ]
                )
            except P4RuntimeWriteError as error:
                print("\n预期中的重复 INSERT：")
                print(error)
                if len(error.details) != 2:
                    raise RuntimeError("server 没有返回两个逐项错误") from error
            else:
                raise RuntimeError("重复 INSERT 没有失败")

            route_h2_wrong_port = route_entry(
                index,
                "10.0.1.2",
                "00:aa:00:00:00:02",
                "00:00:00:00:01:02",
                1,
            )
            client.write([update(p4runtime_pb2.Update.MODIFY, route_h2_wrong_port)])
            print("\nMODIFY：临时把 10.0.1.2/32 改到 port 1")
            client.write([update(p4runtime_pb2.Update.MODIFY, route_h2)])
            print("MODIFY：恢复到 port 2")

            client.write([update(p4runtime_pb2.Update.DELETE, route_h2)])
            print(f"DELETE 后 route_v4={count(client, 'route_v4')}")
            client.write([update(p4runtime_pb2.Update.INSERT, route_h2)])
            print(f"重新 INSERT 后 route_v4={count(client, 'route_v4')}")
    except grpc.RpcError as error:
        print(f"gRPC 失败：{error.code().name}: {error.details()}", file=sys.stderr)
        return 1
    except (ArbitrationError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"实验失败：{error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
