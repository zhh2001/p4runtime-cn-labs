# 术语表

这里保留规范中的英文名称，中文只负责解释，不另造一套缩写。

| 名称 | 简要说明 |
| --- | --- |
| target / device | 执行 P4 pipeline 并提供 P4Runtime service 的设备。本教程中就是 BMv2。 |
| controller / client | 通过 gRPC 调用 P4Runtime service 的控制面程序。 |
| pipeline | P4 程序描述的数据包处理逻辑，以及 target 使用的编译结果。 |
| P4Info | P4 程序暴露给控制面的元数据，包含 table、action、counter 等对象及其 ID。 |
| P4 Device Config | target 专用的 pipeline 二进制。本教程中使用 BMv2 JSON。 |
| Entity | P4Runtime 可读写对象的统一容器，例如 TableEntry 或 CounterEntry。 |
| TableEntry | table 中的一条规则，通常由 match key、action、priority 等字段组成。 |
| ActionProfile | 让 TableEntry 间接引用 member 或 group 的控制面对象；带 selector 时可用于 ECMP。 |
| P4Runtime service | target 提供的 gRPC service，包含 Read、Write、Capabilities 等 RPC。 |
| StreamChannel | controller 与 target 之间的双向 stream，用于 arbitration、Packet I/O 等消息。 |
| arbitration | 多个 controller 竞争写权限的过程；同一 role 只有 primary 可以写。 |
| primary / backup | 同一 device 和 role 下，primary 拥有写权限，其他在线 controller 是 backup。 |
| election ID | controller 宣告的 128-bit 选举编号，用于确定 primary。 |
| role | controller 管理权限的逻辑范围。未指定时使用 default role。 |
| bytestring | Protobuf `bytes` 表示的 P4 数值，编码规则会影响匹配字段和 action 参数。 |
| PacketIn / PacketOut | 通过 StreamChannel 在 target 与 controller 之间传递的完整数据包。 |
| PRE | Packet Replication Engine，负责 multicast 和 clone 等复制行为。 |
| BMv2 | P4 的参考软件交换机 Behavioral Model version 2。 |
| v1model | BMv2 `simple_switch` 常用的 P4 architecture。 |
