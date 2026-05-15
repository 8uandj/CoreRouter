# Makefile — Build P4 programs cho 3S-COM Phase 7
#
# Usage:
#   make all         — Build tat ca cac MSD profile (4, 5, 8, 10)
#   make clean       — Xoá build artifacts

P4_SRC    := srv6_basic.p4
BUILD_DIR := build
DOCKER_IMG := p4lang/p4app:latest

.PHONY: all clean msd_4 msd_5 msd_8 msd_10

all: msd_4 msd_5 msd_8 msd_10

# ──────────────────────────────────────────────────────────────
# BUILD: Custom MSD Profiles for 10-node Topology
# ──────────────────────────────────────────────────────────────

msd_%: $(P4_SRC)
	@echo "🔨 Compiling Switch Profile (MSD=$*)..."
	@mkdir -p $(BUILD_DIR)/msd_$*
	docker run --rm --entrypoint p4c-bm2-ss \
		-v $(PWD):/p4 $(DOCKER_IMG) \
		--std p4-16 \
		-D MAX_SID_DEPTH=$* \
		--target bmv2 --arch v1model \
		-o /p4/$(BUILD_DIR)/msd_$*/srv6_msd_$*.json \
		--p4runtime-files /p4/$(BUILD_DIR)/msd_$*/srv6_msd_$*.p4info.txt \
		/p4/$(P4_SRC)
	@echo "✅ Switch binary: $(BUILD_DIR)/msd_$*/srv6_msd_$*.json"

clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf $(BUILD_DIR)/
	@echo "✅ Clean complete."
