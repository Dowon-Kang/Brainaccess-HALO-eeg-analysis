"""Minimal run logger for validation runs (V-xx).

Every run writes reports/runs/<RUN_ID>/run.json with: command, start/end time (UTC), duration,
git commit (+ dirty flag), python/package versions, inputs, outputs and any shapes/metrics the
script registers. stdout is tee'd to reports/runs/<RUN_ID>/stdout.log.
No raw EEG is read by any V-run; inputs are repo files or synthetic data generated with fixed seeds.
"""
import datetime as _dt
import json
import os
import platform
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _git(*args):
    try:
        return subprocess.check_output(["git", "-C", ROOT, *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "UNKNOWN"


def _sha(path):
    import hashlib
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return "missing"


def _versions(mods):
    out = {"python": platform.python_version()}
    for m in mods:
        try:
            out[m] = __import__(m).__version__
        except Exception:
            out[m] = "not installed"
    return out


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
            st.flush()

    def flush(self):
        for st in self.streams:
            st.flush()


class Run:
    def __init__(self, run_id, purpose, inputs=(), modules=("numpy", "scipy", "sklearn", "pandas", "pyriemann", "matplotlib")):
        self.dir = os.path.join(ROOT, "reports", "runs", run_id)
        os.makedirs(self.dir, exist_ok=True)
        self.meta = dict(run_id=run_id, purpose=purpose, command=" ".join([os.path.relpath(sys.executable, ROOT) if False else "python"] + sys.argv),
                         started_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                         git_commit=_git("rev-parse", "HEAD"), git_dirty=bool(_git("status", "--porcelain")),
                         platform=platform.platform(), versions=_versions(modules), inputs=list(inputs),
                         outputs=[], shapes={}, metrics={}, notes=[], raw_eeg_used=False,
                         file_sha256={p: _sha(os.path.join(ROOT, p)) for p in
                                      [os.path.relpath(os.path.abspath(sys.argv[0]), ROOT), "research/validation/_runlog.py", *inputs]})
        self._t0 = time.time()
        self._log = open(os.path.join(self.dir, "stdout.log"), "w", encoding="utf-8")
        self._stdout = sys.stdout
        sys.stdout = _Tee(self._stdout, self._log)

    def shape(self, name, shape):
        self.meta["shapes"][name] = list(shape)

    def metric(self, name, value):
        self.meta["metrics"][name] = value

    def output(self, path):
        self.meta["outputs"].append(os.path.relpath(path, ROOT))

    def note(self, text):
        self.meta["notes"].append(text)

    def close(self):
        self.meta["finished_utc"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        self.meta["duration_sec"] = round(time.time() - self._t0, 2)
        sys.stdout = self._stdout
        self._log.close()
        with open(os.path.join(self.dir, "run.json"), "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=1, default=str)
        print(f"[run] {self.meta['run_id']} done in {self.meta['duration_sec']} s -> {os.path.relpath(self.dir, ROOT)}/run.json")
