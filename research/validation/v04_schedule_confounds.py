"""V-04  Schedule-related confounds in the evaluation protocol (design analysis + synthetic simulation).

Background (repository facts, see reports/INITIAL_ANALYSIS.md):
  * colour order = protocol.sequence_plan(seed); before 2026-11-24 every session of a participant used the same seed
    (docs/plan_changes.md, Change 3) -> repeated sessions of P001/P002/P003 had IDENTICAL colour schedules;
  * the stored within-subject CV groups by block-within-session (build_epochs.py: block = subj_session_bN), so the
    "twin" blocks (same block number, same schedule, other session) sit in the training set;
  * the stored permutation test shuffles labels at TRIAL level within each block (run_extra.py / perm_fine.py),
    which (i) separates obs1/obs2 of the same sequence and (ii) does not reproduce the shared schedule across sessions;
  * max_same_color_run = 2 makes the previous sequence's colour weakly informative about the current colour.

Parts
  A. exact schedules for the session-1 seeds of participants 1, 2, 3, 8: P(current colour == previous colour),
     and the balanced-accuracy ceiling of a decoder that only knows the previous sequence's colour (population value
     from 20 000 generated blocks).
  B. simulation: no colour signal, time-in-session VEP modulation (drift_amp 0 / 0.5 / 1.0), identical vs. distinct
     schedules over 3 sessions; leave-one-group-out with groups = block-within-session (stored), block number across
     sessions (twin-aware), session.  REPS repetitions per cell.
  C. simulation: false-positive rate of three permutation nulls under identical schedules, drift_amp in {0, 1}:
     trial-level within block (stored) / sequence-level within block / sequence-level shared across twin sessions.
  D. simulation: carry-over component that depends only on the previous sequence's colour (carry_uv 0 / 2 uV).
All synthetic magnitudes are illustrative; the real-data magnitude of each mechanism is UNKNOWN.
Usage : python v04_schedule_confounds.py [REPS_B] [REPS_C] [N_PERM]
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402
from scipy import stats  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import _synth as S  # noqa: E402
from _runlog import ROOT, Run  # noqa: E402
import rgb_pipeline as rp  # noqa: E402

REPS_B = int(sys.argv[1]) if len(sys.argv) > 1 else 30
REPS_C = int(sys.argv[2]) if len(sys.argv) > 2 else 20
N_PERM = int(sys.argv[3]) if len(sys.argv) > 3 else 100
run = Run("V04", "Schedule confounds: twin schedules, permutation exchangeability, previous-colour carry-over",
          inputs=["rgb-eeg-lab/scripts/protocol.py", "rgb-eeg-lab/config/protocol.json", "rgb-ml-analysis/code/rgb_pipeline.py",
                  "research/validation/_synth.py"])
run.note(f"REPS_B={REPS_B}, REPS_C={REPS_C}, N_PERM={N_PERM}; synthetic EEG only")
PIPE = "F2a ERP(O1,O2)+sLDA"

# ------------------------------------------------------------------ A. exact schedules
print("=== A. schedules reconstructed from session-1 seeds (seed = base + participant number)")
rowsA = []
for pid in [1, 2, 3, 8]:
    seed = S.BASE + pid
    sch = S.schedule(seed)
    same = [sch[i][1] == sch[i - 1][1] for i in range(1, len(sch)) if sch[i][0] == sch[i - 1][0]]
    rowsA.append(dict(participant_number=pid, seed=seed, n_sequences=len(sch), first_block=" ".join(c for b, c in sch if b == 1),
                      p_same_as_prev=np.mean(same)))
dfA = pd.DataFrame(rowsA)
print(dfA.to_string(index=False))
same_pop = []
rng = np.random.default_rng(0)
for k in range(20000):
    blk = S.protocol.sequence_plan(int(rng.integers(1e9)), 1, 6, 2)
    same_pop += [blk[i][1] == blk[i - 1][1] for i in range(1, 18)]
p_same = float(np.mean(same_pop))
# decoder that sees only the previous colour: predict one of the two other colours uniformly at random.
# first sequence of each block has no predecessor -> 1/3.  Expected accuracy (balanced by symmetry):
ceiling = (17 / 18) * (1 - p_same) / 2 + (1 / 18) * (1 / 3)
print(f"population P(current == previous) within block = {p_same:.4f} (unconstrained shuffle: {5/17:.4f})")
print(f"balanced-accuracy ceiling of a previous-colour-only decoder = {ceiling:.4f}")
fp = os.path.join(run.dir, "A_schedules.csv")
dfA.to_csv(fp, index=False)
run.output(fp)
run.metric("p_same_as_prev_population", round(p_same, 4))
run.metric("prev_colour_only_bacc_ceiling", round(ceiling, 4))


# ------------------------------------------------------------------ helpers
def evaluate_groups(d, groups_key):
    return rp.evaluate(rp.pipelines(250.0)[PIPE], d["X"], d["y"], d[groups_key])[0]


def b_job(rep, identical, drift):
    import warnings as w
    w.filterwarnings("ignore")
    rng = np.random.default_rng(1_000_000 + 1000 * rep + int(10 * drift) + (0 if identical else 500))
    d = S.make_subject(rng, pid=2, identical=identical, drift_amp=drift)
    return [dict(rep=rep, schedule="identical" if identical else "distinct", drift_amp=drift, grouping=gk,
                 bacc=evaluate_groups(d, gk)) for gk in ["block", "block_index", "session"]]


# ------------------------------------------------------------------ B
print("\n=== B. twin schedules x drift x CV grouping (no colour signal)")
jobs = [(r, ident, dr) for r in range(REPS_B) for ident in (True, False) for dr in (0.0, 0.5, 1.0)]
resB = Parallel(n_jobs=4)(delayed(b_job)(*j) for j in jobs)
dfB = pd.DataFrame([x for rr in resB for x in rr])
sumB = dfB.groupby(["schedule", "drift_amp", "grouping"]).bacc.agg(["count", "mean", "std"]).reset_index()
sumB["t_vs_1/3"] = (sumB["mean"] - 1 / 3) / (sumB["std"] / np.sqrt(sumB["count"]))
sumB["p_one_sided"] = 1 - stats.t.cdf(sumB["t_vs_1/3"], sumB["count"] - 1)
print(sumB.round(4).to_string(index=False))
dfB.to_csv(os.path.join(run.dir, "B_scores.csv"), index=False)
sumB.round(5).to_csv(os.path.join(run.dir, "B_summary.csv"), index=False)
run.output(os.path.join(run.dir, "B_summary.csv"))
for _, r in sumB.iterrows():
    run.metric(f"B_mean_bacc[{r.schedule},drift={r.drift_amp},{r.grouping}]", round(float(r["mean"]), 4))


# ------------------------------------------------------------------ C
def permute(d, kind, rng):
    y = d["y"].copy()
    if kind == "trial_within_block":                       # stored method
        for b in np.unique(d["block"]):
            i = np.where(d["block"] == b)[0]
            y[i] = rng.permutation(y[i])
        return y
    # sequence-level: permute the colour of whole sequences (obs1+obs2 together)
    seq_key = np.array([f"{s}_{q}" for s, q in zip(d["session"], d["seq"])])
    if kind == "sequence_within_block":
        for b in np.unique(d["block"]):
            seqs = np.unique(seq_key[d["block"] == b])
            cols = np.array([y[seq_key == s][0] for s in seqs])
            newc = rng.permutation(cols)
            for s, c in zip(seqs, newc):
                y[seq_key == s] = c
        return y
    if kind == "sequence_shared_schedule":                # same permutation for twin blocks in all sessions
        for bi in np.unique(d["block_index"]):
            m = d["block_index"] == bi
            seq_nums = np.unique(d["seq"][m])
            cols = np.array([y[m & (d["seq"] == q)][0] for q in seq_nums])
            perm = rng.permutation(len(seq_nums))
            for q, c in zip(seq_nums, cols[perm]):
                y[m & (d["seq"] == q)] = c
        return y
    raise ValueError(kind)


def c_job(rep, drift):
    import warnings as w
    w.filterwarnings("ignore")
    rng = np.random.default_rng(2_000_000 + 1000 * rep + int(10 * drift))
    d = S.make_subject(rng, pid=2, identical=True, drift_amp=drift)
    pipe = rp.pipelines(250.0)[PIPE]
    obs = rp.evaluate(pipe, d["X"], d["y"], d["block"])[0]
    out = []
    for kind in ["trial_within_block", "sequence_within_block", "sequence_shared_schedule"]:
        prng = np.random.default_rng(rep * 7 + 1)
        null = np.array([rp.evaluate(pipe, d["X"], permute(d, kind, prng), d["block"])[0] for _ in range(N_PERM)])
        out.append(dict(rep=rep, drift_amp=drift, null_kind=kind, observed=obs, null_mean=null.mean(), null_sd=null.std(),
                        p=(np.sum(null >= obs) + 1) / (N_PERM + 1)))
    return out


print(f"\n=== C. permutation-null calibration under identical schedules ({REPS_C} reps x {N_PERM} perms)")
resC = Parallel(n_jobs=4)(delayed(c_job)(r, dr) for r in range(REPS_C) for dr in (0.0, 1.0))
dfC = pd.DataFrame([x for rr in resC for x in rr])
sumC = dfC.groupby(["drift_amp", "null_kind"]).agg(n=("p", "size"), fpr_at_05=("p", lambda p: float(np.mean(p <= 0.05))),
                                                   mean_p=("p", "mean"), mean_null_sd=("null_sd", "mean"),
                                                   mean_observed=("observed", "mean")).reset_index()
print(sumC.round(4).to_string(index=False))
dfC.to_csv(os.path.join(run.dir, "C_perm.csv"), index=False)
sumC.round(5).to_csv(os.path.join(run.dir, "C_summary.csv"), index=False)
run.output(os.path.join(run.dir, "C_summary.csv"))
for _, r in sumC.iterrows():
    run.metric(f"C_fpr05[drift={r.drift_amp},{r.null_kind}]", round(float(r.fpr_at_05), 3))


# ------------------------------------------------------------------ D
def d_job(rep, carry):
    import warnings as w
    w.filterwarnings("ignore")
    rng = np.random.default_rng(3_000_000 + 1000 * rep + int(10 * carry))
    d = S.make_subject(rng, pid=2, identical=False, carry_uv=carry)
    return dict(rep=rep, carry_uv=carry, bacc=evaluate_groups(d, "block"))


print(f"\n=== D. previous-colour carry-over only (no current-colour signal), {REPS_B} reps")
dfD = pd.DataFrame(Parallel(n_jobs=4)(delayed(d_job)(r, c) for r in range(REPS_B) for c in (0.0, 2.0)))
sumD = dfD.groupby("carry_uv").bacc.agg(["count", "mean", "std"]).reset_index()
sumD["t_vs_1/3"] = (sumD["mean"] - 1 / 3) / (sumD["std"] / np.sqrt(sumD["count"]))
print(sumD.round(4).to_string(index=False))
dfD.to_csv(os.path.join(run.dir, "D_scores.csv"), index=False)
sumD.round(5).to_csv(os.path.join(run.dir, "D_summary.csv"), index=False)
run.output(os.path.join(run.dir, "D_summary.csv"))
for _, r in sumD.iterrows():
    run.metric(f"D_mean_bacc[carry={r.carry_uv}]", round(float(r["mean"]), 4))

# ------------------------------------------------------------------ figure
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
ax = axes[0]
lab = {"block": "block-within-session (stored)", "block_index": "block number across sessions (twin-aware)", "session": "leave-one-session-out"}
colr = {"block": "#c0392b", "block_index": "#1f5fa8", "session": "#2e7d32"}
for j, sched in enumerate(["identical", "distinct"]):
    for gk in ["block", "block_index", "session"]:
        s = sumB[(sumB.schedule == sched) & (sumB.grouping == gk)]
        ax.errorbar(s.drift_amp + (0.03 * ["block", "block_index", "session"].index(gk)) + 1.4 * j, s["mean"] * 100,
                    yerr=1.96 * s["std"] / np.sqrt(s["count"]) * 100, fmt="o-", color=colr[gk], ms=4, capsize=2,
                    label=lab[gk] if j == 0 else None)
ax.axhline(100 / 3, color="#333", ls="--", lw=0.8)
ax.set_xticks([0, 0.5, 1.0, 1.4, 1.9, 2.4])
ax.set_xticklabels(["0", "0.5", "1.0", "0", "0.5", "1.0"])
ax.set_xlabel("drift_amp   (left: identical schedules | right: distinct schedules)")
ax.set_ylabel("mean balanced accuracy (%) ± 95% CI of mean")
ax.set_title("B · no colour signal: time-in-session drift × schedule × CV grouping", fontsize=9)
ax.legend(fontsize=7, frameon=False)
ax.spines[["top", "right"]].set_visible(False)
ax = axes[1]
kinds = ["trial_within_block", "sequence_within_block", "sequence_shared_schedule"]
x = np.arange(len(kinds))
for k, dr in enumerate([0.0, 1.0]):
    v = [sumC[(sumC.drift_amp == dr) & (sumC.null_kind == kd)].fpr_at_05.iloc[0] for kd in kinds]
    ax.bar(x + 0.38 * k, v, width=0.36, color=["#999", "#c0392b"][k], label=f"drift_amp={dr}")
ax.axhline(0.05, color="#333", ls="--", lw=0.8)
ax.set_xticks(x + 0.19)
ax.set_xticklabels(["trial-level\nwithin block (stored)", "sequence-level\nwithin block", "sequence-level\nshared across twins"], fontsize=8)
ax.set_ylabel(f"false-positive rate at p≤0.05  (n={REPS_C} reps/bar)")
ax.set_title("C · permutation-null calibration, identical schedules, no colour signal", fontsize=9)
ax.legend(fontsize=7, frameon=False)
ax.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, f"Synthetic data only (research/validation/_synth.py); pipeline {PIPE}; 3 sessions × 180 trials. "
         "Magnitudes are illustrative; whether these mechanisms operate in the real recordings is UNKNOWN.", fontsize=7)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fp = os.path.join(ROOT, "reports", "figures", "V04_schedule_confounds.png")
fig.savefig(fp, dpi=130)
run.output(fp)
run.close()
