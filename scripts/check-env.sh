#!/usr/bin/env bash

set -u

required=(
  p4c
  p4c-bm2-ss
  simple_switch_grpc
  mn
  python3
  protoc
  make
  ip
  ping
  tcpdump
  sudo
)

missing=0

echo "系统环境"
if [[ -r /etc/os-release ]]; then
  os_name=$(sed -n 's/^PRETTY_NAME=//p' /etc/os-release | tr -d '"')
  echo "  OS: ${os_name:-未知}"
else
  echo "  OS: 无法读取 /etc/os-release"
fi

echo
echo "必要命令"
for command_name in "${required[@]}"; do
  if command_path=$(command -v "$command_name" 2>/dev/null); then
    printf '  [ok] %-22s %s\n' "$command_name" "$command_path"
  else
    printf '  [缺少] %s\n' "$command_name"
    missing=1
  fi
done

echo
echo "版本摘要"
printf '  p4c:     %s\n' "$(p4c --version 2>/dev/null | head -n 1 || echo 未安装)"
printf '  BMv2:    %s\n' "$(simple_switch_grpc --version 2>/dev/null | head -n 1 || echo 未安装)"
mininet_version=$(mn --version 2>/dev/null | head -n 1)
if [[ -z "$mininet_version" ]] && command -v dpkg-query >/dev/null 2>&1; then
  mininet_version=$(dpkg-query -W -f='${Version}' mininet 2>/dev/null || true)
fi
printf '  Mininet: %s\n' "${mininet_version:-未知}"
printf '  Python:  %s\n' "$(python3 --version 2>/dev/null || echo 未安装)"
printf '  protoc:  %s\n' "$(protoc --version 2>/dev/null || echo 未安装)"

if (( missing != 0 )); then
  echo
  echo "环境还不完整，请先按 docs/setup.md 补齐缺少的工具。"
  exit 1
fi

echo
echo "基础环境可用。"
