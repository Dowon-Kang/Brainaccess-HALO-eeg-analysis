"""Synthetic epoch generator matched to the RGB protocol (used by V-03 / V-04 only; never mixed with real data).

Design  : protocol.sequence_plan(seed, blocks=5, per_color=6, max_run=2) from rgb-eeg-lab/scripts/protocol.py,
          two observation trials (obs1, obs2) per sequence -> 180 trials per session.
Epochs  : 4 channels in the order used by rgb-ml-analysis (O1, O2, Fp2, Fp1), 250 Hz,
          window [TMIN-MARGIN, TMAX+MARGIN] = [-0.28, 3.08] s -> 840 samples, baseline-corrected on [-0.2, 0] s
          exactly like build_epochs.py.
Signal  : band-limited (0.5-30 Hz) 1/f background (SD ~8 uV) with channel correlation, occipital alpha,
          a colour-independent onset VEP on O1/O2, and optional components:
            colour_uv  : class-specific VEP difference on O1/O2 (R: negative 120 ms, G: positive 250 ms, B: none)
            drift_amp  : time-in-session modulation of the common VEP amplitude (habituation within block +
                         linear trend over the session); identical shape in every session
            carry_uv   : carry-over component on O1/O2 that depends on the PREVIOUS sequence's colour only
All values are illustrative assumptions, not estimates from the real recordings.
"""
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "rgb-eeg-lab", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "rgb-ml-analysis", "code"))
import protocol  # noqa: E402  (rgb-eeg-lab/scripts/protocol.py)

SF = 250.0
TMIN, TMAX, MARGIN = -0.2, 3.0, 0.08
N0, N1 = int(round((TMIN - MARGIN) * SF)), int(round((TMAX + MARGIN) * SF))
NS = N1 - N0                       # 840
T = (np.arange(NS) + N0) / SF      # seconds relative to onset
B0, B1 = int(round(MARGIN * SF)), int(round((MARGIN - TMIN) * SF))
CFG = protocol.load()
BASE = CFG["seed"]["base"]
OFF = CFG["seed"].get("session_offset", 1000)


def schedule(seed):
    """List of (block, colour) for the 90 sequences of one session."""
    d = CFG["design"]
    return protocol.sequence_plan(seed, d["blocks"], d["per_color_per_block"], d["max_same_color_run"])


def _bandlimited(rng, n_trials, n_ch):
    f = np.fft.rfftfreq(NS, 1 / SF)
    W = rng.standard_normal((n_trials, n_ch, NS))
    F = np.fft.rfft(W, axis=-1)
    gain = np.zeros_like(f)
    band = (f >= 0.5) & (f <= 30)
    gain[band] = 1 / np.sqrt(f[band])
    X = np.fft.irfft(F * gain, n=NS, axis=-1)
    return X / X.std(axis=(0, 2), keepdims=True)


def _gauss(t0, sd):
    return np.exp(-((T - t0) / sd) ** 2)


VEP = -3.0 * _gauss(0.10, 0.02) + 5.0 * _gauss(0.18, 0.03) + 1.5 * _gauss(0.35, 0.08) * (T > 0)
CEFF = {"R": -1.0 * _gauss(0.12, 0.025), "G": 1.0 * _gauss(0.25, 0.04), "B": 0.0 * T}
CARRY = {"R": 1.0 * _gauss(0.30, 0.10), "G": -1.0 * _gauss(0.30, 0.10), "B": 0.0 * T}


def make_session(rng, seed, colour_uv=0.0, drift_amp=0.0, carry_uv=0.0, session_gain=1.0):
    """Return X (n,4,840), colour labels, block index (1..5), seq index, position-in-session, prev-colour."""
    sch = schedule(seed)
    labels, blocks, seqs, prev = [], [], [], []
    for i, (b, c) in enumerate(sch):
        pc = sch[i - 1][1] if i > 0 and sch[i - 1][0] == b else "none"
        for _rep in (1, 2):
            labels.append(c); blocks.append(b); seqs.append(i + 1); prev.append(pc)
    n = len(labels)
    mix = np.array([[1.0, 0.6, 0.1, 0.1], [0.6, 1.0, 0.1, 0.1], [0.1, 0.1, 1.0, 0.6], [0.1, 0.1, 0.6, 1.0]])
    L = np.linalg.cholesky(mix)
    X = 8.0 * np.einsum("ij,njt->nit", L, _bandlimited(rng, n, 4))
    ph = rng.uniform(0, 2 * np.pi, n)
    fa = rng.normal(10, 0.7, n)
    amp = rng.uniform(2, 6, n)
    alpha = amp[:, None] * np.sin(2 * np.pi * fa[:, None] * T[None, :] + ph[:, None])
    X[:, 0] += alpha; X[:, 1] += 0.9 * alpha
    pos = np.arange(n)
    pos_in_block = np.array([k % 36 for k in range(n)])
    h = np.exp(-pos_in_block / 10.0) - 0.25 + 0.5 * (pos / n - 0.5)          # same shape every session
    gain = session_gain * (1.0 + drift_amp * h)
    for k in range(n):
        w = gain[k] * VEP + colour_uv * CEFF[labels[k]]
        if carry_uv and prev[k] != "none":
            w = w + carry_uv * CARRY[prev[k]]
        X[k, 0] += w; X[k, 1] += 0.9 * w
    X -= X[:, :, B0:B1].mean(2, keepdims=True)
    return X, np.array(labels), np.array(blocks), np.array(seqs), pos, np.array(prev)


def make_subject(rng, pid=2, n_sessions=3, identical=True, **kw):
    """Concatenate sessions; identical=True reuses the session-1 seed (practice before 2026-11-24),
    identical=False uses the Change-3 rule seed = base + pid + 1000*(session-1)."""
    out = {k: [] for k in ["X", "y", "block", "seq", "session", "block_index", "pos", "prev"]}
    for s in range(1, n_sessions + 1):
        seed = BASE + pid + (0 if identical else OFF * (s - 1))
        X, y, b, q, p, pv = make_session(rng, seed, session_gain=rng.uniform(0.8, 1.2), **kw)
        out["X"].append(X); out["y"].append(y); out["seq"].append(q); out["pos"].append(p); out["prev"].append(pv)
        out["block"].append(np.array([f"S{s}_b{x}" for x in b]))
        out["block_index"].append(np.array([f"b{x}" for x in b]))
        out["session"].append(np.array([f"S{s}"] * len(y)))
    return {k: np.concatenate(v) for k, v in out.items()}
