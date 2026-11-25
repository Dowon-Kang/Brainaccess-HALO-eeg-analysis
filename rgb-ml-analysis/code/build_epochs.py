"""Build obs-phase (and gray1 control) epochs for every matched session -> epochs.npz"""
import sys, glob, os, numpy as np, pandas as pd; sys.path.insert(0, "/home/claude/scripts")
from scipy import signal
SESS = [  # (subject, session_tag, events file, db cache)
 ("P001", "1103", "P01_main_20261103_170120", "20261103_164755"),
 ("P001", "1112", "P001_main_20261112_155406", "20261112_155440"),
 ("P001", "1119", "P001_main_20261119_154457", "20261119_155305"),
 ("P002", "1111", "P002_main_20261111_115753", "20261111_115250"),
 ("P002", "1124", "P002_main_20261124_154626", "20261124_154629"),
 ("P002", "1125", "P002_main_20261125_110004", "20261125_105925"),
 ("P003", "1120", "P003_main_20261120_215816", "20261120_215815"),
 ("P003", "1121", "P003_main_20261121_231003", "20261121_230656"),
 ("P003", "1125", "P003_main_20261125_133632", "20261125_133035"),
 ("P08",  "1109a", "P08_main_20261109_181531", "20261109_181548"),
 ("P08",  "1109b", "P08_main_20261109_184749", "20261109_181548"),
]
TMIN, TMAX, MARGIN = -0.2, 3.0, 0.08
def filt(eeg, sf):
    sos = signal.butter(4, [0.5, 30], btype="band", fs=sf, output="sos")
    x = signal.sosfiltfilt(sos, eeg - eeg.mean(1, keepdims=True), axis=1)
    b, a = signal.iirnotch(60, 30, fs=sf); return signal.filtfilt(b, a, x, axis=1)
cache = {}
out = {k: [] for k in ["X", "color", "subject", "session", "block", "seq", "phase", "ptp", "contact_bad"]}
for subj, ses, ev, db in SESS:
    if db not in cache:
        z = np.load(f"cache/{db}.npz"); cache = {db: (filt(z["eeg"].astype(float), float(z["sfreq"])), z["t"], z["contact"], float(z["sfreq"]))}
    x, t, contact, sf = cache[db]
    d = pd.read_csv(f"/mnt/user-data/uploads/data/{ev}_events.csv")
    d = d[d.marker.str.contains(r"\|obs\d\||\|gray1\|", regex=True, na=False)]
    n0, n1 = int(round((TMIN - MARGIN) * sf)), int(round((TMAX + MARGIN) * sf))
    b0, b1 = int(round(MARGIN * sf)), int(round((MARGIN - TMIN) * sf))
    for _, r in d.iterrows():
        k = int(np.searchsorted(t, r.onset_lsl))
        if k + n0 < 0 or k + n1 > x.shape[1] or abs(t[min(k, len(t)-1)] - r.onset_lsl) > 0.01: continue
        ep = x[:, k + n0:k + n1].copy(); ep -= ep[:, b0:b1].mean(1, keepdims=True)
        core = ep[:, b0 - int(round(-TMIN*sf)) + 0: ] if False else ep[:, int(round(MARGIN*sf)):int(round((MARGIN+TMAX-TMIN)*sf))]
        out["X"].append(ep.astype(np.float32)); out["color"].append(r.color); out["subject"].append(subj)
        out["session"].append(f"{subj}_{ses[:4]}"); out["block"].append(f"{subj}_{ses[:4]}_b{int(r.block)}")
        out["seq"].append(int(r.seq)); out["phase"].append(r.marker.split("|")[2])
        out["ptp"].append(np.ptp(core, axis=1)); out["contact_bad"].append(bool((contact[:, k+n0:k+n1] == 0).any()))
np.savez_compressed("epochs.npz", **{k: np.array(v) for k, v in out.items()}, sfreq=250.0, tmin=TMIN, tmax=TMAX, margin=MARGIN)
X = np.array(out["X"]); ph = np.array(out["phase"]); ptp = np.array(out["ptp"]); ses = np.array(out["session"]); cb = np.array(out["contact_bad"])
print("epochs", X.shape)
df = pd.DataFrame({"session": ses, "phase": ph, "ptp4": ptp.max(1), "ptpO": ptp[:, :2].max(1), "cbad": cb})
obs = df[df.phase.str.startswith("obs")]
for thr in [100, 150, 200, 300]:
    print(f"keep rate (obs) thr={thr}uV  4ch:", obs.groupby("session").apply(lambda g: round(((g.ptp4 < thr) & ~g.cbad).mean(), 2)).to_dict())
for thr in [100, 150, 200]:
    print(f"keep rate (obs) thr={thr}uV  O1/O2 only:", obs.groupby("session").apply(lambda g: round(((g.ptpO < thr) & ~g.cbad).mean(), 2)).to_dict())
print("median ptp per ch (obs):", np.median(ptp[df.phase.str.startswith('obs').values], axis=0).round(1))
