# 环境准备

教程的主环境是 Ubuntu 24.04。交换机使用 BMv2 `simple_switch_grpc`，拓扑交给 Mininet，P4 程序由 `p4c-bm2-ss` 编译。

## 需要的工具

至少需要下面这些命令：

```text
p4c  p4c-bm2-ss  simple_switch_grpc  mn
python3  protoc  make  ip  ping  tcpdump  sudo
```

运行检查：

```bash
make check-env
```

检查脚本只读取版本和命令路径，不会安装软件，也不会修改系统。

## 推荐版本

本仓库优先验证以下组合：

| 组件 | 版本 |
| --- | --- |
| Ubuntu | 24.04 |
| P4 compiler | 1.2.5.x |
| BMv2 | 1.15.x |
| Mininet | 2.3.x |
| Python | 3.12 |

小版本不完全一致通常没有关系。出现行为差异时，先记录 `p4c --version` 和 `simple_switch_grpc --version`，再对照实验中的已知限制。

## Python 环境为何分开

交互实验会用到 `p4runtime-shell==0.0.6`。它当前固定依赖 P4Runtime 1.4.1，因此放在 `.venv-shell`。

后面的 Python controller 直接使用官方 `p4runtime==1.5.0` bindings，放在 `.venv`。两个环境不混装，可以避免 pip 为了解决依赖而悄悄降级。对应的安装命令会随实验一起加入。

## 关于 sudo

Mininet 创建 network namespace 和虚拟网卡时需要 root 权限。仓库脚本不会保存密码，也不会把凭据放进命令参数。实验中只对启动、停止拓扑和清理残留接口使用 `sudo`。

如果一次实验异常退出，可先执行：

```bash
sudo mn -c
```

后续实验还会提供自己的清理命令，不需要手工查杀 BMv2 进程。
