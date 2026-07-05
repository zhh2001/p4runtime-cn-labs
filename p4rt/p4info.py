"""从 P4Info 名称解析控制面对象 ID。"""

from __future__ import annotations

from dataclasses import dataclass

from google.protobuf.message import Message
from p4.config.v1 import p4info_pb2


class P4ObjectNotFound(KeyError):
    pass


@dataclass(frozen=True)
class P4InfoObject:
    kind: str
    id: int
    name: str
    alias: str
    message: Message


class P4InfoIndex:
    """为常用 P4Info 对象建立按名称与 ID 查询的索引。"""

    COLLECTIONS = {
        "table": "tables",
        "action": "actions",
        "action_profile": "action_profiles",
        "counter": "counters",
        "direct_counter": "direct_counters",
        "meter": "meters",
        "direct_meter": "direct_meters",
        "controller_packet_metadata": "controller_packet_metadata",
        "value_set": "value_sets",
        "register": "registers",
        "digest": "digests",
        "extern": "externs",
    }

    def __init__(self, p4info: p4info_pb2.P4Info) -> None:
        self.p4info = p4info
        self._by_id: dict[tuple[str, int], P4InfoObject] = {}
        self._by_name: dict[tuple[str, str], P4InfoObject] = {}

        for kind, collection_name in self.COLLECTIONS.items():
            for message in getattr(p4info, collection_name):
                preamble = message.preamble
                item = P4InfoObject(
                    kind=kind,
                    id=preamble.id,
                    name=preamble.name,
                    alias=preamble.alias,
                    message=message,
                )
                self._by_id[(kind, item.id)] = item
                self._register_name(kind, item.name, item)
                if item.alias:
                    self._register_name(kind, item.alias, item)

    def _register_name(self, kind: str, name: str, item: P4InfoObject) -> None:
        key = (kind, name)
        existing = self._by_name.get(key)
        if existing is not None and existing.id != item.id:
            raise ValueError(f"{kind} 名称不唯一：{name}")
        self._by_name[key] = item

    def resolve(self, kind: str, name_or_id: str | int) -> P4InfoObject:
        if kind not in self.COLLECTIONS:
            raise ValueError(f"未知 P4Info 对象类型：{kind}")

        if isinstance(name_or_id, int):
            item = self._by_id.get((kind, name_or_id))
        else:
            item = self._by_name.get((kind, name_or_id))

        if item is None:
            raise P4ObjectNotFound(f"找不到 {kind}：{name_or_id}")
        return item

    def all(self, kind: str) -> tuple[P4InfoObject, ...]:
        if kind not in self.COLLECTIONS:
            raise ValueError(f"未知 P4Info 对象类型：{kind}")
        items = (item for (item_kind, _), item in self._by_id.items() if item_kind == kind)
        return tuple(sorted(items, key=lambda item: item.name))

    def table(self, name_or_id: str | int) -> P4InfoObject:
        return self.resolve("table", name_or_id)

    def action(self, name_or_id: str | int) -> P4InfoObject:
        return self.resolve("action", name_or_id)
