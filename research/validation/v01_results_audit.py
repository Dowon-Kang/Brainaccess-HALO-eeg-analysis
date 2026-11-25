"""V-01  Audit of the stored exploratory results (rgb-ml-analysis/results/*.csv).

Inputs : only the 5 CSV files committed in the repository (aggregated numbers; raw EEG not available).
Checks :
  A. internal arithmetic consistency (means, deltas, trial counts, Bonferroni factor, binomial thresholds)
  B. implied per-subject permutation-null spread (from null_mean and null95)
  C. selection-bias diagnostics for the 19-pipeline comparison:
     - best-of-19 vs. baseline per subject
     - leave-one-subject-out (LOSubjO) pipeline selection: choose the pipeline with the best mean on the
       other 3 subjects, read off its score on the held-out subject
     - between-subject agreement of pipeline rankings (Kendall's W, pairwise Spearman)
     - each pipeline score expressed in units of that subject's implied null SD
Outputs: reports/runs/V01/*.csv, reports/figures/V01_*.png, run.json
Caveat : every number here is derived from stored aggregates that cannot be re-generated without the raw data.
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
from _runlog import ROOT, Run  # noqa: E402

RES = os.path.join(ROOT, "rgb-ml-analysis", "results")
FIG = os.path.join(ROOT, "reports", "figures")
files = {k: os.path.join(RES, f"{k}.csv") for k in ["methods", "subjects", "sessions", "controls", "generalization"]}
run = Run("V01", "Audit stored exploratory results: consistency + selection-bias diagnostics",
          inputs=[os.path.relpath(p, ROOT) for p in files.values()])
D = {k: pd.read_csv(p) for k, p in files.items()}
for k, d in D.items():
    run.shape(k, d.shape)
SUBJ = ["P002", "P003", "P08", "P001"]
checks = []


def check(name, ok, detail):
    checks.append(dict(check=name, status="PASS" if ok else "FAIL", detail=detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


# ---------------------------------------------------------------- A. consistency
m = D["methods"]
mean_re = m[SUBJ].mean(axis=1).round(1)
diff = (mean_re - m["mean"]).abs()
check("methods.mean == unweighted mean of 4 subjects", bool((diff <= 0.051).all()), f"max |diff| = {diff.max():.3f} pp")
base = m.loc[m.factor == "기준", "mean"].iloc[0]
d_re = (m["mean"] - base).round(1)
check("methods.delta_pp == mean - baseline mean", bool(((d_re - m["delta_pp"]).abs() <= 0.051).all()),
      f"baseline mean = {base} %, max |diff| = {(d_re - m['delta_pp']).abs().max():.3f}")
check("19 pipelines listed", len(m) == 19, f"n rows = {len(m)}")

s = D["sessions"]
used = s[s.used == "사용"]
tri = used.groupby("subject").kept.sum()
sj = D["subjects"].set_index("subject")
for subj in SUBJ:
    check(f"subjects.trials == sum(kept of used sessions) [{subj}]", int(tri[subj]) == int(sj.loc[subj, "trials"]),
          f"sessions.csv {int(tri[subj])} vs subjects.csv {int(sj.loc[subj, 'trials'])}")
kp = (s.kept / s.total * 100)
check("sessions.keep_pct consistent with kept/total (±1 pp; stored values are rounded to whole %)",
      bool(((kp - s.keep_pct).abs() <= 1.0).all()), f"max |diff| = {(kp - s.keep_pct).abs().max():.2f} pp")
for subj in SUBJ:
    p, nperm, pb = sj.loc[subj, ["p", "n_perm", "p_bonf"]]
    check(f"p_bonf == min(1, 19 p) [{subj}]", abs(min(1, 19 * p) - pb) < 0.002, f"p={p}, n_perm={nperm}, 19p={19*p:.4f}, stored={pb}")
    check(f"p >= 1/(n_perm+1) [{subj}]", p >= 1 / (nperm + 1) - 1e-9, f"min attainable p = {1/(nperm+1):.4f}")
c = D["controls"]
for _, r in c.iterrows():
    thr = stats.binom.ppf(0.95, int(r.n), 1 / 3) / int(r.n) * 100
    check(f"controls.chance95 == binom.ppf(.95,n,1/3)/n [{r.subject}, {r.model}]", abs(thr - r.chance95) < 0.06,
          f"recomputed {thr:.2f} vs stored {r.chance95}")
g = D["generalization"]
pairs = [("P002", "ERP O1·O2", "ERP O1·O2만 + sLDA"), ("P002", "ERP 4채널", "ERP 4채널 + sLDA (기준선)"),
         ("P003", "ERP O1·O2", "ERP O1·O2만 + sLDA"), ("P003", "ERP 4채널", "ERP 4채널 + sLDA (기준선)")]
for subj, gm, mm in pairs:
    gv = g[(g.subject == subj) & (g.model == gm) & g.scheme.str.startswith("블록")].bacc.iloc[0]
    mv = m.loc[m.method == mm, subj].iloc[0]
    check(f"generalization block-wise == methods [{subj}, {gm}]", abs(gv - mv) < 0.051, f"{gv} vs {mv}")
for subj in ["P002", "P003"]:
    check(f"subjects.bacc == methods best pipeline [{subj}]",
          abs(sj.loc[subj, "bacc"] - m.loc[m.method == "ERP O1·O2만 + sLDA", subj].iloc[0]) < 0.051,
          f"{sj.loc[subj, 'bacc']}")

# ---------------------------------------------------------------- B. implied null spread
z95 = stats.norm.ppf(0.95)
null = sj[["trials", "null_mean", "null95", "n_perm"]].copy()
null["null_sd_implied"] = (null.null95 - null.null_mean) / z95
null["binomial_sd_iid"] = np.sqrt((1 / 3) * (2 / 3) / null.trials) * 100
null["sd_ratio_perm_over_iid"] = null.null_sd_implied / null.binomial_sd_iid
print("\nImplied permutation-null SD per subject (normal approx. from null95):\n", null.round(2).to_string())
null.round(3).to_csv(os.path.join(run.dir, "null_spread.csv"))
run.output(os.path.join(run.dir, "null_spread.csv"))

# ---------------------------------------------------------------- C. selection bias
sd = null.null_sd_implied
M = m.set_index("method")[SUBJ]
best = M.max()
basev = M.loc["ERP 4채널 + sLDA (기준선)"]
tab = pd.DataFrame({"best_of_19": best, "best_pipeline": M.idxmax(), "baseline": basev,
                    "best_minus_baseline_pp": best - basev, "null_mean": null.null_mean, "null_sd": sd,
                    "best_z_vs_nullmean": (best - null.null_mean) / sd})
# Expected maximum of K independent standard normals (upper reference; pipelines are positively correlated,
# so the true expected max of correlated null scores is smaller).
K = len(M)
rng = np.random.default_rng(0)
emax = rng.standard_normal((200000, K)).max(1).mean()
tab["E[max of 19 indep. nulls]_pp"] = null.null_mean + emax * sd
print(f"\nE[max of {K} independent N(0,1)] = {emax:.3f}")
print(tab.round(2).to_string())
tab.round(3).to_csv(os.path.join(run.dir, "best_vs_baseline.csv"))
run.output(os.path.join(run.dir, "best_vs_baseline.csv"))

# leave-one-subject-out selection
rows = []
for held in SUBJ:
    others = [x for x in SUBJ if x != held]
    pick = M[others].mean(axis=1).idxmax()
    rows.append(dict(held_out=held, selected_on_others=pick, others_mean=M.loc[pick, others].mean(),
                     held_out_score=M.loc[pick, held], held_out_baseline=basev[held],
                     held_out_null95=sj.loc[held, "null95"], held_out_null_mean=sj.loc[held, "null_mean"]))
lo = pd.DataFrame(rows)
lo["exceeds_null95"] = lo.held_out_score > lo.held_out_null95
print("\nLeave-one-subject-out pipeline selection:\n", lo.round(2).to_string())
print(f"mean held-out score of LOSubjO-selected pipelines = {lo.held_out_score.mean():.2f} % "
      f"(vs in-sample best-mean pipeline {M.mean(axis=1).max():.2f} %)")
lo.round(3).to_csv(os.path.join(run.dir, "loso_selection.csv"), index=False)
run.output(os.path.join(run.dir, "loso_selection.csv"))
run.metric("loso_selected_mean_heldout_bacc", round(float(lo.held_out_score.mean()), 2))
run.metric("insample_best_mean_bacc", round(float(M.mean(axis=1).max()), 2))

# ranking agreement
R = M.rank(axis=0)
n, k = R.shape
Ssum = ((R.sum(axis=1) - k * (n + 1) / 2) ** 2).sum()
W = 12 * Ssum / (k ** 2 * (n ** 3 - n))
chi2 = k * (n - 1) * W
pW = 1 - stats.chi2.cdf(chi2, n - 1)
sp = M.corr(method="spearman")
print(f"\nKendall's W across 4 subjects (19 pipelines) = {W:.3f}, chi2({n-1}) = {chi2:.2f}, p = {pW:.3f}")
print("Pairwise Spearman rho of pipeline scores:\n", sp.round(2).to_string())
run.metric("kendall_W", round(float(W), 3))
run.metric("kendall_W_p", round(float(pW), 4))
sp.round(3).to_csv(os.path.join(run.dir, "ranking_spearman.csv"))
run.output(os.path.join(run.dir, "ranking_spearman.csv"))

zt = (M - null.null_mean) / sd
zt.round(2).to_csv(os.path.join(run.dir, "pipeline_z_vs_null.csv"))
run.output(os.path.join(run.dir, "pipeline_z_vs_null.csv"))
n_above = int((M.values > sj.loc[SUBJ, "null95"].values[None, :]).sum())
print(f"\npipeline x subject cells above that subject's null95: {n_above} / {M.size} "
      f"(5% expected under the null if independent = {0.05*M.size:.1f})")
run.metric("cells_above_null95", f"{n_above}/{M.size}")

pd.DataFrame(checks).to_csv(os.path.join(run.dir, "consistency_checks.csv"), index=False)
run.output(os.path.join(run.dir, "consistency_checks.csv"))
run.metric("consistency_checks_pass", f"{sum(c['status']=='PASS' for c in checks)}/{len(checks)}")

# ---------------------------------------------------------------- figure
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

fig, axes = plt.subplots(1, 4, figsize=(15, 6.2), sharey=True)
order = M.mean(axis=1).sort_values().index
for ax, subj in zip(axes, SUBJ):
    vals = M.loc[order, subj]
    nm, n95 = sj.loc[subj, "null_mean"], sj.loc[subj, "null95"]
    ax.axvspan(nm - 1.96 * sd[subj], nm + 1.96 * sd[subj], color="#bbbbbb", alpha=0.35, lw=0,
               label="permutation null ≈95% band")
    ax.axvline(33.33, color="#555", lw=0.8, ls="--", label="uniform chance 33.3%")
    ax.axvline(n95, color="#b22", lw=0.8, ls=":", label="null 95th pct (one-sided)")
    colors = ["#1f5fa8" if i == "ERP 4채널 + sLDA (기준선)" else "#444" for i in vals.index]
    ax.scatter(vals.values, range(len(vals)), c=colors, s=18, zorder=3)
    ax.set_title(f"{subj}  (n={int(sj.loc[subj,'trials'])})", fontsize=10)
    ax.set_xlabel("balanced accuracy (%)")
    ax.set_xlim(10, 50)
    ax.spines[["top", "right"]].set_visible(False)
axes[0].set_yticks(range(len(order)))
axes[0].set_yticklabels([m.set_index("method").loc[i, "pipeline"] for i in order], fontsize=7)
axes[0].legend(fontsize=7, frameon=False, loc="lower left")
fig.suptitle("V01 · Stored 19-pipeline results vs. each subject's permutation-null spread (leave-one-block-out)", fontsize=11)
fig.text(0.01, 0.01, "Source: rgb-ml-analysis/results/methods.csv, subjects.csv (stored aggregates; not regenerated). "
         "Null band = null_mean ± 1.96·SD, SD implied from (null95 − null_mean)/1.645 (normal approx.). "
         "Blue = baseline pipeline. Limitation: null spread was estimated for the O1·O2 pipeline only.", fontsize=7)
fig.tight_layout(rect=(0, 0.04, 1, 0.96))
fp = os.path.join(FIG, "V01_pipelines_vs_null.png")
fig.savefig(fp, dpi=130)
run.output(fp)
run.note("All numbers derive from stored aggregate CSVs; the raw EEG needed to regenerate them is not in this environment.")
run.close()
