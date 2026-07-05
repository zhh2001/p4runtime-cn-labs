SHELL := /usr/bin/env bash

LAB ?= 01
LAB_DIR := $(firstword $(wildcard labs/$(LAB)-*))
LAB_NAME := $(notdir $(LAB_DIR))
P4_SOURCE := $(LAB_DIR)/main.p4
BUILD_DIR := build/$(LAB_NAME)
P4C ?= p4c-bm2-ss

.PHONY: help setup check-env require-lab build inspect clean check

help:
	@echo "可用命令："
	@echo "  make check-env  检查本机 P4 实验工具"
	@echo "  make setup      确认基础环境可用"
	@echo "  make build LAB=01    编译指定实验"
	@echo "  make inspect LAB=01  查看 P4Info 对象"
	@echo "  make clean      删除编译产物"
	@echo "  make check      运行当前阶段的静态检查"

setup: check-env
	@echo "基础工具已经就绪；Python 虚拟环境会在对应实验中创建。"

check-env:
	@./scripts/check-env.sh

require-lab:
	@if [[ -z "$(LAB_DIR)" || ! -f "$(P4_SOURCE)" ]]; then \
		echo "找不到 LAB=$(LAB) 对应的 P4 实验。" >&2; \
		exit 1; \
	fi

build: require-lab
	@mkdir -p "$(BUILD_DIR)"
	$(P4C) --std p4-16 \
		--p4runtime-files "$(BUILD_DIR)/p4info.txtpb" \
		--p4runtime-format text \
		-o "$(BUILD_DIR)/pipeline.json" \
		"$(P4_SOURCE)"
	@echo "编译结果：$(BUILD_DIR)"

inspect: build
	@python3 scripts/inspect-p4info.py "$(BUILD_DIR)/p4info.txtpb"

clean:
	@rm -rf build

check: check-env
	@bash -n scripts/check-env.sh
	@python3 -m py_compile scripts/inspect-p4info.py
	@$(MAKE) --no-print-directory inspect LAB=01 >/dev/null
	@python3 -m json.tool build/01-pipeline/pipeline.json >/dev/null
	@python3 scripts/inspect-p4info.py build/01-pipeline/p4info.txtpb | grep -q '^action .*0x01'
	@python3 scripts/inspect-p4info.py build/01-pipeline/p4info.txtpb | grep -q '^table .*0x02'
	@echo "当前检查通过。"
