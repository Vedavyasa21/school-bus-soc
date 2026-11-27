"""Builds all tables used in the paper from results/*.csv and gem5 stats -> tables.json."""
import json
import os
import re
import numpy as np
import pandas as pd
from scipy import stats

BASE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(BASE, "results")
GEM5_R = os.path.abspath(os.path.join(BASE, "..", "experiments", "results"))

df_all = pd.read_csv(os.path.join(R, "sweep_all.csv"))
d0 = df_all[df_all["mode"] == "RAW_40"].copy()

def prep(sub):
    sub = sub[sub["seed"] != 2024].copy()
    sub["cr"] = sub["crit_miss"] / sub["crit_n"].replace(0, np.nan)
    sub["wr"] = sub["warn_miss"] / sub["warn_n"].replace(0, np.nan)
    sub["sr"] = sub["safe_miss"] / sub["safe_n"].replace(0, np.nan)
    sub["ar"] = (sub["crit_miss"] + sub["warn_miss"] + sub["safe_miss"]) / (
        sub["crit_n"] + sub["warn_n"] + sub["safe_n"]
    )
    sub["ca"] = sub["crit_sum"] / sub["crit_n"].replace(0, np.nan)
    sub["wa"] = sub["warn_sum"] / sub["warn_n"].replace(0, np.nan)
    sub["sa"] = sub["safe_sum"] / sub["safe_n"].replace(0, np.nan)
    return sub

d_raw40 = prep(df_all[df_all["mode"] == "RAW_40"])
d_coal40 = prep(df_all[df_all["mode"] == "COAL_40"])
d_long = prep(df_all[df_all["mode"] == "LONG_RAW"])
d_long_coal = prep(df_all[df_all["mode"] == "LONG_COAL"])
d_cpu50 = prep(df_all[df_all["mode"] == "CPU50_1000"])

def mci(x):
    x = x.dropna()
    return float(x.mean()), float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))

NAMES = {
    "FIFO": "FIFO",
    "FIXED-SENSOR": "Fixed (sensor)",
    "SAFETY-AWARE": "Safety-aware",
    "SA-RISK-ONLY": "SA (risk only, no aging)",
    "SA-AGING-ONLY": "SA (aging only, no risk)",
    "ZONE-FIFO": "Zone, then arrival",
    "EDF": "EDF",
    "P-ZONE-FIFO": "Preemptive zone",
    "P-EDF": "Preemptive EDF",
}
ORDER_7 = ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "EDF", "P-ZONE-FIFO", "P-EDF"]
ORDER_9 = ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "SA-RISK-ONLY", "SA-AGING-ONLY", "ZONE-FIFO", "EDF", "P-ZONE-FIFO", "P-EDF"]

out = {}

# 1. Steady-state LONG_RAW (N=1,000) critical miss ratio across key loads
loads_key = [100, 125, 150, 200, 300, 400]
out["t_crit_long"] = [["Policy"] + [f"{L}%" for L in loads_key]] + [
    [NAMES[p]] + [f"{m:.3f} +/- {h:.3f}" for m, h in [mci(d_long[(d_long.load == L) & (d_long.policy == p)].cr) for L in loads_key]]
    for p in ORDER_7
]

# Legacy RAW_40 (N=40) critical miss ratio for continuity
out["t_crit_raw40"] = [["Policy"] + [f"{L}%" for L in [100, 150, 200, 300, 400]]] + [
    [NAMES[p]] + [f"{m:.3f} +/- {h:.3f}" for m, h in [mci(d_raw40[(d_raw40.load == L) & (d_raw40.policy == p)].cr) for L in [100, 150, 200, 300, 400]]]
    for p in ORDER_7
]

# 2. Steady-state LONG_RAW (N=1,000) zone breakdown at 100% and 400% + 2x2 factorial ablation
for key, L in [("t_long100", 100), ("t_long400", 400), ("t_raw100", 100), ("t_raw400", 400)]:
    src = d_long if "long" in key else d_raw40
    rows = [["Policy", "Crit miss", "Warn miss", "Safe miss", "All miss", "Crit avg (ms)", "Warn avg (ms)", "Safe avg (ms)", "Crit max (ms)"]]
    for p in ORDER_9:
        g = src[(src.load == L) & (src.policy == p)]
        rows.append([
            NAMES[p], f"{g.cr.mean():.3f}", f"{g.wr.mean():.3f}", f"{g.sr.mean():.3f}", f"{g.ar.mean():.3f}",
            f"{g.ca.mean():.1f}", f"{g.wa.mean():.1f}", f"{g.sa.mean():.1f}", f"{int(g.crit_max.max())}"
        ])
    out[key] = rows

# 3. 13-load Feasibility Comparison (LONG_RAW vs LONG_COAL vs RAW_40)
rows_feas = [["Load", "RAW_40 rho", "RAW_40 P-EDF feas", "LONG_RAW rho", "LONG_RAW P-EDF feas", "LONG_COAL rho", "LONG_COAL SA noCrit", "LONG_COAL P-EDF feas"]]
for L in sorted(d_long.load.unique()):
    pe_r = d_raw40[(d_raw40.policy == "P-EDF") & (d_raw40.load == L)]
    pe_l = d_long[(d_long.policy == "P-EDF") & (d_long.load == L)]
    pe_lc = d_long_coal[(d_long_coal.policy == "P-EDF") & (d_long_coal.load == L)]
    sa_lc = d_long_coal[(d_long_coal.policy == "SAFETY-AWARE") & (d_long_coal.load == L)]
    rows_feas.append([
        f"{L}%",
        f"{pe_r.rho.mean():.2f}", f"{int(((pe_r.crit_miss+pe_r.warn_miss+pe_r.safe_miss)==0).sum())}/100",
        f"{pe_l.rho.mean():.2f}", f"{int(((pe_l.crit_miss+pe_l.warn_miss+pe_l.safe_miss)==0).sum())}/100",
        f"{pe_lc.rho.mean():.2f}", f"{int((sa_lc.crit_miss==0).sum())}/100",
        f"{int(((pe_lc.crit_miss+pe_lc.warn_miss+pe_lc.safe_miss)==0).sum())}/100",
    ])
out["t_feas_all"] = rows_feas

# 4. Coalesced vs Raw comparison (400% overload & 100%)
rows_coal = [["Stream (100 seeds)", "Mean crit/warn/safe", "rho (100%)", "rho (400%)", "FIFO crit 400%", "Fixed crit 400%", "SA crit 400%", "Zone-FIFO crit 400%", "EDF crit 400%"]]
for lbl, src in [("RAW_40 (N=40)", d_raw40), ("COAL_40 (25 ms coal.)", d_coal40), ("LONG_RAW (N=1,000)", d_long), ("LONG_COAL (25 ms coal.)", d_long_coal)]:
    g100 = src[(src.load == 100) & (src.policy == "FIFO")]
    g400 = src[src.load == 400]
    mc, mw, ms = g100.crit_n.mean(), g100.warn_n.mean(), g100.safe_n.mean()
    r100 = g100.rho.mean()
    r400 = g400[g400.policy == "FIFO"].rho.mean()
    c_vals = [f"{g400[g400.policy==p].cr.mean():.3f}" for p in ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "EDF"]]
    rows_coal.append([lbl, f"{mc:.1f} / {mw:.1f} / {ms:.1f}", f"{r100:.2f}", f"{r400:.2f}"] + c_vals)
out["t_coal"] = rows_coal

# 5. Stage 1 Detection, Sensitivity, ROC & 200-MC
det = pd.read_csv(os.path.join(R, "det.csv"), header=None, names=["tag", "seed", "tp", "fp", "fn", "tn"])
def drow(lbl, t):
    TP, FP, FN, TN = int(t.tp.sum()), int(t.fp.sum()), int(t.fn.sum()), int(t.tn.sum())
    return [lbl, str(TP), str(FP), str(FN), str(TN),
            f"{TP/(TP+FP):.3f}", f"{TP/(TP+FN):.3f}", f"{(TP+TN)/(TP+FP+FN+TN):.3f}"]
out["t_det"] = [["Data", "TP", "FP", "FN", "TN", "Precision", "Recall", "Accuracy"],
                drow("100 seeds (4,000 frames)", det[det.seed != 2024]),
                drow("Seed 2024 (40 frames)", det[det.seed == 2024])]

sens = pd.read_csv(os.path.join(R, "sensitivity.csv"))
mc = pd.read_csv(os.path.join(R, "sensitivity_mc.csv"))
rows_sens = [["Configuration", "Prec.", "Rec.", "Acc.", "F1", "FP (int.)", "Stand. TP/559"]]
for _, r in sens.iterrows():
    rows_sens.append([
        r.config, f"{r.precision:.3f}", f"{r.recall:.3f}", f"{r.accuracy:.3f}",
        f"{r.f1:.3f}", f"{int(r.fp)} ({int(r.fp_interior)})", f"{int(r.standing_tp)} ({r.standing_tp/559:.1%})"
    ])
rows_sens.append([
    "200 MC ±20% random draws (mean ± SD)",
    f"{mc.precision.mean():.3f} ± {mc.precision.std(ddof=1):.3f}",
    f"{mc.recall.mean():.3f} ± {mc.recall.std(ddof=1):.3f}",
    f"{mc.accuracy.mean():.3f} ± {mc.accuracy.std(ddof=1):.3f}",
    f"{mc.f1.mean():.3f} ± {mc.f1.std(ddof=1):.3f}",
    f"{mc.fp.mean():.1f} ± {mc.fp.std(ddof=1):.1f}",
    f"{mc.standing_tp.mean():.1f} [160-298]",
])
out["t_sens"] = rows_sens

roc = pd.read_csv(os.path.join(R, "fusion_roc.csv"))
roc40 = roc[roc.threshold == 40]
rows_roc = [["Fusion Rule (T = 40)", "Prec.", "Rec.", "FPR", "F1", "FP (int.)", "Stand. Rec."]]
for rule in ["Weighted+both_close", "2-of-3 voting", "Max-of-sensors", "Weighted-motion-only", "AND-fusion"]:
    r = roc40[roc40.rule == rule].iloc[0]
    rows_roc.append([
        rule, f"{r.precision:.3f}", f"{r.recall:.3f}", f"{r.fpr:.3f}",
        f"{r.f1:.3f}", f"{int(r.fp)} ({int(r.fp_interior)})", f"{r.standing_recall:.3f}"
    ])
out["t_roc40"] = rows_roc

# 6. Case Study Seed 2024 (RAW_40 100%, RAW_40 400%, COAL_40 400%)
for key, mode, L in [("t_2024_100", "RAW_40", 100), ("t_2024_400", "RAW_40", 400), ("t_2024_coal400", "COAL_40", 400)]:
    sub = df_all[(df_all["mode"] == mode) & (df_all["seed"] == 2024) & (df_all["load"] == L)]
    rows = [["Policy", "Avg all", "Avg crit", "Avg warn", "Avg safe", "Max crit", "Crit miss", "Warn miss", "Total miss", "Makespan"]]
    for p in ORDER_7:
        r = sub[sub.policy == p].iloc[0]
        tot_n = int(r.crit_n + r.warn_n + r.safe_n)
        tot_m = int(r.crit_miss + r.warn_miss + r.safe_miss)
        wa = f"{r.warn_sum/r.warn_n:.2f}" if r.warn_n > 0 else "0.00"
        sa = f"{r.safe_sum/r.safe_n:.2f}" if r.safe_n > 0 else "0.00"
        rows.append([
            NAMES[p], f"{r.all_sum/tot_n:.2f}", f"{r.crit_sum/r.crit_n:.2f}", wa, sa,
            f"{int(r.crit_max)}", f"{int(r.crit_miss)}/{int(r.crit_n)}",
            f"{int(r.warn_miss)}/{int(r.warn_n)}", f"{tot_m}/{tot_n}", f"{int(r.makespan)}"
        ])
    out[key] = rows

# 7. CPU50_1000 summary
rows_cpu50 = [["Load", "rho (110 us/evt)", "SA crit miss", "SA all miss", "FIFO crit miss", "Fixed crit miss"]]
for L in [50, 100, 150, 200, 300, 400]:
    g_sa = d_cpu50[(d_cpu50.load == L) & (d_cpu50.policy == "SAFETY-AWARE")]
    g_fi = d_cpu50[(d_cpu50.load == L) & (d_cpu50.policy == "FIFO")]
    g_fx = d_cpu50[(d_cpu50.load == L) & (d_cpu50.policy == "FIXED-SENSOR")]
    rows_cpu50.append([
        f"{L}%", f"{g_sa.rho.mean():.4f}", f"{g_sa.cr.mean():.4f}",
        f"{g_sa.ar.mean():.4f}", f"{g_fi.cr.mean():.4f}", f"{g_fx.cr.mean():.4f}"
    ])
out["t_cpu50"] = rows_cpu50

# 8. gem5 stats & single-pipeline extraction
def parse_gem5_prof(name):
    txt = open(os.path.join(GEM5_R, name, "stdout.txt"), encoding="utf-8", errors="ignore").read()
    stages = {}
    for stg in ["SensorInput", "SensorFusion", "DangerDetect", "FIFO", "FIXED-PRIORITY", "SAFETY-AWARE", "WarningGen",
                "TOTAL_COMPUTE", "SINGLE_FIFO", "SINGLE_FIXED-PRIORITY", "SINGLE_SAFETY-AWARE"]:
        m = re.search(rf"^{re.escape(stg)}\s+(\d+)\s+(\d+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)", txt, re.M)
        if m:
            stages[stg] = {
                "cycles": int(m.group(1)), "insts": int(m.group(2)),
                "cyc_evt": float(m.group(3)), "us_1ghz": float(m.group(4)), "ipc": float(m.group(5))
            }
    exit_ticks = int(re.search(r"Exiting @ tick (\d+)", txt).group(1))
    stxt = open(os.path.join(GEM5_R, name, "stats.txt"), encoding="utf-8", errors="ignore").read()
    blocks = stxt.split("---------- Begin Simulation Statistics ----------")[1:]
    b_cyc = [int(re.search(r"system\.cpu\.numCycles\s+(\d+)", b).group(1)) for b in blocks]
    b_ins = [int(re.search(r"system\.cpu\.commitStats0\.numInsts\s+(\d+)", b).group(1)) for b in blocks]
    return {"stages": stages, "exit_cycles": exit_ticks // 1000, "block_cycles": b_cyc, "block_insts": b_ins}

gem5_info = {n: parse_gem5_prof(n) for n in ["prof_timing", "prof_minor"]}
for n in ["demo_timing", "demo_quiet100", "demo_stress"]:
    stxt = open(os.path.join(GEM5_R, n, "stats.txt"), encoding="utf-8", errors="ignore").read()
    last = stxt.split("---------- Begin Simulation Statistics ----------")[-1]
    gem5_info[n] = {
        "cycles": int(re.search(r"system\.cpu\.numCycles\s+(\d+)", last).group(1)),
        "insts": int(re.search(r"system\.cpu\.commitStats0\.numInsts\s+(\d+)", last).group(1)),
    }

# 9. Complete m=52 Holm-Bonferroni tables for LONG_RAW & RAW_40
holm_out = {}
pairs = [("SAFETY-AWARE", "FIFO"), ("SAFETY-AWARE", "FIXED-SENSOR"), ("SAFETY-AWARE", "ZONE-FIFO"), ("P-ZONE-FIFO", "SAFETY-AWARE")]
for mode_key, src in [("LONG_RAW", d_long), ("RAW_40", d_raw40)]:
    raw_rows = []
    for L in sorted(src.load.unique()):
        for p1, p2 in pairs:
            x = src[(src.load == L) & (src.policy == p1)].set_index("seed").cr
            y = src[(src.load == L) & (src.policy == p2)].set_index("seed").cr
            k = x.dropna().index.intersection(y.dropna().index)
            diff = x[k] - y[k]
            pval = 1.0 if diff.abs().sum() == 0 else float(stats.wilcoxon(x[k], y[k]).pvalue)
            raw_rows.append({"load": int(L), "p1": p1, "p2": p2, "diff": float(diff.mean()), "raw_p": pval})
    order = np.argsort([r["raw_p"] for r in raw_rows])
    prev = 0.0
    m_tot = len(raw_rows)
    for rank, idx in enumerate(order):
        val = min(1.0, (m_tot - rank) * raw_rows[idx]["raw_p"])
        prev = max(prev, val)
        raw_rows[idx]["holm_p"] = prev
    holm_out[mode_key] = raw_rows

out_path = os.path.join(BASE, "tables.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"tables": out, "gem5": gem5_info, "holm": holm_out}, f, indent=1)

print("Generated tables.json cleanly. Keys:", list(out.keys()))
print(f"LONG_RAW 100% rho={d_long[(d_long.load == 100) & (d_long.policy == 'FIFO')].rho.mean():.3f}, "
      f"400% rho={d_long[(d_long.load == 400) & (d_long.policy == 'FIFO')].rho.mean():.3f} | "
      f"COAL_40 100% rho={d_coal40[(d_coal40.load == 100) & (d_coal40.policy == 'FIFO')].rho.mean():.3f}, "
      f"400% rho={d_coal40[(d_coal40.load == 400) & (d_coal40.policy == 'FIFO')].rho.mean():.3f} | "
      f"LONG_COAL 400% rho={d_long_coal[(d_long_coal.load == 400) & (d_long_coal.policy == 'FIFO')].rho.mean():.3f}")
for n in ["prof_timing", "prof_minor"]:
    s = gem5_info[n]["stages"]
    print(f"{n}: SINGLE_SA={s['SINGLE_SAFETY-AWARE']['cycles']} cyc ({s['SINGLE_SAFETY-AWARE']['us_1ghz']} us, {s['SINGLE_SAFETY-AWARE']['cyc_evt']} cyc/evt), TOTAL={s['TOTAL_COMPUTE']['cycles']}")
