# Safety-Aware Event Scheduling for a School Bus Pedestrian Protection Controller

**RISC-V Architecture Modeling, gem5 Hardware Profiling, and Multi-Seed Schedulability Study**

---

## Overview

This repository contains the complete C controller model, gem5 RISC-V platform configuration, per-stage hardware profiler (`m5ops` + `rdcycle`), multi-seed/multi-load experiment harness, raw CSV logs, and figure/table generation scripts supporting the paper:

> *Safety-Aware Event Scheduling for a School Bus Pedestrian Protection Controller: A RISC-V/gem5 Simulation Study*

### Controller Pipeline (`src/`)

1. **Sensor Input (`sensor_input.c/.h`)**: Generates seeded synthetic multi-sensor streams (ultrasonic 0–400 cm with 3% sensor dropout, short-range proximity 3–150 cm, motion level 0–100, door status, and bus speed) across six scenarios (`IDLE`, `APPROACH`, `CROSSING`, `STANDING`, `OBSTACLE`, `NOISE`).
2. **Sensor Fusion (`sensor_fusion.c/.h`)**: Computes weighted confidence (`0.35 US + 0.25 PR + 0.40 MO`) with cross-sensor disagreement penalties and dual-sensor close-range confirmation (`both_close` within 200 cm) to detect stationary/crouching children.
3. **Danger-Zone Classification (`danger_detection.c/.h`)**: Maps distance, confidence, door state, and vehicle speed to `SAFE`, `WARNING` ($\le 300\text{ cm}$), and `CRITICAL` zones using a stopping-distance model ($\tau = 0.4\text{ s}$ reaction, $a = 5.0\text{ m/s}^2$ deceleration).
4. **Priority Scheduling (`priority_scheduler.c/.h` & `experiments_extra/sweep.c`)**: Evaluates `FIFO`, `FIXED-SENSOR`, `SAFETY-AWARE` (zone $\times 1000 + \text{risk}$ with safe-to-warning anti-starvation aging), `ZONE-FIFO` (zone then arrival), `EDF`, `P-ZONE-FIFO` (preemptive zone), and `P-EDF` (preemptive EDF).
5. **Driver & V2X Warnings (`warning_system.c/.h`)**: Dispatches driver cabin alerts (`[INFO]`, `[CAUTION]`, `[DANGER]`) and V2V/C-V2X emergency safety messages.
6. **Per-Stage gem5 Profiler (`profile_stages.c`)**: Isolates compute stages without console `printf` overhead using RISC-V `rdcycle`/`rdinstret` CSRs and gem5 `m5ops` (`libm5.a`).

---

## Reproducing All Results

### 1. Build & Run Case Study on gem5 (RISC-V SE Mode)

```bash
# Nominal load (100%, seed 2024, verbose)
python3 experiments/run_experiments.py --gem5 ~/gem5/build/RISCV/gem5.opt --demo

# 400% overload case study on gem5 (RiscvTimingSimpleCPU)
~/gem5/build/RISCV/gem5.opt --outdir=experiments/results/demo_stress \
    configs/school_bus_soc.py --binary build/school_bus_soc \
    --args "40 2024 0 400" --cpu-type timing
```

### 2. Per-Stage Hardware Cycle Profiling on gem5 (`RiscvTimingSimpleCPU` & `RiscvMinorCPU`)

```bash
make prof
~/gem5/build/RISCV/gem5.opt --outdir=experiments/results/prof_timing \
    configs/school_bus_soc.py --binary build/school_bus_soc_prof \
    --args "40 2024" --cpu-type timing

~/gem5/build/RISCV/gem5.opt --outdir=experiments/results/prof_minor \
    configs/school_bus_soc.py --binary build/school_bus_soc_prof \
    --args "40 2024" --cpu-type minor
```

### 3. Run 100-Seed Sweep, Feasibility, Sensitivity & Regenerate CSVs/Figures

```bash
cd experiments_extra
bash run_all.sh
```

This generates:
- `experiments_extra/results/sweep.csv` (100 seeds × 13 loads × 7 policies + seed 2024)
- `experiments_extra/results/det.csv` & `frames.csv` (4,000 labeled frames)
- `experiments_extra/results/sensitivity.csv` (±20% fusion weight & stationary-rule ablation)
- `experiments_extra/results/analysis_printout.txt` & `tables.json`
- Publication-quality plots in `figures/*.png`
