# Makefile — Build P4 programs cho 3S-COM Phase 4
#
# Usage:
#   make all         — Build cả core và border switch
#   make core        — Build cho Core switch (MSD=10)
#   make border      — Build cho Border switch (MSD=3)
#   make clean       — Xoá build artifacts
#   make run-core    — Chạy BMv2 core switch (cần sudo)
#   make run-border  — Chạy BMv2 border switch (cần sudo)
#   make verify      — Xác minh MSD constraint bằng test packet

P4_SRC    := srv6_basic.p4
BUILD_DIR := build
DOCKER_IMG := p4lang/p4app:latest

.PHONY: all core border clean run-core run-border verify

all: core border

# ──────────────────────────────────────────────────────────────
# BUILD: Core Switch (Hà Nội, Đà Nẵng, HCM) — MSD = 10
# ──────────────────────────────────────────────────────────────
core: $(BUILD_DIR)/core/srv6_core.json

$(BUILD_DIR)/core/srv6_core.json: $(P4_SRC)
	@echo "🔨 Compiling Core Switch (MSD=10)..."
	@mkdir -p $(BUILD_DIR)/core
	docker run --rm --entrypoint p4c-bm2-ss \
		-v $(PWD):/p4 $(DOCKER_IMG) \
		--std p4-16 \
		-D MAX_SID_DEPTH=10 \
		--target bmv2 --arch v1model \
		-o /p4/$(BUILD_DIR)/core/srv6_core.json \
		--p4runtime-files /p4/$(BUILD_DIR)/core/srv6_core.p4info.txt \
		/p4/$(P4_SRC)
	@echo "✅ Core switch binary: $(BUILD_DIR)/core/srv6_core.json"

# ──────────────────────────────────────────────────────────────
# BUILD: Border Switch (Huế, Ninh Bình, ...) — MSD = 3
# ──────────────────────────────────────────────────────────────
border: $(BUILD_DIR)/border/srv6_border.json

$(BUILD_DIR)/border/srv6_border.json: $(P4_SRC)
	@echo "🔨 Compiling Border Switch (MSD=3)..."
	@mkdir -p $(BUILD_DIR)/border
	docker run --rm --entrypoint p4c-bm2-ss \
		-v $(PWD):/p4 $(DOCKER_IMG) \
		--std p4-16 \
		-D MAX_SID_DEPTH=3 \
		--target bmv2 --arch v1model \
		-o /p4/$(BUILD_DIR)/border/srv6_border.json \
		--p4runtime-files /p4/$(BUILD_DIR)/border/srv6_border.p4info.txt \
		/p4/$(P4_SRC)
	@echo "✅ Border switch binary: $(BUILD_DIR)/border/srv6_border.json"

# ──────────────────────────────────────────────────────────────
# RUN: Khởi chạy BMv2 soft-switch (simple_switch_grpc)
# Cần đang có Mininet net đang chạy và interface sẵn sàng.
# ──────────────────────────────────────────────────────────────
run-core: $(BUILD_DIR)/core/srv6_core.json
	@echo "🚀 Starting Core BMv2 switch (grpc port 50051)..."
	docker run --rm --network host --privileged \
		-v $(PWD)/$(BUILD_DIR)/core:/data \
		p4lang/behavioral-model:latest \
		simple_switch_grpc \
		--device-id 1 \
		--log-console \
		--thrift-port 9090 \
		-i 0@eth0 -i 1@eth1 -i 2@eth2 \
		-- /data/srv6_core.json

run-border: $(BUILD_DIR)/border/srv6_border.json
	@echo "🚀 Starting Border BMv2 switch (grpc port 50052)..."
	docker run --rm --network host --privileged \
		-v $(PWD)/$(BUILD_DIR)/border:/data \
		p4lang/behavioral-model:latest \
		simple_switch_grpc \
		--device-id 2 \
		--log-console \
		--thrift-port 9091 \
		-i 0@eth0 -i 1@eth1 \
		-- /data/srv6_border.json

# ──────────────────────────────────────────────────────────────
# TEST: Verify MSD Enforcement
# Tạo một gói test với quá nhiều SID và kiểm tra switch DROP nó.
# ──────────────────────────────────────────────────────────────
verify: $(BUILD_DIR)/core/srv6_core.json
	@echo "🧪 Testing MSD Enforcement (should DROP packet with 11 SIDs)..."
	docker run --rm -v $(PWD):/p4 -v $(PWD)/$(BUILD_DIR)/core:/data \
		p4lang/p4app:latest \
		python3 /p4/tests/test_msd_enforcement.py
	@echo ""
	@echo "🧪 Testing valid packet (should FORWARD packet with 3 SIDs)..."
	@echo "   (Use Wireshark/tcpdump on egress interface to confirm)"

clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf $(BUILD_DIR)/
	@echo "✅ Clean complete."
