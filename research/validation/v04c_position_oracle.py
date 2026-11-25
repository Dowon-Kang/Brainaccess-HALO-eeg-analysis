"""V-04c  Position-only 'oracle' under the STORED cross-validation grouping (design analysis, no EEG).

Question: if a classifier knew nothing but the global sequence number of a trial (s001-s090, as written in the marker),
          how well could it predict the colour under the grouping the stored analysis used
          (groups = subject_session_block, leave-one-block-out, all of a subject's sessions pooled)?
Rule    : predict the majority colour among TRAINING trials with the same sequence number; if none, guess at random.
Session structures reconstructed from rgb-ml-analysis/results/sessions.csv + rgb-eeg-lab/docs/plan_changes.md
(INFERRED, see reports/INITIAL_ANALYSIS.md §4); trial rejection ignored (all obs trials kept, 2 per sequence).
Interpretation: this is an upper bound on how much a perfectly position-encoding EEG feature could exploit the
identical schedules of repeated sessions. Real EEG does not encode the sequence number this precisely (V-04 B).
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

sys.path.insert(0, os.path.dirname(__file__))
import _synth as S  # noqa: E402
from _runlog import Run  # noqa: E402

run = Run("V04c", "Position-only oracle under the stored leave-one-block-out grouping (design analysis)",
          inputs=["rgb-eeg-lab/scripts/protocol.py", "rgb-eeg-lab/config/protocol.json", "research/validation/_synth.py",
                  "rgb-ml-analysis/results/sessions.csv"], modules=("numpy", "pandas", "sklearn"))
B, OFF = S.BASE, S.OFF
ALL = range(1, 91)
# (session tag, seed, sequence numbers included)
STRUCT = {
    "P001": [("1103", B + 1, ALL), ("1112", B + 1, ALL)],
    "P002 (1125 = session-1 seed)": [("1111", B + 2, ALL), ("1124", B + 2, ALL), ("1125", B + 2, ALL)],
    "P002 (1125 = session-2 seed)": [("1111", B + 2, ALL), ("1124", B + 2, ALL), ("1125", B + 2 + OFF, ALL)],
    "P003": [("1120", B + 3, ALL), ("1121", B + 3, list(range(19, 37)) + list(range(37, 49))), ("1125", B + 3, range(37, 91))],
    "P08": [("1109", B + 8, ALL)],
    "control: 3 sessions, distinct seeds": [("s1", B + 2, ALL), ("s2", B + 2 + OFF, ALL), ("s3", B + 2 + 2 * OFF, ALL)],
}
rng = np.random.default_rng(0)
rows = []
for subj, sessions in STRUCT.items():
    y, seq, grp = [], [], []
    for tag, seed, seqs in sessions:
        sch = S.schedule(seed)
        for q in seqs:
            b, c = sch[q - 1]
            for _rep in (1, 2):
                y.append(c); seq.append(q); grp.append(f"{tag}_b{b}")
    y, seq, grp = map(np.array, (y, seq, grp))
    pred = np.empty_like(y)
    for g in np.unique(grp):
        te, tr = grp == g, grp != g
        for i in np.where(te)[0]:
            lab = y[tr & (seq == seq[i])]
            if len(lab) == 0:
                pred[i] = ["R", "G", "B"][rng.integers(3)]
            else:
                vals, cnt = np.unique(lab, return_counts=True)
                top = vals[cnt == cnt.max()]
                pred[i] = top[rng.integers(len(top))]
    ba = balanced_accuracy_score(y, pred)
    rows.append(dict(structure=subj, n_trials=len(y), n_groups=len(np.unique(grp)), position_oracle_bacc=round(ba, 4)))
df = pd.DataFrame(rows)
print(df.to_string(index=False))
fp = os.path.join(run.dir, "position_oracle.csv")
df.to_csv(fp, index=False)
run.output(fp)
for _, r in df.iterrows():
    run.metric(f"bacc[{r.structure}]", float(r.position_oracle_bacc))
run.close()
