"""构造教程所需的 P4Runtime Entity。"""

from __future__ import annotations

import ipaddress

from p4.config.v1 import p4info_pb2
from p4.v1 import p4runtime_pb2

from .p4info import P4InfoIndex


def encode(value: str | int, bitwidth: int) -> bytes:
    """把无符号 P4 bit<W> 值编码为 canonical bytestring。"""
    if isinstance(value, str):
        if bitwidth == 32 and "." in value:
            number = int(ipaddress.IPv4Address(value))
        elif bitwidth == 48 and ":" in value:
            parts = value.split(":")
            if len(parts) != 6 or any(len(part) != 2 for part in parts):
                raise ValueError(f"无效 MAC 地址：{value}")
            try:
                number = int("".join(parts), 16)
            except ValueError as error:
                raise ValueError(f"无效 MAC 地址：{value}") from error
        else:
            number = int(value, 0)
    else:
        number = value

    if bitwidth <= 0:
        raise ValueError("bitwidth 必须大于 0")
    if number < 0 or number >= 1 << bitwidth:
        raise ValueError(f"值 {value} 超出 bit<{bitwidth}> 范围")

    padded = number.to_bytes((bitwidth + 7) // 8, byteorder="big")
    canonical = padded.lstrip(b"\x00")
    return canonical or b"\x00"


class TableEntryBuilder:
    def __init__(self, index: P4InfoIndex, table_name: str | int) -> None:
        self._index = index
        self._table = index.table(table_name)
        self._entry = p4runtime_pb2.TableEntry(table_id=self._table.id)
        self._matched_fields: set[int] = set()

    def _match_field(self, name: str):
        candidates = [
            field
            for field in self._table.message.match_fields
            if field.name == name or field.name.rsplit(".", maxsplit=1)[-1] == name
        ]
        if len(candidates) != 1:
            raise ValueError(f"match field 不唯一或不存在：{name}")
        return candidates[0]

    def exact(self, field_name: str, value: str | int) -> "TableEntryBuilder":
        field = self._match_field(field_name)
        if field.match_type != p4info_pb2.MatchField.EXACT:
            raise ValueError(f"{field.name} 不是 EXACT field")
        self._ensure_new_match(field.id)
        match = self._entry.match.add(field_id=field.id)
        match.exact.value = encode(value, field.bitwidth)
        return self

    def lpm(
        self,
        field_name: str,
        value: str | int,
        prefix_len: int,
    ) -> "TableEntryBuilder":
        field = self._match_field(field_name)
        if field.match_type != p4info_pb2.MatchField.LPM:
            raise ValueError(f"{field.name} 不是 LPM field")
        if not 0 < prefix_len <= field.bitwidth:
            raise ValueError(f"prefix length 必须在 1..{field.bitwidth} 之间")

        if isinstance(value, str) and "." in value:
            raw_value = int(ipaddress.IPv4Address(value))
        elif isinstance(value, str):
            raw_value = int(value, 0)
        else:
            raw_value = value
        mask = ((1 << prefix_len) - 1) << (field.bitwidth - prefix_len)
        network_value = raw_value & mask

        self._ensure_new_match(field.id)
        match = self._entry.match.add(field_id=field.id)
        match.lpm.value = encode(network_value, field.bitwidth)
        match.lpm.prefix_len = prefix_len
        return self

    def _ensure_new_match(self, field_id: int) -> None:
        if field_id in self._matched_fields:
            raise ValueError(f"match field {field_id} 已设置")
        self._matched_fields.add(field_id)

    def action(self, action_name: str | int, **params: str | int) -> "TableEntryBuilder":
        action = self._index.action(action_name)
        allowed_ids = {ref.id for ref in self._table.message.action_refs}
        if action.id not in allowed_ids:
            raise ValueError(f"表 {self._table.name} 不允许 action {action.name}")

        action_message = self._entry.action.action
        action_message.action_id = action.id
        param_info = {param.name: param for param in action.message.params}
        unknown = set(params) - set(param_info)
        missing = set(param_info) - set(params)
        if unknown or missing:
            raise ValueError(
                f"action 参数不匹配，缺少 {sorted(missing)}，未知 {sorted(unknown)}"
            )

        for name, value in params.items():
            info = param_info[name]
            param = action_message.params.add(param_id=info.id)
            param.value = encode(value, info.bitwidth)
        return self

    def priority(self, value: int) -> "TableEntryBuilder":
        if value <= 0:
            raise ValueError("priority 必须大于 0")
        self._entry.priority = value
        return self

    def build(self) -> p4runtime_pb2.TableEntry:
        result = p4runtime_pb2.TableEntry()
        result.CopyFrom(self._entry)
        return result


def entity(table_entry: p4runtime_pb2.TableEntry) -> p4runtime_pb2.Entity:
    result = p4runtime_pb2.Entity()
    result.table_entry.CopyFrom(table_entry)
    return result


def update(
    update_type: int,
    table_entry: p4runtime_pb2.TableEntry,
) -> p4runtime_pb2.Update:
    result = p4runtime_pb2.Update(type=update_type)
    result.entity.table_entry.CopyFrom(table_entry)
    return result
