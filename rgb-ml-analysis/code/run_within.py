"""Within-subject comparison of all factor pipelines (leave-one-block-out)."""
import sys, time, warnings, json
sys.path.insert(0, "/home/claude/scripts"); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import rgb_pipeline as rp

z = np.load("/home/claude/work/epochs.npz", allow_pickle=True)
meta = pd.DataFrame({k: z[k] for k in ["color", "subject", "session", "block", "phase", "contact_bad"]})
keep = (z["ptp"].max(1) < 150) & ~meta.contact_bad.values & meta.phase.str.startswith("obs").values
keep &= meta.session.values != "P001_1119"           # only 2 clean trials
X_all, M = z["X"][keep].astype(float), meta[keep].reset_index(drop=True)
subjects = sys.argv[1].split(",") if len(sys.argv) > 1 else ["P002", "P003", "P08", "P001"]
rows = []
for subj in subjects:
    m = (M.subject == subj).values
    X, y, g, ses = X_all[m], M.color.values[m], M.block.values[m], M.session.values[m]
    print(f"\n##### {subj}: n={len(y)} blocks={len(np.unique(g))} sessions={len(np.unique(ses))} chance95={rp.binomial_chance(len(y),3):.3f}", flush=True)
    P = rp.pipelines(250.0)
    variants = list(P.items())
    Xea = rp.apply_ea_per_group(X, ses)
    for name in ["F2a ERP(4ch)+sLDA", "F2c xDAWN-TS+LR", "F2d sustained Cov-TS+LR"]:
        variants.append(("F7 EA + " + name.split(" ", 1)[1], ("EA", P[name])))
    for name, pipe in variants:
        t0 = time.time()
        if isinstance(pipe, tuple):
            ba, pf, pred = rp.evaluate(pipe[1], Xea, y, g)
        else:
            ba, pf, pred = rp.evaluate(pipe, X, y, g)
        rows.append(dict(subject=subj, pipeline=name, bacc=ba, fold_mean=pf.mean(), fold_sd=pf.std(), n=len(y),
                         chance95=rp.binomial_chance(len(y), 3), secs=time.time() - t0))
        print(f"  {name:34s} bAcc={ba:.3f}  (fold mean {pf.mean():.3f}±{pf.std():.3f})  {time.time()-t0:.0f}s", flush=True)
        pd.DataFrame(rows).to_csv(f"/home/claude/work/results_within_{'_'.join(subjects)}.csv", index=False)
