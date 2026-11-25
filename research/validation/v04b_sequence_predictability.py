"""V-04b  How predictable is the current colour from the colour HISTORY alone? (design analysis, no EEG)

protocol.sequence_plan draws each block as a uniformly random arrangement of 6 R, 6 G, 6 B with no run longer than 2
(rejection sampling). Because the counts per block are fixed, later sequences are partly determined by earlier ones.
This script computes, over N generated blocks, the accuracy of three history-only 'decoders' that never see EEG:
  prev-only  : guess uniformly among the two colours different from the previous sequence's colour
  counts     : guess the colour with the most remaining items in the block (ties at random)
  counts+run : as 'counts', but never guess a colour that would create a run of 3
and the per-position accuracy of 'counts+run'. If EEG carried any memory of earlier colours (adaptation, expectation),
a classifier could in principle exploit this structure without decoding the current colour.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import _synth as S  # noqa: E402
from _runlog import Run  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
run = Run("V04b", "History-only predictability of colour under the 6/6/6, max-run-2 block design",
          inputs=["rgb-eeg-lab/scripts/protocol.py", "rgb-eeg-lab/config/protocol.json", "research/validation/_synth.py"],
          modules=("numpy", "pandas"))
rng = np.random.default_rng(1)
C = ["R", "G", "B"]
hits = {"prev-only": [], "counts": [], "counts+run": []}
pos_hits = np.zeros(18)
for _ in range(N):
    blk = [c for _, c in S.protocol.sequence_plan(int(rng.integers(1e9)), 1, 6, 2)]
    rem = {c: 6 for c in C}
    for i, c in enumerate(blk):
        # prev-only
        if i == 0:
            g = C[rng.integers(3)]
        else:
            others = [x for x in C if x != blk[i - 1]]
            g = others[rng.integers(2)]
        hits["prev-only"].append(g == c)
        # counts
        m = max(rem.values())
        cand = [x for x in C if rem[x] == m]
        hits["counts"].append(cand[rng.integers(len(cand))] == c)
        # counts + run constraint
        banned = blk[i - 1] if i >= 2 and blk[i - 1] == blk[i - 2] else None
        allowed = [x for x in C if rem[x] > 0 and x != banned] or [x for x in C if rem[x] > 0]
        m2 = max(rem[x] for x in allowed)
        cand2 = [x for x in allowed if rem[x] == m2]
        h = cand2[rng.integers(len(cand2))] == c
        hits["counts+run"].append(h)
        pos_hits[i] += h
        rem[c] -= 1
res = pd.DataFrame([dict(decoder=k, accuracy=np.mean(v), se=np.std(v) / np.sqrt(len(v))) for k, v in hits.items()])
print(res.round(4).to_string(index=False))
pos = pd.DataFrame({"position_in_block": np.arange(1, 19), "accuracy_counts+run": pos_hits / N})
print(pos.round(3).to_string(index=False))
for name, df in [("decoders.csv", res), ("per_position.csv", pos)]:
    fp = os.path.join(run.dir, name)
    df.round(5).to_csv(fp, index=False)
    run.output(fp)
for _, r in res.iterrows():
    run.metric(f"acc[{r.decoder}]", round(float(r.accuracy), 4))
run.note("Accuracy of a decoder that only knows earlier colours of the same block; balanced accuracy equals accuracy by symmetry of the design.")
run.close()
