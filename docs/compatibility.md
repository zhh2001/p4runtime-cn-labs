# 兼容性说明

下面记录的是本仓库实际使用的组合，不是对所有 P4Runtime target 的兼容承诺。

## 工具版本

| 组件 | 版本 | 在仓库中的用途 |
| --- | --- | --- |
| P4Runtime specification | 1.5.0 | 协议语义依据 |
| Python `p4runtime` | 1.5.0 | controller、单元测试和 1.5 Protobuf |
| `protobuf` | 3.20.3 | 兼容官方 1.5 Python wheel 的生成方式 |
| P4Runtime Shell | 0.0.6 | 交互式 pipeline 与 TableEntry 实验 |
| Shell 内的 P4Runtime bindings | 1.4.1 | 由 Shell 依赖固定，不能混入主 venv |
| BMv2 `simple_switch_grpc` | 1.15.x | v1model 数据面和 P4Runtime server |
| BMv2 声明的 API version | 1.3.0 | Capabilities 的实际返回值 |
| P4 compiler | 1.2.5.x | 本地编译。CI 固定使用 1.2.5.13 |

## 功能覆盖

| 能力 | 本仓库状态 | 备注 |
| --- | --- | --- |
| P4Info、pipeline set/get | 可运行 | Shell 与 Python 两条路径都覆盖 |
| TableEntry、batch、错误详情 | 可运行 | 包含 exact、LPM、default entry 和 wildcard read |
| Counter、direct counter、meter | 可运行 | BMv2 只用于功能验证，不做精度结论 |
| ActionProfile member/group | 可运行 | 实验 06 使用传统 selector 编程 |
| Multicast 与 `Replica.port` | 可运行 | 使用推荐的 `bytes port` 字段 |
| PacketIn、PacketOut | 可运行 | v1model CPU port 固定为 510 |
| primary / backup Write 权限 | 可运行 | 实测 backup 收到 `PERMISSION_DENIED` |
| `CapabilitiesRequest.device_id` | client 已使用 | 旧 server 会按 Protobuf 兼容规则处理未知字段 |
| `weights_disallowed` | bindings 测试 | 未向 BMv2 下发 |
| `action_selection_mode`、`size_semantics` | bindings 测试 | 未向 BMv2 下发 |
| multicast `backup_replicas` | bindings 测试 | 没有伪装成 failover 实验 |
| v1.5 历史最高 election ID 规则 | target 行为不同 | BMv2 1.15 会先自动提升低 ID backup |
| TLS、自定义 role config、硬件 target | 未覆盖 | 留给具体部署环境 |

`bindings 测试`只表示消息能由官方 1.5 Python package 正确构造。判断真实设备是否支持某项能力，还要看 server 文档、Capabilities 扩展和运行结果。
