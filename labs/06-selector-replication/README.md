# 实验 06：Action Selector 与 Multicast

这一章有三个主机：h1 访问 VIP `10.0.0.100`，Action Selector 在 h2、h3 两个 backend member 之间选择。目的地址 `239.1.1.1` 则通过 PRE 同时复制到两个 backend 端口。

## 运行

终端一：

```bash
sudo make run LAB=06
```

终端二：

```bash
make controller LAB=06
```

controller 配置完成后会暂停。在 Mininet 中运行：

```text
mininet> h1 ping -c 20 10.0.0.100
```

VIP 同时配置在 h2、h3 的 loopback。P4 selector 使用源地址和 IPv4 identification 做 hash，同一轮 ping 的 request 应分散到两个输出端口。reply 通过单独的 member 3 返回 h1。

接着观察 multicast。先启动两份一次性抓包：

```text
mininet> h2 tcpdump -ni h2-eth0 -c 1 'udp and dst 239.1.1.1' > /tmp/h2-mcast.log 2>&1 &
mininet> h3 tcpdump -ni h3-eth0 -c 1 'udp and dst 239.1.1.1' > /tmp/h3-mcast.log 2>&1 &
```

再由 h1 发一帧：

```text
mininet> h1 python3 -c "from scapy.all import Ether,IP,UDP,sendp; sendp(Ether(dst='01:00:5e:01:01:01')/IP(dst='239.1.1.1')/UDP(dport=9000), iface='h1-eth0', verbose=False)"
mininet> h2 cat /tmp/h2-mcast.log
mininet> h3 cat /tmp/h3-mcast.log
```

两个日志都应出现一帧。回到 controller 终端按回车，它会读回 member、group、端口 counter 和 multicast replicas。

## Member、Group 与 TableEntry

`backend_selector` 是 `with_selector: true` 的 ActionProfile。controller 按依赖顺序配置：

1. INSERT 四个 `ActionProfileMember`；
2. INSERT group 100，其中 member 1、2 权重都为 1；
3. INSERT `MulticastGroupEntry` 1；
4. 最后 INSERT 引用 group/member 的 TableEntry。

先写引用者会得到 `NOT_FOUND` 或 `FAILED_PRECONDITION`。删除时顺序相反：先移除 TableEntry，再删 group，最后删 member。

VIP 表项的 action 是 `action_profile_group_id=100`。回程和 multicast 表项直接引用 member ID。P4Info 中标为 `selector` 的 fields 只参与动态选择，不进入 TableEntry match key。

## MulticastGroupEntry

group 1 包含 `(port=2, instance=1)` 和 `(port=3, instance=2)`。代码使用 v1.4 起推荐的 `bytes port`，没有继续写已 deprecated 的 `uint32 egress_port`。

P4 action 只设置 `standard_metadata.mcast_grp=1`。复制数量和端口完全由 PRE entry 决定。`instance` 用来区分 replica，不是输出端口。

## v1.5 新字段怎样处理

单元测试会构造这些 v1.5 消息：

- `ActionProfileActionSet.action_selection_mode=RANDOM`；
- `size_semantics=SUM_OF_MEMBERS`；
- P4Info `weights_disallowed=true`；
- multicast replica 的 `backup_replicas`。

本实验的 BMv2 路径不发送这些字段。它声明的 API version 是 1.3.0，不能据此承诺运行时支持。实际 group 使用传统 member/group 编程和默认 hash mode。backup replica 只验证 1.5 bindings 能正确表示，不伪装成 failover demo。
