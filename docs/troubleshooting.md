# 排错清单

先运行：

```bash
make check-env
```

版本和命令路径正常后，再按下面的症状往下查。一次只改一件事，通常比反复重装环境更快。

## 编译找不到 include 或 target

确认使用的是 `p4c-bm2-ss`，不是只装了 frontend 的 `p4c`。在仓库根目录执行：

```bash
make clean
make build LAB=01
```

实验 06 编译时会出现 action profile default action 的 `unsupported` warning。这是当前 BMv2 backend 的已知提示，编译返回 0 且后续 selector 实验可以运行。

## 连接 127.0.0.1:9559 超时

先确认 Mininet 终端仍在运行，再检查监听端口和 BMv2 进程：

```bash
ss -ltn | grep 9559
pgrep -af simple_switch_grpc
```

没有监听通常是拓扑未启动或 BMv2 提前退出。查看 `build/logs/s1.log`，不要直接重复启动第二份拓扑。

## 看到 ALREADY_EXISTS 或 PERMISSION_DENIED

`ALREADY_EXISTS` 要结合位置判断：Write 中出现时多半是重复 INSERT。arbitration response 中出现时表示当前 controller 是 backup。

backup 发送 Write 会得到 `PERMISSION_DENIED`。检查 election ID、role 和 primary 的 StreamChannel 是否仍在线，不要靠重试绕过权限判断。

## pipeline 配置失败

P4Info 和 device config 必须来自同一次编译。删掉旧产物后重建：

```bash
make clean
make build LAB=03
```

如果 `device_id`、gRPC 地址或端口不是默认值，拓扑和 controller 两边要一起修改。

## Python 报 Protobuf descriptor 错误

不要在系统 Python 或 `.venv-shell` 中运行 controller。重新准备主环境：

```bash
rm -rf .venv
make python-env
```

主环境固定 `p4runtime==1.5.0` 和 `protobuf==3.20.3`。Shell 使用另一套依赖，两个 venv 不能合并。

## ping 不通，但 RPC 没报错

按顺序看三件事：

1. Mininet 主机是否有实验要求的静态 ARP；
2. controller 是否已经写完表项，且仍保持 primary；
3. `build/logs/s1.log` 是否有 parser、端口或 P4Runtime 错误。

实验 05 还要看 meter 配置，实验 06 要读 counter 判断 selector 选了哪个 port，实验 07 则只有 primary 会收到 PacketIn。

## batch 只返回 UNKNOWN

`UNKNOWN` 是 Write batch 的顶层状态，不代表每个 update 都是同一种错误。使用实验 04 的错误解析查看 `google.rpc.Status.details`。

很大的 batch 还可能碰到 gRPC metadata 上限，最后只看到 `RESOURCE_EXHAUSTED`。这时应缩小 batch，并按规范附录调整 client 的 `grpc.max_metadata_size`，不要丢掉逐项错误后继续猜。

## 退出后端口仍被占用

先退出 Mininet CLI。异常中断时执行：

```bash
sudo make stop
```

清理后再确认 9559、9560 没有监听，且不存在 `simple_switch_grpc` 进程。若仍有残留，保留日志并检查是哪个终端启动的，不要把 `kill -9` 写进实验脚本。
