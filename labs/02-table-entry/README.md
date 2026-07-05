# 实验 02：P4Runtime Shell 与 TableEntry

这一章把 controller 与 BMv2 接上，并用 Shell 配好一条双向 IPv4 路径。pipeline 中有两张表：`allow_src` 做 exact match，`route_v4` 做 LPM。

## 拓扑

```text
h1 10.0.1.1 ──(1) s1 (2)── h2 10.0.1.2
                   │
        P4Runtime 127.0.0.1:9559
        device_id 1, CPU port 510
```

BMv2 使用 `--no-p4` 启动。此时 gRPC service 已经可用，但交换机还没有 pipeline，经过端口的报文都会被丢弃。

## 1. 准备 Shell

第一次运行需要联网安装依赖：

```bash
make setup
```

Shell 被安装到 `.venv-shell`。当前官方 `p4runtime-shell==0.0.6` 固定依赖 `p4runtime==1.4.1`，所以它不会与后面使用 v1.5.0 bindings 的 Python controller 共用 venv。

## 2. 启动交换机

打开第一个终端：

```bash
sudo make run LAB=02
```

看到 Mininet prompt 后，先不要退出。可以输入一次 `h1 ping -c 1 h2`，此时不通是正常的：pipeline 尚未安装，而且也没有任何路由表项。

## 3. 连接 Shell

打开第二个终端：

```bash
make shell LAB=02
```

这条命令会先编译 `main.p4`，然后由 Shell 顺序完成：

1. 打开 gRPC channel 和双向 `StreamChannel`；
2. 发送 `MasterArbitrationUpdate`，使用 election ID `(0, 1)`；
3. 以 `VERIFY_AND_COMMIT` 安装 P4Info 与 BMv2 JSON；
4. 调用 `GetForwardingPipelineConfig` 把 P4Info 读回来。

进入 `P4Runtime sh >>>` 后依次输入：

```python
APIVersion()
p4info.pkg_info
tables
actions
```

`APIVersion()` 来自 `Capabilities` RPC，返回的是 BMv2 server 实现的 API 版本，不是 Shell package 的版本。`tables` 和 `actions` 能列出对象，说明 Shell 已经使用读回的 P4Info 建立了本地索引。

这里有一个有意保留的版本差异：v1.5.0 为 `CapabilitiesRequest` 增加了 `device_id`，但本章的 v1.4.1 Shell bindings 还没有这个字段。新增字段是向后兼容的，因此旧 client 仍可查询 server-wide API version。第五阶段的 Python client 会改用 v1.5.0 bindings，并显式填写 `device_id=1`。

## 4. 写入 exact 表项

`allow_src` 默认丢包。先允许两个实验主机的源地址：

```python
allow_h1 = table_entry["allow_src"](action="permit")
allow_h1.match["src_addr"] = "10.0.1.1"
allow_h1.insert()

allow_h2 = table_entry["allow_src"](action="permit")
allow_h2.match["src_addr"] = "10.0.1.2"
allow_h2.insert()
```

exact match 必须给出完整字段值。这里没有 priority，因为相同 key 不会同时匹配多条 exact entry。

## 5. 写入 LPM 表项

再为两个方向各写一条 `/32` 路由：

```python
route_to_h1 = table_entry["route_v4"](action="rewrite_and_forward")
route_to_h1.match["dst_addr"] = "10.0.1.1/32"
route_to_h1.action["src_mac"] = "00:aa:00:00:00:01"
route_to_h1.action["dst_mac"] = "00:00:00:00:01:01"
route_to_h1.action["port"] = "1"
route_to_h1.insert()

route_to_h2 = table_entry["route_v4"](action="rewrite_and_forward")
route_to_h2.match["dst_addr"] = "10.0.1.2/32"
route_to_h2.action["src_mac"] = "00:aa:00:00:00:02"
route_to_h2.action["dst_mac"] = "00:00:00:00:01:02"
route_to_h2.action["port"] = "2"
route_to_h2.insert()
```

回到 Mininet 终端验证：

```text
mininet> h1 ping -c 3 h2
```

现在应该能收到三次回复。只写单向 route 或漏掉一条 `allow_src`，都会让 ping 表现为不通。这也是排查控制面配置时很常见的只配了一半。

`route_v4` 使用 LPM。若同时存在 `10.0.1.0/24` 和 `10.0.1.2/32`，后者对 h2 更具体，因此优先命中。LPM 的选择由 prefix length 决定，也不需要填写 `priority`。ternary 和 range 才依赖显式 priority。

## 6. Read 与 default entry

只给出 table ID、不填写 match fields，就是对该表做 wildcard read：

```python
table_entry["allow_src"].read(lambda entry: print(entry))
table_entry["route_v4"].read(lambda entry: print(entry))
```

default entry 要显式标记：

```python
default_route = table_entry["route_v4"](is_default=True)
default_route.read(lambda entry: print(entry))
```

它没有 match key，当前 action 是 `drop`。普通 entry 用 `INSERT` 创建、`MODIFY` 更新、`DELETE` 删除。default entry 始终存在，只能用 `MODIFY` 改 action，不能执行 `INSERT` 或 `DELETE`。

打印结果中的 IP、MAC 和端口最终都会变成 Protobuf `bytes`。Shell 默认启用 canonical bytestring 编码，可以这样确认：

```python
global_options["canonical_bytestrings"]
```

值应为 `True`。controller 传的是无符号 bitstring 的最短编码，不是 Python 字符串本身。Shell 替我们完成了字符串解析和编码。

## 7. MODIFY 与 DELETE

把去往 h2 的端口临时改成 1：

```python
route_to_h2.action["port"] = "1"
route_to_h2.modify()
```

此时 h1 的 ping 会失败。恢复端口后再次 `MODIFY`：

```python
route_to_h2.action["port"] = "2"
route_to_h2.modify()
```

也可以删除再插回同一个对象：

```python
route_to_h2.delete()
route_to_h2.insert()
```

在同一会话中对已经存在的 key 再执行 `insert()`，server 应返回 `ALREADY_EXISTS`，而不是悄悄覆盖旧值。

## 8. 退出与清理

在 Shell 中输入 `exit`，再回到 Mininet 终端输入 `exit`。如果终端被意外关闭，执行：

```bash
sudo make stop
```

BMv2 日志保存在 `build/logs/s1.log`，属于本地运行产物，不会提交。停止拓扑后 forwarding state 也随 BMv2 进程消失，下次实验会从空状态开始。
