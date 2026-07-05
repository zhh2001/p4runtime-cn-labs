import unittest

from p4.config.v1 import p4info_pb2

from p4rt.p4info import P4InfoIndex, P4ObjectNotFound


class P4InfoIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self.p4info = p4info_pb2.P4Info()
        table = self.p4info.tables.add()
        table.preamble.id = 0x02000001
        table.preamble.name = "IngressPipe.route_v4"
        table.preamble.alias = "route_v4"

        action = self.p4info.actions.add()
        action.preamble.id = 0x01000001
        action.preamble.name = "IngressPipe.forward"
        action.preamble.alias = "forward"

        self.index = P4InfoIndex(self.p4info)

    def test_resolves_full_name_alias_and_id(self) -> None:
        self.assertEqual(self.index.table("IngressPipe.route_v4").id, 0x02000001)
        self.assertEqual(self.index.table("route_v4").id, 0x02000001)
        self.assertEqual(self.index.table(0x02000001).name, "IngressPipe.route_v4")

    def test_keeps_object_types_separate(self) -> None:
        self.assertEqual(self.index.action("forward").kind, "action")
        self.assertEqual([item.alias for item in self.index.all("table")], ["route_v4"])

    def test_missing_object_raises_clear_error(self) -> None:
        with self.assertRaises(P4ObjectNotFound):
            self.index.table("missing")


if __name__ == "__main__":
    unittest.main()
