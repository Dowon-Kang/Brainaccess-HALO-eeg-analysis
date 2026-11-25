"""Minimal run logger for validation runs (V-xx).

Every run writes reports/runs/<RUN_ID>/run.json with: command, working directory, start/end time (UTC), duration,
git commit (+ dirty flag), python/package versions, SHA-256 of the script/helpers/inputs, configuration
(CLI arguments, seed rules, generator parameters), inputs, outputs, shapes, metrics, warnings summary and exit status.
stdout is tee'd to stdout.log and stderr to stderr.log in reports/runs/<RUN_ID>/; warnings raised in the main process
are counted per (category, message) and written to warnings.log (worker processes report theirs via
Run.add_warnings). No raw EEG is read by any V-run; inputs are repo files or synthetic data generated with fixed seeds.

History: V-01 .. V-04c ran with an earlier version of this logger (stdout only, no stderr/warnings capture; several
scripts suppressed warnings with warnings.filterwarnings("ignore")). Their run.json therefore has no warnings field.
"""
import atexit
import collections
import datetime as _dt
import json
import os
import platform
import subprocess
import sys
import time
import warnings

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
    def __init__(self, run_id, purpose, inputs=(), modules=("numpy", "scipy", "sklearn", "pandas", "pyriemann", "matplotlib"),
                 config=None):
        self.dir = os.path.join(ROOT, "reports", "runs", run_id)
        os.makedirs(self.dir, exist_ok=True)
        script = os.path.relpath(os.path.abspath(sys.argv[0]), ROOT)
        self.meta = dict(run_id=run_id, purpose=purpose, command=" ".join(["python", script] + sys.argv[1:]),
                         cwd=os.path.relpath(os.getcwd(), ROOT),
                         started_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                         git_commit=_git("rev-parse", "HEAD"), git_dirty=bool(_git("status", "--porcelain")),
                         platform=platform.platform(), versions=_versions(modules), config=dict(config or {}),
                         inputs=list(inputs), outputs=[], shapes={}, metrics={}, notes=[], raw_eeg_used=False,
                         file_sha256={p: _sha(os.path.join(ROOT, p)) for p in [script, "research/validation/_runlog.py", *inputs]},
                         exit_status="running")
        self._t0 = time.time()
        self._warn = collections.Counter()
        self._log = open(os.path.join(self.dir, "stdout.log"), "w", encoding="utf-8")
        self._err = open(os.path.join(self.dir, "stderr.log"), "w", encoding="utf-8")
        self._stdout, self._stderr = sys.stdout, sys.stderr
        sys.stdout = _Tee(self._stdout, self._log)
        sys.stderr = _Tee(self._stderr, self._err)
        self._orig_showwarning = warnings.showwarning
        warnings.simplefilter("always")
        warnings.showwarning = self._showwarning
        self._closed = False
        atexit.register(self._abort)

    def _showwarning(self, message, category, filename, lineno, file=None, line=None):
        self._warn[(category.__name__, str(message).splitlines()[0][:300])] += 1

    def add_warnings(self, counter):
        """Merge warnings collected in worker processes: iterable of ((category, message), count)."""
        for k, v in dict(counter).items():
            self._warn[tuple(k) if not isinstance(k, tuple) else k] += v

    def shape(self, name, shape):
        self.meta["shapes"][name] = list(shape)

    def metric(self, name, value):
        self.meta["metrics"][name] = value

    def output(self, path):
        self.meta["outputs"].append(os.path.relpath(path, ROOT))

    def note(self, text):
        self.meta["notes"].append(text)

    def _write(self):
        self.meta["finished_utc"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        self.meta["duration_sec"] = round(time.time() - self._t0, 2)
        self.meta["warnings_total"] = int(sum(self._warn.values()))
        self.meta["warnings_distinct"] = len(self._warn)
        with open(os.path.join(self.dir, "warnings.log"), "w", encoding="utf-8") as f:
            for (cat, msg), n in self._warn.most_common():
                f.write(f"{n}\t{cat}\t{msg}\n")
        with open(os.path.join(self.dir, "run.json"), "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=1, default=str)

    def _abort(self):
        if not self._closed:
            self.meta["exit_status"] = "aborted (exception or early exit; see stderr.log)"
            self._restore()
            self._write()

    def _restore(self):
        sys.stdout, sys.stderr = self._stdout, self._stderr
        warnings.showwarning = self._orig_showwarning
        self._log.close()
        self._err.close()

    def close(self):
        self.meta["exit_status"] = "ok"
        self._closed = True
        self._restore()
        self._write()
        print(f"[run] {self.meta['run_id']} done in {self.meta['duration_sec']} s, warnings={self.meta['warnings_total']} "
              f"-> {os.path.relpath(self.dir, ROOT)}/run.json")
