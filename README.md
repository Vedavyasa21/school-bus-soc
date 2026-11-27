# Zone-Priority Event Scheduling for a School Bus Pedestrian Protection Controller

**A Synthetic-Workload Study with RISC-V/gem5 Cycle Profiling**

[![Release](https://img.shields.io/badge/release-v1.0--paper-blue)](https://github.com/Vedavyasa21/school-bus-soc/releases/tag/v1.0-paper)

---

## Overview

This repository contains the modular five-stage C controller model, gem5 RISC-V platform configuration (`gem5 v25.1.0.1`), single-pipeline and multi-policy per-stage hardware profiler (`rdcycle`/`rdinstret` CSRs + gem5 `m5ops`), 100-seed / 13-load schedulability harness (`N=40` bursts, `N=1,000` steady-state, `25 ms` track coalescing, and `50 MHz` scaled compute-only sweeps), five-rule ROC & 200-draw Monte Carlo fusion sensitivity suite, raw CSV logs, terminal verification captures (`evidence/`), and publication figure/table scripts supporting the paper:

> *Zone-Priority Event Scheduling for a School Bus Pedestrian Protection Controller: A Synthetic-Workload Study with RISC-V/gem5 Cycle Profiling*

### Controller Pipeline (`src/`)

1. **Sensor Input (`sensor_input.c/.h`)**: Generates deterministic xorshift-seeded synthetic multi-sensor streams (`ultrasonic 0–400 cm` with `3%` dropout, `proximity 3–150 cm`, `motion 0–100`, door state, and vehicle speed `km/h`) across six scenarios (`IDLE 25%`, `APPROACH 25%`, `CROSSING 12%`, `STANDING 12%`, `OBSTACLE 14%`, `NOISE 12%`). Note `SENSOR_NOISE` produces `24–76 cm` echoes (`rand_i(30,70)+noise(6)`) in `35%` of noise frames.
2. **Sensor Fusion (`sensor_fusion.c/.h`)**: Computes a normalized weighted score `conf = (us_s*w_us + pr_s*w_pr + mo_s*w_mo) / (w_us + w_pr + w_mo)` (`35/25/40` baseline, clamped `[0, 100]`) with disagreement penalties and dual close-range confirmation (`both_close = us_echo && prox_echo && dist <= 200`, within `150 cm` proximity coverage) for standing children.
3. **Danger-Zone Classification (`danger_detection.c/.h`)**: Applies a `300 cm` warning limit and unclamped integer kinematic stopping-distance critical bound (`d_stop = floor(4*v_cms/10) + floor(v_cms^2/1000)`, `crit_cm = max(150, 100 + d_stop)` up to `439 cm` at `15 km/h`, with `tau = 0.4 s`, `a = 5.0 m/s^2 = 500 cm/s^2`).
4. **Priority Scheduling (`priority_scheduler.c/.h` & `experiments_extra/sweep.c`)**: Compares `FIFO`, `FIXED-SENSOR`, `SAFETY-AWARE`, `SA-RISK-ONLY`, `SA-AGING-ONLY`, `ZONE-FIFO`, `EDF`, `P-ZONE-FIFO`, and `P-EDF` across raw streams (`RAW_40`, `LONG_RAW`), `25 ms` track-coalesced streams (`COAL_40`, `LONG_COAL`), and `50 MHz × 1.5 RTOS` pure-CPU timing (`CPU50_1000`: `110 us/evt`).
5. **Driver & V2X Warnings (`warning_system.c/.h`)**: Generates `[INFO]`, `[CAUTION]`, and `[DANGER]` cabin alerts and V2V text logs.
6. **Per-Stage gem5 Profiler (`profile_stages.c`)**: Isolates each stage plus single-pipeline deployment totals (`SINGLE_FIFO`, `SINGLE_FIXED-PRIORITY`, `SINGLE_SAFETY-AWARE`) without console formatting distortion using RISC-V `rdcycle`/`rdinstret` CSRs and `libm5.a` (`m5_reset_stats`/`m5_dump_stats`).

---

## Requirements & gem5 RISC-V Build Setup

- **Host OS**: Ubuntu / Linux (tested on Ubuntu under WSL2)
- **RISC-V Cross-Compiler**: `riscv64-linux-gnu-gcc` (`-march=rv64gc -mabi=lp64d -O2 -static`)
- **gem5 Simulator**: `gem5 v25.1.0.1` built for `RISCV` (`build/RISCV/gem5.opt`) plus `util/m5/build/riscv/out/libm5.a`
- **Python Analysis Stack**: Python 3 (`numpy`, `pandas`, `scipy`, `matplotlib`)

---

## Single-Command Reproduction

```bash
# 1) Run 100-seed / 13-load sweeps (RAW_40, COAL_40, LONG_RAW, LONG_COAL, CPU50_1000),
#    5-rule ROC + 200-MC fusion sensitivity, Holm-Bonferroni tests, tables.json, and all figures
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
| **Tables 1–8 & Figs. 1–4** | Static model parameters & diagrams (`src/*.h`, `configs/school_bus_soc.py`, `make_figures3.py`) | `src/*.h`, `figures/fig_{system_arch,method_flow,danger_flow,gem5_arch}.png` |
| **Fig. 5 (gem5 banner)** | `experiments/run_experiments.py --demo` | `evidence/raw_01_gem5_config_banner.png` |
| **Table 9 & Figs. 6–7** | `experiments_extra/dump.c`, `make_figures3.py` | `experiments_extra/results/{det,frames,seed2024}.csv`, `evidence/term_stage1_2024.png` |
| **Tables 10–11 & Fig. 8** | `experiments_extra/sensitivity.c`, `make_figures3.py` | `experiments_extra/results/{sensitivity,fusion_roc,sensitivity_mc}.csv`, `figures/fig_fusion_roc.png` |
| **Tables 12–13 & Figs. 9–10** | `experiments_extra/sweep.c`, `make_tables.py`, `make_figures3.py` | `experiments_extra/results/sweep_all.csv`, `demo_timing/stats.txt`, `evidence/term_stage3_2024.png` |
| **Tables 14–18 & Figs. 11–12** | `experiments_extra/sweep.c`, `make_tables.py`, `make_figures3.py` | `experiments_extra/results/sweep_all.csv`, `tables.json` (`LONG_RAW`, `LONG_COAL`, `m=52` Holm) |
| **Tables 19–20 & Fig. 13** | `src/main.c`, `src/profile_stages.c`, `sweep.c` (`CPU50_1000`), `make_figures3.py` | `experiments/results/{demo_*,prof_*}/{stats.txt,stdout.txt}`, `evidence/term_{prof,md5}_2024.png` |

---

## Deterministic Output Checksums (`run_all.sh`)

```text
29aff614915fff4e6ebff6b3c159508b  experiments_extra/results/sweep.csv
5da8b11ac371991f4fed03437d112601  experiments_extra/results/sweep_all.csv
1035cad44bb9817ba1fa4be1132b7776  experiments_extra/results/det.csv
d9e58dede65ae0fbb97d84b73ac69763  experiments_extra/results/sensitivity.csv
e3feb035ec456694c9250dace0eb4325  experiments_extra/results/fusion_roc.csv
d3fd0ed7b045ac2b7360de13c41a76e5  experiments_extra/results/sensitivity_mc.csv
```

## License

Released under the [MIT License](LICENSE).
