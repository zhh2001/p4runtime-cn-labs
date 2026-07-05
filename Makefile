SHELL := /usr/bin/env bash

.PHONY: help setup check-env check

help:
	@echo "可用命令："
	@echo "  make check-env  检查本机 P4 实验工具"
	@echo "  make setup      确认基础环境可用"
	@echo "  make check      运行当前阶段的静态检查"

setup: check-env
	@echo "基础工具已经就绪；Python 虚拟环境会在对应实验中创建。"

check-env:
	@./scripts/check-env.sh

check: check-env
	@bash -n scripts/check-env.sh
	@echo "基础检查通过。"
