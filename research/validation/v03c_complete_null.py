"""V-03c  Completes V-03: the two stored pipelines V-03 left incomplete, on the SAME synthetic data sets.

Gap in V-03 (found by the report fact-check):
  * 'F7 EA + sustained Cov-TS+LR' (methods.csv 'EA + 지속반응') was not run at all -> only 18 of 19 stored pipelines;
  * 'F6 nested-tuned ERP+sLDA' was run on null reps 0-2 only (3 reps) for compute reasons.
Design: identical to V-03 (research/validation/_synth.py, 3 sessions x 180 obs trials, distinct schedules, groups =
        session x block, leave-one-block-out via rp.evaluate). Null data set for rep r is regenerated from
        np.random.default_rng(r) exactly as V-03 did, so scores are directly comparable/combinable with V-03.
          - EA + sustained Cov-TS+LR: null reps 0..19
          - F6 nested-tuned ERP+sLDA: null reps 3..19 (reps 0-2 already in V-03)
Warnings are NOT suppressed; they are counted per worker and written to warnings.log.
Usage : python v03c_complete_null.py [R_NULL]
"""
import collections
import os
import sys
import warnings

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

sys.path.insert(0, os.path.dirname(__file__))
import _synth as S  # noqa: E402
from _runlog import Run  # noqa: E402
import rgb_pipeline as rp  # noqa: E402

R_NULL = int(sys.argv[1]) if len(sys.argv) > 1 else 20
run = Run("V03c", "Complete V-03 null calibration: EA + sustained Cov-TS+LR (20 reps) and F6 nested (reps 3..19)",
          inputs=["rgb-ml-analysis/code/rgb_pipeline.py", "rgb-eeg-lab/scripts/protocol.py", "research/validation/_synth.py",
                  "research/validation/v03_synthetic_leakage.py", "reports/runs/V03/scores.csv"],
          config=dict(R_NULL=R_NULL, null_data_seed="np.random.default_rng(rep) (same as V-03 null)", subject="pid=2, 3 sessions, identical=False",
                      cv="rp.evaluate, groups = session x block (leave-one-block-out)", n_jobs=4))


def job(kind, rep):
    rec = collections.Counter()
    with warnings.catch_warnings(record=True) as wl:
        warnings.simplefilter("always")
        d = S.make_subject(np.random.default_rng(rep), pid=2, identical=False, colour_uv=0.0)
        X, y, g, ses = d["X"], d["y"], d["block"], d["session"]
        P = rp.pipelines(250.0)
        if kind == "F7 EA + sustained Cov-TS+LR":
            ba = rp.evaluate(P["F2d sustained Cov-TS+LR"], rp.apply_ea_per_group(X, ses), y, g)[0]
        else:
            ba = rp.evaluate(P["F6 nested-tuned ERP+sLDA"], X, y, g)[0]
    for w in wl:
        rec[(w.category.__name__, str(w.message).splitlines()[0][:300])] += 1
    return dict(condition="null", rep=rep, pipeline=kind, bacc=ba, n=len(y)), rec


jobs = [("F6 nested-tuned ERP+sLDA", r) for r in range(3, R_NULL)] + [("F7 EA + sustained Cov-TS+LR", r) for r in range(R_NULL)]
out = Parallel(n_jobs=4)(delayed(job)(*j) for j in jobs)
for _, rec in out:
    run.add_warnings(rec)
new = pd.DataFrame([r for r, _ in out])
v03 = pd.read_csv(os.path.join(S.ROOT, "reports", "runs", "V03", "scores.csv"), keep_default_na=False)
comb = pd.concat([v03[v03.condition == "null"], new], ignore_index=True)
run.shape("new_scores", new.shape)
run.shape("combined_null_scores", comb.shape)
for name, df in [("scores_new.csv", new), ("null_scores_combined_V03_V03c.csv", comb)]:
    fp = os.path.join(run.dir, name)
    df.to_csv(fp, index=False)
    run.output(fp)
summ = comb.groupby("pipeline").bacc.agg(["count", "mean", "std"]).reset_index()
summ["se"] = summ["std"] / np.sqrt(summ["count"])
summ["t_vs_1/3"] = (summ["mean"] - 1 / 3) / summ["se"]
summ = summ.sort_values("mean")
print(summ.round(4).to_string(index=False))
fp = os.path.join(run.dir, "null_summary_19_pipelines.csv")
summ.round(5).to_csv(fp, index=False)
run.output(fp)
run.metric("n_pipelines", int(len(summ)))
run.metric("null_mean_range", [round(float(summ["mean"].min()), 4), round(float(summ["mean"].max()), 4)])
run.metric("max_t_vs_1/3", round(float(summ["t_vs_1/3"].max()), 3))
run.metric("min_count", int(summ["count"].min()))
for _, r in summ.iterrows():
    run.metric(f"null_mean[{r.pipeline}]", round(float(r["mean"]), 4))
run.close()
