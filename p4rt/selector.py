"""ActionProfile 与 multicast 消息构造。"""

from __future__ import annotations

from collections.abc import Iterable

from p4.v1 import p4runtime_pb2

from .entities import encode
from .p4info import P4InfoIndex


def _action(index: P4InfoIndex, action_name: str, params: dict[str, str | int]):
    action_info = index.action(action_name)
    result = p4runtime_pb2.Action(action_id=action_info.id)
    param_info = {item.name: item for item in action_info.message.params}
    if set(params) != set(param_info):
        raise ValueError(
            f"action 参数不匹配，期望 {sorted(param_info)}，收到 {sorted(params)}"
        )
    for name, value in params.items():
        info = param_info[name]
        result.params.add(param_id=info.id, value=encode(value, info.bitwidth))
    return result


def profile_member(
    index: P4InfoIndex,
    profile_name: str,
    member_id: int,
    action_name: str,
    **params: str | int,
) -> p4runtime_pb2.Entity:
    profile = index.resolve("action_profile", profile_name)
    result = p4runtime_pb2.Entity()
    member = result.action_profile_member
    member.action_profile_id = profile.id
    member.member_id = member_id
    member.action.CopyFrom(_action(index, action_name, params))
    return result


def profile_group(
    index: P4InfoIndex,
    profile_name: str,
    group_id: int,
    members: Iterable[tuple[int, int]],
    *,
    max_size: int,
) -> p4runtime_pb2.Entity:
    profile = index.resolve("action_profile", profile_name)
    result = p4runtime_pb2.Entity()
    group = result.action_profile_group
    group.action_profile_id = profile.id
    group.group_id = group_id
    group.max_size = max_size
    for member_id, weight in members:
        group.members.add(member_id=member_id, weight=weight)
    return result


def multicast_group(
    group_id: int,
    replicas: Iterable[tuple[int, int]],
) -> p4runtime_pb2.Entity:
    result = p4runtime_pb2.Entity()
    group = result.packet_replication_engine_entry.multicast_group_entry
    group.multicast_group_id = group_id
    for port, instance in replicas:
        replica = group.replicas.add(instance=instance)
        replica.port = encode(port, 32)
    return result
