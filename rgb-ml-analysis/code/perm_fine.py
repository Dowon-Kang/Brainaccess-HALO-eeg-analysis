import sys, warnings; sys.path.insert(0, "/home/claude/scripts"); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from joblib import Parallel, delayed
import rgb_pipeline as rp
z = np.load("/home/claude/work/epochs.npz", allow_pickle=True)
meta = pd.DataFrame({k: z[k] for k in ["color", "subject", "session", "block", "phase", "contact_bad"]})
clean = (z["ptp"].max(1) < 150) & ~meta.contact_bad.values & (meta.session.values != "P001_1119") & meta.phase.str.startswith("obs").values
P = rp.pipelines(250.0)
def perm_once(pipe, X, y, g, seed):
    import warnings; warnings.filterwarnings("ignore")
    rng = np.random.default_rng(seed); yp = y.copy()
    for b in np.unique(g):
        i = np.where(g == b)[0]; yp[i] = rng.permutation(yp[i])
    return rp.evaluate(pipe, X, yp, g)[0]
rows = []
for subj, name, ea in [("P002", "F2a ERP(O1,O2)+sLDA", False), ("P003", "F2a ERP(O1,O2)+sLDA", False), ("P003", "F2a ERP(4ch)+sLDA", True)]:
    m = clean & (meta.subject == subj).values
    X, y, g, ses = z["X"][m].astype(float), meta.color.values[m], meta.block.values[m], meta.session.values[m]
    if ea: X = rp.apply_ea_per_group(X, ses)
    s = rp.evaluate(P[name], X, y, g)[0]
    null = np.array(Parallel(n_jobs=2)(delayed(perm_once)(P[name], X, y, g, k) for k in range(1000)))
    p = (np.sum(null >= s) + 1) / 1001; zsc = (s - null.mean()) / null.std()
    rows.append(dict(subject=subj, pipeline=("EA + " if ea else "") + name, bacc=s, null_mean=null.mean(), null_sd=null.std(), z=zsc, p_perm=p, p_bonf19=min(1, p * 19)))
    print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv("/home/claude/work/results_perm_fine.csv", index=False)
