# P4Runtime 中文教程

这个仓库记录我学习 P4Runtime 控制平面的过程。重点是用几个能跑起来的小实验，弄清楚 controller 怎样认识并配置一条 P4 pipeline。

教程面向已经了解 Ethernet、IPv4、路由表等基本概念的读者。没有接触过 P4 也可以从头跟，但这里不会系统讲解 P4_16 语法（P4 语法可以在 [p4-language-guide-zh](https://github.com/zhh2001/p4-language-guide-zh) 学习），只会补上实验需要的部分。

## 会做哪些实验

第一版计划包含八个实验：

1. 编译一条最小 pipeline，查看 P4Info；
2. 用 P4Runtime Shell 安装 pipeline、读写表项；
3. 用 Python 建立 gRPC session；
4. 处理 Read、Write、batch 和错误详情；
5. 读取 counter，配置 meter；
6. 使用 ActionProfile、ECMP 和 multicast；
7. 收发 PacketIn、PacketOut；
8. 观察两个 controller 之间的 arbitration。

代码以 Ubuntu 24.04、Mininet 和 BMv2 `simple_switch_grpc` 为主要环境。协议语义以 [P4Runtime v1.5.0](https://p4lang.github.io/p4runtime/spec/v1.5.0/P4Runtime-Spec.html) 为准。如果 BMv2 暂时不支持某项新能力，正文会直接标出来。

## 开始之前

先检查本机工具：

```bash
make check-env
```

目前使用的基准版本是：

- Ubuntu 24.04
- P4 compiler 1.2.5.x
- BMv2 1.15.x
- Mininet 2.3.x
- Python 3.12

详细说明见[环境准备](docs/setup.md)。如果你已经有一套能运行 P4 官方 tutorials 的环境，通常不需要重复安装。

第一个实验已经可以运行：

```bash
make build LAB=01
make inspect LAB=01
```

实验正文见 [Pipeline 与 P4Info](labs/01-pipeline/README.md)。这一章只编译和观察文件，还不会启动交换机，也不需要 `sudo`。

准备进入 Shell 实验时，先创建它自己的 Python 环境：

```bash
make setup
```

然后按 [P4Runtime Shell 与 TableEntry](labs/02-table-entry/README.md) 中的双终端步骤启动 Mininet、安装 pipeline，并写入第一组转发表项。

完成 Shell 实验后，可以在[自己建立 P4Runtime session](labs/03-python-client/README.md)中改用 1.5.0 Python bindings，观察 arbitration、Capabilities 和 pipeline RPC 的实际消息流。

接下来的 [Read、Write 与逐项错误](labs/04-write-read/README.md)会直接构造 `TableEntry`，并解释一个 batch 中部分 update 失败时怎样找到真正的错误。

## 阅读方式

每个实验都会给出目标、拓扑、关键代码、运行步骤和观察结果。建议先照着跑通，再回头看对应的规范章节。P4Runtime 里很多细节，例如 bytestring 编码和 primary controller 权限，只看消息结构很容易漏掉。

仓库仍在按实验逐步补齐。当前路线和各阶段边界放在[学习路线](docs/roadmap.md)，常见名称可查[术语表](docs/glossary.md)。

## 许可

仓库代码和文字采用 [Apache License 2.0](LICENSE)。引用规范或其他项目时，以[参考资料](docs/references.md)列出的原始来源为准。
