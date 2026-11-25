"""Cross-session / cross-subject (factor 7), gray1 control, permutation tests (factor 9)."""
import sys, time, warnings
sys.path.insert(0, "/home/claude/scripts"); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from joblib import Parallel, delayed
import rgb_pipeline as rp

z = np.load("/home/claude/work/epochs.npz", allow_pickle=True)
meta = pd.DataFrame({k: z[k] for k in ["color", "subject", "session", "block", "phase", "contact_bad"]})
clean = (z["ptp"].max(1) < 150) & ~meta.contact_bad.values & (meta.session.values != "P001_1119")
P = rp.pipelines(250.0)
PRIMARY = "F2a ERP(O1,O2)+sLDA"           # pre-specified, theory-driven (occipital VEP)
rows = []
log = lambda *a: print(*a, flush=True)


def data(phase_prefix, subj=None):
    m = clean & meta.phase.str.startswith(phase_prefix).values
    if subj: m &= (meta.subject == subj).values
    return z["X"][m].astype(float), meta[m].reset_index(drop=True)


# ---- A. cross-session (leave-one-session-out), with / without EA
log("\n=== A. cross-session (train on other days, test on a new day)")
for subj in ["P002", "P003", "P001"]:
    X, M = data("obs", subj); y, ses = M.color.values, M.session.values
    Xea = rp.apply_ea_per_group(X, ses)
    for name in ["F2a ERP(O1,O2)+sLDA", "F2a ERP(4ch)+sLDA", "F2c xDAWN-TS+LR"]:
        for tag, XX in [("raw", X), ("EA", Xea)]:
            ba, pf, _ = rp.evaluate(P[name], XX, y, ses)
            rows.append(dict(analysis="cross-session", subject=subj, pipeline=name, variant=tag, bacc=ba, n=len(y)))
            log(f"  {subj} {name:24s} {tag:3s} bAcc={ba:.3f} per-session={np.round(pf, 2)}")

# ---- B. cross-subject (leave-one-subject-out), with / without EA per session
log("\n=== B. cross-subject (train on others, test on unseen person)")
X, M = data("obs"); y, sub, ses = M.color.values, M.subject.values, M.session.values
Xea = rp.apply_ea_per_group(X, ses)
for name in ["F2a ERP(O1,O2)+sLDA", "F2a ERP(4ch)+sLDA", "F2c xDAWN-TS+LR"]:
    for tag, XX in [("raw", X), ("EA", Xea)]:
        ba, pf, _ = rp.evaluate(P[name], XX, y, sub)
        rows.append(dict(analysis="cross-subject", subject="all", pipeline=name, variant=tag, bacc=ba, n=len(y)))
        log(f"  {name:24s} {tag:3s} bAcc={ba:.3f} per-subject={dict(zip(np.unique(sub), np.round(pf, 2)))}")

# ---- C. gray1 control: grey screen BEFORE the colour, labelled with the upcoming colour -> must be chance
log("\n=== C. gray1 control (no colour on screen; should be chance)")
for subj in ["P002", "P003", "P08"]:
    X, M = data("gray1", subj); y, g, ses = M.color.values, M.block.values, M.session.values
    for name, XX in [(PRIMARY, X), ("F7 EA + ERP(4ch)+sLDA", rp.apply_ea_per_group(X, ses))]:
        pipe = P["F2a ERP(4ch)+sLDA"] if name.startswith("F7") else P[name]
        ba, pf, _ = rp.evaluate(pipe, XX, y, g)
        rows.append(dict(analysis="gray1-control", subject=subj, pipeline=name, variant="", bacc=ba, n=len(y)))
        log(f"  {subj} {name:26s} bAcc={ba:.3f} (n={len(y)}, chance95={rp.binomial_chance(len(y),3):.3f})")
pd.DataFrame(rows).to_csv("/home/claude/work/results_extra.csv", index=False)

# ---- D. permutation tests (labels shuffled within block; full outer CV each time)
log("\n=== D. permutation tests (200 perms, within-block shuffles)")
def perm_once(pipe, X, y, g, seed):
    rng = np.random.default_rng(seed); yp = y.copy()
    for b in np.unique(g):
        i = np.where(g == b)[0]; yp[i] = rng.permutation(yp[i])
    return rp.evaluate(pipe, X, yp, g)[0]

tests = [("P002", PRIMARY, False), ("P003", PRIMARY, False), ("P08", PRIMARY, False), ("P001", PRIMARY, False),
         ("P003", "F2a ERP(4ch)+sLDA", True), ("P002", "F2a ERP(4ch)+sLDA", True)]
for extra in sys.argv[1:]:   # "SUBJ|PIPELINE|EA"
    s, pn, ea = extra.split("|"); tests.append((s, pn, ea == "EA"))
prow = []
for subj, name, ea in tests:
    X, M = data("obs", subj); y, g, ses = M.color.values, M.block.values, M.session.values
    if ea: X = rp.apply_ea_per_group(X, ses)
    obs_score = rp.evaluate(P[name], X, y, g)[0]
    t0 = time.time()
    null = np.array(Parallel(n_jobs=2)(delayed(perm_once)(P[name], X, y, g, s) for s in range(200)))
    p = (np.sum(null >= obs_score) + 1) / 201
    prow.append(dict(subject=subj, pipeline=("EA + " if ea else "") + name, bacc=obs_score, null_mean=null.mean(),
                     null_95=np.quantile(null, 0.95), p=p, n=len(y)))
    log(f"  {subj} {('EA + ' if ea else '') + name:30s} bAcc={obs_score:.3f} null mean={null.mean():.3f} "
        f"null95={np.quantile(null, .95):.3f} p={p:.3f}  ({time.time()-t0:.0f}s)")
    pd.DataFrame(prow).to_csv("/home/claude/work/results_perm.csv", index=False)
