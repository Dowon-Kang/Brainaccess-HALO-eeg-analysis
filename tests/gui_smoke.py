r"""Optional real PsychoPy/Qt/OpenGL smoke test with synthetic keyboard responses.

Run from the project root: .venv\Scripts\python.exe -X utf8 tests\gui_smoke.py
Opens small windows, closes them automatically, and uses a temporary CSV directory.
This checks rendering/integration, not display calibration or real keyboard latency.
"""

import csv
import importlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import python_sart as task
from sart_data import INFO_FIELDS


INFO = ["SMOKE_TEST", "1", "High-Stimulation", "C0", "Female", "21", "Junior", "Yes", "QA"]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    task.load_psychopy()
    from psychopy.gui import qtgui
    QtCore = importlib.import_module(f"{qtgui.haveQt}.QtCore")
    # Exercise the real dialog API, including the mapping returned by PsychoPy 2026.
    class AutoDialog(task.gui.Dlg):
        def addField(self, key, *args, **kwargs):
            if key in INFO_FIELDS:
                value = INFO[INFO_FIELDS.index(key)]
                kwargs['initial'] = kwargs['choices'].index(value) if kwargs.get('choices') else value
            return super().addField(key, *args, **kwargs)

        def show(self):
            QtCore.QTimer.singleShot(200, self.accept)
            return super().show()

    with patch.object(task.gui, 'Dlg', AutoDialog):
        assert task.part_info_gui() == INFO, 'Real dialog returned incorrect participant values'
    print('Real Qt participant dialog: OK')

    state = {'trial': 0, 'responded': False}
    real_trial = task.sart_trial

    def wrapped_trial(*args, **kwargs):
        state['trial'] += 1
        state['responded'] = False
        return real_trial(*args, **kwargs)

    def keyboard(keyList=None, timeStamped=False, **kwargs):
        if timeStamped is not False:
            rt = float(timeStamped.getTime())
            if state['trial'] == 5 and rt >= 0.1:
                return [('escape', rt)]
            # Fixed order starts 1, 2, 3, 4: Go correct, omission, commission, Go correct.
            delay = {1: 0.1, 3: 0.3, 4: 0.4}.get(state['trial'])
            if delay is not None and rt >= delay and not state['responded']:
                state['responded'] = True
                return [('space', rt)]
            return []
        if keyList and 'b' in keyList:
            return ['b']
        if keyList and 'space' in keyList:
            return ['space']
        return []

    with tempfile.TemporaryDirectory(prefix='sart_gui_smoke_') as directory:
        root = Path(directory)
        with patch.object(task.event, 'getKeys', keyboard), \
             patch.object(task, 'sart_trial', wrapped_trial), \
             patch.object(task, 'SHOW_COUNTDOWN', False):
            for phase in ('pre', 'post'):
                state['trial'] = 0
                result = task.sart(path=root, part_info=INFO, phase=phase,
                                   fixed=True, reps=1, fullscr=False)
                assert result['completed_trials'] == 4
                assert abs(result['go_omission_rate_pct'] - 100 / 3) < 1e-9
                assert result['nogo_commission_rate_pct'] == 100
                assert result['median_correct_go_rt_ms'] >= 100
        raw_paths = list((root / 'raw').glob('*.csv'))
        trials = [row for path in raw_paths for row in read_csv(path)]
        overall = [row for row in read_csv(root / 'summary.csv') if row['window'] == 'overall']
        assert len(raw_paths) == 2
        assert len(trials) == 8 and len(overall) == 2
        assert len({row['run_id'] for row in trials}) == 2
        assert {row['phase'] for row in trials} == {'pre', 'post'}
        assert all(row['status'] == 'ABORTED' for row in overall)
        assert all(float(row['stimulus_onset_elapsed_s']) >= 0 for row in trials)
        assert all((root / row['raw_file']).is_file() for row in overall)
    print('Real PsychoPy window, digit/mask, PRE/POST raw CSV, mid-block ESC: OK')
    print('GUI_SMOKE_OK (synthetic responses; temporary data removed)')


if __name__ == '__main__':
    main()
