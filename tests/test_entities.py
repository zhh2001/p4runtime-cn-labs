import unittest

from p4.config.v1 import p4info_pb2

from p4rt.entities import TableEntryBuilder, encode
from p4rt.p4info import P4InfoIndex


class EntityBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        p4info = p4info_pb2.P4Info()
        table = p4info.tables.add()
        table.preamble.id = 0x02000001
        table.preamble.name = "Ingress.route_v4"
        table.preamble.alias = "route_v4"
        field = table.match_fields.add(id=1, name="hdr.ipv4.dst")
        field.bitwidth = 32
        field.match_type = p4info_pb2.MatchField.LPM
        table.action_refs.add(id=0x01000001)

        action = p4info.actions.add()
        action.preamble.id = 0x01000001
        action.preamble.name = "Ingress.forward"
        action.preamble.alias = "forward"
        action.params.add(id=1, name="port", bitwidth=9)
        self.index = P4InfoIndex(p4info)

    def test_canonical_bytestring(self) -> None:
        self.assertEqual(encode(0, 9), b"\x00")
        self.assertEqual(encode(2, 9), b"\x02")
        self.assertEqual(encode("10.0.1.2", 32), b"\x0a\x00\x01\x02")
        self.assertEqual(encode("00:aa:00:00:00:02", 48), b"\xaa\x00\x00\x00\x02")

    def test_builds_lpm_entry_and_masks_host_bits(self) -> None:
        entry = (
            TableEntryBuilder(self.index, "route_v4")
            .lpm("dst", "10.0.1.99", 24)
            .action("forward", port=2)
            .build()
        )
        self.assertEqual(entry.table_id, 0x02000001)
        self.assertEqual(entry.match[0].field_id, 1)
        self.assertEqual(entry.match[0].lpm.value, b"\x0a\x00\x01\x00")
        self.assertEqual(entry.match[0].lpm.prefix_len, 24)
        self.assertEqual(entry.action.action.params[0].value, b"\x02")

    def test_rejects_action_not_referenced_by_table(self) -> None:
        other = self.index.p4info.actions.add()
        other.preamble.id = 0x01000002
        other.preamble.name = "Ingress.other"
        index = P4InfoIndex(self.index.p4info)
        with self.assertRaisesRegex(ValueError, "不允许 action"):
            TableEntryBuilder(index, "route_v4").action("Ingress.other")


if __name__ == "__main__":
    unittest.main()
