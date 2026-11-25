import sys, time, warnings; sys.path.insert(0, "/home/claude/scripts")
warnings.filterwarnings("ignore")
import numpy as np
from ba_io import load_db
import rgb_pipeline as rp

r = load_db(sys.argv[1], workdir="/home/claude/work")
x = rp.preprocess_continuous(r["eeg"], r["sfreq"]); t = r["t"]; sf = r["sfreq"]
print("filtered std per ch (uV):", x.std(1).round(1))
rng = np.random.default_rng(42)
onsets = t[0] + 5 + np.cumsum(rng.uniform(1.2, 1.6, 900)); onsets = onsets[onsets < t[-1] - 5]
labels = np.array(["R", "G", "B"])[rng.permutation(np.arange(len(onsets)) % 3)]
groups_all = np.digitize(onsets, np.quantile(onsets, [0.2, 0.4, 0.6, 0.8]))   # 5 pseudo-sessions

def inject(x, amp):
    x = x.copy(); tt = np.arange(int(0.6*sf))/sf
    n1 = -np.exp(-((tt-0.10)/0.02)**2); p1 = np.exp(-((tt-0.16)/0.03)**2)
    gain = {"R": (1.0, 0.2), "G": (0.5, 0.6), "B": (0.0, 1.0)}
    for on, lab in zip(onsets, labels):
        k = np.searchsorted(t, on); a, b = gain[lab]
        wave = amp*(a*n1 + b*p1)
        x[:2, k:k+len(tt)] += wave   # O1, O2 only
    return x

for cond, amp in [("NULL (no signal)", 0.0), ("INJECTED (3 uV)", 3.0)]:
    xx = inject(x, amp)
    X, y, keep, why = rp.epoch(xx, t, sf, onsets, labels, contact=r["contact"], ptp_uv=150)
    g = groups_all[keep]
    print(f"\n=== {cond}: epochs {len(y)} kept, rejected {why}, chance95={rp.binomial_chance(len(y),3):.3f}")
    P = rp.pipelines(sf)
    names = ["F2a ERP(4ch)+sLDA", "F2c xDAWN-TS+LR", "F6 nested-tuned ERP+sLDA", "F8a soft-voting(ERP,TS,BP)"]
    for n in names:
        t0 = time.time(); ba, pf, _ = rp.evaluate(P[n], X, y, g)
        print(f"  {n:32s} bAcc={ba:.3f}  folds={np.round(pf,2)}  ({time.time()-t0:.0f}s)")
    s, perm, p = rp.permutation_p(P["F2a ERP(4ch)+sLDA"], X, y, g, n_perm=100)
    print(f"  permutation (sLDA): score={s:.3f} null mean={perm.mean():.3f} p={p:.3f}")
