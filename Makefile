CC ?= gcc
CFLAGS ?= -O2 -static -Wall -Wextra -Isrc
RISCV_CC ?= riscv64-linux-gnu-gcc
RISCV_CFLAGS ?= -O2 -static -Wall -Wextra -march=rv64gc -mabi=lp64d -Isrc
GEM5 ?= /home/vedavyasa/gem5/build/RISCV/gem5.opt
GEM5_DIR ?= /home/vedavyasa/gem5

SRCS = src/main.c \
       src/sensor_input.c \
       src/sensor_fusion.c \
       src/danger_detection.c \
       src/priority_scheduler.c \
       src/warning_system.c

BUILD_DIR = build
BIN = $(BUILD_DIR)/school_bus_soc
PROF_BIN = $(BUILD_DIR)/school_bus_soc_prof
LIBM5 = $(GEM5_DIR)/util/m5/build/riscv/out/libm5.a
CORE_SRCS = src/sensor_input.c \
            src/sensor_fusion.c \
            src/danger_detection.c \
            src/priority_scheduler.c \
            src/warning_system.c

.PHONY: all build prof run-native gem5-demo gem5-prof gem5-experiments clean help

all: build

build: $(BIN)

$(BIN): $(SRCS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SRCS) -o $(BIN)
	@echo "Build successful: $(BIN)"

prof: $(PROF_BIN)

$(PROF_BIN): src/profile_stages.c $(CORE_SRCS)
	@mkdir -p $(BUILD_DIR)
	$(RISCV_CC) $(RISCV_CFLAGS) -DGEM5_M5OPS -I$(GEM5_DIR)/include src/profile_stages.c $(CORE_SRCS) $(LIBM5) -o $(PROF_BIN)
	@echo "RISC-V profiler build successful: $(PROF_BIN)"

gem5-prof: prof
	@echo "=== Running gem5 Per-Stage Cycle Profiler (RISC-V) ==="
	$(GEM5) --outdir=experiments/results/prof_timing configs/school_bus_soc.py --binary $(PROF_BIN) --args "40 2024" --cpu-type timing

run-native: build
	@echo "=== Running SoC Application Natively ==="
	./$(BIN) 40 2024 1

gem5-demo: build
	@echo "=== Running gem5 Simulation Demo ==="
	python3 experiments/run_experiments.py --gem5 $(GEM5) --demo

gem5-experiments: build
	@echo "=== Running Full gem5 Microarchitectural Experiment Suite ==="
	python3 experiments/run_experiments.py --gem5 $(GEM5) --cpus timing,o3 --events 32,64,128 --seeds 2024,2025

clean:
	rm -rf $(BUILD_DIR) experiments/results m5out
	@echo "Clean completed."

help:
	@echo "Smart School Bus Safety & Priority Management SoC"
	@echo "Targets:"
	@echo "  make              - Compile the static binary into $(BIN)"
	@echo "  make run-native   - Execute binary directly on Linux host for verification"
	@echo "  make gem5-demo    - Run gem5 simulation with verbose live output (for screenshots)"
	@echo "  make gem5-experiments - Run full benchmark matrix across CPU models and workloads"
	@echo "  make clean        - Remove build and result directories"
