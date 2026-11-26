"""Figures generated from program logs (results/*.csv). Run from experiments_extra/."""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, FancyBboxPatch, FancyArrowPatch
from scipy import stats

plt.rcParams["font.family"] = "DejaVu Serif"
R = "results/"
OUT = "../figures/"
COL = {"FIFO": "#4C78B5", "FIXED-SENSOR": "#B5574C", "SAFETY-AWARE": "#3E9B5A",
       "ZONE-FIFO": "#E08A2B", "P-ZONE-FIFO": "#555555"}

def save(fig, name):
    fig.savefig(OUT + name, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

# 1. Confidence per event, seed 2024 (auto-annotated from seed2024.csv)
s = pd.read_csv(R + "seed2024.csv")
zc = {"SAFE": "#8FCB9B", "WARNING": "#F2C45A", "CRITICAL": "#E07B72"}
fig, ax = plt.subplots(figsize=(7.2, 3.0))
ax.bar(s.id, s.conf, color=[zc[z] for z in s.zone], edgecolor="#333", lw=0.5)
ax.axhline(40, color="#333", ls="--", lw=1)
ax.text(39.6, 42, "detection limit 40", ha="right", fontsize=7)
box = dict(boxstyle="round,pad=0.2", fc="white", ec="#999", lw=0.5)

fp_rows = s[(s.det == "YES") & (s.tru == "no") & (s.scene == "NOISE")]
if len(fp_rows):
    r0 = fp_rows.iloc[0]
    ax.annotate(f"event {int(r0.id)}: false positive\n(noise spike)",
                xy=(r0.id, r0.conf), xytext=(max(1.0, r0.id - 10), 104),
                fontsize=7, bbox=box, arrowprops=dict(arrowstyle="->", lw=0.8))

fn_rows = s[(s.det == "no") & (s.tru == "YES")]
if len(fn_rows):
    r1 = fn_rows.iloc[-1]
    ax.annotate(f"event {int(r1.id)}: missed child\n({int(r1.dist)} cm, conf. {int(r1.conf)})",
                xy=(r1.id, r1.conf), xytext=(min(30.5, r1.id - 4), 76),
                fontsize=7, bbox=box, arrowprops=dict(arrowstyle="->", lw=0.8))

ax.set_xlabel("Event ID (seed 2024)", fontsize=8)
ax.set_ylabel("Fused confidence", fontsize=8)
ax.set_ylim(0, 125)
ax.set_xticks(range(0, 40, 2))
ax.tick_params(labelsize=7)
ax.legend(handles=[Patch(fc=zc[k], ec="#333", label=k) for k in zc],
          fontsize=7, loc="upper left", ncol=3, frameon=False)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
save(fig, "fig_confidence40.png")

# 2. Latency per event (100%) and critical events at 400%
fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 5.0), gridspec_kw={"height_ratios": [1.1, 1]})
for k, c, m in [("fifo100", COL["FIFO"], "o"), ("fixed100", COL["FIXED-SENSOR"], "s"), ("sa100", COL["SAFETY-AWARE"], "^")]:
    a1.plot(s.id, s[k], "-" + m, ms=3, lw=1.0, color=c,
            label={"fifo100": "FIFO", "fixed100": "Fixed (sensor)", "sa100": "Safety-aware"}[k])
a1.axhline(40, color="#B22222", ls="--", lw=0.8, alpha=0.7)
a1.set_ylabel("Latency (ms), load 100 %", fontsize=8)
a1.set_xlabel("Event ID (seed 2024)", fontsize=8)
a1.legend(fontsize=7, frameon=False, ncol=3, loc="upper left")
a1.tick_params(labelsize=7)
a1.set_ylim(0, max(45, s[["fifo100", "fixed100", "sa100"]].max().max() + 8))

crit = s[s.zone == "CRITICAL"].reset_index(drop=True)
x = np.arange(len(crit))
w = 0.27
for j, (k, c, lab) in enumerate([("fifo400", COL["FIFO"], "FIFO"), ("fixed400", COL["FIXED-SENSOR"], "Fixed (sensor)"), ("sa400", COL["SAFETY-AWARE"], "Safety-aware")]):
    a2.bar(x + (j - 1) * w, crit[k], w, color=c, edgecolor="#333", lw=0.4, label=lab)
a2.axhline(40, color="#B22222", ls="--", lw=1)
a2.text(len(crit) - 0.5, 42, "critical deadline 40 ms", ha="right", fontsize=7, color="#B22222")
a2.set_xticks(x)
a2.set_xticklabels(crit.id, fontsize=6.5)
a2.set_xlabel("Critical event ID (seed 2024)", fontsize=8)
a2.set_ylabel("Latency (ms), load 400 %", fontsize=8)
a2.tick_params(labelsize=7)
a2.legend(fontsize=7, frameon=False, ncol=3, loc="upper left")
for a in (a1, a2):
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
fig.tight_layout()
save(fig, "fig_latency40.png")

# 3. Critical miss ratio vs load (100 seeds) with finer knee points
d = pd.read_csv(R + "sweep.csv")
d = d[d.seed != 2024]
d["crit_ratio"] = d.crit_miss / d.crit_n.replace(0, np.nan)
fig, ax = plt.subplots(figsize=(7.2, 3.1))
loads = sorted(d.load.unique())
for pol in ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "P-ZONE-FIFO"]:
    g = d[d.policy == pol]
    m, h = [], []
    for L in loads:
        x_val = g[g.load == L].crit_ratio.dropna()
        m.append(x_val.mean())
        h.append(stats.t.ppf(.975, len(x_val) - 1) * x_val.std(ddof=1) / np.sqrt(len(x_val)))
    m, h = np.array(m), np.array(h)
    ax.plot(loads, m, "-o", ms=3, lw=1.2, color=COL[pol],
            label={"FIXED-SENSOR": "Fixed (sensor)", "SAFETY-AWARE": "Safety-aware",
                   "ZONE-FIFO": "Zone, then arrival", "P-ZONE-FIFO": "Preemptive zone, then arrival"}.get(pol, pol))
    ax.fill_between(loads, np.clip(m - h, 0, 1), np.clip(m + h, 0, 1), color=COL[pol], alpha=0.15, lw=0)
ax.set_xlabel("Load (arrival rate, % of nominal)", fontsize=8)
ax.set_ylabel("Critical deadline-miss ratio", fontsize=8)
ax.set_ylim(0, 0.95)
ax.tick_params(labelsize=7)
ax.legend(fontsize=7, frameon=False, loc="upper left")
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
save(fig, "fig_crit_vs_load.png")

# 4. Miss ratio by zone at 200% and 400%
d["warn_ratio"] = d.warn_miss / d.warn_n.replace(0, np.nan)
d["safe_ratio"] = d.safe_miss / d.safe_n.replace(0, np.nan)
pols = ["FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "P-ZONE-FIFO"]
fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
for ax, L in zip(axs, [200, 400]):
    w = 0.16
    for j, pol in enumerate(pols):
        g = d[(d.load == L) & (d.policy == pol)]
        vals = [g.crit_ratio.mean(), g.warn_ratio.mean(), g.safe_ratio.mean()]
        ax.bar(np.arange(3) + (j - 2) * w, vals, w, color=COL[pol], edgecolor="#333", lw=0.4)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["Critical", "Warning", "Safe"], fontsize=7)
    ax.set_title("Load %d %%" % L, fontsize=8)
    ax.tick_params(labelsize=7)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
axs[0].set_ylabel("Mean deadline-miss ratio", fontsize=8)
axs[1].legend(handles=[Patch(fc=COL[p], ec="#333", label=l) for p, l in zip(pols, ["FIFO", "Fixed (sensor)", "Safety-aware", "Zone, then arrival", "Preemptive zone"])],
              fontsize=6.5, frameon=False, loc="upper right")
fig.tight_layout()
save(fig, "fig_tradeoff.png")

# 5. Method flow
def box_fn(ax, x, y, w, h, t, fc, fs=6.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec="#333", lw=0.9))
    ax.text(x + w/2, y + h/2, t, ha="center", va="center", fontsize=fs, linespacing=1.3)

fig, ax = plt.subplots(figsize=(3.4, 5.0))
ax.set_xlim(0, 100); ax.set_ylim(0, 150); ax.axis("off")
steps = [
    ("Set events, seed, load", "#EEEEEE"),
    ("Build C program\n(static, RISC-V gcc)", "#DCE6F5"),
    ("Generate sensor frames\n(6 scenes inc. STANDING)", "#DCE6F5"),
    ("Fuse sensors (w/ stationary\ncheck) + stopping-dist zones", "#DDEFD9"),
    ("Scale arrival times\nby the load factor", "#FCEBC2"),
    ("Run 7 scheduling policies\non identical event streams", "#E6DDF2"),
    ("Profile per-stage cycles\non gem5 (m5ops + rdcycle)", "#F6CFCB"),
    ("Repeat 100 seeds x 13 loads\n& weight sensitivity check", "#EEEEEE"),
]
y = 136
for i, (t, c) in enumerate(steps):
    box_fn(ax, 10, y, 80, 11, t, c)
    if i < len(steps) - 1:
        ax.add_patch(FancyArrowPatch((50, y - 0.5), (50, y - 6.5), arrowstyle="-|>", mutation_scale=9, lw=1.1, color="#222"))
    y -= 18
save(fig, "fig_method_flow.png")
print("All figures generated cleanly.")
