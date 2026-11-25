import sys, glob, os, numpy as np; sys.path.insert(0, "/home/claude/scripts")
from ba_io import load_db
dbs = sorted(glob.glob("/mnt/user-data/uploads/BrainAccessData/sub-001/ses-001/*_eeg.db")) + ["/home/claude/work/zips/z1/subj-1_ses-S001_task-_run-001_20261124_154629_eeg.db"]
for p in dbs:
    tag = os.path.basename(p).split("_run-001_")[1].replace("_eeg.db", "")
    out = f"/home/claude/work/cache/{tag}.npz"
    if os.path.exists(out): continue
    r = load_db(p, workdir="/home/claude/work")
    s = r["sample"]; ds = np.diff(s)
    np.savez(out, eeg=r["eeg"].astype(np.float32), t=r["t"], contact=r["contact"].astype(np.int8), sfreq=r["sfreq"])
    print(f"{tag}: n={r['eeg'].shape[1]} dur={(r['t'][-1]-r['t'][0])/60:.1f}min  t=[{r['t'][0]:.1f},{r['t'][-1]:.1f}]  lost={int((ds[ds>1]-1).sum())} gaps>0.1s={int((np.diff(r['t'])>0.1).sum())}")
