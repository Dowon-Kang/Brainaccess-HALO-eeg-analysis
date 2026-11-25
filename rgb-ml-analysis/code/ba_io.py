"""BrainAccess Board .db (SQLite) loader + flexible marker-file loader.

DB layout (verified on real files):
  data_<uid>        : data (npy blob, shape (11, n)), time (npy blob, LSL timestamps (n,)),
                      local_clock, clock_offset
  meta_<uid>        : channels CSV, sf, metadata JSON
  annotations_<uid> : annotation text, time (LSL clock)  -> only "sync n=..." in RGB runs
Channel order: O1, O2, Fp2, Fp1, contact_O1..contact_Fp1, Sample, Streaming, Battery
"""
import io
import os
import shutil
import sqlite3
import tempfile

import numpy as np
import pandas as pd

EEG_CH = ["O1", "O2", "Fp2", "Fp1"]


def _open_copy(path, workdir=None):
    """Copy db (+wal/shm) to a temp dir so the original is never touched."""
    d = tempfile.mkdtemp(dir=workdir)
    base = os.path.basename(path)
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(path + ext):
            shutil.copy(path + ext, os.path.join(d, base + ext))
    return sqlite3.connect(os.path.join(d, base)), d


def load_db(path, workdir=None):
    con, d = _open_copy(path, workdir)
    try:
        cur = con.cursor()
        tabs = [r[0] for r in cur.execute("select name from sqlite_master where type='table'")]
        dt = [t for t in tabs if t.startswith("data_")][0]
        mt = [t for t in tabs if t.startswith("meta_")][0]
        at = [t for t in tabs if t.startswith("annotations_")]
        chans, sf = cur.execute(f'select channels, sf from "{mt}"').fetchone()
        chans = chans.split(",")
        blocks, times = [], []
        for data, tm in cur.execute(f'select data, time from "{dt}" order by local_clock'):
            blocks.append(np.load(io.BytesIO(data)))
            times.append(np.load(io.BytesIO(tm)))
        X = np.concatenate(blocks, axis=1)
        t = np.concatenate(times)
        ann = []
        for a in at:
            ann += cur.execute(f'select annotation, time from "{a}"').fetchall()
    finally:
        con.close()
        shutil.rmtree(d, ignore_errors=True)
    order = np.argsort(t, kind="stable")
    X, t = X[:, order], t[order]
    idx = {c: i for i, c in enumerate(chans)}
    eeg = np.vstack([X[idx[c]] for c in EEG_CH])
    contact = np.vstack([X[idx["contact_" + c]] for c in EEG_CH]) if "contact_O1" in idx else None
    sample = X[idx["Sample"]] if "Sample" in idx else None
    ann = pd.DataFrame(ann, columns=["annotation", "time"])
    return dict(eeg=eeg, t=t, sfreq=float(sf), contact=contact, sample=sample,
                annotations=ann, ch_names=EEG_CH, path=path)


_TIME_COLS = ["lsl_time", "lsl_timestamp", "timestamp", "time", "onset", "t", "marker_time"]
_LABEL_COLS = ["label", "marker", "event", "description", "color", "colour", "stim", "condition", "annotation"]


def load_markers(path):
    """Read a marker CSV/TSV and return DataFrame(time, label). Column names guessed."""
    sep = "\t" if path.lower().endswith((".tsv", ".txt")) else ","
    df = pd.read_csv(path, sep=sep)
    low = {c.lower().strip(): c for c in df.columns}
    tcol = next((low[c] for c in _TIME_COLS if c in low), None)
    lcol = next((low[c] for c in _LABEL_COLS if c in low), None)
    if tcol is None or lcol is None:
        raise ValueError(f"marker columns not recognised: {list(df.columns)}")
    return pd.DataFrame({"time": df[tcol].astype(float), "label": df[lcol].astype(str)})
