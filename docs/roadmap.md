# 学习路线

这条路线先让交换机动起来，再逐步拆开 P4Runtime 消息。章节顺序有意把复杂的 Python controller 放在 Shell 之后：先看清对象，再讨论代码怎么组织。

| 实验 | 主要问题 | 对应规范主题 |
| --- | --- | --- |
| 01 Pipeline 与 P4Info | P4 程序怎样变成控制面 API？ | Reference Architecture、P4Info、pipeline config |
| 02 TableEntry | controller 怎样写入和读回转发表？ | bytestring、TableEntry、Read、Write |
| 03 Python session | gRPC channel 和 controller session 如何建立？ | Capabilities、StreamChannel、arbitration |
| 04 批量操作与错误 | 一个 batch 部分失败时能看到什么？ | error reporting、atomicity |
| 05 Counter 与 Meter | 控制面如何观察并约束流量？ | CounterEntry、MeterEntry |
| 06 Selector 与复制 | ECMP 和 multicast 在 API 中怎样表达？ | ActionProfile、PRE |
| 07 Packet I/O | 数据包如何经过控制面再回到 pipeline？ | PacketIn、PacketOut |
| 08 Controller 主备 | primary 失效后谁能继续写设备？ | client arbitration |

## 每个实验的完成标准

一个实验只有同时满足以下条件才算完成：

- P4 程序能从干净目录重新编译；
- 给出的命令可以按顺序运行；
- 结果可以通过 ping、抓包、RPC 返回值或测试断言观察；
- 关闭实验后不残留 BMv2 进程和 Mininet 接口；
- target 不支持的行为写明限制，不用“理论上应该”代替结果。

## 不在第一版处理的内容

第一版不覆盖硬件 target、厂商 SDK、完整 PSA extern、自定义 role config 和生产环境 TLS。它们都很重要，但会让入门路线从“理解 P4Runtime”偏到部署细节。
