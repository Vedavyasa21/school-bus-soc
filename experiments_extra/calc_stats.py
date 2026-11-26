import pandas as pd, numpy as np
from scipy import stats

det = pd.read_csv('results/det.csv', header=None, names=['tag','seed','tp','fp','fn','tn'])
det = det[det.seed != 2024].copy()
det['prec'] = det.tp / (det.tp + det.fp)
det['rec']  = det.tp / (det.tp + det.fn)
det['acc']  = (det.tp + det.tn) / (det.tp + det.fp + det.fn + det.tn)
det['f1']   = 2 * det.prec * det.rec / (det.prec + det.rec)
print('=== PER-SEED DETECTION (n=100 seeds) ===')
for col in ['prec', 'rec', 'acc', 'f1']:
    s = det[col].dropna()
    h = stats.t.ppf(0.975, len(s) - 1) * s.std(ddof=1) / np.sqrt(len(s))
    print(f'  {col}: mean={s.mean():.4f} +/- {h:.4f} (n={len(s)})')

d = pd.read_csv('results/sweep.csv')
d = d[d.seed != 2024].copy()
d['crit_ratio'] = d.crit_miss / d.crit_n
tests = []
for load in [100, 150, 200, 300, 400]:
    for a, b in [('SAFETY-AWARE', 'FIFO'), ('SAFETY-AWARE', 'FIXED-SENSOR'),
                 ('SAFETY-AWARE', 'ZONE-FIFO'), ('P-ZONE-FIFO', 'SAFETY-AWARE')]:
        x = d[(d.load == load) & (d.policy == a)].set_index('seed').crit_ratio
        y = d[(d.load == load) & (d.policy == b)].set_index('seed').crit_ratio
        w = stats.wilcoxon(x, y)
        tests.append((load, f'{a} vs {b}', (x - y).mean(), w.pvalue))
pvals = np.array([t[3] for t in tests])
order = np.argsort(pvals)
holm = np.empty_like(pvals)
rmax = 0.0
m = len(pvals)
for rank, idx in enumerate(order):
    rmax = max(rmax, min(1.0, pvals[idx] * (m - rank)))
    holm[idx] = rmax
print('\n=== WILCOXON + HOLM-BONFERRONI (m=20 tests) ===')
for t, hp in zip(tests, holm):
    print(f'  load={t[0]} {t[1]:30s} diff={t[2]:+.3f} raw_p={t[3]:.2e} holm_p={hp:.2e}')
