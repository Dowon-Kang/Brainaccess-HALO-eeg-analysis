"""F-01  Regenerate report figures from stored run outputs (no recomputation of any result).

  V03_null_calibration.png  <- reports/runs/V03c/null_scores_combined_V03_V03c.csv + reports/runs/V03/scores.csv (signal)
  V04_schedule_confounds.png <- reports/runs/V04/B_summary.csv, C_perm.csv
Each figure carries experiment ID, data source, units/axis definitions, interpretation and limitations.
Usage: python make_figures.py [v03] [v04]   (default: both)
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
from _runlog import ROOT, Run  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

which = set(sys.argv[1:]) or {"v03", "v04"}
RUNS = os.path.join(ROOT, "reports", "runs")
FIG = os.path.join(ROOT, "reports", "figures")
inputs = []
if "v03" in which:
    inputs += ["reports/runs/V03c/null_scores_combined_V03_V03c.csv", "reports/runs/V03/scores.csv"]
if "v04" in which:
    inputs += ["reports/runs/V04/B_summary.csv", "reports/runs/V04/C_perm.csv"]
run = Run("F01", "Regenerate V-03 and V-04 figures from stored run outputs", inputs=inputs,
          modules=("numpy", "pandas", "scipy", "matplotlib"), config=dict(which=sorted(which)))


def cp_ci(k, n, a=0.05):
    lo = 0.0 if k == 0 else stats.beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - a / 2, k + 1, n - k)
    return lo, hi


if "v03" in which:
    null = pd.read_csv(os.path.join(RUNS, "V03c", "null_scores_combined_V03_V03c.csv"), keep_default_na=False)
    sig = pd.read_csv(os.path.join(RUNS, "V03", "scores.csv"), keep_default_na=False)
    sig = sig[sig.condition == "signal"]
    g = null.groupby("pipeline").bacc.agg(["count", "mean", "std"])
    g["se"] = g["std"] / np.sqrt(g["count"])
    order = g.sort_values("mean").index.tolist()
    sd_iid = np.sqrt((1 / 3) * (2 / 3) / 540)
    fig, ax = plt.subplots(figsize=(9.5, 7.8))
    ax.axvspan(100 / 3 - 196 * sd_iid, 100 / 3 + 196 * sd_iid, color="#ddd", alpha=0.6, lw=0, label="1/3 ± 1.96·iid binomial SD (n=540)")
    for i, n in enumerate(order):
        v = null[null.pipeline == n].bacc * 100
        ax.scatter(v, np.full(len(v), i) + np.random.default_rng(i).uniform(-0.15, 0.15, len(v)), s=7, color="#888", alpha=0.6, zorder=2)
        m, se = g.loc[n, "mean"] * 100, g.loc[n, "se"] * 100
        ax.errorbar(m, i, xerr=1.96 * se, fmt="o", color="#1f5fa8", ms=5, capsize=2, zorder=3)
        s = sig[sig.pipeline == n].bacc * 100
        if len(s):
            ax.plot(s.mean(), i, "D", color="#c0392b", ms=4.5, zorder=4)
    ax.axvline(100 / 3, color="#333", ls="--", lw=0.8)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{n}  (null n={int(g.loc[n, 'count'])})" for n in order], fontsize=7)
    ax.set_xlabel("balanced accuracy (%) — leave-one-block-out, 15 blocks, n = 540 trials per synthetic data set")
    ax.plot([], [], "o", color="#1f5fa8", label="null mean ± 95% CI (no colour information)")
    ax.plot([], [], "D", color="#c0392b", label="1.5 µV colour effect, mean of 5 reps (F6: 3)")
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.set_title("V-03 + V-03c · synthetic null calibration of all 19 stored pipelines", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.038, "Data: SYNTHETIC (research/validation/_synth.py), not real EEG — shows pipeline behaviour, not study results. "
             "Sources: reports/runs/V03, V03c. Null reps 0–19 share data sets across pipelines.", fontsize=6.5)
    fig.text(0.01, 0.022, "Interpretation: no pipeline's null mean exceeds 1/3 by more than 3 SE (no label leakage detected).", fontsize=6.5)
    fig.text(0.01, 0.006, "Limitations: the grey band assumes independent trials and is narrower than the real CV null spread (V-01, V-03b); "
             "the signal check is weak (5 reps).", fontsize=6.5)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fp = os.path.join(FIG, "V03_null_calibration.png")
    fig.savefig(fp, dpi=130)
    run.output(fp)
    run.metric("v03_pipelines_plotted", len(order))

if "v04" in which:
    B = pd.read_csv(os.path.join(RUNS, "V04", "B_summary.csv"))
    C = pd.read_csv(os.path.join(RUNS, "V04", "C_perm.csv"))
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4))
    ax = axes[0]
    lab = {"block": "block-within-session (stored)", "block_index": "block number across sessions (twin-aware)", "session": "leave-one-session-out"}
    col = {"block": "#c0392b", "block_index": "#1f5fa8", "session": "#2e7d32"}
    for j, sched in enumerate(["identical", "distinct"]):
        for k, gk in enumerate(["block", "block_index", "session"]):
            s = B[(B.schedule == sched) & (B.grouping == gk)]
            ax.errorbar(s.drift_amp + 0.03 * k + 1.4 * j, s["mean"] * 100, yerr=1.96 * s["std"] / np.sqrt(s["count"]) * 100,
                        fmt="o-", color=col[gk], ms=4, capsize=2, label=lab[gk] if j == 0 else None)
    ax.axhline(100 / 3, color="#333", ls="--", lw=0.8)
    ax.set_xticks([0, 0.5, 1.0, 1.4, 1.9, 2.4])
    ax.set_xticklabels(["0", "0.5", "1.0", "0", "0.5", "1.0"])
    ax.set_xlabel("drift_amp (dimensionless: fractional modulation of the onset-VEP amplitude over the session)\n"
                  "left three: identical schedules across 3 sessions | right three: distinct schedules", fontsize=8)
    ax.set_ylabel("mean balanced accuracy (%) ± 95% CI of the mean (30 reps)")
    ax.set_title("B · no colour signal: drift × schedule × CV grouping", fontsize=9)
    ax.legend(fontsize=7, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax = axes[1]
    kinds = ["trial_within_block", "sequence_within_block", "sequence_shared_schedule"]
    for k, dr in enumerate([0.0, 1.0]):
        for i, kd in enumerate(kinds):
            p = C[(C.drift_amp == dr) & (C.null_kind == kd)].p.values
            n, hit = len(p), int((p <= 0.05).sum())
            lo, hi = cp_ci(hit, n)
            x = i + 0.38 * k
            ax.bar(x, hit / n, width=0.36, color=["#999", "#c0392b"][k], label=f"drift_amp = {dr}" if i == 0 else None)
            ax.errorbar(x, hit / n, yerr=[[hit / n - lo], [hi - hit / n]], color="#222", capsize=3, lw=0.9)
            ax.text(x, hi + 0.01, f"{hit}/{n}", ha="center", fontsize=7)
    ax.axhline(0.05, color="#333", ls="--", lw=0.8)
    ax.set_xticks(np.arange(3) + 0.19)
    ax.set_xticklabels(["trial-level\nwithin block (stored)", "sequence-level\nwithin block", "sequence-level\nshared across twins"], fontsize=8)
    ax.set_ylabel("false-positive rate at p ≤ 0.05 (Clopper–Pearson 95% CI)")
    ax.set_title("C · permutation-null calibration, identical schedules, no colour signal", fontsize=9)
    ax.legend(fontsize=7, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("V-04 (synthetic) · schedule confounds — parts A and D are reported as tables only (EXPERIMENT_LOG V-04)", fontsize=10)
    fig.text(0.01, 0.035, "Data: SYNTHETIC (research/validation/_synth.py), pipeline F2a ERP(O1,O2)+sLDA, 3 sessions × 180 trials; sources reports/runs/V04/B_summary.csv, C_perm.csv.", fontsize=6.5)
    fig.text(0.01, 0.012, "Interpretation: smooth drift did not inflate BA even with identical schedules (B). Limitation: C is underpowered (20 reps; CI up to ~17–32%) and "
             "obs1/obs2 noise was independent, so permutation anti-conservativeness in real data is NOT excluded.", fontsize=6.5)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fp = os.path.join(FIG, "V04_schedule_confounds.png")
    fig.savefig(fp, dpi=130)
    run.output(fp)
run.close()
