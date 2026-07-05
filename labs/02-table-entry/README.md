# 实验 02：第一次 P4Runtime Shell 会话

这一阶段先把 controller 与 BMv2 接上。表项读写会在下一步补齐，现在只确认四件事：server 已监听、controller 完成 arbitration、pipeline 成功安装、P4Info 能被重新读回。

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

## 4. 退出与清理

在 Shell 中输入 `exit`，再回到 Mininet 终端输入 `exit`。如果终端被意外关闭，执行：

```bash
sudo make stop
```

BMv2 日志保存在 `build/logs/s1.log`，属于本地运行产物，不会提交。

这一阶段主要对应规范中的 [Client Arbitration](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-client-arbitration)、[SetForwardingPipelineConfig](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-setforwardingpipelineconfig-rpc)、[GetForwardingPipelineConfig](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-getforwardingpipelineconfig-rpc) 和 [Capabilities](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-capabilities-rpc)。
