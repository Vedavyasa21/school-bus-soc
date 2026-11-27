#!/usr/bin/env bash
# Rebuilds and re-runs all controller sweeps, sensitivity ablation, and figure/table generators.
set -e
cd "$(dirname "$0")"
SRC=../src
MODS="$SRC/sensor_input.c $SRC/sensor_fusion.c $SRC/danger_detection.c $SRC/priority_scheduler.c"
mkdir -p ../build results ../figures
gcc -O2 -Wall -Wextra -I "$SRC" -o ../build/sweep       sweep.c       $MODS
gcc -O2 -Wall -Wextra -I "$SRC" -o ../build/dump        dump.c        $MODS
gcc -O2 -Wall -Wextra -I "$SRC" -o ../build/sensitivity sensitivity.c $SRC/sensor_input.c $SRC/sensor_fusion.c
../build/sweep
../build/dump results/frames.csv results/seed2024.csv
../build/sensitivity > results/sensitivity.csv
PY=python3
if [ -x "../.venv/bin/python" ]; then PY="$(cd .. && pwd)/.venv/bin/python"; fi
"$PY" analyze.py > results/analysis_printout.txt
"$PY" make_tables.py > results/tables_summary.txt
"$PY" make_figures3.py
echo "---- checksums ----"
md5sum results/sweep.csv results/det.csv results/sensitivity.csv
