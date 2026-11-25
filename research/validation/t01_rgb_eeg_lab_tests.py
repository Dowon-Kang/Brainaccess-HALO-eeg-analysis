"""T-01  Run the existing rgb-eeg-lab test suite (synthetic data only) and log the result.

Command executed: python -m pytest tests -q -p no:cacheprovider   (cwd = rgb-eeg-lab)
The suite is the user's own code; this wrapper only records command, versions, duration, exit code and output.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _runlog import ROOT, Run  # noqa: E402

run = Run("T01", "Existing rgb-eeg-lab pytest suite (synthetic data, user code unchanged)",
          inputs=["rgb-eeg-lab/tests/test_pipeline.py", "rgb-eeg-lab/scripts/xdf_qc.py", "rgb-eeg-lab/scripts/train_svm.py",
                  "rgb-eeg-lab/scripts/protocol.py", "rgb-eeg-lab/config/protocol.json"],
          modules=("numpy", "scipy", "sklearn", "mne", "pyxdf", "pylsl", "pytest", "matplotlib"),
          config=dict(command="python -m pytest tests -q -p no:cacheprovider", cwd="rgb-eeg-lab"))
cp = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
                    cwd=os.path.join(ROOT, "rgb-eeg-lab"), capture_output=True, text=True)
print(cp.stdout)
if cp.stderr:
    sys.stderr.write(cp.stderr)
last = [l for l in cp.stdout.splitlines() if l.strip()][-1] if cp.stdout.strip() else ""
run.metric("pytest_exit_code", cp.returncode)
run.metric("pytest_summary", last)
run.close()
