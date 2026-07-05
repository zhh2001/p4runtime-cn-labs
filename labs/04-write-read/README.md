# 实验 04：Read、Write 与逐项错误

上一章只安装 pipeline。这一章开始用 Python 直接构造 `TableEntry`，一次写入多条 update，并把 Write RPC 的嵌套错误拆开。

## 先跑起来

第一个终端：

```bash
sudo make run LAB=04
```

第二个终端：

```bash
make controller LAB=04
```

controller 最后会恢复完整的双向表项。回到 Mininet 验证：

```text
mininet> h1 ping -c 3 h2
```

## TableEntry builder 做了什么

`TableEntryBuilder` 不保存硬编码 ID。它先用 `P4InfoIndex` 找到 table、match field、action 和 action parameter，再把名称变成 P4Runtime 消息中的数字 ID。

本章只实现实际用到的类型：

- unsigned `bit<W>` 的 canonical bytestring；
- IPv4 和 MAC 字符串；
- EXACT 与 LPM；
- direct action 及其参数。

例如端口 2 是 `bit<9>`，legacy padded 编码是 `00 02`，canonical 编码只发送 `02`。零值仍保留一个 `00`。对 LPM 输入 `10.0.1.99/24` 时，builder 会清掉 host bits，线上值是 `10.0.1.0/24`。

## Batch Write

第一次 Write 包含四条 `INSERT`：两个 exact `allow_src` 和两个 LPM `route_v4`。`WriteRequest.atomicity` 使用规范要求所有 server 都支持的 `CONTINUE_ON_ERROR`。

这不等于事务。server 必须尝试 batch 中的每条 update，但数据面可能看见中间状态；如果需要 all-or-none，需要 target 另外支持 `ROLLBACK_ON_ERROR` 或 `DATAPLANE_ATOMIC`。

## Wildcard Read

`read_table("route_v4")` 只设置 table ID，不填写 match fields，因此会读回这张表的普通 entry。Read RPC 返回 stream，公共 client 会逐个展开 `ReadResponse.entities`。

本实验期望看到：

```text
wildcard Read：allow_src=2
wildcard Read：route_v4=2
```

default entry 不包含在这里的计数中。要读取它，需要构造 `is_default_action=true` 的查询，这在 Shell 章节已经演示过。

## 为什么一个 Write 错误有三层

controller 随后故意对两条已有 key 再次执行 `INSERT`。顶层 gRPC 通常只显示 `UNKNOWN`，真正有用的信息位于 trailing metadata：

```text
grpc-status-details-bin
└── google.rpc.Status
    ├── details[0] -> p4.v1.Error: ALREADY_EXISTS
    └── details[1] -> p4.v1.Error: ALREADY_EXISTS
```

`parse_write_error()` 按 `details` 的位置保留原 batch index，并跳过 canonical code 为 `OK` 的项目。正常输出类似：

```text
Write RPC 中有 update 失败：
  update[0] ALREADY_EXISTS: ...
  update[1] ALREADY_EXISTS: ...
```

不能只打印 `error.details()`，否则读者只会得到一条模糊的顶层错误，也不知道 batch 中究竟是哪项失败。

## CRUD 的剩余部分

controller 还会依次完成：

1. 用 `MODIFY` 把 h2 路由临时指向错误端口；
2. 再次 `MODIFY` 恢复 port 2；
3. `DELETE` h2 路由并确认表项数变成 1；
4. 重新 `INSERT`，确认表项数回到 2。

`DELETE` 的身份由 table ID、match fields 和必要时的 priority 决定，action 内容不参与定位。实验代码为了复用同一个对象仍保留 action，BMv2 会忽略这些非 key 字段。

退出 Mininet 后 forwarding state 会消失。异常退出使用 `sudo make stop`。

对应规范章节：[Error Reporting](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-error-reporting)、[Write RPC](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-write-rpc)、[Read RPC](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-read-rpc)。
