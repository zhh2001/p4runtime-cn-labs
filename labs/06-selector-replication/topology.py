#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.topo import Topo

from tools.p4_mininet import P4RuntimeSwitch


class BackendTopo(Topo):
    def build(self, grpc_addr: str, device_id: int, cpu_port: int) -> None:
        h1 = self.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
        h2 = self.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
        h3 = self.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")
        s1 = self.addSwitch(
            "s1",
            cls=P4RuntimeSwitch,
            grpc_addr=grpc_addr,
            device_id=device_id,
            cpu_port=cpu_port,
            log_dir=str(REPO_ROOT / "build" / "logs"),
        )
        self.addLink(h1, s1, port2=1)
        self.addLink(h2, s1, port2=2)
        self.addLink(h3, s1, port2=3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Selector 与 multicast 实验拓扑")
    parser.add_argument("--grpc-addr", default="127.0.0.1:9559")
    parser.add_argument("--device-id", type=int, default=1)
    parser.add_argument("--cpu-port", type=int, default=510)
    parser.add_argument("--no-cli", action="store_true")
    parser.add_argument("--duration", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.device_id == 0:
        raise SystemExit("P4Runtime v1.5.0 不允许 device_id=0")

    setLogLevel("info")
    network = Mininet(
        topo=BackendTopo(
            grpc_addr=args.grpc_addr,
            device_id=args.device_id,
            cpu_port=args.cpu_port,
        ),
        controller=None,
    )
    try:
        network.start()
        h1, h2, h3 = network.get("h1", "h2", "h3")
        h1.setARP("10.0.0.100", "00:aa:00:00:00:64")
        for backend in (h2, h3):
            backend.cmd("ip addr add 10.0.0.100/32 dev lo")
            backend.setARP("10.0.0.1", "00:00:00:00:00:01")
        print(f"\nP4Runtime server: {args.grpc_addr}, device_id={args.device_id}")
        print("VIP 10.0.0.100 同时配置在 h2、h3 的 loopback。")
        print("日志：build/logs/s1.log\n")
        if args.no_cli:
            time.sleep(args.duration)
        else:
            CLI(network)
    finally:
        network.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
