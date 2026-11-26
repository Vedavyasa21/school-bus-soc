import pandas as pd, numpy as np
from scipy import stats

d = pd.read_csv('results/sweep.csv')
d = d[d.seed != 2024]
d['crit_ratio'] = np.where(d.crit_n > 0, d.crit_miss / d.crit_n.replace(0, np.nan), np.nan)
d['warn_ratio'] = np.where(d.warn_n > 0, d.warn_miss / d.warn_n.replace(0, np.nan), np.nan)
d['safe_ratio'] = np.where(d.safe_n > 0, d.safe_miss / d.safe_n.replace(0, np.nan), np.nan)
d['all_ratio']  = (d.crit_miss + d.warn_miss + d.safe_miss) / (d.crit_n + d.warn_n + d.safe_n)
d['crit_avg'] = d.crit_sum / d.crit_n.replace(0, np.nan)
d['warn_avg'] = d.warn_sum / d.warn_n.replace(0, np.nan)
d['safe_avg'] = d.safe_sum / d.safe_n.replace(0, np.nan)
d['all_avg']  = d.all_sum / (d.crit_n + d.warn_n + d.safe_n)

def ci(x):
    x = x.dropna()
    m = x.mean()
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return m, h

rows = []
for (load, pol), g in d.groupby(['load', 'policy']):
    r = {'load': load, 'policy': pol, 'rho': g.rho.mean()}
    for c in ['crit_ratio', 'warn_ratio', 'safe_ratio', 'all_ratio', 'crit_avg', 'warn_avg', 'safe_avg', 'all_avg']:
        m, h = ci(g[c])
        r[c] = m
        r[c + '_ci'] = h
    r['crit_max_mean'] = g.crit_max.mean()
    r['crit_max_worst'] = g.crit_max.max()
    r['crit_zero_miss_seeds'] = int((g.crit_miss == 0).sum())
    rows.append(r)

S = pd.DataFrame(rows)
S.to_csv('results/summary.csv', index=False)
pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 30)

print("seeds with >=1 critical event:", d[(d.load == 100) & (d.policy == 'FIFO')].crit_n.gt(0).sum(),
      "mean crit events/seed:", d[(d.load == 100) & (d.policy == 'FIFO')].crit_n.mean().round(2))
print(S[S.load.isin([100, 125, 150, 200, 400])][
    ['load', 'policy', 'rho', 'crit_ratio', 'crit_ratio_ci', 'warn_ratio', 'safe_ratio',
     'all_ratio', 'crit_avg', 'warn_avg', 'safe_avg', 'crit_max_mean', 'crit_max_worst', 'crit_zero_miss_seeds']
].round(3).to_string())

print("\nWilcoxon paired tests on per-seed critical miss ratio")
for load in [150, 200, 300, 400]:
    for a, b in [('SAFETY-AWARE', 'FIFO'), ('SAFETY-AWARE', 'FIXED-SENSOR'),
                 ('SAFETY-AWARE', 'ZONE-FIFO'), ('P-ZONE-FIFO', 'SAFETY-AWARE')]:
        x = d[(d.load == load) & (d.policy == a)].set_index('seed').crit_ratio
        y = d[(d.load == load) & (d.policy == b)].set_index('seed').crit_ratio
        k = x.dropna().index.intersection(y.dropna().index)
        x, y = x[k], y[k]
        diff = x - y
        if (diff == 0).all():
            print(load, a, 'vs', b, 'identical')
            continue
        w = stats.wilcoxon(x, y)
        print(load, a, 'vs', b, 'mean diff %.3f' % diff.mean(), 'p=%.2g' % w.pvalue, 'n=%d' % len(x))

print("\nEDF identical to ZONE-FIFO? ",
      (d[d.policy == 'EDF'].reset_index(drop=True)[['crit_miss', 'warn_miss', 'safe_miss', 'crit_max', 'all_sum']] ==
       d[d.policy == 'ZONE-FIFO'].reset_index(drop=True)[['crit_miss', 'warn_miss', 'safe_miss', 'crit_max', 'all_sum']]).all().all())
print("P-EDF identical to P-ZONE? ",
      (d[d.policy == 'P-EDF'].reset_index(drop=True)[['crit_miss', 'warn_miss', 'safe_miss', 'crit_max', 'all_sum']] ==
       d[d.policy == 'P-ZONE-FIFO'].reset_index(drop=True)[['crit_miss', 'warn_miss', 'safe_miss', 'crit_max', 'all_sum']]).all().all())

pe = d[d.policy == 'P-EDF'].copy()
pe['any'] = pe.crit_miss + pe.warn_miss + pe.safe_miss
print("\nShare of seeds with zero misses under P-EDF (feasible):")
print(pe.groupby('load')['any'].apply(lambda x: (x == 0).mean()).round(2).to_string())
pe['crit_zero'] = pe.crit_miss == 0
print("Share of seeds with zero CRITICAL misses under P-EDF:")
print(pe.groupby('load')['crit_zero'].mean().round(2).to_string())

det = pd.read_csv('results/det.csv', header=None, names=['tag', 'seed', 'tp', 'fp', 'fn', 'tn'])
det = det[det.seed != 2024]
TP, FP, FN, TN = det.tp.sum(), det.fp.sum(), det.fn.sum(), det.tn.sum()
print("\nDetection over %d seeds x 40 frames: TP=%d FP=%d FN=%d TN=%d" % (len(det), TP, FP, FN, TN))
print("precision %.3f recall %.3f accuracy %.3f FPR %.3f FNR %.3f" %
      (TP / (TP + FP), TP / (TP + FN), (TP + TN) / (TP + FP + FN + TN), FP / (FP + TN), FN / (FN + TP)))

fr = pd.read_csv('results/frames.csv')
st = fr[fr.scene == 'STANDING']
print("\nSTANDING scene frames (100 seeds): total=%d detected(TP)=%d missed(FN)=%d recall=%.3f" %
      (len(st), int(st.present.sum()), int((st.present == 0).sum()), st.present.mean() if len(st) else 0.0))

sens = pd.read_csv('results/sensitivity.csv')
print("\nFusion sensitivity & stationary-rule ablation:")
print(sens.to_string(index=False))
