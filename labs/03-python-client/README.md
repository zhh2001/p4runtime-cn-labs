# 实验 03：自己建立 P4Runtime session

P4Runtime Shell 很适合观察对象，但它隐藏了 session 建立过程。这一章改用官方 1.5.0 Python bindings，直接调用 generated gRPC stub。目标仍然克制：成为 primary、查询 Capabilities、安装 pipeline、读回 P4Info。

## 代码分工

```text
controller.py
    │
    ├── P4RuntimeClient ── channel / StreamChannel / arbitration / RPC
    │
    └── P4InfoIndex ───── full name / alias / ID
```

公共代码放在仓库根目录的 `p4rt` package。它不是新的协议封装，只把每个 controller 都会重复写的连接与索引逻辑收拢起来。RPC request 仍直接使用 `p4.v1.p4runtime_pb2`。

## 1. 准备环境

```bash
make setup
make test
```

`.venv` 安装 `p4runtime==1.5.0`，与 `.venv-shell` 完全分开。由于官方 wheel 中的 generated code 仍使用旧 protobuf descriptor API，这里固定 `protobuf==3.20.3`；如果放任 pip 安装 protobuf 7，import `p4runtime_pb2` 就会失败。

## 2. 启动 BMv2

第一个终端：

```bash
sudo make run LAB=03
```

交换机仍以 `--no-p4` 启动，默认使用 `device_id=1` 和 `127.0.0.1:9559`。

## 3. 运行 controller

第二个终端：

```bash
make controller LAB=03
```

正常输出大致如下，具体对象 ID 由 compiler 生成：

```text
controller 已成为 primary：device_id=1, election_id=(0, 1)
server 声明的 P4Runtime API：1.3.0
已安装并读回 pipeline：p4runtime-cn-labs/03-python-client
P4Info tables：
  0x02......  IngressPipe.route_v4 (alias: route_v4)
```

这里同时出现三个版本，不要混在一起：

- 本教程依据的规范和 Python bindings 是 1.5.0；
- BMv2 通过 Capabilities 声明它实现的 API version，本机版本返回 1.3.0；
- pipeline 自己的 `PkgInfo.version` 当前是 0.1.0。

minor version 的新增字段保持 wire-compatible。v1.3 server 不认识 v1.5 `CapabilitiesRequest.device_id` 时会忽略它，仍能返回 server-wide 版本。

## 4. Session 是怎样建立的

`P4RuntimeClient.connect()` 依次完成：

1. 建立 insecure gRPC channel，并等待 channel ready；
2. 启动双向 `StreamChannel`；
3. 发送带有 `device_id=1`、election ID `(0, 1)` 的 `MasterArbitrationUpdate`；
4. 等待 server 回应，只有 `status.code == OK` 才把自己标为 primary。

`StreamChannel` 的 request 由 queue 驱动，response 在单独线程读取。现在只有 arbitration 使用它，后面的 Packet I/O 会复用同一条 stream，而不是另开连接。

## 5. 安装并读回 pipeline

`set_pipeline()` 构造 `SetForwardingPipelineConfigRequest`：

- `action` 使用 `VERIFY_AND_COMMIT`；
- `config.p4info` 来自 text-format P4Info；
- `config.p4_device_config` 是 BMv2 JSON 的原始 bytes；
- 写操作携带当前 primary 的 election ID。

安装成功后，controller 再用 `P4INFO_AND_COOKIE` 调用 `GetForwardingPipelineConfig`。这一步验证 server 保存的配置，而不是继续相信本地文件。

`P4InfoIndex` 同时登记 full name、alias 和 ID，例如三种写法都指向同一张表：

```python
index.table("IngressPipe.route_v4")
index.table("route_v4")
index.table(0x02c60dcf)  # 这里只是示意，不要硬编码实际 ID
```

运行结束时 context manager 会关闭 stream 和 channel。回到 Mininet 终端输入 `exit`；异常退出时使用 `sudo make stop`。

对应规范章节：[Client Arbitration](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-client-arbitration)、[Forwarding Pipeline Configuration](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-p4-forwarding-pipeline-config)、[Capabilities](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html#sec-capabilities-rpc)。
