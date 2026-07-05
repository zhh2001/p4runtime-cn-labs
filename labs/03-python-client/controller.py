#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import grpc

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from p4rt import ArbitrationError, P4RuntimeClient, parse_election_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="安装 pipeline 并读取 P4Info")
    parser.add_argument("--grpc-addr", default="127.0.0.1:9559")
    parser.add_argument("--device-id", type=int, default=1)
    parser.add_argument("--election-id", type=parse_election_id, default=(0, 1))
    parser.add_argument("--p4info", type=Path, required=True)
    parser.add_argument("--device-config", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        with P4RuntimeClient(
            args.grpc_addr,
            device_id=args.device_id,
            election_id=args.election_id,
        ) as client:
            print(
                f"controller 已成为 primary：device_id={args.device_id}, "
                f"election_id={args.election_id}"
            )

            capabilities = client.capabilities()
            print(f"server 声明的 P4Runtime API：{capabilities.p4runtime_api_version}")

            client.set_pipeline(args.p4info, args.device_config)
            p4info = client.get_p4info()
            index = client.p4info_index

            print(f"已安装并读回 pipeline：{p4info.pkg_info.name}")
            print("P4Info tables：")
            for item in index.all("table"):
                print(f"  0x{item.id:08x}  {item.name} (alias: {item.alias})")
            print("P4Info actions：")
            for item in index.all("action"):
                print(f"  0x{item.id:08x}  {item.name} (alias: {item.alias})")
    except grpc.RpcError as error:
        print(f"gRPC 失败：{error.code().name}: {error.details()}", file=sys.stderr)
        return 1
    except (ArbitrationError, OSError, TimeoutError, ValueError) as error:
        print(f"启动失败：{error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
