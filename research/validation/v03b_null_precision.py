"""V-03b  Follow-up of V-03: precise null bias and sensitivity for the two key ERP pipelines.

Why  : in V-03 (20 reps) the null means of 'F2a ERP(4ch)+sLDA' (0.3454, t=2.63) and 'F2a ERP(O1,O2)+sLDA'
       (0.3469, t=2.13) sat ~1.2-1.4 pp above 1/3, and the 1.5 uV sensitivity check (5 reps) was weak.
       More repetitions decide whether that offset is evaluation bias or chance.
Design: same generator/design as V-03 (3 sessions x 180 trials, distinct schedules, leave-one-block-out);
        null R_NULL reps; injected colour effect 1.5 and 3.0 uV, R_SIG reps each.
Usage : python v03b_null_precision.py [R_NULL] [R_SIG]
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import _synth as S  # noqa: E402
from _runlog import Run  # noqa: E402
import rgb_pipeline as rp  # noqa: E402

R_NULL = int(sys.argv[1]) if len(sys.argv) > 1 else 200
R_SIG = int(sys.argv[2]) if len(sys.argv) > 2 else 30
PIPES = ["F2a ERP(4ch)+sLDA", "F2a ERP(O1,O2)+sLDA"]
run = Run("V03b", "Precise null bias + sensitivity of the two key ERP pipelines (synthetic, leave-one-block-out)",
          inputs=["rgb-ml-analysis/code/rgb_pipeline.py", "rgb-eeg-lab/scripts/protocol.py", "research/validation/_synth.py"])
run.note(f"R_NULL={R_NULL}, R_SIG={R_SIG}; seeds 50_000+rep (null), 60_000/70_000+rep (signal) — disjoint from V-03")
P = rp.pipelines(250.0)
rows = []
for cond, amp, base, R in [("null", 0.0, 50_000, R_NULL), ("signal_1.5uV", 1.5, 60_000, R_SIG), ("signal_3.0uV", 3.0, 70_000, R_SIG)]:
    for rep in range(R):
        d = S.make_subject(np.random.default_rng(base + rep), pid=2, identical=False, colour_uv=amp)
        for n in PIPES:
            rows.append(dict(condition=cond, rep=rep, pipeline=n, bacc=rp.evaluate(P[n], d["X"], d["y"], d["block"])[0]))
df = pd.DataFrame(rows)
fp = os.path.join(run.dir, "scores.csv")
df.to_csv(fp, index=False)
run.output(fp)
run.shape("scores", df.shape)
summ = df.groupby(["condition", "pipeline"]).bacc.agg(["count", "mean", "std"]).reset_index()
summ["se"] = summ["std"] / np.sqrt(summ["count"])
summ["ci95_lo"] = summ["mean"] - 1.96 * summ["se"]
summ["ci95_hi"] = summ["mean"] + 1.96 * summ["se"]
summ["t_vs_1/3"] = (summ["mean"] - 1 / 3) / summ["se"]
summ["p_two_sided"] = 2 * (1 - stats.t.cdf(summ["t_vs_1/3"].abs(), summ["count"] - 1))
print(summ.round(4).to_string(index=False))
fp = os.path.join(run.dir, "summary.csv")
summ.round(5).to_csv(fp, index=False)
run.output(fp)
for _, r in summ.iterrows():
    run.metric(f"{r.condition}|{r.pipeline}|mean", round(float(r["mean"]), 4))
    run.metric(f"{r.condition}|{r.pipeline}|p_vs_1/3", round(float(r.p_two_sided), 4))
run.close()
