# 实验 05：Counter 与 Meter

这一章给 `route_v4` 加上三类资源：每条路由自己的 direct counter、按输出端口索引的 indirect counter，以及 packet meter。

## 运行步骤

终端一：

```bash
sudo make run LAB=05
```

终端二：

```bash
make controller LAB=05
```

controller 配好 pipeline、路由和 meter 后会暂停。回到 Mininet：

```text
mininet> h1 ping -c 5 h2
```

再回到 controller 终端按回车。两个方向都应出现非零的 packet/byte count，最后退出 Mininet。

## Direct 与 indirect counter

`route_hits` 通过 table 的 `counters` property 绑定到 `route_v4`。每个 table entry 自动拥有一个 counter cell，命中 entry 时由 v1model 更新，P4 action 不需要显式调用 `count()`。

`port_packets` 是一个大小为 4 的独立 counter array。`rewrite_and_forward` 根据输出端口调用 `count(port)`，所以 index 1 和 2 分别统计发往两个端口的流量。

两者的控制面寻址也不同：

- `CounterEntry` 使用 `counter_id + index`；
- `DirectCounterEntry` 使用关联 TableEntry 的 key，不携带 direct counter ID。

本实验的 wildcard direct-counter read 只填写 `route_v4` 的 table ID，因此会返回该表所有普通 entry 的 counter data。

## 配置 MeterEntry

`port_meter` 同样是大小为 4 的 array，单位是 packets。controller 对 index 1 和 2 发送 `MODIFY MeterEntry`：

```text
cir=1000, cburst=100, pir=1000, pburst=100
```

这里选择宽松参数，让手工 ping 保持 green。action 仍会读取 color，若为 red 则丢包。meter 的速率和 burst 单位由 P4Info `MeterSpec.unit` 决定，不能看到四个数字就默认它们一定是 bytes/s。

MeterEntry 不使用 `INSERT` 或 `DELETE`：cell 随 extern array 一直存在，控制面通过 `MODIFY` 改配置。未配置的 cell 使用 target 的默认行为，规范定义为始终 green。

这个实验只验证语义与读写，不用 BMv2 的调度精度做性能结论。不同 target 对 token bucket、时间粒度和可选 per-color counter 的支持可能不同。
