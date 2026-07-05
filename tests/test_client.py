import tempfile
import unittest
from pathlib import Path

from google.protobuf import text_format
from p4.config.v1 import p4info_pb2
from p4.v1 import p4runtime_pb2

from p4rt.client import P4RuntimeClient, parse_election_id


class ClientMessageTest(unittest.TestCase):
    def test_rejects_zero_device_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "device_id=0"):
            P4RuntimeClient(device_id=0)

    def test_parses_election_id(self) -> None:
        self.assertEqual(parse_election_id("0,1"), (0, 1))
        self.assertEqual(parse_election_id("0x1,0xff"), (1, 255))
        with self.assertRaises(ValueError):
            parse_election_id("1")

    def test_builds_v15_pipeline_request(self) -> None:
        p4info = p4info_pb2.P4Info()
        p4info.pkg_info.name = "unit-test"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p4info_path = root / "p4info.txtpb"
            config_path = root / "pipeline.json"
            p4info_path.write_text(text_format.MessageToString(p4info), encoding="utf-8")
            config_path.write_bytes(b"{}")

            client = P4RuntimeClient(device_id=7, election_id=(2, 3))
            request = client.build_pipeline_request(p4info_path, config_path)

        self.assertEqual(request.device_id, 7)
        self.assertEqual((request.election_id.high, request.election_id.low), (2, 3))
        self.assertEqual(
            request.action,
            p4runtime_pb2.SetForwardingPipelineConfigRequest.VERIFY_AND_COMMIT,
        )
        self.assertEqual(request.config.p4info.pkg_info.name, "unit-test")
        self.assertEqual(request.config.p4_device_config, b"{}")


if __name__ == "__main__":
    unittest.main()
