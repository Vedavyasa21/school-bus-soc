"""Builds the tables used in the paper from results/*.csv -> tables.json"""
import json, numpy as np, pandas as pd
from scipy import stats

d0 = pd.read_csv('results/sweep.csv')
d = d0[d0.seed != 2024].copy()
d['cr'] = d.crit_miss / d.crit_n.replace(0, np.nan)
d['wr'] = d.warn_miss / d.warn_n.replace(0, np.nan)
d['sr'] = d.safe_miss / d.safe_n.replace(0, np.nan)
d['ar'] = (d.crit_miss + d.warn_miss + d.safe_miss) / (d.crit_n + d.warn_n + d.safe_n)
d['ca'] = d.crit_sum / d.crit_n.replace(0, np.nan)
d['wa'] = d.warn_sum / d.warn_n.replace(0, np.nan)
d['sa'] = d.safe_sum / d.safe_n.replace(0, np.nan)

def mci(x):
    x = x.dropna()
    return x.mean(), stats.t.ppf(.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))

NAMES = {
    'FIFO': 'FIFO',
    'FIXED-SENSOR': 'Fixed (sensor)',
    'SAFETY-AWARE': 'Safety-aware',
    'ZONE-FIFO': 'Zone, then arrival',
    'EDF': 'EDF',
    'P-ZONE-FIFO': 'Preemptive zone',
    'P-EDF': 'Preemptive EDF'
}
ORDER = list(NAMES)
out = {}
loads = [100, 150, 200, 300, 400]
out['t_crit'] = [['Policy'] + ['%d %%' % L for L in loads]] + [
    [NAMES[p]] + ['%.3f ± %.3f' % mci(d[(d.load == L) & (d.policy == p)].cr) for L in loads] for p in ORDER
]

for key, L in [('t_zone400', 400), ('t_zone100', 100)]:
    rows = [['Policy', 'Crit. miss', 'Warn. miss', 'All miss', 'Crit. avg (ms)', 'Warn. avg (ms)', 'Safe avg (ms)', 'Crit. worst (ms)']]
    for p in ORDER:
        g = d[(d.load == L) & (d.policy == p)]
        rows.append([NAMES[p], '%.3f' % g.cr.mean(), '%.3f' % g.wr.mean(), '%.3f' % g.ar.mean(),
                     '%.1f' % g.ca.mean(), '%.1f' % g.wa.mean(), '%.1f' % g.sa.mean(), '%d' % g.crit_max.max()])
    out[key] = rows

pe = d[d.policy == 'P-EDF'].copy()
pe['anym'] = pe.crit_miss + pe.warn_miss + pe.safe_miss
rows = [['Load', 'Offered load', 'Seeds feasible', 'Seeds with no critical miss']]
for L in sorted(d.load.unique()):
    g = pe[pe.load == L]
    rows.append(['%d %%' % L, '%.2f' % g.rho.mean(), '%d / 100' % (g.anym == 0).sum(), '%d / 100' % (g.crit_miss == 0).sum()])
out['t_feas'] = rows

det = pd.read_csv('results/det.csv', header=None, names=['tag', 'seed', 'tp', 'fp', 'fn', 'tn'])
a = det[det.seed != 2024]
b = det[det.seed == 2024]
def drow(lbl, t):
    TP, FP, FN, TN = t.tp.sum(), t.fp.sum(), t.fn.sum(), t.tn.sum()
    return [lbl, str(TP), str(FP), str(FN), str(TN),
            '%.3f' % (TP / (TP + FP)), '%.3f' % (TP / (TP + FN)), '%.3f' % ((TP + TN) / (TP + FP + FN + TN))]
out['t_det'] = [['Data', 'TP', 'FP', 'FN', 'TN', 'Precision', 'Recall', 'Accuracy'], drow('100 seeds', a), drow('Seed 2024', b)]

sens = pd.read_csv('results/sensitivity.csv')
out['t_sens'] = [list(sens.columns)] + sens.values.tolist()

# Case study 2024 tables (100% and 400%)
for key, L in [('t_2024_100', 100), ('t_2024_400', 400)]:
    sub = d0[(d0.seed == 2024) & (d0.load == L)]
    rows = [['Policy', 'Avg all', 'Avg crit', 'Avg warn', 'Avg safe', 'Max crit', 'Crit miss', 'Warn miss', 'Safe miss', 'Total miss', 'Makespan']]
    for p in ['FIFO', 'FIXED-SENSOR', 'SAFETY-AWARE', 'ZONE-FIFO', 'EDF', 'P-ZONE-FIFO', 'P-EDF']:
        r = sub[sub.policy == p].iloc[0]
        tot_n = r.crit_n + r.warn_n + r.safe_n
        tot_m = r.crit_miss + r.warn_miss + r.safe_miss
        rows.append([NAMES[p], '%.2f' % (r.all_sum / tot_n), '%.2f' % (r.crit_sum / r.crit_n),
                     '%.2f' % (r.warn_sum / r.warn_n), '%.2f' % (r.safe_sum / r.safe_n),
                     '%d' % r.crit_max, '%d/%d' % (r.crit_miss, r.crit_n),
                     '%d/%d' % (r.warn_miss, r.warn_n), '%d/%d' % (r.safe_miss, r.safe_n),
                     '%d/%d' % (tot_m, tot_n), '%d' % r.makespan])
    out[key] = rows

txt = {}
for p in ORDER:
    for L in [100, 125, 150, 200, 400]:
        g = d[(d.load == L) & (d.policy == p)]
        m, h = mci(g.cr)
        txt['%s_%d' % (p, L)] = (round(m, 3), round(h, 3), int((g.crit_miss > 0).sum()), int(g.crit_max.max()))

def wil(L, p1, p2):
    x = d[(d.load == L) & (d.policy == p1)].set_index('seed').cr
    y = d[(d.load == L) & (d.policy == p2)].set_index('seed').cr
    k = x.dropna().index.intersection(y.dropna().index)
    x, y = x[k], y[k]
    if (x - y).abs().sum() == 0:
        return 'identical'
    return 'diff %.3f p=%.2g n=%d' % ((x - y).mean(), stats.wilcoxon(x, y).pvalue, len(x))

for L in [100, 150, 200, 300, 400]:
    for p1, p2 in [('SAFETY-AWARE', 'FIFO'), ('SAFETY-AWARE', 'FIXED-SENSOR'),
                   ('SAFETY-AWARE', 'ZONE-FIFO'), ('P-ZONE-FIFO', 'SAFETY-AWARE'), ('FIXED-SENSOR', 'FIFO')]:
        txt['W_%d_%s_vs_%s' % (L, p1, p2)] = wil(L, p1, p2)

json.dump({'tables': out, 'text': txt}, open('tables.json', 'w'), indent=1)
for k, v in txt.items(): print(k, v)
print("\nDONE tables.json")
