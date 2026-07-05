# P4Runtime v1.5 变更导读

v1.5.0 没有推翻原来的 Read、Write 或 StreamChannel。它主要补齐了 adaptive load balancing、按 device 查询 Capabilities 和 multicast failover 所需的字段。旧 controller 仍能和 v1.5 server 交互，但不会自动用到这些新能力。

## Capabilities 带上 device_id

`CapabilitiesRequest` 新增 `device_id`。一个 P4Runtime server 管理多个 device 时，返回值可以因 device 而异。本仓库的 client 总是填写非零 ID：

```python
request = p4runtime_pb2.CapabilitiesRequest(device_id=self.device_id)
```

`CapabilitiesResponse` 还增加了用于实验性能力的 `Any` 字段。它只是扩展入口，具体消息格式仍由实现方定义，通用 controller 不能仅凭字段存在就猜测内容。

## device_id 不能是 0

规范现在明确禁止 `device_id=0`。这是为了区分合法 ID 和 Protobuf 的默认值。本仓库在建立 channel 之前便拒绝 0，拓扑脚本也做同样检查。

这条规则属于协议语义，不代表旧 target 一定会主动报错。controller 自己先校验，错误会更靠近配置来源。

## ActionProfile 的新选择方式

v1.5 为 ActionProfile 增加了三组信息：

- P4Info 的 `weights_disallowed` 表明权重由 switch 控制，controller 不应下发 weight；
- `ActionProfileActionSet.action_selection_mode` 可以按 group 选择算法；
- `size_semantics` 说明 group size 按 member 数量还是 weight 总和计算。

这些字段主要服务于 dynamic load balancing 和 adaptive routing。[实验 06](../labs/06-selector-replication/README.md)仍使用传统 member/group 编程。单元测试只证明 1.5 bindings 能构造新消息，不把它当作 BMv2 已支持的功能。

## Multicast backup replicas

每个 multicast `Replica` 现在可以携带 `backup_replicas`。当主输出路径失效时，支持该能力的 target 可以在本地切换，不必等 controller 重写 multicast group。

backup replica 不是普通 replica 列表的另一种写法。是否检测端口状态、怎样挑选 backup，都依赖 target。本仓库没有合适的 BMv2 运行时实现，因此只覆盖 Protobuf 表示。

## 版本号不能代替能力探测

Python 使用 `p4runtime==1.5.0`，表示 client 能看到 1.5 的 Protobuf 字段。它不改变 server。当前 BMv2 1.15 的 Capabilities 返回 1.3.0，P4Runtime Shell 0.0.6 则依赖 1.4.1 bindings。三者可以一起做基础实验，但新字段不能据此宣称端到端可用。

另一个例子是 arbitration。v1.5 要求 primary 断开后保留历史最高 election ID，接管者需提交不小于该值的新 ID。BMv2 1.15 会先提升仍在线的低 ID backup，[实验 07](../labs/07-stream-arbitration/README.md)对这个差异做了兼容处理。
