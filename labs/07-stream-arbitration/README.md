# 实验 07：Packet I/O 与控制器仲裁

这个实验不在交换机里写转发表。普通端口收到的帧一律送到 CPU port，primary controller 根据目的 MAC 再发 PacketOut。这样效率很低，却很适合看清一条 StreamChannel 上同时发生的两件事：Packet I/O 和 arbitration。

## 先跑通 Packet I/O

终端一启动拓扑：

```bash
sudo make run LAB=07
```

终端二启动 primary。它使用 election ID `(0, 2)`，并负责安装 pipeline：

```bash
make controller LAB=07 ELECTION_ID=0,2 \
  CONTROLLER_ARGS="--name primary --install-pipeline"
```

回到 Mininet：

```text
mininet> h1 ping -c 3 10.0.0.2
```

拓扑已预置静态 ARP，所以每个 ICMP request 和 reply 都会走一次 PacketIn，再由 controller 发 PacketOut。primary 终端会打印 ingress port、egress port 和 punt reason。

## 接入 backup

终端三连接第二个 controller：

```bash
make controller LAB=07 ELECTION_ID=0,1 \
  CONTROLLER_ARGS="--name backup --promote-election-id 0,3"
```

它收到的 arbitration status 是 `ALREADY_EXISTS`，说明同一 `(device_id, role)` 已有 primary。脚本还会绕过本地的 primary 检查，直接发一次测试 Write。BMv2 应返回 `PERMISSION_DENIED`。这条测试表项使用保留的实验 MAC，失败后不会留下状态。

此时再 ping，PacketIn 仍只到 primary，backup 保持安静。

## 模拟接管

在 primary 终端按 `Ctrl-C`。按 v1.5 语义，StreamChannel 断开后 backup 会收到 `NOT_FOUND`，表示当前没有 primary。旧 election ID 不能直接接管，因为 server 记得见过的最高值 `(0, 2)`。脚本随后发送更大的 `(0, 3)`。

接管成功后，backup 会 INSERT 再 DELETE 一条测试表项，确认 Write 权限已经转移。再次执行：

```text
mininet> h1 ping -c 3 10.0.0.2
```

流量应恢复，由原 backup 打印 PacketIn/PacketOut。结束时退出两个 controller，再在 Mininet 输入 `exit`。

BMv2 1.15 的 Capabilities 声明 API 1.3.0，它在这里会直接返回 `OK`，先把仍在线的 `(0, 1)` 提升为 primary。这和 v1.5 的历史最高 ID 规则不同。脚本同时接受 `NOT_FOUND` 与这个旧行为，但无论收到哪一种通知，都会先把 election ID 更新到 `(0, 3)` 再恢复实验。

## ControllerPacketMetadata

P4 程序声明了两个 `@controller_header`：

| header | metadata ID | 字段 | bitwidth |
| --- | ---: | --- | ---: |
| `packet_in` | 1 | `ingress_port` | 16 |
| `packet_in` | 2 | `reason` | 8 |
| `packet_out` | 1 | `egress_port` | 16 |

ID 来自 P4Info，不是 Protobuf 字段序号。`PacketMetadata.value` 仍使用 P4Runtime canonical bytestring，例如 port 2 编码为单字节 `02`，而不是固定补齐到 16 bit。

BMv2 的 CPU port 设为 510。它是本实验的 v1model target 约定，不等同于 PSA 定义的 controller-side `SDN_PORT_CPU`。

## Arbitration 要记住的边界

- StreamChannel 按 device 建立。默认 role 留空，表示完整 pipeline 权限。
- 同一 `(device_id, role)` 最多一个 primary。backup 可以保持连接，但不能 Write 或参与默认的 Packet I/O。
- primary 断线不会让旧的较小 election ID 自动胜出。接管者需要提交不小于历史最高值的新 ID，实际部署通常由外部 HA 系统分配它。
- Read 不修改状态，不要求 election ID，也不要求先建立 StreamChannel。Get RPC 同样不要求 primary，本实验的 backup 用它取得 P4Info。
