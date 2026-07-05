"""展开 P4Runtime Write RPC 的逐项错误。"""

from __future__ import annotations

from dataclasses import dataclass

import grpc
from google.rpc import code_pb2, status_pb2
from p4.v1 import p4runtime_pb2


@dataclass(frozen=True)
class WriteErrorDetail:
    index: int
    canonical_code: int
    code_name: str
    message: str
    space: str
    target_code: int


def parse_write_error(error: grpc.RpcError) -> tuple[WriteErrorDetail, ...]:
    status = None
    for key, value in error.trailing_metadata() or ():
        if key == "grpc-status-details-bin":
            status = status_pb2.Status()
            status.ParseFromString(value)
            break

    if status is None:
        return ()

    details = []
    for index, packed in enumerate(status.details):
        item = p4runtime_pb2.Error()
        if not packed.Unpack(item) or item.canonical_code == code_pb2.OK:
            continue
        try:
            code_name = code_pb2.Code.Name(item.canonical_code)
        except ValueError:
            code_name = str(item.canonical_code)
        details.append(
            WriteErrorDetail(
                index=index,
                canonical_code=item.canonical_code,
                code_name=code_name,
                message=item.message,
                space=item.space,
                target_code=item.code,
            )
        )
    return tuple(details)


class P4RuntimeWriteError(RuntimeError):
    def __init__(self, error: grpc.RpcError) -> None:
        self.grpc_code = error.code()
        self.grpc_message = error.details() or ""
        self.details = parse_write_error(error)
        super().__init__(str(self))

    def __str__(self) -> str:
        if not self.details:
            return f"Write RPC 失败：{self.grpc_code.name}: {self.grpc_message}"

        lines = ["Write RPC 中有 update 失败："]
        for detail in self.details:
            lines.append(f"  update[{detail.index}] {detail.code_name}: {detail.message}")
        return "\n".join(lines)
