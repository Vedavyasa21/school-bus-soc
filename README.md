# Safety-Aware Event Scheduling for a School Bus Pedestrian Protection Controller

**RISC-V Architecture Modeling, gem5 Hardware Profiling, and Multi-Seed Schedulability Study**

[![Release](https://img.shields.io/badge/release-v1.0--paper-blue)](https://github.com/Vedavyasa21/school-bus-soc/releases/tag/v1.0-paper)

---

## Overview

This repository contains the complete C controller model, gem5 RISC-V platform configuration (`gem5 v25.1.0.1`), per-stage hardware profiler (`rdcycle`/`rdinstret` CSRs + gem5 `m5ops`), 100-seed / 13-load experiment harness, normalized fusion sensitivity benchmark, raw CSV logs, raw terminal execution evidence (`evidence/`), and publication figure/table generators supporting the paper:

> *Safety-Aware Event Scheduling for a School Bus Pedestrian Protection Controller: A RISC-V/gem5 Simulation Study*

### Controller Pipeline (`src/`)

1. **Sensor Input (`sensor_input.c/.h`)**: Generates deterministic xorshift-seeded synthetic multi-sensor streams (ultrasonic `0–400 cm` with `3%` dropout, short-range proximity `3–150 cm`, motion `0–100`, door state, and vehicle speed `km/h`) across six scenarios (`IDLE 25%`, `APPROACH 25%`, `CROSSING 12%`, `STANDING 12%`, `OBSTACLE 14%`, `NOISE 12%`).
2. **Sensor Fusion (`sensor_fusion.c/.h`)**: Computes a normalized weighted score `conf = (us_s*w_us + pr_s*w_pr + mo_s*w_mo) / (w_us + w_pr + w_mo)` (`35/25/40` baseline, clamped `[0, 100]`) with cross-sensor disagreement penalties and dual short-range confirmation (`both_close = us_echo && prox_echo && dist <= 200`) to detect stationary/crouching children.
3. **Danger-Zone Classification (`danger_detection.c/.h`)**: Applies a `300 cm` warning threshold and integer kinematic stopping-distance critical threshold (`d_stop = floor(4*v_cms/10) + floor(v_cms^2/1000)`, `crit_cm = clamp(100 + d_stop, 150, 220)` cm when `door_open` or `bus_speed_kmh > 0`, with `tau = 0.4 s`, `a = 5.0 m/s^2 = 500 cm/s^2`).
4. **Priority Scheduling (`priority_scheduler.c/.h` & `experiments_extra/sweep.c`)**: Compares `FIFO`, `FIXED-SENSOR`, `SAFETY-AWARE` (`zone * 1000 + risk` with safe-to-warning aging at `250 ms`), `ZONE-FIFO`, `EDF`, `P-ZONE-FIFO`, and `P-EDF` under `3/6/9 ms` service times and `300/100/40 ms` deadlines.
5. **Driver & V2X Warnings (`warning_system.c/.h`)**: Generates `[INFO]`, `[CAUTION]`, and `[DANGER]` cabin alerts and V2V text logs.
6. **Per-Stage gem5 Profiler (`profile_stages.c`)**: Isolates each stage without console formatting distortion using RISC-V `rdcycle`/`rdinstret` CSRs and `m5_reset_stats`/`m5_dump_stats` (`libm5.a`).

---

## Requirements & gem5 RISC-V Build Setup

- **Host OS**: Ubuntu / Linux (tested on Ubuntu 24.04/26.04 under WSL2)
- **RISC-V Cross-Compiler**: `riscv64-linux-gnu-gcc` (`-march=rv64gc -mabi=lp64d -O2 -static`)
- **gem5 Simulator**: `gem5 v25.1.0.1` built for `RISCV` (`build/RISCV/gem5.opt`) plus `util/m5/build/riscv/out/libm5.a` (`scons build/RISCV/gem5.opt -j$(nproc)`)
- **Python Analysis Stack**: Python 3 (`numpy`, `pandas`, `scipy`, `matplotlib`)

---

## Single-Command Reproduction

```bash
# 1) Run 100-seed / 13-load sweep, normalized fusion sensitivity, Holm tests, and all paper figures
cd experiments_extra && bash run_all.sh && cd ..

# 2) Run gem5 RISC-V SE case studies (verbose 100%, quiet 100%, quiet 400%) and per-stage m5ops/rdcycle profiling
python3 experiments/run_experiments.py --gem5 ~/gem5/build/RISCV/gem5.opt --demo && \
  ~/gem5/build/RISCV/gem5.opt --outdir=experiments/results/demo_quiet100 configs/school_bus_soc.py --binary build/school_bus_soc --args "40 2024 0 100" --cpu-type timing && \
  ~/gem5/build/RISCV/gem5.opt --outdir=experiments/results/demo_stress   configs/school_bus_soc.py --binary build/school_bus_soc --args "40 2024 0 400" --cpu-type timing && \
  make gem5-prof && \
  ~/gem5/build/RISCV/gem5.opt --outdir=experiments/results/prof_minor    configs/school_bus_soc.py --binary build/school_bus_soc_prof --args "40 2024" --cpu-type minor
```

---

## Paper-to-Artifact Mapping

| Paper Artifact | Generator / Source | Raw Data / Archived Evidence |
|---|---|---|
| **Tables 1–8 & Figs. 1–4** | Static model parameters & diagrams (`src/*.h`, `configs/school_bus_soc.py`, `make_figures3.py`) | `src/sensor_input.h`, `sensor_fusion.h`, `danger_detection.h`, `priority_scheduler.h`, `figures/fig_gem5_arch.png` |
| **Fig. 5 (gem5 banner)** | `experiments/run_experiments.py --demo` | `evidence/raw_01_gem5_config_banner.png` |
| **Table 9 & Fig. 6** | `experiments_extra/dump.c`, `make_figures3.py` | `experiments_extra/results/det.csv`, `frames.csv`, `seed2024.csv`, `evidence/term_stage1_2024.png` |
| **Fig. 7 (Seed 2024 Conf.)** | `experiments_extra/make_figures3.py` | `experiments_extra/results/seed2024.csv`, `figures/fig_confidence40.png` |
| **Table 10 (Sensitivity)** | `experiments_extra/sensitivity.c` | `experiments_extra/results/sensitivity.csv` |
| **Tables 11–12 & Figs. 8–9** | `experiments_extra/sweep.c`, `make_tables.py`, `make_figures3.py` | `experiments_extra/results/sweep.csv`, `tables.json`, `demo_timing/stats.txt`, `evidence/term_stage3_2024.png` |
| **Tables 13–16 & Figs. 10–11** | `experiments_extra/sweep.c`, `analyze.py`, `calc_stats.py`, `make_tables.py` | `experiments_extra/results/sweep.csv`, `summary.csv`, `analysis_printout.txt` |
| **Table 17 (Full-run gem5)** | `src/main.c`, `configs/school_bus_soc.py` | `experiments/results/{demo_timing,demo_quiet100,demo_stress}/stats.txt` |
| **Table 18 & Fig. 12** | `src/profile_stages.c`, `make_figures3.py` | `experiments/results/{prof_timing,prof_minor}/{stats.txt,stdout.txt}`, `evidence/term_prof_2024.png`, `evidence/term_md5_2024.png` |

Archived terminal captures and deterministic MD5 verification outputs are stored in [`evidence/`](evidence/).

---

## Deterministic Output Checksums (`run_all.sh`)

```text
c81e9b5057819dd02f97f3300ffcde55  experiments_extra/results/sweep.csv
1035cad44bb9817ba1fa4be1132b7776  experiments_extra/results/det.csv
8b3423de1de73f176aa1136219edaa2f  experiments_extra/results/sensitivity.csv
```

## License

Released under the [MIT License](LICENSE).
