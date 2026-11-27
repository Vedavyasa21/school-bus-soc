"""Publication-grade figures generated directly from program logs and gem5 stats.
Run from experiments_extra/."""
import os
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, FancyBboxPatch, FancyArrowPatch
from scipy import stats

plt.rcParams["font.family"] = "DejaVu Serif"
plt.rcParams["axes.linewidth"] = 0.9

R = "results/"
GEM5_R = "../experiments/results/"
OUT = "../figures/"
os.makedirs(OUT, exist_ok=True)

COL = {
    "FIFO": "#3B69A8",
    "FIXED-SENSOR": "#B54A42",
    "SAFETY-AWARE": "#2E8B57",
    "ZONE-FIFO": "#D9822B",
    "P-ZONE-FIFO": "#4A4A4A",
    "EDF": "#7D3C98",
}

def save(fig, name):
    fig.savefig(OUT + name, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ---------------------------------------------------------------------------
# Architecture & Methodology Flow Diagrams (updated: no 220 cm clamp!)
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
    ("Scale arrival times + 25 ms\ntrack coalescing option", "#FCEBC2"),
    ("Run 9 scheduling policies\n(raw N=40, 1000 & 50 MHz CPU)", "#E6DDF2"),
    ("Profile single-pipeline cycles\nin gem5 (m5ops + rdcycle)", "#F6CFCB"),
    ("100 seeds x 13 loads\n& m=52 Holm / 200-MC eval.", "#EEEEEE"),
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
    (41.5, 11, 17.5, 27, "Danger Detection", "SAFE (risk 0-34)\nWARNING <= 300 cm\nCRITICAL <= crit_cm\nmax(150, 100+d_stop)\nRisk score 0-100", "#FCEBC2"),
    (61.5, 11, 17.5, 27, "Priority Scheduler", "FIFO / Fixed / SA\n2x2 Risk x Aging\nZone / EDF / Preempt\n25 ms track coalescing", "#E6DDF2"),
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
ax.text(50, 3.75, "C controller compiled static for RISC-V (rv64gc) and profiled per stage (single pipeline & 3-policy) in gem5 SE mode",
        ha="center", va="center", fontsize=6.7)
save(fig, "fig_system_arch.png")

fig, ax = plt.subplots(figsize=(3.6, 4.7))
ax.set_xlim(0, 100); ax.set_ylim(0, 138); ax.axis("off")
def fbox(x, y, w, h, t, fc, fs=6.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.35,rounding_size=1.2", fc=fc, ec="#222", lw=0.9))
    ax.text(x + w/2, y + h/2, t, ha="center", va="center", fontsize=fs, linespacing=1.3)

fbox(8,  119, 50, 14, "Fused result\n(confidence, distance,\nboth_close)", "#DCE6F5")
fbox(4,  89,  58, 19, "Child present?\nconf >= 40 and\n(motion >= 20 or both_close)", "#EEEEEE")
fbox(74, 91,  22, 15, "SAFE\nrisk 0-34", "#DDEFD9")
fbox(4,  58,  58, 21, "Distance <= crit_cm?\nmax(150, 100 + d_stop)\n(up to 439 cm @ 15 km/h)", "#EEEEEE")
fbox(74, 61,  22, 15, "CRITICAL\nrisk 70-100", "#F6CFCB")
fbox(4,  29,  58, 17, "Distance <= 300 cm?\n(min crossing perimeter;\ncapped below crit_cm)", "#EEEEEE")
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

fig, ax = plt.subplots(figsize=(3.6, 4.85))
ax.set_xlim(0, 100); ax.set_ylim(0, 146); ax.axis("off")
def gbox(x, y, w, h, t, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec="#222", lw=0.9))
    ax.text(x + w/2, y + h/2, t, ha="center", va="center", fontsize=6.6, linespacing=1.35)
def garr(x0, y0, x1, y1):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=8.5, lw=1.0, color="#222"))

gbox(12, 129, 76, 12, "Static RISC-V binary\n(rv64gc, lp64d)", "#E2E6EC")
gbox(12, 105, 76, 13, "CPU model, 1 GHz ref\nTimingSimple / Minor (50 MHz scale)", "#DCE6F5")
gbox(4,  78,  41, 15, "L1 I-cache\n32 KiB, 4-way", "#DDEFD9")
gbox(55, 78,  41, 15, "L1 D-cache\n32 KiB, 4-way", "#DDEFD9")
gbox(12, 54,  76, 11, "L2 bus (crossbar)", "#F2EFE4")
gbox(18, 30,  64, 13, "L2 cache\n256 KiB, 8-way", "#DDEFD9")
gbox(12, 16,  76,  8, "System bus (crossbar)", "#F2EFE4")
gbox(12,  1,  76,  9, "Memory controller\nDDR3-1600, 512 MiB", "#FCEBC2")
garr(50, 128.5, 50, 118.5)
garr(34, 104.5, 25,  93.5)
garr(66, 104.5, 75,  93.5)
garr(25,  77.5, 36,  65.5)
garr(75,  77.5, 64,  65.5)
garr(50,  53.5, 50,  43.5)
garr(50,  29.5, 50,  24.5)
garr(50,  15.5, 50,  10.5)
save(fig, "fig_gem5_arch.png")

# ---------------------------------------------------------------------------
# Stage 1 Seed-2024 Detection & Distance Envelope (with updated crit_cm)
# ---------------------------------------------------------------------------
s = pd.read_csv(R + "seed2024.csv")
fr = pd.read_csv(R + "frames.csv")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.1), gridspec_kw={"width_ratios": [1.35, 1.0]})
for z, c, mk in [("SAFE", "#3E9B5A", "o"), ("WARNING", "#D9822B", "s"), ("CRITICAL", "#C0392B", "^")]:
    sub = s[s.zone == z]
    ax1.scatter(sub.id, sub.dist, c=c, marker=mk, s=28, edgecolors="#222", lw=0.5, label=f"{z} ({len(sub)})")
for _, r in s[(s.det == "YES") & (s.tru == "no")].iterrows():
    ax1.scatter([r.id], [r.dist], s=85, facecolors="none", edgecolors="#8E44AD", lw=1.4)
for _, r in s[(s.det == "no") & (s.tru == "YES")].iterrows():
    ax1.scatter([r.id], [r.dist], s=85, facecolors="none", edgecolors="#000", lw=1.4, ls="--")
ax1.axhline(150, color="#555", ls=":", lw=1.0, label="Prox. max (150 cm)")
ax1.axhline(300, color="#D9822B", ls="--", lw=1.0, label="Warning limit (300 cm)")
ax1.annotate("Ev.20 NOISE FP", xy=(20, 71), xytext=(4.0, 20), fontsize=7.0,
             bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#8E44AD", lw=0.5),
             arrowprops=dict(arrowstyle="->", lw=0.7, color="#8E44AD"))
ax1.annotate("Ev.28/37 FN", xy=(28, 285), xytext=(28.5, 428), fontsize=7.0,
             bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#222", lw=0.5),
             arrowprops=dict(arrowstyle="->", lw=0.7, color="#222"))
ax1.set_xlabel("Event ID (seed 2024)", fontsize=8.4)
ax1.set_ylabel("Estimated distance (cm)", fontsize=8.4)
ax1.set_title("(b) Seed 2024 classification & errors", fontsize=8.8, fontweight="bold")
ax1.set_ylim(0, 520)
ax1.tick_params(labelsize=7.5)
ax1.legend(fontsize=6.6, ncol=2, frameon=False, loc="upper left")
ax1.grid(axis="y", ls=":", alpha=0.35)

scenes = ["APPROACH", "CROSSING", "STANDING", "OBSTACLE", "NOISE", "IDLE"]
short_sc = ["Appr.", "Cross.", "Stand.", "Obst.", "Noise", "Idle"]
tp_c = [len(fr[(fr.scene == sc) & (fr.present == 1) & (fr.truth == 1)]) for sc in scenes]
fn_c = [len(fr[(fr.scene == sc) & (fr.present == 0) & (fr.truth == 1)]) for sc in scenes]
fp_c = [len(fr[(fr.scene == sc) & (fr.present == 1) & (fr.truth == 0)]) for sc in scenes]
tn_c = [len(fr[(fr.scene == sc) & (fr.present == 0) & (fr.truth == 0)]) for sc in scenes]
xi = np.arange(len(scenes))
ax2.bar(xi, tp_c, color="#3E9B5A", edgecolor="#222", lw=0.45, label=f"TP ({sum(tp_c):,})")
ax2.bar(xi, fn_c, bottom=tp_c, color="#E67E22", edgecolor="#222", lw=0.45, label=f"FN ({sum(fn_c):,})")
ax2.bar(xi, tn_c, bottom=np.array(tp_c)+np.array(fn_c), color="#7FB3D5", edgecolor="#222", lw=0.45, label=f"TN ({sum(tn_c):,})")
ax2.bar(xi, fp_c, bottom=np.array(tp_c)+np.array(fn_c)+np.array(tn_c), color="#8E44AD", edgecolor="#222", lw=0.45, label=f"FP ({sum(fp_c):,})")
ax2.set_xticks(xi)
ax2.set_xticklabels(short_sc, fontsize=7.5)
ax2.set_ylabel("Frames (n = 4,000, 100 seeds)", fontsize=8.4)
ax2.set_title("(c) Detection outcomes by scene", fontsize=8.8, fontweight="bold")
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
# Confidence per event, seed 2024
# ---------------------------------------------------------------------------
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
    ax.annotate(f"Event {int(r0.id)}: NOISE FP\n(dist {int(r0.dist)} cm, conf {int(r0.conf)})",
                xy=(r0.id, r0.conf + 1), xytext=(11.2, 109),
                fontsize=7.6, bbox=box, arrowprops=dict(arrowstyle="->", lw=0.9, color="#222"))
fn_rows = s[(s.det == "no") & (s.tru == "YES")]
if len(fn_rows):
    r1 = fn_rows.iloc[-1]
    ax.annotate(f"Event {int(r1.id)}: missed child FN\n({int(r1.dist)} cm, conf {int(r1.conf)})",
                xy=(r1.id, r1.conf + 1), xytext=(28.8, 92),
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
# NEW Fig: Fusion Rule ROC Sweep & 200-MC Random Weight Distribution
# ---------------------------------------------------------------------------
roc = pd.read_csv(R + "fusion_roc.csv")
mc = pd.read_csv(R + "sensitivity_mc.csv")
fig, (f1, f2) = plt.subplots(1, 2, figsize=(7.4, 3.05), gridspec_kw={"width_ratios": [1.22, 1.0]})
rule_styles = [
    ("Weighted+both_close", "#2E8B57", "-o", "Weighted+both_close"),
    ("2-of-3 voting",       "#3B69A8", "--s", "2-of-3 voting"),
    ("Max-of-sensors",      "#D9822B", ":^",  "Max-of-sensors"),
    ("Weighted-motion-only","#B54A42", "-.D", "Weighted-motion-only"),
    ("AND-fusion",          "#7D3C98", ":v",  "AND-fusion"),
]
for rname, col, fmt, lbl in rule_styles:
    sub = roc[roc.rule == rname].sort_values("threshold")
    f1.plot(sub.fpr, sub.recall, fmt, ms=3.5, lw=1.35, color=col, label=lbl)
    pt40 = sub[sub.threshold == 40].iloc[0]
    f1.scatter([pt40.fpr], [pt40.recall], s=58, facecolors="none", edgecolors="#111", lw=1.2, zorder=6)
f1.plot([0, 0.65], [0, 0.65], "--", color="#AAA", lw=0.8)
f1.annotate("T=40\n(0.150, 0.853)", xy=(0.1496, 0.8526), xytext=(0.24, 0.68),
            fontsize=6.9, bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="#2E8B57", lw=0.6),
            arrowprops=dict(arrowstyle="->", lw=0.8, color="#2E8B57"))
f1.set_xlabel("False positive rate (FPR)", fontsize=8.4)
f1.set_ylabel("True positive rate (Recall)", fontsize=8.4)
f1.set_title("(a) Fusion rules across thresholds (T=25..65)", fontsize=8.5, fontweight="bold")
f1.set_xlim(-0.02, 0.63); f1.set_ylim(0.14, 1.04)
f1.tick_params(labelsize=7.5)
f1.grid(True, ls=":", alpha=0.35)
f1.legend(fontsize=6.6, frameon=False, loc="lower right")

bp = f2.boxplot([mc.precision, mc.recall, mc.accuracy, mc.f1],
                tick_labels=["Precision", "Recall", "Accuracy", "F1 score"],
                patch_artist=True, widths=0.45,
                medianprops=dict(color="#111", lw=1.3),
                flierprops=dict(marker=".", ms=3.5, alpha=0.5))
for patch, col in zip(bp["boxes"], ["#3B69A8", "#2E8B57", "#D9822B", "#7D3C98"]):
    patch.set_facecolor(col); patch.set_alpha(0.65)
f2.set_ylabel("Metric score (4,000 frames)", fontsize=8.4)
f2.set_title("(b) 200 MC +/-20% simultaneous weight draws", fontsize=8.5, fontweight="bold")
f2.set_ylim(0.73, 0.94)
f2.tick_params(labelsize=7.5)
f2.grid(axis="y", ls=":", alpha=0.35)
for a in (f1, f2):
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
fig.tight_layout()
save(fig, "fig_fusion_roc.png")

# ---------------------------------------------------------------------------
# Seed 2024 Latency per event (100%) and critical events at 400%
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
a2.set_xticklabels(crit.id, fontsize=7.0)
a2.set_xlabel("Critical event ID (seed 2024)", fontsize=8.8)
a2.set_ylabel("Latency (ms), 400% load", fontsize=8.8)
a2.set_ylim(0, max(230, crit[["fifo400", "fixed400", "sa400"]].max().max() + 26))
a2.tick_params(labelsize=7.6)
a2.legend(fontsize=7.6, frameon=False, ncol=4, loc="upper left")
a2.grid(axis="y", ls=":", alpha=0.35)
a2.set_axisbelow(True)
for a in (a1, a2):
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
fig.tight_layout()
save(fig, "fig_latency40.png")

# ---------------------------------------------------------------------------
# Seed 2024 Overload Summary (RAW vs 25 ms Coalesced) & gem5 Config
# ---------------------------------------------------------------------------
sw_all = pd.read_csv(R + "sweep_all.csv")
s24_r = sw_all[(sw_all["mode"] == "RAW_40") & (sw_all["seed"] == 2024)]
s24_c = sw_all[(sw_all["mode"] == "COAL_40") & (sw_all["seed"] == 2024)]
fig, (b1, b2) = plt.subplots(1, 2, figsize=(7.4, 3.0), gridspec_kw={"width_ratios": [1.35, 1.0]})
pol_list = ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "P-EDF"]
pol_labs = ["FIFO", "Fixed", "Safety-\nAware", "Zone-\nFIFO", "P-EDF"]
r0_s24 = s24_r[(s24_r.load == 400) & (s24_r.policy == "FIFO")].iloc[0]
crit_n_24, warn_n_24, rho_400_24 = int(r0_s24.crit_n), int(r0_s24.warn_n), float(r0_s24.rho)
crit400 = [s24_r[(s24_r.load == 400) & (s24_r.policy == p)].iloc[0].crit_miss for p in pol_list]
warn400 = [s24_r[(s24_r.load == 400) & (s24_r.policy == p)].iloc[0].warn_miss for p in pol_list]
coal400 = [s24_c[(s24_c.load == 400) & (s24_c.policy == p)].iloc[0].crit_miss for p in pol_list]
xi = np.arange(len(pol_list))
w = 0.28
r1 = b1.bar(xi - w, crit400, w, color="#C0392B", edgecolor="#222", lw=0.5, label=f"Raw critical (of {crit_n_24})")
r2 = b1.bar(xi,     warn400, w, color="#E08A2B", edgecolor="#222", lw=0.5, label=f"Raw warning (of {warn_n_24})")
r3 = b1.bar(xi + w, coal400, w, color="#2E8B57", edgecolor="#222", lw=0.5, label="Coalesced critical (0/3)")
for bar in list(r1) + list(r2) + list(r3):
    h = bar.get_height()
    b1.text(bar.get_x() + bar.get_width()/2, h + 0.3, f"{int(h)}", ha="center", va="bottom", fontsize=6.8)
b1.set_xticks(xi); b1.set_xticklabels(pol_labs, fontsize=7.5)
b1.set_ylim(0, max(crit400) + 8.0)
b1.set_ylabel("Missed deadlines (seed 2024)", fontsize=8.3)
b1.set_title(f"(a) Seed 2024 400% misses (raw rho={rho_400_24:.2f})", fontsize=8.4, fontweight="bold")
b1.legend(fontsize=6.9, frameon=False, loc="upper left")
b1.grid(axis="y", ls=":", alpha=0.35); b1.set_axisbelow(True)
for sp in ("top", "right"): b1.spines[sp].set_visible(False)

def _stat_c(name, pat):
    txt = open(GEM5_R + name + "/stats.txt", encoding="utf-8", errors="ignore").read()
    last = txt.split("---------- Begin Simulation Statistics ----------")[-1]
    return int(re.search(pat, last).group(1))

_v1_c = _stat_c("demo_timing", r"system\.cpu\.numCycles\s+(\d+)")
_q1_c = _stat_c("demo_quiet100", r"system\.cpu\.numCycles\s+(\d+)")
_s4_c = _stat_c("demo_stress", r"system\.cpu\.numCycles\s+(\d+)")
b2.axis("off")
b2.set_title("(b) gem5 RISC-V SE Configuration", fontsize=8.6, fontweight="bold")
cfg_txt = (
    "Simulator  : gem5 v25.1.0.1 (SE mode)\n"
    "Target ISA : RISC-V 64 (rv64gc / lp64d)\n"
    "Compiler   : riscv64-linux-gnu-gcc -O2 -static\n"
    "CPU Models : TimingSimpleCPU & MinorCPU\n"
    "Ref Clock  : 1 GHz (plus 50 MHz embedded scale)\n"
    "L1 Caches  : 32 KiB I / 32 KiB D (4-way, 2 cyc)\n"
    "L2 Cache   : 256 KiB shared (8-way, 20 cyc)\n"
    "Memory     : 512 MiB DDR3-1600\n"
    f"Exit Tick  : {_v1_c*1000:,} (verbose 100%)\n"
    f"             {_q1_c*1000:,} (quiet 100%)\n"
    f"             {_s4_c*1000:,} (quiet 400%)"
)
b2.add_patch(FancyBboxPatch((0.03, 0.04), 0.94, 0.90, boxstyle="round,pad=0.025,rounding_size=0.035",
                            fc="#F7F9FC", ec="#445", lw=0.9, transform=b2.transAxes))
b2.text(0.06, 0.49, cfg_txt, transform=b2.transAxes, va="center", ha="left",
        family="DejaVu Sans Mono", fontsize=5.85, linespacing=1.40, color="#111")
fig.tight_layout()
save(fig, "fig_seed2024_summary.png")

# ---------------------------------------------------------------------------
# Steady-State LONG_RAW (N=1,000) Critical Miss Curve + Coalescing/Ablation
# ---------------------------------------------------------------------------
d_lr = sw_all[(sw_all["mode"] == "LONG_RAW") & (sw_all["seed"] != 2024)].copy()
d_lc = sw_all[(sw_all["mode"] == "LONG_COAL") & (sw_all["seed"] != 2024)].copy()
for dd in (d_lr, d_lc):
    dd["cr"] = dd.crit_miss / dd.crit_n.replace(0, np.nan)
    dd["wr"] = dd.warn_miss / dd.warn_n.replace(0, np.nan)
    dd["sr"] = dd.safe_miss / dd.safe_n.replace(0, np.nan)

fig, (c1, c2) = plt.subplots(1, 2, figsize=(7.4, 3.15), gridspec_kw={"width_ratios": [1.18, 1.0]})
loads = sorted(d_lr.load.unique())
for pol, lab in [
    ("FIFO", "FIFO"), ("FIXED-SENSOR", "Fixed (sensor)"),
    ("SAFETY-AWARE", "Safety-aware"), ("ZONE-FIFO", "Zone, then arrival"),
    ("P-ZONE-FIFO", "Preemptive zone"), ("EDF", "EDF"),
]:
    g = d_lr[d_lr.policy == pol]
    m, h = [], []
    for L in loads:
        xv = g[g.load == L].cr.dropna()
        m.append(xv.mean())
        h.append(stats.t.ppf(0.975, len(xv) - 1) * xv.std(ddof=1) / np.sqrt(len(xv)))
    m, h = np.array(m), np.array(h)
    ls = "--" if pol == "EDF" else "-"
    c1.plot(loads, m, ls + "o", ms=2.8, lw=1.3, color=COL[pol], label=lab)
    c1.fill_between(loads, np.clip(m - h, 0, 1), np.clip(m + h, 0, 1), color=COL[pol], alpha=0.14, lw=0)
c1.set_xlabel("Offered arrival scale (% of nominal)", fontsize=8.3)
c1.set_ylabel("Critical deadline-miss ratio", fontsize=8.3)
c1.set_title("(a) Steady-state raw stream (N=1,000, 100 seeds)", fontsize=8.3, fontweight="bold")
c1.set_ylim(-0.02, 1.05)
c1.tick_params(labelsize=7.5); c1.grid(True, ls=":", alpha=0.35)
c1.legend(fontsize=6.4, frameon=True, facecolor="white", edgecolor="#DDD", framealpha=0.92, loc="lower right", ncol=1)

# Panel (b): 25 ms Coalesced LONG_COAL at 50..400% + CPU50 reference
for pol, lab, col in [
    ("FIFO", "FIFO (coalesced)", COL["FIFO"]),
    ("EDF", "EDF (coalesced)", COL["EDF"]),
    ("FIXED-SENSOR", "Fixed (coalesced)", COL["FIXED-SENSOR"]),
    ("SAFETY-AWARE", "Safety-aware (coal.)", COL["SAFETY-AWARE"]),
    ("ZONE-FIFO", "Zone-FIFO (coal.)", COL["ZONE-FIFO"]),
]:
    g = d_lc[d_lc.policy == pol]
    m = [g[g.load == L].cr.mean() for L in loads]
    c2.plot(loads, m, "-o", ms=2.8, lw=1.35, color=col, label=lab)
c2.axhline(0.0, color="#2E8B57", ls=":", lw=0.8)
c2.set_xlabel("Offered arrival scale (% of nominal)", fontsize=8.3)
c2.set_ylabel("Critical miss ratio (25 ms coalesced)", fontsize=8.3)
c2.set_title("(b) 25 ms track coalescing (N=1,000 frames)", fontsize=8.3, fontweight="bold")
c2.set_ylim(-0.03, 0.88)
c2.tick_params(labelsize=7.5); c2.grid(True, ls=":", alpha=0.35)
c2.legend(fontsize=6.6, frameon=False, loc="upper left")
for a in (c1, c2):
    for sp in ("top", "right"): a.spines[sp].set_visible(False)
fig.tight_layout()
save(fig, "fig_crit_vs_load.png")

# ---------------------------------------------------------------------------
# Steady-State LONG_RAW Miss Ratio by Zone at 200% and 400%
# ---------------------------------------------------------------------------
pols = ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "P-ZONE-FIFO"]
fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.1), sharey=True)
for ax, L in zip(axs, [200, 400]):
    w = 0.16
    for j, pol in enumerate(pols):
        g = d_lr[(d_lr.load == L) & (d_lr.policy == pol)]
        vals = [g.cr.mean(), g.wr.mean(), g.sr.mean()]
        ax.bar(np.arange(3) + (j - 2) * w, vals, w, color=COL[pol], edgecolor="#333", lw=0.45)
    ax.set_xticks(range(3)); ax.set_xticklabels(["Critical", "Warning", "Safe"], fontsize=8.2)
    ax.set_title(f"Steady-State Load {L}% (N=1,000)", fontsize=8.8, fontweight="bold")
    ax.tick_params(labelsize=7.8); ax.grid(axis="y", ls=":", alpha=0.35); ax.set_axisbelow(True)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
axs[0].set_ylabel("Mean deadline-miss ratio", fontsize=8.8)
axs[1].legend(
    handles=[Patch(fc=COL[p], ec="#333", label=l)
             for p, l in zip(pols, ["FIFO", "Fixed (sensor)", "Safety-aware", "Zone, then arrival", "Preemptive zone"])],
    fontsize=7.3, frameon=True, facecolor="white", edgecolor="#DDD", loc="upper center",
    bbox_to_anchor=(-0.08, -0.15), ncol=5, framealpha=0.95,
)
fig.tight_layout()
save(fig, "fig_tradeoff.png")

# ---------------------------------------------------------------------------
# Per-Stage Compute Profile (Single-Pipeline vs 3-Policy) & Full Reconciliation
# ---------------------------------------------------------------------------
def load_stat_val(name, pat):
    txt = open(GEM5_R + name + "/stats.txt", encoding="utf-8", errors="ignore").read()
    last = txt.split("---------- Begin Simulation Statistics ----------")[-1]
    return int(re.search(pat, last).group(1))

demo_v1_c = load_stat_val("demo_timing", r"system\.cpu\.numCycles\s+(\d+)")
demo_q1_c = load_stat_val("demo_quiet100", r"system\.cpu\.numCycles\s+(\d+)")
demo_s4_c = load_stat_val("demo_stress", r"system\.cpu\.numCycles\s+(\d+)")
prof_printf_c = load_stat_val("prof_timing", r"system\.cpu\.numCycles\s+(\d+)")

def parse_prof_stdout(name):
    txt = open(GEM5_R + name + "/stdout.txt", encoding="utf-8", errors="ignore").read()
    order = ["SensorInput", "SensorFusion", "DangerDetect", "FIFO", "FIXED-PRIORITY", "SAFETY-AWARE", "WarningGen"]
    cyc_us = []
    for stg in order:
        m = re.search(rf"^{re.escape(stg)}\s+(\d+)\s+(\d+)\s+[0-9.]+\s+([0-9.]+)", txt, re.M)
        cyc_us.append(int(m.group(1)) / 1000.0)
    mt = re.search(r"^TOTAL_COMPUTE\s+(\d+)\s+\d+\s+[0-9.]+\s+([0-9.]+)\s+([0-9.]+)", txt, re.M)
    ms = re.search(r"^SINGLE_SAFETY-AWARE\s+(\d+)\s+\d+\s+[0-9.]+\s+([0-9.]+)\s+([0-9.]+)", txt, re.M)
    me = re.search(r"Exiting @ tick (\d+)", txt)
    return cyc_us, float(mt.group(2)), float(mt.group(3)), float(ms.group(2)), float(ms.group(3)), int(me.group(1)) // 1000

stages = ["SensorIn", "Fusion", "Danger", "FIFO", "Fixed", "Safety", "Warning"]
tim_c, tim_tot_us, tim_ipc, tim_sa_us, tim_sa_ipc, prof_exit_c = parse_prof_stdout("prof_timing")
min_c, min_tot_us, min_ipc, min_sa_us, min_sa_ipc, _           = parse_prof_stdout("prof_minor")

fig, (p1, p2) = plt.subplots(1, 2, figsize=(7.4, 3.2), gridspec_kw={"width_ratios": [1.3, 1.0]})
xi = np.arange(len(stages)); w = 0.36
p1.bar(xi - w/2, tim_c, w, color="#3B69A8", edgecolor="#222", lw=0.45,
       label=f"TimingSimple (1-pipe SA: {tim_sa_us:.1f} us)")
p1.bar(xi + w/2, min_c, w, color="#2E8B57", edgecolor="#222", lw=0.45,
       label=f"MinorCPU (1-pipe SA: {min_sa_us:.1f} us)")
p1.set_xticks(xi); p1.set_xticklabels(stages, fontsize=7.2)
p1.set_ylabel("Simulated compute time (us @ 1 GHz)", fontsize=8.2)
p1.set_title("(a) Isolated stage compute (rdcycle)", fontsize=8.7, fontweight="bold")
p1.legend(fontsize=6.7, frameon=False, loc="upper left")
p1.grid(axis="y", ls=":", alpha=0.35); p1.set_axisbelow(True)

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
p2.bar(xr, verb_m, 0.52, bottom=comp_m+rt_m, color="#D9822B", edgecolor="#222", lw=0.45, label="15-line (prof) / verbose stdout")
tots = [prof_exit_c/1e6, demo_q1_c/1e6, demo_s4_c/1e6, demo_v1_c/1e6]
for i, tv in enumerate(tots):
    p2.text(i, tv + 0.07, f"{tv:.2f}M", ha="center", va="bottom", fontsize=7.4, fontweight="bold")
p2.set_xticks(xr); p2.set_xticklabels(runs, fontsize=7.0); p2.set_ylim(0, 4.25)
p2.set_ylabel("Total cycles (millions @ 1 GHz)", fontsize=8.2)
p2.set_title("(b) Full-binary cycle reconciliation", fontsize=8.7, fontweight="bold")
p2.legend(fontsize=6.5, frameon=False, loc="upper left")
p2.grid(axis="y", ls=":", alpha=0.35); p2.set_axisbelow(True)
for a in (p1, p2):
    for sp in ("top", "right"): a.spines[sp].set_visible(False)
fig.tight_layout()
save(fig, "fig_gem5_profile.png")

print("All publication figures generated cleanly.")
