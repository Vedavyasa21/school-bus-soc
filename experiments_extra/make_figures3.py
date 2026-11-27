"""Publication-grade figures generated directly from program logs and gem5 stats.
Run from experiments_extra/."""
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D
from scipy import stats

plt.rcParams["font.family"] = "DejaVu Serif"
plt.rcParams["axes.linewidth"] = 0.9
R = "results/"
GEM5_R = "../experiments/results/"
OUT = "../figures/"
COL = {
    "FIFO": "#3B69A8",
    "FIXED-SENSOR": "#B54A42",
    "SAFETY-AWARE": "#2E8B57",
    "ZONE-FIFO": "#D9822B",
    "P-ZONE-FIFO": "#4A4A4A",
}

def save(fig, name):
    fig.savefig(OUT + name, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ---------------------------------------------------------------------------
# Fig. 6: Confidence per event, seed 2024 (clean spacing, zero overlaps)
# ---------------------------------------------------------------------------
s = pd.read_csv(R + "seed2024.csv")
zc = {"SAFE": "#8FCB9B", "WARNING": "#F2C45A", "CRITICAL": "#E07B72"}
fig, ax = plt.subplots(figsize=(7.4, 3.2))
ax.bar(s.id, s.conf, color=[zc[z] for z in s.zone], edgecolor="#333", lw=0.55)
ax.axhline(40, color="#222", ls="--", lw=1.15)
ax.annotate("limit = 40", xy=(9.0, 40), xytext=(9.0, 16), ha="center", va="center", fontsize=7.2,
            bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="#666", lw=0.45),
            arrowprops=dict(arrowstyle="->", lw=0.75, color="#333"))
box = dict(boxstyle="round,pad=0.25", fc="white", ec="#777", lw=0.6)

fp_rows = s[(s.det == "YES") & (s.tru == "no") & (s.scene == "NOISE")]
if len(fp_rows):
    r0 = fp_rows.iloc[0]
    ax.annotate("Event 20: NOISE FP\n(dist 71 cm, conf 41)",
                xy=(r0.id, r0.conf + 1), xytext=(22.2, 108),
                fontsize=7.6, bbox=box, arrowprops=dict(arrowstyle="->", lw=0.9, color="#222"))

fn_rows = s[(s.det == "no") & (s.tru == "YES")]
if len(fn_rows):
    r1 = fn_rows.iloc[-1]
    ax.annotate(f"Event {int(r1.id)}: missed child FN\n({int(r1.dist)} cm, conf {int(r1.conf)})",
                xy=(r1.id, r1.conf + 1), xytext=(30.0, 95),
                fontsize=7.6, bbox=box, arrowprops=dict(arrowstyle="->", lw=0.9, color="#222"))

ax.set_xlabel("Event ID (seed 2024)", fontsize=8.8)
ax.set_ylabel("Normalized fused confidence", fontsize=8.8)
ax.set_ylim(0, 134)
ax.set_xticks(range(0, 40, 2))
ax.tick_params(labelsize=7.8)
ax.grid(axis="y", ls=":", alpha=0.35)
ax.set_axisbelow(True)
ax.legend(handles=[Patch(fc=zc[k], ec="#333", label=k) for k in zc],
          fontsize=8.0, loc="upper left", ncol=3, frameon=False)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
save(fig, "fig_confidence40.png")

# ---------------------------------------------------------------------------
# Fig. 7: Latency per event (100%) and critical events at 400%
# ---------------------------------------------------------------------------
fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.4, 5.2), gridspec_kw={"height_ratios": [1.08, 1]})
for k, c, m, lab in [
    ("fifo100", COL["FIFO"], "o", "FIFO"),
    ("fixed100", COL["FIXED-SENSOR"], "s", "Fixed (sensor)"),
    ("sa100", COL["SAFETY-AWARE"], "^", "Safety-aware"),
]:
    a1.plot(s.id, s[k], "-" + m, ms=3.4, lw=1.35, color=c, label=lab)
a1.axhline(40, color="#B22222", ls="--", lw=1.1, label="Critical deadline (40 ms)")
a1.set_ylabel("Latency (ms), 100% load", fontsize=8.8)
a1.set_xlabel("Event ID (seed 2024)", fontsize=8.8)
a1.legend(fontsize=7.6, frameon=False, ncol=4, loc="upper left")
a1.tick_params(labelsize=7.8)
a1.set_ylim(0, max(50, s[["fifo100", "fixed100", "sa100"]].max().max() + 12))
a1.grid(axis="y", ls=":", alpha=0.35)

crit = s[s.zone == "CRITICAL"].reset_index(drop=True)
x = np.arange(len(crit))
w = 0.27
for j, (k, c, lab) in enumerate([
    ("fifo400", COL["FIFO"], "FIFO"),
    ("fixed400", COL["FIXED-SENSOR"], "Fixed (sensor)"),
    ("sa400", COL["SAFETY-AWARE"], "Safety-aware"),
]):
    a2.bar(x + (j - 1) * w, crit[k], w, color=c, edgecolor="#333", lw=0.45, label=lab)
a2.axhline(40, color="#B22222", ls="--", lw=1.15, label="Critical deadline (40 ms)")
a2.set_xticks(x)
a2.set_xticklabels(crit.id, fontsize=7.4)
a2.set_xlabel("Critical event ID (seed 2024)", fontsize=8.8)
a2.set_ylabel("Latency (ms), 400% load", fontsize=8.8)
a2.set_ylim(0, 232)
a2.tick_params(labelsize=7.8)
a2.legend(fontsize=7.6, frameon=False, ncol=4, loc="upper left")
a2.grid(axis="y", ls=":", alpha=0.35)
a2.set_axisbelow(True)
for a in (a1, a2):
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
fig.tight_layout()
save(fig, "fig_latency40.png")

# ---------------------------------------------------------------------------
# Fig. 9: Critical miss ratio vs load (100 seeds, 13 loads)
# ---------------------------------------------------------------------------
d = pd.read_csv(R + "sweep.csv")
d = d[d.seed != 2024].copy()
d["crit_ratio"] = d.crit_miss / d.crit_n.replace(0, np.nan)
fig, ax = plt.subplots(figsize=(7.4, 3.2))
loads = sorted(d.load.unique())
for pol in ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "P-ZONE-FIFO"]:
    g = d[d.policy == pol]
    m, h = [], []
    for L in loads:
        x_val = g[g.load == L].crit_ratio.dropna()
        m.append(x_val.mean())
        h.append(stats.t.ppf(0.975, len(x_val) - 1) * x_val.std(ddof=1) / np.sqrt(len(x_val)))
    m, h = np.array(m), np.array(h)
    ax.plot(loads, m, "-o", ms=3.5, lw=1.55, color=COL[pol],
            label={"FIXED-SENSOR": "Fixed (sensor)", "SAFETY-AWARE": "Safety-aware",
                   "ZONE-FIFO": "Zone, then arrival", "P-ZONE-FIFO": "Preemptive zone, then arrival"}.get(pol, pol))
    ax.fill_between(loads, np.clip(m - h, 0, 1), np.clip(m + h, 0, 1), color=COL[pol], alpha=0.16, lw=0)
ax.set_xlabel("Offered arrival scale (% of nominal)", fontsize=8.8)
ax.set_ylabel("Critical deadline-miss ratio", fontsize=8.8)
ax.set_ylim(0, 0.95)
ax.tick_params(labelsize=7.8)
ax.grid(True, ls=":", alpha=0.35)
ax.legend(fontsize=7.8, frameon=False, loc="upper left")
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
save(fig, "fig_crit_vs_load.png")

# ---------------------------------------------------------------------------
# Fig. 10: Miss ratio by zone at 200% and 400%
# ---------------------------------------------------------------------------
d["warn_ratio"] = d.warn_miss / d.warn_n.replace(0, np.nan)
d["safe_ratio"] = d.safe_miss / d.safe_n.replace(0, np.nan)
pols = ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "P-ZONE-FIFO"]
fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.1), sharey=True)
for ax, L in zip(axs, [200, 400]):
    w = 0.16
    for j, pol in enumerate(pols):
        g = d[(d.load == L) & (d.policy == pol)]
        vals = [g.crit_ratio.mean(), g.warn_ratio.mean(), g.safe_ratio.mean()]
        ax.bar(np.arange(3) + (j - 2) * w, vals, w, color=COL[pol], edgecolor="#333", lw=0.45)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["Critical", "Warning", "Safe"], fontsize=8.2)
    ax.set_title(f"Load {L}%", fontsize=9.0, fontweight="bold")
    ax.tick_params(labelsize=7.8)
    ax.grid(axis="y", ls=":", alpha=0.35)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
axs[0].set_ylabel("Mean deadline-miss ratio", fontsize=8.8)
axs[1].legend(
    handles=[Patch(fc=COL[p], ec="#333", label=l)
             for p, l in zip(pols, ["FIFO", "Fixed (sensor)", "Safety-aware", "Zone, then arrival", "Preemptive zone"])],
    fontsize=7.4, frameon=False, loc="upper right",
)
fig.tight_layout()
save(fig, "fig_tradeoff.png")

# ---------------------------------------------------------------------------
# Fig. 5 (NEW CLEAN FIGURE): Stage 1 Seed-2024 Detection & Distance Envelope
# ---------------------------------------------------------------------------
fr = pd.read_csv(R + "frames.csv")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.1), gridspec_kw={"width_ratios": [1.35, 1.0]})
for z, c, mk in [("SAFE", "#3E9B5A", "o"), ("WARNING", "#D9822B", "s"), ("CRITICAL", "#C0392B", "^")]:
    sub = s[s.zone == z]
    ax1.scatter(sub.id, sub.dist, c=c, marker=mk, s=28, edgecolors="#222", lw=0.5, label=f"{z} ({len(sub)})")
# Highlight FP and FN directly on distance trajectory
for _, r in s[(s.det == "YES") & (s.tru == "no")].iterrows():
    ax1.scatter([r.id], [r.dist], s=85, facecolors="none", edgecolors="#8E44AD", lw=1.4)
for _, r in s[(s.det == "no") & (s.tru == "YES")].iterrows():
    ax1.scatter([r.id], [r.dist], s=85, facecolors="none", edgecolors="#000", lw=1.4, ls="--")
ax1.axhline(150, color="#555", ls=":", lw=1.0, label="Prox. max (150 cm)")
ax1.axhline(300, color="#D9822B", ls="--", lw=1.0, label="Warning limit (300 cm)")
ax1.annotate("Ev.20 NOISE FP", xy=(20, 71), xytext=(4.0, 20), fontsize=7.0,
             bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#8E44AD", lw=0.5),
             arrowprops=dict(arrowstyle="->", lw=0.7, color="#8E44AD"))
ax1.annotate("Ev.28/37 FN", xy=(28, 285), xytext=(29.5, 355), fontsize=7.0,
             bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#222", lw=0.5),
             arrowprops=dict(arrowstyle="->", lw=0.7, color="#222"))
ax1.set_xlabel("Event ID (seed 2024)", fontsize=8.4)
ax1.set_ylabel("Estimated distance (cm)", fontsize=8.4)
ax1.set_title("(a) Seed 2024 classification & errors", fontsize=8.8, fontweight="bold")
ax1.set_ylim(0, 520)
ax1.tick_params(labelsize=7.5)
ax1.legend(fontsize=6.6, ncol=2, frameon=False, loc="upper left")
ax1.grid(axis="y", ls=":", alpha=0.35)

# Panel (b): Pooled 4,000-frame scene outcome breakdown
scenes = ["APPROACH", "CROSSING", "STANDING", "OBSTACLE", "NOISE", "IDLE"]
short_sc = ["Appr.", "Cross.", "Stand.", "Obst.", "Noise", "Idle"]
tp_c = [len(fr[(fr.scene == sc) & (fr.present == 1) & (fr.truth == 1)]) for sc in scenes]
fn_c = [len(fr[(fr.scene == sc) & (fr.present == 0) & (fr.truth == 1)]) for sc in scenes]
fp_c = [len(fr[(fr.scene == sc) & (fr.present == 1) & (fr.truth == 0)]) for sc in scenes]
tn_c = [len(fr[(fr.scene == sc) & (fr.present == 0) & (fr.truth == 0)]) for sc in scenes]
xi = np.arange(len(scenes))
ax2.bar(xi, tp_c, color="#3E9B5A", edgecolor="#222", lw=0.45, label="TP (2,071)")
ax2.bar(xi, fn_c, bottom=tp_c, color="#E67E22", edgecolor="#222", lw=0.45, label="FN (358)")
ax2.bar(xi, tn_c, bottom=np.array(tp_c)+np.array(fn_c), color="#7FB3D5", edgecolor="#222", lw=0.45, label="TN (1,336)")
ax2.bar(xi, fp_c, bottom=np.array(tp_c)+np.array(fn_c)+np.array(tn_c), color="#8E44AD", edgecolor="#222", lw=0.45, label="FP (235)")
ax2.set_xticks(xi)
ax2.set_xticklabels(short_sc, fontsize=7.5)
ax2.set_ylabel("Frames (n = 4,000, 100 seeds)", fontsize=8.4)
ax2.set_title("(b) Detection outcomes by scene", fontsize=8.8, fontweight="bold")
ax2.tick_params(labelsize=7.5)
ax2.legend(fontsize=6.8, frameon=False, loc="upper right")
ax2.grid(axis="y", ls=":", alpha=0.35)
ax2.set_axisbelow(True)
for a in (ax1, ax2):
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
fig.tight_layout()
save(fig, "fig_stage1_seed2024.png")

# ---------------------------------------------------------------------------
# Fig. 8 (NEW CLEAN FIGURE): Seed 2024 Case Study Summary & Platform Settings
# ---------------------------------------------------------------------------
sw = pd.read_csv(R + "sweep.csv")
s24 = sw[sw.seed == 2024]
fig, (b1, b2) = plt.subplots(1, 2, figsize=(7.4, 3.0), gridspec_kw={"width_ratios": [1.35, 1.0]})
pol_list = ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "P-EDF"]
pol_labs = ["FIFO", "Fixed", "Safety-\nAware", "Zone-\nFIFO", "P-EDF"]
r0_s24 = s24[(s24.load == 400) & (s24.policy == "FIFO")].iloc[0]
crit_n_24 = int(r0_s24.crit_n)
warn_n_24 = int(r0_s24.warn_n)
rho_400_24 = float(r0_s24.rho)
crit400 = [s24[(s24.load == 400) & (s24.policy == p)].iloc[0].crit_miss for p in pol_list]
warn400 = [s24[(s24.load == 400) & (s24.policy == p)].iloc[0].warn_miss for p in pol_list]
xi = np.arange(len(pol_list))
w = 0.34
r1 = b1.bar(xi - w/2, crit400, w, color="#C0392B", edgecolor="#222", lw=0.5, label=f"Critical misses (of {crit_n_24})")
r2 = b1.bar(xi + w/2, warn400, w, color="#E08A2B", edgecolor="#222", lw=0.5, label=f"Warning misses (of {warn_n_24})")
for bar in list(r1) + list(r2):
    h = bar.get_height()
    b1.text(bar.get_x() + bar.get_width()/2, h + 0.35, f"{int(h)}", ha="center", va="bottom", fontsize=7.2)
b1.set_xticks(xi)
b1.set_xticklabels(pol_labs, fontsize=7.6)
b1.set_ylim(0, max(crit400) + 7.5)
b1.set_ylabel("Missed deadlines (seed 2024)", fontsize=8.4)
b1.set_title(f"(a) Seed 2024 400% overload misses (rho = {rho_400_24:.2f})", fontsize=8.7, fontweight="bold")
b1.legend(fontsize=7.3, frameon=False, loc="upper left")
b1.grid(axis="y", ls=":", alpha=0.35)
b1.set_axisbelow(True)
for sp in ("top", "right"):
    b1.spines[sp].set_visible(False)

def _stat_c(name, pat):
    txt = open(GEM5_R + name + "/stats.txt", encoding="utf-8", errors="ignore").read()
    last = txt.split("---------- Begin Simulation Statistics ----------")[-1]
    return int(re.search(pat, last).group(1))

_v1_c = _stat_c("demo_timing", r"system\.cpu\.numCycles\s+(\d+)")
_q1_c = _stat_c("demo_quiet100", r"system\.cpu\.numCycles\s+(\d+)")
_s4_c = _stat_c("demo_stress", r"system\.cpu\.numCycles\s+(\d+)")

b2.axis("off")
b2.set_title("(b) gem5 RISC-V SE Configuration", fontsize=8.7, fontweight="bold")
cfg_txt = (
    "Simulator  : gem5 v25.1.0.1 (SE mode)\n"
    "Target ISA : RISC-V 64 (rv64gc / lp64d)\n"
    "Compiler   : riscv64-linux-gnu-gcc -O2 -static\n"
    "CPU Models : RiscvTimingSimpleCPU @ 1 GHz\n"
    "             RiscvMinorCPU @ 1 GHz\n"
    "L1 Caches  : 32 KiB I / 32 KiB D (4-way, 2 cyc)\n"
    "L2 Cache   : 256 KiB shared (8-way, 20 cyc)\n"
    "Memory     : 512 MiB DDR3-1600\n"
    f"Exit Tick  : {_v1_c*1000:,} (verbose 100%)\n"
    f"             {_q1_c*1000:,} (quiet 100%)\n"
    f"             {_s4_c*1000:,} (quiet 400%)"
)
b2.add_patch(FancyBboxPatch((0.04, 0.05), 0.92, 0.88, boxstyle="round,pad=0.025,rounding_size=0.035",
                            fc="#F7F9FC", ec="#445", lw=0.9, transform=b2.transAxes))
b2.text(0.07, 0.49, cfg_txt, transform=b2.transAxes, va="center", ha="left",
        family="DejaVu Sans Mono", fontsize=6.0, linespacing=1.42, color="#111")
fig.tight_layout()
save(fig, "fig_seed2024_summary.png")

# ---------------------------------------------------------------------------
# Fig. 11 (NEW CLEAN FIGURE): Per-Stage Compute Profile & Full-Run Reconciliation
# ---------------------------------------------------------------------------
def load_stat_val(name, pat):
    txt = open(GEM5_R + name + "/stats.txt", encoding="utf-8", errors="ignore").read()
    last = txt.split("---------- Begin Simulation Statistics ----------")[-1]
    return int(re.search(pat, last).group(1))

demo_v1_c = load_stat_val("demo_timing", r"system\.cpu\.numCycles\s+(\d+)")
demo_q1_c = load_stat_val("demo_quiet100", r"system\.cpu\.numCycles\s+(\d+)")
demo_s4_c = load_stat_val("demo_stress", r"system\.cpu\.numCycles\s+(\d+)")

def parse_prof_stdout(name):
    txt = open(GEM5_R + name + "/stdout.txt", encoding="utf-8", errors="ignore").read()
    order = ["SensorInput", "SensorFusion", "DangerDetect", "FIFO", "FIXED-PRIORITY", "SAFETY-AWARE", "WarningGen"]
    cyc_us = []
    for stg in order:
        m = re.search(rf"^{re.escape(stg)}\s+(\d+)\s+(\d+)\s+[0-9.]+\s+([0-9.]+)", txt, re.M)
        cyc_us.append(int(m.group(1)) / 1000.0)
    mt = re.search(r"^TOTAL_COMPUTE\s+(\d+)\s+\d+\s+[0-9.]+\s+([0-9.]+)\s+([0-9.]+)", txt, re.M)
    me = re.search(r"Exiting @ tick (\d+)", txt)
    return cyc_us, float(mt.group(2)), float(mt.group(3)), int(me.group(1)) // 1000

stages = ["SensorIn", "Fusion", "Danger", "FIFO", "Fixed", "Safety", "Warning"]
tim_c, tim_tot_us, tim_ipc, prof_exit_c = parse_prof_stdout("prof_timing")
min_c, min_tot_us, min_ipc, _           = parse_prof_stdout("prof_minor")
prof_printf_c = load_stat_val("prof_timing", r"system\.cpu\.numCycles\s+(\d+)")

fig, (p1, p2) = plt.subplots(1, 2, figsize=(7.4, 3.2), gridspec_kw={"width_ratios": [1.3, 1.0]})
xi = np.arange(len(stages))
w = 0.36
p1.bar(xi - w/2, tim_c, w, color="#3B69A8", edgecolor="#222", lw=0.45, label=f"TimingSimple ({tim_tot_us:.1f} µs, IPC {tim_ipc:.3f})")
p1.bar(xi + w/2, min_c, w, color="#2E8B57", edgecolor="#222", lw=0.45, label=f"MinorCPU ({min_tot_us:.1f} µs, IPC {min_ipc:.3f})")
p1.set_xticks(xi)
p1.set_xticklabels(stages, fontsize=7.2)
p1.set_ylabel("Simulated compute time (µs @ 1 GHz)", fontsize=8.2)
p1.set_title("(a) Isolated stage compute (rdcycle)", fontsize=8.7, fontweight="bold")
p1.legend(fontsize=6.9, frameon=False, loc="upper left")
p1.grid(axis="y", ls=":", alpha=0.35)
p1.set_axisbelow(True)

# Panel (b): Stacked full-run reconciliation in millions of cycles
runs = ["prof_timing\n(m5ops)", "Quiet 100%\n(main)", "Quiet 400%\n(main)", "Verbose 100%\n(main)"]
c_m = tim_tot_us / 1000.0
q4_delta = (demo_s4_c - demo_q1_c) / 1e6
v1_delta = (demo_v1_c - demo_q1_c) / 1e6
p_pr_m = prof_printf_c / 1e6
p_init_m = (prof_exit_c / 1e6) - c_m - p_pr_m
comp_m = np.array([c_m, c_m, c_m + q4_delta, c_m])
rt_m   = np.array([p_init_m, demo_q1_c/1e6 - c_m, demo_s4_c/1e6 - (c_m + q4_delta), demo_q1_c/1e6 - c_m])
verb_m = np.array([p_pr_m, 0.000, 0.000, v1_delta])
xr = np.arange(len(runs))
p2.bar(xr, comp_m, 0.52, color="#2E8B57", edgecolor="#222", lw=0.45, label="Compute / queue logic")
p2.bar(xr, rt_m,   0.52, bottom=comp_m, color="#95A5A6", edgecolor="#222", lw=0.45, label="Summary I/O + glibc runtime")
p2.bar(xr, verb_m, 0.52, bottom=comp_m+rt_m, color="#D9822B", edgecolor="#222", lw=0.45, label="11-line (prof) / 190-line verbose")
tots = [prof_exit_c/1e6, demo_q1_c/1e6, demo_s4_c/1e6, demo_v1_c/1e6]
for i, tv in enumerate(tots):
    p2.text(i, tv + 0.07, f"{tv:.2f}M", ha="center", va="bottom", fontsize=7.4, fontweight="bold")
p2.set_xticks(xr)
p2.set_xticklabels(runs, fontsize=7.0)
p2.set_ylim(0, 4.25)
p2.set_ylabel("Total cycles (millions @ 1 GHz)", fontsize=8.2)
p2.set_title("(b) Full-binary cycle reconciliation", fontsize=8.7, fontweight="bold")
p2.legend(fontsize=6.6, frameon=False, loc="upper left")
p2.grid(axis="y", ls=":", alpha=0.35)
p2.set_axisbelow(True)
for a in (p1, p2):
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
fig.tight_layout()
save(fig, "fig_gem5_profile.png")

# ---------------------------------------------------------------------------
# Method flow & System architecture & Danger flow
# ---------------------------------------------------------------------------
def box_fn(ax, x, y, w, h, t, fc, fs=6.8):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec="#333", lw=0.9))
    ax.text(x + w/2, y + h/2, t, ha="center", va="center", fontsize=fs, linespacing=1.3)

fig, ax = plt.subplots(figsize=(3.4, 5.0))
ax.set_xlim(0, 100); ax.set_ylim(0, 150); ax.axis("off")
steps = [
    ("Set events, seed, load", "#EEEEEE"),
    ("Build C program\n(static, RISC-V gcc)", "#DCE6F5"),
    ("Generate sensor frames\n(6 scenes inc. STANDING)", "#DCE6F5"),
    ("Fuse sensors (normalized)\n+ stopping-dist zones", "#DDEFD9"),
    ("Scale arrival times\nby the load factor", "#FCEBC2"),
    ("Run 7 scheduling policies\non identical event streams", "#E6DDF2"),
    ("Profile per-stage cycles\non gem5 (m5ops + rdcycle)", "#F6CFCB"),
    ("100 seeds x 13 loads\n& Holm / CI evaluation", "#EEEEEE"),
]
y = 136
for i, (t, c) in enumerate(steps):
    box_fn(ax, 10, y, 80, 11, t, c)
    if i < len(steps) - 1:
        ax.add_patch(FancyArrowPatch((50, y - 0.5), (50, y - 6.5), arrowstyle="-|>", mutation_scale=9, lw=1.1, color="#222"))
    y -= 18
save(fig, "fig_method_flow.png")

fig, ax = plt.subplots(figsize=(8.2, 3.1))
ax.set_xlim(0, 100); ax.set_ylim(0, 42); ax.axis("off")
arch_boxes = [
    (1.5, 11, 17.5, 27, "Sensor Input", "Ultrasonic 0-400 cm\nProximity 3-150 cm\nMotion 0-100\n6 scenes (w/ STANDING)\nxorshift, fixed seed", "#DCE6F5"),
    (21.5, 11, 17.5, 27, "Sensor Fusion", "Scores 0-100\nNormalized 35/25/40\nCross-check penalties\nStationary dual check\nChild present?", "#DDEFD9"),
    (41.5, 11, 17.5, 27, "Danger Detection", "SAFE (risk 0-34)\nWARNING <= 300 cm\nCRITICAL <= crit_cm\nStopping-dist rule\nRisk score 0-100", "#FCEBC2"),
    (61.5, 11, 17.5, 27, "Priority Scheduler", "FIFO / Fixed-Sensor\nSafety-aware / Zone\nEDF / Preemptive\nAging after 250 ms", "#E6DDF2"),
    (81.5, 11, 17.0, 27, "Warning System", "Driver alert\nV2V/C-V2X text\nProcessing log\nPolicy summary", "#F6CFCB"),
]
for bx, by, bw, bh, title, body, fc in arch_boxes:
    ax.add_patch(FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0.3,rounding_size=1.2", fc=fc, ec="#222", lw=1.0))
    ax.text(bx + bw/2, by + bh - 4.0, title, ha="center", va="center", fontsize=7.4, fontweight="bold")
    ax.text(bx + bw/2, by + (bh - 5.5)/2, body, ha="center", va="center", fontsize=5.8, linespacing=1.45)
labels = ["SensorFrame", "FusionResult", "DangerResult", "SchedEvent"]
for i, lbl in enumerate(labels):
    x0 = arch_boxes[i][0] + arch_boxes[i][2] + 0.35
    x1 = arch_boxes[i+1][0] - 0.35
    ax.add_patch(FancyArrowPatch((x0, 24.5), (x1, 24.5), arrowstyle="-|>", mutation_scale=8, lw=1.0, color="#222"))
    ax.text((x0 + x1)/2, 8.2, lbl, ha="center", va="center", fontsize=6.0, style="italic")
ax.add_patch(FancyBboxPatch((1.5, 1.5), 97, 4.5, boxstyle="round,pad=0.2,rounding_size=0.9", fc="#EEEEEE", ec="#222", lw=0.9))
ax.text(50, 3.75, "C controller compiled static for RISC-V (rv64gc) and profiled per stage with m5ops/rdcycle in gem5 SE mode",
        ha="center", va="center", fontsize=6.8)
save(fig, "fig_system_arch.png")

fig, ax = plt.subplots(figsize=(3.6, 4.7))
ax.set_xlim(0, 100); ax.set_ylim(0, 138); ax.axis("off")
def fbox(x, y, w, h, t, fc, fs=6.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.35,rounding_size=1.2", fc=fc, ec="#222", lw=0.9))
    ax.text(x + w/2, y + h/2, t, ha="center", va="center", fontsize=fs, linespacing=1.3)

fbox(8,  119, 50, 14, "Fused result\n(confidence, distance,\nboth_close)", "#DCE6F5")
fbox(4,  89,  58, 19, "Child present?\nconf >= 40 and\n(motion >= 20 or both_close)", "#EEEEEE")
fbox(74, 91,  22, 15, "SAFE\nrisk 0-34", "#DDEFD9")
fbox(4,  58,  58, 21, "Distance <= crit_cm?\n(100 cm base; 150-220 cm\nstopping distance / door)", "#EEEEEE")
fbox(74, 61,  22, 15, "CRITICAL\nrisk 70-100", "#F6CFCB")
fbox(4,  29,  58, 17, "Distance <= 300 cm?\n(300 cm warning perimeter)", "#EEEEEE")
fbox(74, 30,  22, 15, "WARNING\nrisk 35-69", "#FCEBC2")
fbox(8,  3,   50, 14, "SAFE\nrisk 0-34", "#DDEFD9")

for (x0, y0, x1, y1, lbl, lx, ly) in [
    (33, 118.5, 33, 108.5, "", 0, 0),
    (62.5, 98.5, 73.5, 98.5, "no", 68, 102.5),
    (33, 88.5, 33, 79.5, "yes", 38.5, 84.0),
    (62.5, 68.5, 73.5, 68.5, "yes", 68, 72.5),
    (33, 57.5, 33, 46.5, "no", 38.5, 52.0),
    (62.5, 37.5, 73.5, 37.5, "yes", 68, 41.5),
    (33, 28.5, 33, 17.5, "no", 38.5, 23.0),
]:
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=8.5, lw=1.0, color="#222"))
    if lbl:
        ax.text(lx, ly, lbl, ha="center", va="center", fontsize=6.4)
save(fig, "fig_danger_flow.png")

print("All publication figures generated cleanly.")
