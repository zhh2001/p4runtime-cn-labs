import unittest

from p4.config.v1 import p4info_pb2
from p4.v1 import p4runtime_pb2

from p4rt.packet import decode_packet_in, packet_out
from p4rt.p4info import P4InfoIndex


class PacketIOMessageTest(unittest.TestCase):
    def setUp(self) -> None:
        p4info = p4info_pb2.P4Info()

        packet_in = p4info.controller_packet_metadata.add()
        packet_in.preamble.id = 0x04000001
        packet_in.preamble.name = "packet_in"
        packet_in.metadata.add(id=1, name="ingress_port", bitwidth=16)
        packet_in.metadata.add(id=2, name="reason", bitwidth=8)

        packet_out_info = p4info.controller_packet_metadata.add()
        packet_out_info.preamble.id = 0x04000002
        packet_out_info.preamble.name = "packet_out"
        packet_out_info.metadata.add(id=1, name="egress_port", bitwidth=16)
        self.index = P4InfoIndex(p4info)

    def test_builds_packet_out_with_canonical_metadata(self) -> None:
        request = packet_out(self.index, b"ethernet-frame", egress_port=2)
        self.assertEqual(request.packet.payload, b"ethernet-frame")
        self.assertEqual(request.packet.metadata[0].metadata_id, 1)
        self.assertEqual(request.packet.metadata[0].value, b"\x02")

    def test_requires_every_packet_out_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "metadata 不匹配"):
            packet_out(self.index, b"frame")

    def test_decodes_packet_in_metadata_by_id(self) -> None:
        packet = p4runtime_pb2.PacketIn(payload=b"frame")
        packet.metadata.add(metadata_id=2, value=b"\x01")
        packet.metadata.add(metadata_id=1, value=b"\x02")
        self.assertEqual(
            decode_packet_in(self.index, packet),
            {"reason": 1, "ingress_port": 2},
        )

    def test_rejects_duplicate_packet_in_metadata(self) -> None:
        packet = p4runtime_pb2.PacketIn(payload=b"frame")
        packet.metadata.add(metadata_id=1, value=b"\x01")
        packet.metadata.add(metadata_id=1, value=b"\x02")
        with self.assertRaisesRegex(ValueError, "metadata 重复"):
            decode_packet_in(self.index, packet)


if __name__ == "__main__":
    unittest.main()
