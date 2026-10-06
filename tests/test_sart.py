import csv
import io
import itertools
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import python_sart as task
from sart_data import (
    INFO_FIELDS, ExperimentStore, calculate_summary, extract_info_values,
    summarize_trials, validate_participant_info, validate_settings,
)


INFO = ["P001", "1", "High-Stimulation", "C0", "Female", "21", "Junior", "Yes", "AB"]


def trial(number=1, rt=300.0, start=10.0, practice=False, trial_num=1):
    responded = rt is not None
    return dict(is_practice=practice, block_num=0 if practice else 1, trial_num=trial_num,
                stimulus=number, omit_number=3, trial_type="nogo" if number == 3 else "go",
                responded=responded, accuracy=int(not responded if number == 3 else responded),
                rt_ms=rt, font_size_cm=1.2, stimulus_onset_perf_s=start,
                trial_end_perf_s=start + 1.15)


def read_table(root, name):
    with (root / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class ValidationTests(unittest.TestCase):
    def test_modern_mapping_reads_values_and_legacy_list_still_works(self):
        mapping = dict(zip(INFO_FIELDS, INFO))
        # Iterating modern PsychoPy's IndexDict would yield field names.
        self.assertEqual(extract_info_values(mapping), INFO)
        self.assertEqual(validate_participant_info(mapping), INFO)
        self.assertEqual(validate_participant_info(INFO), INFO)

    def test_blank_labels_invalid_age_and_dropdowns_are_rejected(self):
        for index, value in [(0, ""), (0, "Part. Number: "), (0, "../P001"),
                             (1, "0"), (2, "invalid"), (3, "C3"), (4, "Please Select"),
                             (5, "-1"), (5, "21.5"), (5, "121"), (5, "Part. Age:"),
                             (6, "Please Select"), (7, ""), (8, "")]:
            with self.subTest(index=index, value=value):
                values = INFO.copy()
                values[index] = value
                with self.assertRaises(ValueError):
                    validate_participant_info(values)

    def test_whitespace_leading_zero_age_and_original_spelling(self):
        values = INFO.copy()
        values[0], values[5], values[6] = " P001 ", "021", "Sophmore"
        normalized = validate_participant_info(values)
        self.assertEqual(normalized[0], "P001")
        self.assertEqual(normalized[5:7], ["21", "Sophomore"])

    def test_invalid_task_configuration(self):
        for settings in [(0, 5, 3, "pre"), (1, 0, 3, "pre"), (1, 5, 10, "pre"),
                         (1, 5, 3, "other"), (True, 5, 3, "pre")]:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                validate_settings(*settings)


class SummaryTests(unittest.TestCase):
    def test_known_accuracy_denominators_and_correct_go_rt(self):
        rows = [trial(rt=200), trial(rt=400), trial(rt=None),
                trial(number=3, rt=None), trial(number=3, rt=100),
                trial(number=3, rt=99, practice=True)]
        metrics = summarize_trials(rows, 3)
        self.assertEqual(metrics["completed_trials"], 5)
        self.assertAlmostEqual(metrics["overall_accuracy_pct"], 60)
        self.assertAlmostEqual(metrics["go_omission_rate_pct"], 100 / 3)
        self.assertEqual(metrics["nogo_commission_rate_pct"], 50)
        self.assertAlmostEqual(metrics["balanced_accuracy_pct"], (200 / 3 + 50) / 2)
        self.assertEqual(metrics["median_correct_go_rt_ms"], 300)
        self.assertAlmostEqual(metrics["go_rt_sd_ms"], 141.421356237)
        self.assertAlmostEqual(metrics["go_rt_cv"], 0.47140452079)

    def test_empty_or_missing_class_is_not_zero_error(self):
        empty = summarize_trials([], 3)
        self.assertIsNone(empty["overall_accuracy_pct"])
        self.assertIsNone(empty["go_omission_rate_pct"])
        self.assertIsNone(empty["nogo_commission_rate_pct"])
        go_only = summarize_trials([trial()], 3)
        self.assertEqual(go_only["go_omission_rate_pct"], 0)
        self.assertIsNone(go_only["nogo_commission_rate_pct"])
        self.assertIsNone(go_only["balanced_accuracy_pct"])
        self.assertIsNone(go_only["go_rt_sd_ms"])

    def test_time_windows_use_first_main_onset_and_exact_boundaries(self):
        rows = [trial(start=10, practice=True), trial(start=100), trial(start=219.9),
                trial(start=220), trial(start=339.9), trial(start=340)]
        summary = calculate_summary(rows, 3)
        self.assertEqual(summary["completed_trials"], 5)
        self.assertEqual([item['metrics']['completed_trials'] for item in summary['time_bins']],
                         [2, 2, 1])
        self.assertEqual(summary["first_4min"]["completed_trials"], 4)
        self.assertFalse(summary["first_4min_partial"])
        self.assertTrue(summary["time_bins"][-1]["is_partial"])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "experiment"
        self.addCleanup(self.temp.cleanup)

    def store(self, phase="pre", info=None):
        store = ExperimentStore(self.root, INFO if info is None else info, phase,
                                blocks=1, reps=5 if phase == "pre" else 12, omit_number=3)
        self.addCleanup(store.close)
        return store

    def test_pre_post_rerun_raw_files_append_summary_and_checkpoint(self):
        pre = self.store()
        row = trial(start=pre.start_perf_s + 1)
        pre.record_trial(row)
        # The row is readable before finish() or return from its block.
        saved = read_table(self.root, pre.raw_path.relative_to(self.root))
        self.assertEqual(len(saved), 1)
        self.assertAlmostEqual(float(saved[0]["stimulus_onset_elapsed_s"]), 1)
        pre.finish("COMPLETED")
        post = self.store("post")
        post.record_trial(trial(number=3, rt=None, start=post.start_perf_s + 2))
        post.finish("ABORTED")
        rerun = self.store()
        rerun.finish("ABORTED")
        self.assertEqual(len({pre.run_id, post.run_id, rerun.run_id}), 3)
        raw_paths = list((self.root / "raw").glob("*.csv"))
        self.assertEqual(len(raw_paths), 3)
        trials = [*read_table(self.root, pre.raw_path.relative_to(self.root)),
                  *read_table(self.root, post.raw_path.relative_to(self.root))]
        self.assertEqual(len(trials), 2)
        self.assertEqual(trials[1]["rt_ms"], "")
        self.assertEqual(trials[1]["accuracy"], "1")
        self.assertEqual(trials[0]["participant_id"], "P001")
        self.assertEqual(trials[0]["session"], "1")
        self.assertEqual(trials[0]["gender"], "Female")
        overall = [row for row in read_table(self.root, "summary.csv") if row['window'] == 'overall']
        self.assertEqual([row['status'] for row in overall], ['COMPLETED', 'ABORTED', 'ABORTED'])
        self.assertEqual(overall[1]["planned_main_trials"], "540")
        self.assertEqual(overall[2]["go_omission_rate_pct"], "")
        self.assertTrue(overall[0]["run_started_at"].endswith("+00:00"))
        self.assertEqual(overall[0]["raw_file"], str(pre.raw_path.relative_to(self.root)))
        self.assertEqual({file.name for file in self.root.iterdir()},
                         {"raw", "summary.csv"})

    def test_each_run_keeps_metadata_without_overwriting_previous_raw_data(self):
        first = self.store()
        first.record_trial(trial(start=first.start_perf_s + 1))
        first.finish("COMPLETED")
        before = first.raw_path.read_bytes()
        for index, value in [(4, "Male"), (3, "C1")]:
            with self.subTest(index=index):
                values = INFO.copy()
                values[index] = value
                current = self.store(info=values)
                current.record_trial(trial(start=current.start_perf_s + 1))
                current.finish("COMPLETED")
                saved = read_table(self.root, current.raw_path.relative_to(self.root))
                field = "gender" if index == 4 else "condition"
                self.assertEqual(saved[0][field], value)
                self.assertEqual(before, first.raw_path.read_bytes())

    def test_corrupt_summary_header_rejected_without_overwriting_it(self):
        self.root.mkdir()
        summary = self.root / "summary.csv"
        summary.write_text("wrong,header\n", encoding="utf-8")
        before = summary.read_bytes()
        with self.assertRaises(ValueError):
            self.store()
        self.assertEqual(summary.read_bytes(), before)

    def test_invalid_inputs_do_not_create_an_output_directory(self):
        values = INFO.copy()
        values[0] = ""
        with self.assertRaises(ValueError):
            self.store(info=values)
        self.assertFalse(self.root.exists())


class RuntimeTests(unittest.TestCase):
    def test_entry_point_selects_pre_and_post_trial_counts(self):
        for phase, reps in [("pre", 5), ("post", 12)]:
            with self.subTest(phase=phase), patch.object(task, 'sart') as run:
                self.assertEqual(task.main(["--phase", phase]), 0)
                self.assertEqual(run.call_args.kwargs['reps'], reps)
                self.assertEqual(run.call_args.kwargs['phase'], phase)

    def test_gui_uses_mapping_values(self):
        dialog = Mock(OK=True, data=dict(zip(INFO_FIELDS, INFO)))
        with patch.object(task, 'gui', SimpleNamespace(Dlg=Mock(return_value=dialog))):
            self.assertEqual(task.part_info_gui(), INFO)

    def test_gui_cancel_creates_no_run(self):
        dialog = Mock(OK=False)
        with patch.object(task, 'gui', SimpleNamespace(Dlg=Mock(return_value=dialog))):
            with self.assertRaises(task.ExperimentAbort):
                task.part_info_gui()

    def test_esc_mid_block_keeps_completed_trials_and_closes_window(self):
        def run_block(*args, **kwargs):
            kwargs['on_trial'](trial(start=task.time.perf_counter()))
            kwargs['on_trial'](trial(number=3, rt=None, start=task.time.perf_counter()))
            raise task.ExperimentAbort()

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            window = Mock()
            with patch.object(task, 'load_psychopy'), \
                 patch.object(task, 'visual', SimpleNamespace(Window=Mock(return_value=window))), \
                 patch.object(task, 'sart_init_inst'), patch.object(task, 'sart_act_task_inst'), \
                 patch.object(task, 'sart_countdown'), patch.object(task, 'show_final_feedback'), \
                 patch.object(task, 'sart_block', side_effect=run_block), redirect_stdout(io.StringIO()):
                summary = task.sart(path=root, part_info=INFO)
            self.assertEqual(summary['completed_trials'], 2)
            raw_path = next((root / 'raw').glob('*.csv'))
            self.assertEqual(len(read_table(root, raw_path.relative_to(root))), 2)
            self.assertEqual(read_table(root, 'summary.csv')[0]['status'], 'ABORTED')
            window.close.assert_called_once()

    def test_feedback_does_not_reduce_main_trial_count_and_fixed_order_is_preserved(self):
        stimulus = SimpleNamespace(TextStim=Mock(), Circle=Mock())

        def factorial(factors):
            return [dict(zip(factors, values)) for values in itertools.product(*factors.values())]

        def handler(sequence, nReps, method):
            return iter(sequence * nReps)

        def response(*args):
            return trial(number=args[-4], practice=args[-2] == 0, trial_num=args[-3])

        recorded = []
        with patch.object(task, 'visual', stimulus), \
             patch.object(task, 'event', SimpleNamespace(Mouse=Mock())), \
             patch.object(task, 'core', SimpleNamespace(Clock=Mock())), \
             patch.object(task, 'data', SimpleNamespace(createFactorialTrialList=factorial, TrialHandler=handler)), \
             patch.object(task, 'sart_trial', side_effect=response), redirect_stdout(io.StringIO()):
            main = task.sart_block(Mock(), True, 3, 5, 1, True, on_trial=recorded.append)
            practice = task.sart_block(Mock(), True, 3, 1, 0, False)
        self.assertEqual(len(main), 225)
        self.assertEqual(len(recorded), 225)
        self.assertEqual(len(practice), 18)
        self.assertEqual([row['stimulus'] for row in main[:18]], list(range(1, 10)) * 2)


class TrialTests(unittest.TestCase):
    def run_trial(self, number, responses):
        now = [0.0]
        pending = list(responses)
        reset_at = [None]
        callbacks = []

        def flip():
            now[0] += 1 / 60
            for callback in callbacks[:]:
                callback()
            callbacks.clear()

        def reset():
            reset_at[0] = now[0]

        def get_keys(**kwargs):
            elapsed = now[0] - reset_at[0]
            ready = [(key, rt) for key, rt in pending if rt <= elapsed]
            pending[:] = [(key, rt) for key, rt in pending if rt > elapsed]
            return ready

        clock = SimpleNamespace(reset=reset)
        win = SimpleNamespace(flip=flip, callOnFlip=callbacks.append)
        stim = Mock()
        with patch.object(task, 'time', SimpleNamespace(perf_counter=lambda: now[0])), \
             patch.object(task, 'core', SimpleNamespace(wait=lambda duration: now.__setitem__(0, now[0] + duration))), \
             patch.object(task, 'event', SimpleNamespace(clearEvents=Mock(), getKeys=get_keys)):
            row = task.sart_trial(win, 3, stim, stim, stim, clock,
                                  1.2, number, 1, 1, Mock())
        self.assertAlmostEqual(reset_at[0], 1 / 60)
        self.assertAlmostEqual(row['stimulus_onset_perf_s'], reset_at[0])
        return row

    def test_response_scoring_in_digit_and_mask_first_response_only(self):
        for number, responses, accuracy, rt in [
                (1, [("space", 0.1), ("space", 0.2)], 1, 100),
                (1, [("space", 0.5)], 1, 500),
                (1, [], 0, None), (3, [], 1, None),
                (3, [("space", 0.3)], 0, 300)]:
            with self.subTest(number=number, responses=responses):
                row = self.run_trial(number, responses)
                self.assertEqual(row['accuracy'], accuracy)
                self.assertEqual(row['rt_ms'], rt)

    def test_response_past_window_is_excluded(self):
        # Responses after the fixed 1.15-second deadline are excluded.
        row = self.run_trial(1, [("space", 1.175)])
        self.assertEqual(row['accuracy'], 0)
        self.assertIsNone(row['rt_ms'])

    def test_escape_aborts_current_trial(self):
        with self.assertRaises(task.ExperimentAbort):
            self.run_trial(1, [("escape", 0.3)])

    def test_unexpected_error_saves_completed_trials_and_propagates(self):
        def run_block(*args, **kwargs):
            kwargs['on_trial'](trial(start=task.time.perf_counter()))
            raise RuntimeError('simulated display error')

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            window = Mock()
            with patch.object(task, 'load_psychopy'), \
                 patch.object(task, 'visual', SimpleNamespace(Window=Mock(return_value=window))), \
                 patch.object(task, 'sart_init_inst'), patch.object(task, 'sart_act_task_inst'), \
                 patch.object(task, 'sart_countdown'), patch.object(task, 'sart_block', side_effect=run_block), \
                 redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, 'simulated display error'):
                task.sart(path=root, part_info=INFO)
            raw_path = next((root / 'raw').glob('*.csv'))
            self.assertEqual(len(read_table(root, raw_path.relative_to(root))), 1)
            self.assertEqual(read_table(root, 'summary.csv')[0]['status'], 'ERROR')
            window.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
