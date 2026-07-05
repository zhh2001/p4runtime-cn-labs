# 实验 01：Pipeline 与 P4Info

这一章先不连接交换机。目标是编译一份最小 IPv4 pipeline，然后看看 controller 将来会拿到什么信息。

## 编译器产出了什么

```text
                        ┌─ pipeline.json ──> BMv2
main.p4 ── p4c-bm2-ss ──┤
                        └─ p4info.txtpb ───> controller
```

`pipeline.json` 描述 BMv2 应该怎样处理报文，它是 target-specific 的。`p4info.txtpb` 描述可以被控制面访问的 table、action 等对象，是 P4Runtime API 的元数据。`.txtpb` 表示 text-format Protobuf。controller 不需要解析 BMv2 JSON。

本实验的 pipeline 只有一张 `route_v4` 表：

- 使用 IPv4 目的地址做 LPM；
- 命中后重写源、目的 MAC，TTL 减一并选择输出端口；
- 没有匹配项时丢包。

完整 P4 程序在 [main.p4](main.p4)。第一次阅读时，先找到 `PacketParser`、`IngressPipe` 和最后的 `V1Switch`，其余部分暂时不用逐行研究。

## 1. 编译

在仓库根目录运行：

```bash
make build LAB=01
```

编译结果位于：

```text
build/01-pipeline/pipeline.json
build/01-pipeline/p4info.txtpb
```

`build/` 不会提交到 Git。随时可以执行 `make clean` 后从头生成。

## 2. 查看 P4Info

先直接读文本：

```bash
sed -n '1,180p' build/01-pipeline/p4info.txtpb
```

再用仓库里的小脚本列出对象：

```bash
make inspect LAB=01
```

输出会包含 `route_v4`、`rewrite_and_forward` 和 `drop`。每个对象都有 32-bit ID，写成十六进制后更容易看出结构：

```text
prefix 0x01  action
prefix 0x02  table
```

ID 的高 8 bit 表示对象类型，低 24 bit 是该类型下的编号。编号由 compiler 生成，重命名对象后可能变化，因此 controller 不应该把这些十进制数字散落在代码里。后面的 Python client 会在启动时按 P4Info 名称查 ID。

文件开头的 `pkg_info` 描述整个 P4 package，不是某个 table。其中名称和版本来自 P4 程序末尾的 `@pkginfo`，`arch: "v1model"` 则由 compiler backend 填写。

## 3. 对照 P4 源码

在 `p4info.txtpb` 中找到 `route_v4`，可以看到：

- `match_fields` 对应 P4 table 的 `key`；
- `match_type: LPM` 来自 `lpm`；
- `action_refs` 指向允许使用的 action；
- `size: 1024` 原样进入 P4Info。

再找到 `rewrite_and_forward`。三个 action 参数各自拥有参数 ID、名称与 bitwidth。P4Runtime 发送的是 ID 和 bytestring，P4 源码名称并不会直接出现在 `WriteRequest` 线上。

## 可以顺手试试

把 `route_v4` 的 `size` 改成 128 后重新编译，观察 P4Info 的变化。也可以临时改名再比较 ID，看完后恢复即可。
