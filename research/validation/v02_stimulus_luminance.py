"""V-02  Nominal photometry of the stimulus colours in config/protocol.json.

Assumes an ideal sRGB display (IEC 61966-2-1 transfer function, D65 white, sRGB->XYZ matrix).
Reports relative luminance Y, CIE 1931 xy chromaticity, Michelson luminance contrast vs. the grey background,
and cone contrast vs. grey (XYZ -> LMS with the Hunt-Pointer-Estevez matrix, D65-normalised).
These are NOMINAL values: the physical monitor (brightness 50 %, unknown gamma/primaries) was never measured
with a photometer/colorimeter according to the repository, so real luminance differences remain UNKNOWN.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from _runlog import ROOT, Run  # noqa: E402

CFG = os.path.join(ROOT, "rgb-eeg-lab", "config", "protocol.json")
run = Run("V02", "Nominal sRGB luminance / chromaticity / cone contrast of RGB stimuli and grey background",
          inputs=[os.path.relpath(CFG, ROOT)], modules=("numpy", "pandas"))
cfg = json.load(open(CFG, encoding="utf-8"))
cols = dict(cfg["stimulus"]["colors_rgb255"])
cols["grey"] = cfg["stimulus"]["gray_rgb255"]


def srgb_to_linear(v):
    v = np.asarray(v, float) / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


M_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
M_HPE = np.array([[0.4002, 0.7076, -0.0808],
                  [-0.2263, 1.1653, 0.0457],
                  [0.0, 0.0, 0.9182]])
rows = {}
for k, rgb in cols.items():
    XYZ = M_XYZ @ srgb_to_linear(rgb)
    s = XYZ.sum()
    rows[k] = dict(rgb255=tuple(rgb), Y_rel=XYZ[1], x=XYZ[0] / s if s else np.nan, y=XYZ[1] / s if s else np.nan,
                   LMS=M_HPE @ XYZ)
g = rows["grey"]
out = []
for k, r in rows.items():
    lc = (r["Y_rel"] - g["Y_rel"]) / (r["Y_rel"] + g["Y_rel"])
    cc = (r["LMS"] - g["LMS"]) / g["LMS"]
    out.append(dict(stimulus=k, rgb255=str(r["rgb255"]), Y_rel=round(r["Y_rel"], 5), Y_ratio_to_grey=round(r["Y_rel"] / g["Y_rel"], 4),
                    michelson_vs_grey=round(lc, 4), x=round(r["x"], 4), y=round(r["y"], 4),
                    L_contrast=round(cc[0], 3), M_contrast=round(cc[1], 3), S_contrast=round(cc[2], 3)))
df = pd.DataFrame(out)
print(df.to_string(index=False))
fp = os.path.join(run.dir, "stimulus_photometry.csv")
df.to_csv(fp, index=False)
run.output(fp)
run.metric("max_abs_michelson_vs_grey", float(df.michelson_vs_grey.abs().max()))
run.note("Nominal iso-luminance holds only for an ideal sRGB display; physical luminance never measured (UNKNOWN).")
run.close()
