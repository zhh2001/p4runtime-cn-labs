SHELL := /usr/bin/env bash

LAB ?= 01
ELECTION_ID ?= 0,1
CONTROLLER_ARGS ?=
LAB_DIR := $(firstword $(wildcard labs/$(LAB)-*))
LAB_NAME := $(notdir $(LAB_DIR))
P4_SOURCE := $(LAB_DIR)/main.p4
BUILD_DIR := build/$(LAB_NAME)
TOPOLOGY := $(LAB_DIR)/topology.py
CONTROLLER := $(LAB_DIR)/controller.py
P4C ?= p4c-bm2-ss

.PHONY: help setup shell-env python-env check-env require-lab require-topology require-controller build inspect run shell controller stop clean test check

help:
	@echo "可用命令："
	@echo "  make check-env  检查本机 P4 实验工具"
	@echo "  make setup      准备基础工具和 P4Runtime Shell"
	@echo "  make build LAB=01    编译指定实验"
	@echo "  make inspect LAB=01  查看 P4Info 对象"
	@echo "  sudo make run LAB=02 启动 Mininet 与 BMv2"
	@echo "  make shell LAB=02    连接 P4Runtime Shell"
	@echo "  make controller LAB=03 运行 Python controller"
	@echo "  sudo make stop       清理 Mininet"
	@echo "  make clean      删除编译产物"
	@echo "  make test       运行 Python 单元测试"
	@echo "  make check      运行当前阶段的静态检查"

setup: check-env shell-env python-env
	@echo "基础工具和两个 Python 环境已经就绪。"

shell-env:
	@./scripts/setup-shell-env.sh

python-env:
	@./scripts/setup-python-env.sh

check-env:
	@./scripts/check-env.sh

require-lab:
	@if [[ -z "$(LAB_DIR)" || ! -f "$(P4_SOURCE)" ]]; then \
		echo "找不到 LAB=$(LAB) 对应的 P4 实验。" >&2; \
		exit 1; \
	fi

require-topology: require-lab
	@if [[ ! -f "$(TOPOLOGY)" ]]; then \
		echo "LAB=$(LAB) 还没有可运行的 Mininet 拓扑。" >&2; \
		exit 1; \
	fi

require-controller: require-lab
	@if [[ ! -f "$(CONTROLLER)" ]]; then \
		echo "LAB=$(LAB) 还没有 Python controller。" >&2; \
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

run: require-topology
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(TOPOLOGY)" \
		--grpc-addr 127.0.0.1:9559 \
		--device-id 1 \
		--cpu-port 510

shell: build
	@if [[ ! -x .venv-shell/bin/python ]]; then \
		echo "缺少 .venv-shell，请先运行 make setup。" >&2; \
		exit 1; \
	fi
	@.venv-shell/bin/python -m p4runtime_sh \
		--grpc-addr 127.0.0.1:9559 \
		--device-id 1 \
		--election-id 0,1 \
		--config "$(BUILD_DIR)/p4info.txtpb,$(BUILD_DIR)/pipeline.json"

controller: build require-controller
	@if [[ ! -x .venv/bin/python ]]; then \
		echo "缺少 .venv，请先运行 make setup。" >&2; \
		exit 1; \
	fi
	@.venv/bin/python "$(CONTROLLER)" \
		--grpc-addr 127.0.0.1:9559 \
		--device-id 1 \
		--election-id "$(ELECTION_ID)" \
		--p4info "$(BUILD_DIR)/p4info.txtpb" \
		--device-config "$(BUILD_DIR)/pipeline.json" $(CONTROLLER_ARGS)

stop:
	@mn -c

clean:
	@rm -rf build

test: python-env
	@.venv/bin/python -m unittest discover -s tests -v

check: check-env
	@bash -n scripts/check-env.sh scripts/setup-shell-env.sh scripts/setup-python-env.sh
	@python3 -m py_compile scripts/inspect-p4info.py scripts/check-markdown-links.py
	@python3 -m py_compile tools/p4_mininet.py labs/02-table-entry/topology.py labs/03-python-client/topology.py labs/04-write-read/topology.py labs/05-resources/topology.py labs/06-selector-replication/topology.py labs/07-stream-arbitration/topology.py
	@python3 -m py_compile p4rt/*.py labs/03-python-client/controller.py labs/04-write-read/controller.py labs/05-resources/controller.py labs/06-selector-replication/controller.py labs/07-stream-arbitration/controller.py tests/*.py
	@$(MAKE) --no-print-directory inspect LAB=01 >/dev/null
	@$(MAKE) --no-print-directory inspect LAB=02 >/dev/null
	@$(MAKE) --no-print-directory inspect LAB=03 >/dev/null
	@$(MAKE) --no-print-directory inspect LAB=04 >/dev/null
	@$(MAKE) --no-print-directory inspect LAB=05 >/dev/null
	@$(MAKE) --no-print-directory inspect LAB=06 >/dev/null
	@$(MAKE) --no-print-directory inspect LAB=07 >/dev/null
	@$(MAKE) --no-print-directory test >/dev/null
	@python3 -m json.tool build/01-pipeline/pipeline.json >/dev/null
	@python3 scripts/inspect-p4info.py build/01-pipeline/p4info.txtpb | grep -q '^action .*0x01'
	@python3 scripts/inspect-p4info.py build/01-pipeline/p4info.txtpb | grep -q '^table .*0x02'
	@grep -q 'match_type: EXACT' build/02-table-entry/p4info.txtpb
	@grep -q 'match_type: LPM' build/02-table-entry/p4info.txtpb
	@python3 scripts/check-markdown-links.py >/dev/null
	@echo "当前检查通过。"
