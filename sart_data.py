"""Validation, behavioral metrics, and CSV storage without PsychoPy dependencies."""

import csv
import math
import statistics
import time
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path


INFO_FIELDS = (
    "Part. Number: ", "Session: ", "Short-form Topic: ", "Condition: ",
    "Part. Gender: ", "Part. Age:  ", "Part. Year in School: ",
    "Do you have normal or corrected-to-normal vision?", "DIS Initials:  ",
)
TOPICS = ("High-Stimulation", "Nature-Calm", "Study-Learning")
CONDITIONS = ("C0", "C1", "C2")
GENDERS = ("Male", "Female", "Other")
SCHOOL_YEARS = (
    "Freshman", "Sophomore", "Junior", "Senior",
    *[f"{n}{'st' if n == 1 else 'nd' if n == 2 else 'rd' if n == 3 else 'th'} Year Graduate Student"
      for n in range(1, 7)],
)
PARTICIPANT_FIELDS = (
    "participant_id", "gender", "age", "school_year", "normal_vision",
)
SESSION_FIELDS = (
    "session_id", "participant_id", "session", "condition", "shortform_topic",
    "exp_initials",
)
TRIAL_FIELDS = (
    "participant_id", "session_id", "run_id", "phase", "is_practice",
    "block_num", "trial_num", "stimulus", "omit_number", "trial_type",
    "responded", "accuracy", "rt_ms", "font_size_cm",
    "stimulus_onset_elapsed_s", "trial_end_elapsed_s",
    "stimulus_onset_perf_s", "trial_end_perf_s", "timing_function",
)
METRIC_FIELDS = (
    "completed_trials", "correct_trials", "overall_accuracy_pct",
    "balanced_accuracy_pct", "go_trials", "go_omissions", "go_omission_rate_pct",
    "go_accuracy_pct", "nogo_trials", "nogo_commission_errors",
    "nogo_commission_rate_pct", "nogo_accuracy_pct", "median_correct_go_rt_ms",
    "mean_correct_go_rt_ms", "go_rt_sd_ms", "go_rt_cv",
)
SUMMARY_FIELDS = (
    "participant_id", "session_id", "run_id", "phase", "status",
    "run_started_at", "run_ended_at", "exp_initials", "blocks", "reps",
    "omit_number", "fixed_order", "practice_enabled", "response_feedback",
    "planned_main_trials", "window", "window_start_s", "window_end_s",
    "is_partial", *METRIC_FIELDS,
)


def extract_info_values(info):
    """Read values explicitly: modern PsychoPy returns an IndexDict, not a list."""
    if isinstance(info, Mapping):
        try:
            return [info[field] for field in INFO_FIELDS]
        except KeyError as exc:
            raise ValueError(f"Missing participant field: {exc.args[0]}") from exc
    values = list(info)
    if len(values) != len(INFO_FIELDS):
        raise ValueError("Expected nine participant/session fields.")
    return values


def validate_participant_info(info):
    values = [str(value).strip() if value is not None else ""
              for value in extract_info_values(info)]
    labels = {field.strip() for field in INFO_FIELDS}
    if any(not value or value in labels or value == "Please Select" for value in values):
        raise ValueError("Complete every participant and session field.")
    participant, session, topic, condition, gender, age, year, vision, initials = values
    if not all(char.isalnum() or char in "_-" for char in participant):
        raise ValueError("Participant ID may contain letters, numbers, '_' and '-' only.")
    if session not in ("1", "2", "3"):
        raise ValueError("Session must be 1, 2 or 3.")
    if topic not in TOPICS or condition not in CONDITIONS or gender not in GENDERS:
        raise ValueError("Choose a valid topic, condition and gender.")
    if not age.isdecimal() or not 1 <= int(age) <= 120:
        raise ValueError("Age must be a whole number between 1 and 120.")
    # Accept the spelling in previously entered participant information.
    year = "Sophomore" if year == "Sophmore" else year
    if year not in SCHOOL_YEARS or vision not in ("Yes", "No"):
        raise ValueError("Choose a valid school year and vision response.")
    return [participant, session, topic, condition, gender, str(int(age)),
            year, vision, initials]


def validate_settings(blocks, reps, omit_number, phase):
    if type(blocks) is not int or blocks < 1 or type(reps) is not int or reps < 1:
        raise ValueError("blocks and reps must be positive integers.")
    if type(omit_number) is not int or omit_number not in range(1, 10):
        raise ValueError("omitNum must be an integer from 1 to 9.")
    if phase not in ("pre", "post"):
        raise ValueError("phase must be 'pre' or 'post'.")


def _percent(numerator, denominator):
    return numerator / denominator * 100.0 if denominator else None


def summarize_trials(rows, omit_number):
    """Only completed main trials; RT statistics use correct Go responses."""
    rows = [row for row in rows if not row["is_practice"]]
    go = [row for row in rows if row["stimulus"] != omit_number]
    nogo = [row for row in rows if row["stimulus"] == omit_number]
    correct = sum(row["accuracy"] for row in rows)
    omissions = sum(not row["responded"] for row in go)
    commissions = sum(row["responded"] for row in nogo)
    go_accuracy = _percent(len(go) - omissions, len(go))
    nogo_accuracy = _percent(len(nogo) - commissions, len(nogo))
    rts = [row["rt_ms"] for row in go if row["accuracy"] == 1 and row["rt_ms"] is not None]
    mean = statistics.mean(rts) if rts else None
    sd = statistics.stdev(rts) if len(rts) >= 2 else None
    return {
        "completed_trials": len(rows), "correct_trials": correct,
        "overall_accuracy_pct": _percent(correct, len(rows)),
        "balanced_accuracy_pct": ((go_accuracy + nogo_accuracy) / 2
                                  if go_accuracy is not None and nogo_accuracy is not None else None),
        "go_trials": len(go), "go_omissions": omissions,
        "go_omission_rate_pct": _percent(omissions, len(go)),
        "go_accuracy_pct": go_accuracy, "nogo_trials": len(nogo),
        "nogo_commission_errors": commissions,
        "nogo_commission_rate_pct": _percent(commissions, len(nogo)),
        "nogo_accuracy_pct": nogo_accuracy,
        "median_correct_go_rt_ms": statistics.median(rts) if rts else None,
        "mean_correct_go_rt_ms": mean, "go_rt_sd_ms": sd,
        "go_rt_cv": sd / mean if sd is not None and mean not in (None, 0) else None,
    }


def calculate_summary(rows, omit_number):
    rows = [row for row in rows if not row["is_practice"]]
    metrics = summarize_trials(rows, omit_number)
    first = min((row["stimulus_onset_perf_s"] for row in rows), default=0.0)
    duration = max((row["trial_end_perf_s"] - first for row in rows), default=0.0)
    bins = []
    for index in range(int(math.ceil(duration / 120.0))):
        start, end = index * 120.0, (index + 1) * 120.0
        selected = [row for row in rows if start <= row["stimulus_onset_perf_s"] - first < end]
        if selected:
            bins.append({"window": f"time_bin_{index + 1}", "start_s": start,
                         "end_s": min(end, duration), "is_partial": duration < end,
                         "metrics": summarize_trials(selected, omit_number)})
    first_four = [row for row in rows if row["stimulus_onset_perf_s"] - first < 240.0]
    return {
        **metrics, "duration_s": duration, "time_bins": bins,
        "first_4min": summarize_trials(first_four, omit_number),
        "first_4min_partial": duration < 240.0,
    }


def _ensure_csv(path, fields):
    if path.exists() and path.stat().st_size:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            if next(csv.reader(handle), None) != list(fields):
                raise ValueError(f"CSV header differs from the expected schema: {path}")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.DictWriter(handle, fieldnames=fields).writeheader()


def _read_csv(path, fields):
    if not path.exists() or not path.stat().st_size:
        return []
    _ensure_csv(path, fields)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _append_csv(path, fields, rows):
    _ensure_csv(path, fields)
    with path.open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=fields).writerows(rows)


class ExperimentStore:
    """One running task, with completed trials flushed immediately to trials.csv.

    Intended for one experiment process at a time in the output directory.
    Metadata is immutable so a mismatched pre/post cannot silently overwrite it.
    """

    def __init__(self, path, info, phase, *, blocks, reps, omit_number,
                 fixed=False, practice=False, response_feedback=True):
        validate_settings(blocks, reps, omit_number, phase)
        values = validate_participant_info(info)
        participant, session, topic, condition, gender, age, year, vision, initials = values
        self.path = Path(path).resolve()
        self.phase = phase
        self.participant_id = participant
        self.session_id = uuid.uuid5(uuid.NAMESPACE_URL, f"sart:{participant}:{session}").hex
        self.run_id = uuid.uuid4().hex
        self.omit_number = omit_number
        self.started_at = datetime.now(timezone.utc)
        self.start_perf_s = time.perf_counter()
        self.settings = dict(blocks=blocks, reps=reps, omit_number=omit_number,
                             fixed_order=int(fixed), practice_enabled=int(practice),
                             response_feedback=int(response_feedback),
                             planned_main_trials=blocks * reps * 45,
                             exp_initials=initials)
        self.rows = []
        self._finished = False
        participant_row = dict(zip(PARTICIPANT_FIELDS, (participant, gender, age, year, vision)))
        session_row = dict(zip(SESSION_FIELDS, (self.session_id, participant, session,
                                               condition, topic, initials)))
        participants = _read_csv(self.path / "participants.csv", PARTICIPANT_FIELDS)
        sessions = _read_csv(self.path / "sessions.csv", SESSION_FIELDS)
        self._check_metadata(participants, participant_row, "participant_id", PARTICIPANT_FIELDS)
        self._check_metadata(sessions, session_row, "session_id", SESSION_FIELDS[:-1])
        self.path.mkdir(parents=True, exist_ok=True)
        schemas = {"participants.csv": PARTICIPANT_FIELDS, "sessions.csv": SESSION_FIELDS,
                   "trials.csv": TRIAL_FIELDS, "summary.csv": SUMMARY_FIELDS}
        # Check every existing header before writing metadata to any file.
        for name, fields in schemas.items():
            csv_path = self.path / name
            if csv_path.exists() and csv_path.stat().st_size:
                _ensure_csv(csv_path, fields)
        for name, fields in schemas.items():
            _ensure_csv(self.path / name, fields)
        if not any(row["participant_id"] == participant for row in participants):
            _append_csv(self.path / "participants.csv", PARTICIPANT_FIELDS, [participant_row])
        if not any(row["session_id"] == self.session_id for row in sessions):
            _append_csv(self.path / "sessions.csv", SESSION_FIELDS, [session_row])
        self._trial_handle = (self.path / "trials.csv").open("a", encoding="utf-8", newline="")
        self._trial_writer = csv.DictWriter(self._trial_handle, fieldnames=TRIAL_FIELDS)

    @staticmethod
    def _check_metadata(existing, incoming, key, fields):
        matching = [row for row in existing if row[key] == incoming[key]]
        if len(matching) > 1:
            raise ValueError(f"Duplicate {key} in existing CSV: {incoming[key]}")
        if matching and any(matching[0][field] != str(incoming[field]) for field in fields):
            raise ValueError(f"Existing information differs for {key}={incoming[key]}. "
                             "Check the participant/session information before continuing.")

    def record_trial(self, row):
        if self._finished:
            raise RuntimeError("Cannot add trials after finishing a run.")
        record = {
            "participant_id": self.participant_id, "session_id": self.session_id,
            "run_id": self.run_id, "phase": self.phase,
            **{key: int(row[key]) if key in ("responded", "is_practice") else row[key]
               for key in TRIAL_FIELDS if key in row},
            "stimulus_onset_elapsed_s": row["stimulus_onset_perf_s"] - self.start_perf_s,
            "trial_end_elapsed_s": row["trial_end_perf_s"] - self.start_perf_s,
            "timing_function": "time.perf_counter; RT clock reset on stimulus flip",
        }
        self._trial_writer.writerow(record)
        self._trial_handle.flush()
        self.rows.append(dict(row))

    def finish(self, status):
        if self._finished:
            raise RuntimeError("Run already finished.")
        if status not in ("COMPLETED", "ABORTED", "ERROR"):
            raise ValueError("Invalid run status.")
        self._trial_handle.close()
        summary = calculate_summary(self.rows, self.omit_number)
        base = dict(participant_id=self.participant_id, session_id=self.session_id,
                    run_id=self.run_id, phase=self.phase, status=status,
                    run_started_at=self.started_at.isoformat(),
                    run_ended_at=datetime.now(timezone.utc).isoformat(), **self.settings)
        windows = [
            dict(window="overall", start_s=0.0, end_s=summary["duration_s"],
                 is_partial=status != "COMPLETED", metrics=summary),
            dict(window="first_4min", start_s=0.0, end_s=min(240.0, summary["duration_s"]),
                 is_partial=summary["first_4min_partial"], metrics=summary["first_4min"]),
            *summary["time_bins"],
        ]
        records = [{**base, "window": window["window"],
                    "window_start_s": window["start_s"], "window_end_s": window["end_s"],
                    "is_partial": int(window["is_partial"]),
                    **{key: window["metrics"][key] for key in METRIC_FIELDS}}
                   for window in windows]
        _append_csv(self.path / "summary.csv", SUMMARY_FIELDS, records)
        self._finished = True
        return summary

    def close(self):
        self._trial_handle.close()
