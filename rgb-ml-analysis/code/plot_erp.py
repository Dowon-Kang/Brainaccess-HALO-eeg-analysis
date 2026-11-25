import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "DejaVu Sans"
z = np.load("/home/claude/work/epochs.npz", allow_pickle=True)
meta = pd.DataFrame({k: z[k] for k in ["color", "subject", "session", "phase", "contact_bad"]})
clean = (z["ptp"].max(1) < 150) & ~meta.contact_bad.values & meta.phase.str.startswith("obs").values & (meta.session.values != "P001_1119")
sf, tmin, margin = 250.0, -0.2, 0.08
X = z["X"][clean]; M = meta[clean].reset_index(drop=True)
t = np.arange(X.shape[2]) / sf + tmin - margin
win = (t >= -0.2) & (t <= 1.0)
cols = {"R": "#d1495b", "G": "#2e933c", "B": "#3a6ea5"}
subs = ["P002", "P003", "P08", "P001"]
fig, axes = plt.subplots(2, 4, figsize=(15, 6.2), sharex=True)
for j, s in enumerate(subs):
    for i, ch in enumerate(["O1", "O2"]):
        ax = axes[i, j]
        for c in ["R", "G", "B"]:
            e = X[(M.subject == s).values & (M.color == c).values][:, i][:, win]
            mu, se = e.mean(0), e.std(0) / np.sqrt(len(e))
            ax.plot(t[win], mu, color=cols[c], lw=1.6, label=f"{c} (n={len(e)})")
            ax.fill_between(t[win], mu - se, mu + se, color=cols[c], alpha=0.18, lw=0)
        ax.axvline(0, color="#888", lw=0.8); ax.axhline(0, color="#bbb", lw=0.6)
        ax.set_title(f"{s} · {ch}", fontsize=10)
        if j == 0: ax.set_ylabel("µV")
        if i == 1: ax.set_xlabel("time from colour onset (s)")
        ax.spines[["top", "right"]].set_visible(False)
        if i == 0: ax.legend(fontsize=7, frameon=False, loc="lower right")
fig.suptitle("Colour-onset VEP at occipital channels (mean ± SEM, clean obs trials)", fontsize=12)
fig.tight_layout()
fig.savefig("/home/claude/work/erp_by_colour.png", dpi=130)
print("saved")
