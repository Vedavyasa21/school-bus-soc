#!/usr/bin/env python3
"""Build the SoC binary, run simulations in gem5, and compare scheduling policies.

Supports both x86 (e.g. build/X86/gem5.opt) and RISC-V (e.g. build/RISCV/gem5.opt).
Automatically identifies the installed gem5 build, selects the matching compiler,
builds the static binary, executes simulations, and records hardware and scheduler metrics.

Examples:
  # Demo run (verbose terminal output with step-by-step events, perfect for screenshots):
  python3 experiments/run_experiments.py --demo

  # Full microarchitectural experiment across CPU models and workloads:
  python3 experiments/run_experiments.py --cpus timing,o3 --events 32,64,128 --seeds 2024,2025
"""

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
BUILD_DIR = os.path.join(ROOT, "build")
CONFIG = os.path.join(ROOT, "configs", "school_bus_soc.py")
RESULT_DIR = os.path.join(ROOT, "experiments", "results")

SOURCES = [
    "main.c",
    "sensor_input.c",
    "sensor_fusion.c",
    "danger_detection.c",
    "priority_scheduler.c",
    "warning_system.c",
]


def detect_arch_from_gem5(gem5_path):
    lower = gem5_path.lower()
    if "riscv" in lower:
        return "riscv"
    elif "x86" in lower:
        return "x86"
    elif "arm" in lower:
        return "arm"
    return "x86"


def find_compiler(user_cc, arch):
    if user_cc:
        return user_cc

    if arch == "riscv":
        for cc in ["riscv64-linux-gnu-gcc", "riscv64-unknown-linux-gnu-gcc"]:
            if shutil.which(cc):
                return cc
        sys.exit(
            "ERROR: No RISC-V cross compiler found (install gcc-riscv64-linux-gnu or pass --cc)."
        )
    elif arch == "arm":
        for cc in ["aarch64-linux-gnu-gcc", "arm-linux-gnueabi-gcc"]:
            if shutil.which(cc):
                return cc
        sys.exit("ERROR: No ARM cross compiler found. Pass --cc.")
    else:  # x86
        for cc in ["gcc", "x86_64-linux-gnu-gcc", "clang"]:
            if shutil.which(cc):
                return cc
        sys.exit("ERROR: No C compiler found (install build-essential or gcc).")


def get_binary_path(arch):
    return os.path.join(BUILD_DIR, "school_bus_soc")


def build(cc, arch):
    os.makedirs(BUILD_DIR, exist_ok=True)
    binary = get_binary_path(arch)
    extra_flags = []
    if arch == "riscv":
        extra_flags = ["-march=rv64gc", "-mabi=lp64d"]

    cmd = [
        cc,
        "-O2",
        "-static",
        "-Wall",
        "-Wextra",
    ] + extra_flags + [
        "-I",
        SRC_DIR,
        "-o",
        binary,
    ] + [os.path.join(SRC_DIR, s) for s in SOURCES]

    print("[build] Compiler   : %s (%s target)" % (cc, arch))
    print("[build] Command    : %s" % " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("[build] Binary built successfully -> %s\n" % binary)
    return binary


def find_gem5(user_bin):
    candidates = []
    if user_bin:
        candidates.append(user_bin)
    if os.environ.get("GEM5_BIN"):
        candidates.append(os.environ["GEM5_BIN"])

    gem5_home = os.environ.get("GEM5_HOME")
    search_dirs = [gem5_home] if gem5_home else []
    search_dirs.extend([
        os.path.expanduser("~/gem5"),
        "/home/vedavyasa/gem5",
        os.path.join(ROOT, "..", "gem5"),
    ])

    for base in search_dirs:
        if base and os.path.isdir(base):
            for arch in ("RISCV", "X86", "ARM"):
                for variant in ("gem5.opt", "gem5.fast", "gem5.debug"):
                    candidates.append(os.path.join(base, "build", arch, variant))

    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return os.path.abspath(c)

    sys.exit(
        "ERROR: gem5 binary not found. Set GEM5_HOME, GEM5_BIN, or pass --gem5 /path/to/gem5.opt"
    )


def gem5_cmd(gem5, outdir, cpu, binary, args_str):
    return [
        gem5,
        "--outdir=" + outdir,
        CONFIG,
        "--binary",
        binary,
        "--args",
        args_str,
        "--cpu-type",
        cpu,
    ]


def parse_results(text):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("RESULT,"):
            f = line.split(",")
            if len(f) == 9:
                rows.append({
                    "policy": f[1],
                    "events": int(f[2]),
                    "avg_all": float(f[3]),
                    "avg_crit": float(f[4]),
                    "max_crit": int(f[5]),
                    "miss_crit": int(f[6]),
                    "miss_all": int(f[7]),
                    "makespan": int(f[8]),
                })
    return rows


def parse_stats(path):
    if not os.path.isfile(path):
        return {}
    with open(path, "r", errors="ignore") as fh:
        content = fh.read()
    blocks = content.split("---------- Begin Simulation Statistics ----------")
    last = blocks[-1]
    stats = {}
    for line in last.splitlines():
        m = re.match(r"^(\S+)\s+([-+0-9.eE]+|nan|inf)\b", line)
        if m:
            try:
                stats[m.group(1)] = float(m.group(2))
            except ValueError:
                pass
    return stats


def find_stat(stats, suffix):
    for k, v in stats.items():
        if k.endswith(suffix):
            return v
    return float("nan")


def hw_metrics(stats):
    insts = find_stat(stats, "simInsts")
    cycles = find_stat(stats, "cpu.numCycles")
    return {
        "sim_seconds": find_stat(stats, "simSeconds"),
        "sim_insts": insts,
        "cycles": cycles,
        "ipc": insts / cycles if cycles and cycles == cycles and cycles > 0 else float("nan"),
        "l1i_miss": find_stat(stats, "icache.overallMissRate::total"),
        "l1d_miss": find_stat(stats, "dcache.overallMissRate::total"),
        "l2_miss": find_stat(stats, "l2cache.overallMissRate::total"),
    }


def run_demo(gem5, cpu, binary, events, seed):
    outdir = os.path.join(RESULT_DIR, "demo_%s" % cpu)
    os.makedirs(outdir, exist_ok=True)
    cmd = gem5_cmd(gem5, outdir, cpu, binary, "%d %d 1" % (events, seed))
    print("[demo] Running command:\n" + " ".join(cmd) + "\n")
    subprocess.run(cmd)


def run_one(gem5, cpu, binary, events, seed, timeout):
    outdir = os.path.join(RESULT_DIR, "%s_n%d_s%d" % (cpu, events, seed))
    os.makedirs(outdir, exist_ok=True)
    cmd = gem5_cmd(gem5, outdir, cpu, binary, "%d %d 0" % (events, seed))
    print("[run] cpu=%s events=%d seed=%d ..." % (cpu, events, seed), end="", flush=True)
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(" [TIMEOUT]")
        return None, None

    with open(os.path.join(outdir, "console.txt"), "w") as fh:
        fh.write(proc.stdout)

    if proc.returncode != 0:
        print(" [FAILED: exit code %d]" % proc.returncode)
        lines = proc.stdout.splitlines()
        print("\n".join(lines[-15:]))
        return None, None

    sched = parse_results(proc.stdout)
    hw = hw_metrics(parse_stats(os.path.join(outdir, "stats.txt")))
    if not sched:
        print(" [NO DATA: missing RESULT lines]")
        return None, None

    print(" [OK]")
    return sched, hw


def print_tables(records):
    print("\n" + "=" * 105)
    print(" EXPERIMENT RESULTS: SCHEDULING ALGORITHM COMPARISON (Simulated Time in ms)")
    print("=" * 105)
    print(
        "%-7s %6s %5s %-16s %9s %9s %8s %9s %8s %9s"
        % (
            "CPU",
            "Events",
            "Seed",
            "Policy",
            "AvgAll",
            "AvgCrit",
            "MaxCrit",
            "MissCrit",
            "MissAll",
            "Makespan",
        )
    )
    for r in records:
        print(
            "%-7s %6d %5d %-16s %9.2f %9.2f %8d %9d %8d %9d"
            % (
                r["cpu"],
                r["events"],
                r["seed"],
                r["policy"],
                r["avg_all"],
                r["avg_crit"],
                r["max_crit"],
                r["miss_crit"],
                r["miss_all"],
                r["makespan"],
            )
        )

    print("\n" + "=" * 105)
    print(" GEM5 MICROARCHITECTURAL HARDWARE STATISTICS")
    print("=" * 105)
    print(
        "%-7s %6s %5s %12s %12s %12s %6s %8s %8s %8s"
        % (
            "CPU",
            "Events",
            "Seed",
            "simSeconds",
            "simInsts",
            "Cycles",
            "IPC",
            "L1I-mr",
            "L1D-mr",
            "L2-mr",
        )
    )
    seen = set()
    for r in records:
        key = (r["cpu"], r["events"], r["seed"])
        if key in seen:
            continue
        seen.add(key)
        print(
            "%-7s %6d %5d %12.6f %12.0f %12.0f %6.3f %8.4f %8.4f %8.4f"
            % (
                r["cpu"],
                r["events"],
                r["seed"],
                r["sim_seconds"],
                r["sim_insts"],
                r["cycles"],
                r["ipc"],
                r["l1i_miss"],
                r["l1d_miss"],
                r["l2_miss"],
            )
        )


def write_csv(records):
    os.makedirs(RESULT_DIR, exist_ok=True)
    path = os.path.join(RESULT_DIR, "summary.csv")
    if not records:
        return
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)
    print("\n[csv] Summary exported to: %s" % path)


def main():
    ap = argparse.ArgumentParser(description="School Bus SoC gem5 Experiment Suite")
    ap.add_argument("--gem5", default=None, help="Path to gem5.opt binary")
    ap.add_argument("--cc", default=None, help="C compiler (gcc or riscv cross-compiler)")
    ap.add_argument("--cpus", default="timing", help="Comma-separated CPU models: timing,minor,o3")
    ap.add_argument("--events", default="32,64,128", help="Comma-separated event counts")
    ap.add_argument("--seeds", default="2024", help="Comma-separated seeds")
    ap.add_argument("--timeout", type=int, default=1800, help="Per-simulation timeout in seconds")
    ap.add_argument(
        "--demo",
        action="store_true",
        help="Run single simulation with live verbose output for screenshots",
    )
    ap.add_argument("--demo-events", type=int, default=40, help="Event count for demo run")
    ap.add_argument("--skip-build", action="store_true", help="Skip compiling the binary")
    args = ap.parse_args()

    gem5 = find_gem5(args.gem5)
    arch = detect_arch_from_gem5(gem5)
    print("=" * 70)
    print(" Smart School Bus SoC gem5 Experiment Suite")
    print(" Detected gem5 Binary : %s" % gem5)
    print(" Target Architecture  : %s" % arch.upper())
    print("=" * 70)

    binary = get_binary_path(arch)
    if not args.skip_build:
        cc = find_compiler(args.cc, arch)
        binary = build(cc, arch)
    elif not os.path.isfile(binary):
        sys.exit("ERROR: Binary missing at %s, please run without --skip-build" % binary)

    cpus = [c.strip() for c in args.cpus.split(",") if c.strip()]
    events = [int(e) for e in args.events.split(",") if e.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    if args.demo:
        run_demo(gem5, cpus[0], binary, args.demo_events, seeds[0])
        return

    records = []
    for cpu in cpus:
        for n in events:
            for seed in seeds:
                sched, hw = run_one(gem5, cpu, binary, n, seed, args.timeout)
                if sched is None:
                    continue
                for row in sched:
                    rec = {"cpu": cpu, "seed": seed}
                    rec.update(row)
                    rec.update(hw)
                    records.append(rec)

    if not records:
        sys.exit("No successful runs to report.")
    print_tables(records)
    write_csv(records)


if __name__ == "__main__":
    main()
