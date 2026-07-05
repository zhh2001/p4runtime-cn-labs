import unittest

import grpc
from google.protobuf.any_pb2 import Any
from google.rpc import code_pb2, status_pb2
from p4.v1 import p4runtime_pb2

from p4rt.errors import parse_write_error


class FakeRpcError(grpc.RpcError):
    def __init__(self, status: status_pb2.Status) -> None:
        self._metadata = (("grpc-status-details-bin", status.SerializeToString()),)

    def trailing_metadata(self):
        return self._metadata


class WriteErrorTest(unittest.TestCase):
    def test_keeps_batch_index_when_ok_detail_is_present(self) -> None:
        status = status_pb2.Status(code=code_pb2.UNKNOWN)
        for code, message in (
            (code_pb2.OK, ""),
            (code_pb2.ALREADY_EXISTS, "duplicate key"),
        ):
            packed = Any()
            packed.Pack(p4runtime_pb2.Error(canonical_code=code, message=message))
            status.details.append(packed)

        details = parse_write_error(FakeRpcError(status))
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0].index, 1)
        self.assertEqual(details[0].code_name, "ALREADY_EXISTS")
        self.assertEqual(details[0].message, "duplicate key")


if __name__ == "__main__":
    unittest.main()
