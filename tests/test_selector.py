import unittest

from p4.config.v1 import p4info_pb2
from p4.v1 import p4runtime_pb2

from p4rt.entities import TableEntryBuilder
from p4rt.p4info import P4InfoIndex
from p4rt.selector import multicast_group, profile_group, profile_member


class SelectorMessageTest(unittest.TestCase):
    def setUp(self) -> None:
        p4info = p4info_pb2.P4Info()
        action = p4info.actions.add()
        action.preamble.id = 0x01000001
        action.preamble.name = "Ingress.set_port"
        action.preamble.alias = "set_port"
        action.params.add(id=1, name="port", bitwidth=9)

        profile = p4info.action_profiles.add()
        profile.preamble.id = 0x11000001
        profile.preamble.name = "Ingress.selector"
        profile.preamble.alias = "selector"
        profile.with_selector = True

        table = p4info.tables.add()
        table.preamble.id = 0x02000001
        table.preamble.name = "Ingress.service"
        table.preamble.alias = "service"
        table.implementation_id = profile.preamble.id
        field = table.match_fields.add(id=1, name="hdr.ipv4.dst")
        field.bitwidth = 32
        field.match_type = p4info_pb2.MatchField.EXACT
        table.action_refs.add(id=action.preamble.id)
        self.index = P4InfoIndex(p4info)

    def test_builds_member_group_and_table_reference(self) -> None:
        member = profile_member(self.index, "selector", 7, "set_port", port=2)
        group = profile_group(self.index, "selector", 9, [(7, 1)], max_size=4)
        table = (
            TableEntryBuilder(self.index, "service")
            .exact("dst", "10.0.0.100")
            .group_id(9)
            .build()
        )
        self.assertEqual(member.action_profile_member.member_id, 7)
        self.assertEqual(member.action_profile_member.action.params[0].value, b"\x02")
        self.assertEqual(group.action_profile_group.members[0].weight, 1)
        self.assertEqual(table.action.action_profile_group_id, 9)

    def test_multicast_uses_preferred_bytes_port(self) -> None:
        value = multicast_group(1, [(2, 10), (3, 11)])
        replicas = value.packet_replication_engine_entry.multicast_group_entry.replicas
        self.assertEqual(replicas[0].WhichOneof("port_kind"), "port")
        self.assertEqual(replicas[0].port, b"\x02")

    def test_v15_fields_can_be_constructed(self) -> None:
        action_set = p4runtime_pb2.ActionProfileActionSet(
            action_selection_mode=p4runtime_pb2.ActionProfileActionSet.RANDOM,
            size_semantics=p4runtime_pb2.ActionProfileActionSet.SUM_OF_MEMBERS,
        )
        replica = p4runtime_pb2.Replica(port=b"\x02", instance=1)
        replica.backup_replicas.add(port=b"\x03", instance=2)
        profile = p4info_pb2.ActionProfile(weights_disallowed=True)

        self.assertEqual(action_set.action_selection_mode, 2)
        self.assertEqual(action_set.size_semantics, 2)
        self.assertEqual(replica.backup_replicas[0].port, b"\x03")
        self.assertTrue(profile.weights_disallowed)


if __name__ == "__main__":
    unittest.main()
