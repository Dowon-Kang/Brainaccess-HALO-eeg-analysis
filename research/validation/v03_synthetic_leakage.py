"""V-03  Leakage / calibration check of the stored pipelines (rgb-ml-analysis/code/rgb_pipeline.py) on SYNTHETIC data.

Question: when the EEG carries NO colour information, does each pipeline's leave-one-block-out balanced accuracy
          (exactly rp.evaluate with block groups, as in run_within.py) centre on 1/3?  And when a small colour effect
          is injected, do the pipelines detect it?
Design  : synthetic subject = 3 sessions x 180 obs trials (P002-sized, n = 540), 15 blocks, schedule from
          protocol.sequence_plan with DISTINCT seeds per session (no twin-schedule structure; that is V-04's topic).
          null:  colour_uv = 0           reps = R_NULL independent noise seeds
          signal: colour_uv = 1.5 uV      reps = R_SIG
Outputs : reports/runs/V03/scores.csv, summary.csv, reports/figures/V03_null_calibration.png
Usage   : python v03_synthetic_leakage.py [R_NULL] [R_SIG] [--skip-slow]
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import _synth as S  # noqa: E402
from _runlog import ROOT, Run  # noqa: E402
import rgb_pipeline as rp  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
R_NULL = int(args[0]) if len(args) > 0 else 20
R_SIG = int(args[1]) if len(args) > 1 else 5
SKIP_SLOW = "--skip-slow" in sys.argv
SLOW = {"F6 nested-tuned ERP+sLDA"}
run = Run("V03", "Null calibration + sensitivity of all 19 stored pipelines on synthetic data (leave-one-block-out)",
          inputs=["rgb-ml-analysis/code/rgb_pipeline.py", "rgb-eeg-lab/scripts/protocol.py", "research/validation/_synth.py"])
run.note(f"R_NULL={R_NULL}, R_SIG={R_SIG}, skip_slow={SKIP_SLOW}; synthetic data only, distinct schedules per session")


def names():
    P = rp.pipelines(250.0)
    out = [n for n in P if not (SKIP_SLOW and n in SLOW)]
    return out + ["F7 EA + ERP(4ch)+sLDA", "F7 EA + xDAWN-TS+LR"]


def one(cond, rep, colour_uv):
    import warnings as w
    w.filterwarnings("ignore")
    rng = np.random.default_rng(10_000 * (cond == "signal") + rep)
    d = S.make_subject(rng, pid=2, identical=False, colour_uv=colour_uv)
    X, y, g, ses = d["X"], d["y"], d["block"], d["session"]
    Xea = rp.apply_ea_per_group(X, ses)
    P = rp.pipelines(250.0)
    rows = []
    for n in names():
        if n.startswith("F7 EA + "):
            base = {"F7 EA + ERP(4ch)+sLDA": "F2a ERP(4ch)+sLDA", "F7 EA + xDAWN-TS+LR": "F2c xDAWN-TS+LR"}[n]
            ba = rp.evaluate(P[base], Xea, y, g)[0]
        elif n in SLOW and rep >= 3:
            continue                                          # slow pipeline: first 3 reps only
        else:
            ba = rp.evaluate(P[n], X, y, g)[0]
        rows.append(dict(condition=cond, rep=rep, pipeline=n, bacc=ba, n=len(y)))
    return rows


jobs = [("null", r, 0.0) for r in range(R_NULL)] + [("signal", r, 1.5) for r in range(R_SIG)]
res = Parallel(n_jobs=4, verbose=0)(delayed(one)(*j) for j in jobs)
df = pd.DataFrame([r for rows in res for r in rows])
run.shape("scores", df.shape)
fp = os.path.join(run.dir, "scores.csv")
df.to_csv(fp, index=False)
run.output(fp)

sd_iid = np.sqrt((1 / 3) * (2 / 3) / 540)
summ = df.groupby(["condition", "pipeline"]).bacc.agg(["count", "mean", "std", "min", "max"]).reset_index()
nul = summ[summ.condition == "null"].copy()
nul["t_vs_1/3"] = (nul["mean"] - 1 / 3) / (nul["std"] / np.sqrt(nul["count"]))
summ = summ.merge(nul[["pipeline", "t_vs_1/3"]], on="pipeline", how="left")
summ.loc[summ.condition != "null", "t_vs_1/3"] = np.nan
print(summ.round(4).to_string(index=False))
print(f"\niid binomial SD for n=540: {sd_iid:.4f}")
fp = os.path.join(run.dir, "summary.csv")
summ.round(5).to_csv(fp, index=False)
run.output(fp)
allnull = df[df.condition == "null"].bacc
run.metric("null_grand_mean_bacc", round(float(allnull.mean()), 4))
run.metric("null_max_pipeline_mean", round(float(nul["mean"].max()), 4))
run.metric("null_pipeline_with_max_mean", nul.loc[nul["mean"].idxmax(), "pipeline"])
run.metric("n_pipelines_null_mean_t_gt_3", int((nul["t_vs_1/3"] > 3).sum()))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

order = nul.sort_values("mean").pipeline.tolist()
fig, ax = plt.subplots(figsize=(9, 7))
for i, n in enumerate(order):
    v = df[(df.condition == "null") & (df.pipeline == n)].bacc * 100
    ax.scatter(v, np.full(len(v), i) + np.random.default_rng(i).uniform(-0.15, 0.15, len(v)), s=8, color="#777", alpha=0.6)
    ax.plot([v.mean()], [i], "o", color="#1f5fa8", ms=6)
    s = df[(df.condition == "signal") & (df.pipeline == n)].bacc * 100
    if len(s):
        ax.plot([s.mean()], [i], "D", color="#c0392b", ms=5)
ax.axvline(100 / 3, color="#333", ls="--", lw=0.8)
ax.axvspan(100 / 3 - 196 * sd_iid, 100 / 3 + 196 * sd_iid, color="#ccc", alpha=0.3, lw=0)
ax.set_yticks(range(len(order)))
ax.set_yticklabels(order, fontsize=7)
ax.set_xlabel("balanced accuracy (%), leave-one-block-out")
ax.set_title("V03 · Synthetic null calibration (grey dots = reps, blue = null mean) and 1.5 µV signal (red ◆)", fontsize=9)
fig.text(0.01, 0.01, "Synthetic data (research/validation/_synth.py), n=540 trials/rep, 15 blocks. Band = 1/3 ± 1.96·iid binomial SD. "
         "Not real EEG: shows pipeline behaviour, not study results.", fontsize=7)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fp = os.path.join(ROOT, "reports", "figures", "V03_null_calibration.png")
fig.savefig(fp, dpi=130)
run.output(fp)
run.close()
