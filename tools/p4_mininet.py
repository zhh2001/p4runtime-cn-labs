#!/usr/bin/env python3

"""Mininet 中用于启动 simple_switch_grpc 的轻量适配层。"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

from mininet.node import Switch


class P4RuntimeSwitch(Switch):
    """以 --no-p4 模式启动 BMv2，等待 controller 安装 pipeline。"""

    def __init__(
        self,
        name: str,
        *,
        grpc_addr: str = "127.0.0.1:9559",
        device_id: int = 1,
        cpu_port: int = 510,
        log_dir: str = "build/logs",
        sw_path: str = "simple_switch_grpc",
        **params,
    ) -> None:
        super().__init__(name, **params)
        self.grpc_addr = grpc_addr
        self.device_id = device_id
        self.cpu_port = cpu_port
        self.log_dir = Path(log_dir)
        self.sw_path = sw_path
        self._process = None
        self._log_file = None

    def start(self, controllers) -> None:
        del controllers

        command = [
            self.sw_path,
            "--device-id",
            str(self.device_id),
            "--no-p4",
            "--log-console",
        ]

        for interface in self.intfList():
            if interface.name == "lo":
                continue
            port = self.ports[interface]
            interface.ifconfig("up")
            command.extend(["-i", f"{port}@{interface.name}"])

        command.extend(
            [
                "--",
                "--grpc-server-addr",
                self.grpc_addr,
                "--cpu-port",
                str(self.cpu_port),
            ]
        )

        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / f"{self.name}.log"
        self._log_file = log_path.open("w", encoding="utf-8")
        self._restore_log_ownership(log_path)
        self._process = self.popen(
            command,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
        )

        try:
            self._wait_until_ready(timeout=5.0)
        except Exception:
            self.stop()
            raise RuntimeError(f"{self.name} 启动失败，请查看 {log_path}") from None

    def _wait_until_ready(self, timeout: float) -> None:
        host, raw_port = self.grpc_addr.rsplit(":", maxsplit=1)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError("BMv2 进程提前退出")
            try:
                with socket.create_connection((host, int(raw_port)), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)

        raise TimeoutError(f"等待 {self.grpc_addr} 超时")

    def _restore_log_ownership(self, log_path: Path) -> None:
        """sudo 启动时，让运行产物仍归原用户所有。"""
        raw_uid = os.environ.get("SUDO_UID")
        raw_gid = os.environ.get("SUDO_GID")
        if raw_uid is None or raw_gid is None:
            return

        uid, gid = int(raw_uid), int(raw_gid)
        for path in (self.log_dir.parent, self.log_dir, log_path):
            os.chown(path, uid, gid)

    def stop(self, deleteIntfs: bool = True) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1)
        self._process = None

        if self._log_file is not None:
            self._log_file.close()
        self._log_file = None

        super().stop(deleteIntfs)
