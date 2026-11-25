"""합성 데이터 회귀·고장 주입 테스트 (장비 불필요).
PowerShell:  python -m pytest tests -q        (또는  python tests\\test_pipeline.py)

정상: 연습 6시퀀스(36) / 1블록 18(108) / 본측정 90(540) 단계 마커 정합성(6단계 설계), 특징 shape (n,64)/(n,32)
      구버전 8단계 기록(phases= 없음)도 검사, 본측정 29분
고장 주입 → FAIL 또는 시행 제외:
  시퀀스 통째 누락, 마커 1개 누락, 중복, 단계 순서 오류, 색 순서 오류, EXP_START 없음,
  누락 표본, 과대 진폭, 기준구간 진폭, 평탄 신호, 시작 5초 이내, 잘못된 채널 라벨,
  단위 미확정(UNVERIFIED)·단위 오선언(FAIL), 유효 시행 0
계획서 일치: 인과 필터(미래 샘플 무영향)·구간 재시작, 반열린 구간 경계, seed 규칙, 본측정 차단
분석: SVM 블록 중첩 CV — 신호 있으면 BA>우연, 시퀀스 셔플이면 ≈우연, PROVISIONAL 거부
도구: flip→LSL 시각 환산, 포토다이오드 본측정 차단, 현장값 입력 검증·변경기록, env_check 실행
"""
import copy
import csv
import os
import subprocess
import sys
import tempfile

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import protocol  # noqa: E402
import xdf_qc as q  # noqa: E402

CFG = protocol.load()
FS = float(CFG["eeg"]["fs"])
LEAD = 10.0          # 녹화 시작 → EXP_START (시작 5초 배제 규칙 밖으로)


def cfg_with(raw_unit="keep", **design):
    """design 덮어쓰기. raw_unit=None이면 단위 미확정 경로 검사 (실제 config 값과 무관하게)."""
    c = copy.deepcopy(CFG)
    c["design"].update(design)
    if raw_unit != "keep":
        c["eeg"]["raw_unit"] = raw_unit
    return c


def synth(mode="practice", pid="T01", cfg=CFG, signal=True, noise=4.0, seed=0, unit_scale=1.0, start_block=1,
          legacy=False, session=1):
    """legacy=True: 스크립트 3.x 기록 흉내 (v2.0 8단계, EXP_START에 phases= 없음)."""
    blocks, pcpb = q.expected_by_mode(cfg, mode)
    sd = protocol.seed_for(cfg, pid, practice=mode != "main", session=session)
    plan = protocol.sequence_plan(sd, blocks, pcpb, cfg["design"]["max_same_color_run"])
    phases = protocol.LEGACY_PHASES if legacy else protocol.phases(cfg)
    t0 = LEAD
    markers = [f"EXP_START|mode={mode}|blocks={blocks}|pcpb={pcpb}|seed={sd}"
               + ("" if legacy else f"|session={session}") + f"|nseq={len(plan)}|fps=60.000"
               f"|frames=180|provisional=0|start_block={start_block}"
               + ("" if legacy else f"|phases={protocol.phases_tag(phases)}") + "|version=test"]
    mt = [t0]; t0 += 1.0
    csv_rows = []
    prev = 0
    for i, (b, c) in enumerate(plan, start=1):
        if b < start_block:
            continue
        if b != prev:
            if prev:
                markers += [f"BLOCK_END|b{prev}", f"REST_START|b{b}", f"REST_END|b{b}"]; mt += [t0, t0, t0 + 1]; t0 += 2
            markers.append(f"BLOCK_START|b{b}"); mt.append(t0); t0 += 0.5
            prev = b
        for ph, rep in phases:
            m = f"b{b}|s{i:03d}|{ph}{rep}|{c}"
            markers.append(m); mt.append(t0)
            csv_rows.append(dict(phase=ph, marker=m, onset_lsl=f"{t0:.6f}"))
            t0 += 3.0
    markers += [f"BLOCK_END|b{prev}", "EXP_END"]; mt += [t0, t0]
    rng = np.random.default_rng(seed)
    t = np.arange(0, t0 + 5, 1 / FS)
    x = rng.normal(0, noise, (len(t), 4))
    if signal:
        f0 = {"R": 10.0, "G": 20.0, "B": 6.0}
        for m, tt in zip(markers, mt):
            g = q.MARKER_RE.match(m)
            if g and g.group(3) == "obs":
                sl = (t >= tt + 0.1) & (t < tt + 1.5)
                x[sl, 2:] += 8 * np.sin(2 * np.pi * f0[g.group(5)] * t[sl])[:, None]
    return dict(x=x * unit_scale, t=t, labels=list(CFG["eeg"]["channels"]), unit=None,
                markers=markers, mt=np.array(mt)), csv_rows


def run_qc(data, cfg=CFG, **kw):
    return q.run(data, "obs", tempfile.mkdtemp(), cfg, **kw)


def st(res, name):
    return res["checks"].status(name)


def drop(d, pred):
    keep = [i for i, m in enumerate(d["markers"]) if not pred(m)]
    d["markers"] = [d["markers"][i] for i in keep]; d["mt"] = d["mt"][keep]


def obs_onset(d, k=0):
    return [tt for m, tt in zip(d["markers"], d["mt"]) if "|obs" in m][k]


MARKER_CHECKS = ["EXP_START 기록", "모드별 설계", "중복 마커", "시퀀스 수", "시퀀스 내부 단계",
                 "단계 순서", "색·블록 순서(seed 재생성)", "종료/STOP", "단계 간격"]


# ------------------------------------------------------------------ 정상
@pytest.mark.parametrize("mode,n_seq", [("practice", 6), ("block", 18), ("main", 90)])
def test_marker_counts_by_mode(mode, n_seq):
    d, _ = synth(mode, signal=False)
    n_phase = sum(1 for m in d["markers"] if q.MARKER_RE.match(m))
    assert n_phase == n_seq * len(protocol.phases(CFG)) == n_seq * 6
    rows, ev = q.parse_markers(d["markers"], d["mt"])
    ck = q.Checks(); q.check_markers(rows, ev, CFG, ck)
    assert all(ck.status(c) == "PASS" for c in MARKER_CHECKS), ck.text()


def test_legacy_8phase_record():
    d, _ = synth("main", signal=False, legacy=True)                # P02·P08 같은 이전 설계 기록
    assert sum(1 for m in d["markers"] if q.MARKER_RE.match(m)) == 720
    rows, ev = q.parse_markers(d["markers"], d["mt"])
    ck = q.Checks(); q.check_markers(rows, ev, CFG, ck)
    assert all(ck.status(c) == "PASS" for c in MARKER_CHECKS), ck.text()
    assert any("이전 설계" in n for n in ck.notes)
    drop(d, lambda m: m.startswith("b1|s002|img2"))                 # 구설계 단계 누락도 검출
    rows, ev = q.parse_markers(d["markers"], d["mt"])
    ck = q.Checks(); q.check_markers(rows, ev, CFG, ck)
    assert ck.status("시퀀스 내부 단계") == "FAIL"


def test_main_duration_29min():
    d, st_ = CFG["design"], CFG["stimulus"]
    seq_sec = len(d["phases"]) * st_["phase_sec"]
    total = d["blocks"] * d["per_color_per_block"] * 3 * seq_sec + (d["blocks"] - 1) * d["rest_sec"]
    assert seq_sec == 18 and total == 29 * 60
    assert protocol.phases(CFG) == [("gray", 1), ("obs", 1), ("gray", 2), ("obs", 2), ("gray", 3), ("img", 1)]
    assert protocol.parse_phases_tag(protocol.phases_tag(protocol.phases(CFG))) == protocol.phases(CFG)
    assert protocol.parse_phases_tag(None) == protocol.LEGACY_PHASES


def test_resume_part_markers():
    d, _ = synth("main", signal=False, start_block=3)              # 블록 3–5 = 시퀀스 37–90
    rows, ev = q.parse_markers(d["markers"], d["mt"])
    ck = q.Checks(); q.check_markers(rows, ev, CFG, ck)
    assert all(ck.status(c) == "PASS" for c in MARKER_CHECKS), ck.text()
    assert "54/54" in ck.text()
    drop(d, lambda m: "|s040|" in m)                               # 이어 하기 파트 안의 누락은 검출
    rows, ev = q.parse_markers(d["markers"], d["mt"])
    ck = q.Checks(); q.check_markers(rows, ev, CFG, ck)
    assert ck.status("시퀀스 수") == "FAIL"


def test_full_pipeline_block_mode():
    d, rows = synth("block")
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["phase", "marker", "onset_lsl"]); w.writeheader(); w.writerows(rows)
    res = run_qc(d, stim_csv=fh.name, cli_unit="uV")
    os.unlink(fh.name)
    unv = [n for n, st_, _ in res["checks"].rows if st_ != "PASS"]
    assert unv == ["모니터 입력 지연"], res["checks"].text()      # 포토다이오드 없이는 항상 UNVERIFIED
    assert res["X4"].shape == (36, 64) and res["X2"].shape == (36, 32)       # 18시퀀스 × 관찰 2회
    assert not res["bad"].any()


# ------------------------------------------------------------------ 마커 고장
def test_missing_whole_sequence():
    d, _ = synth(); drop(d, lambda m: "|s003|" in m)
    r = run_qc(d)
    assert st(r, "시퀀스 수") == "FAIL" and r["checks"].verdict() == "NO-GO"


def test_missing_single_marker():
    d, _ = synth(); drop(d, lambda m: m.startswith("b1|s002|img1"))
    assert st(run_qc(d), "시퀀스 내부 단계") == "FAIL"


def test_duplicate_marker():
    d, _ = synth()
    i = next(i for i, m in enumerate(d["markers"]) if "|obs1|" in m)
    d["markers"].insert(i + 1, d["markers"][i]); d["mt"] = np.insert(d["mt"], i + 1, d["mt"][i] + 0.01)
    assert st(run_qc(d), "중복 마커") == "FAIL"


def test_wrong_phase_order():
    d, _ = synth()
    i = next(i for i, m in enumerate(d["markers"]) if "|s001|obs1|" in m)
    j = next(i for i, m in enumerate(d["markers"]) if "|s001|gray2|" in m)
    d["mt"][i], d["mt"][j] = d["mt"][j], d["mt"][i]
    assert st(run_qc(d), "단계 순서") == "FAIL"


def test_wrong_color_order():
    d, _ = synth()
    c = next(m for m in d["markers"] if "|s001|" in m)[-1]
    other = "G" if c != "G" else "R"
    d["markers"] = [m[:-1] + other if "|s001|" in m else m for m in d["markers"]]
    assert st(run_qc(d), "색·블록 순서(seed 재생성)") == "FAIL"


def test_no_exp_start():
    d, _ = synth(); drop(d, lambda m: m.startswith("EXP_START"))
    assert st(run_qc(d), "EXP_START 기록") == "FAIL"


def test_stop_event_fails():
    d, _ = synth(); drop(d, lambda m: m == "EXP_END")
    d["markers"].append("STOP|b1|s006"); d["mt"] = np.append(d["mt"], d["mt"][-1])
    assert st(run_qc(d), "종료/STOP") == "FAIL"


# ------------------------------------------------------------------ EEG 고장
def test_missing_samples_excluded():
    d, _ = synth(signal=False)
    on = obs_onset(d, 0)
    cut = (d["t"] > on + 0.5) & (d["t"] < on + 0.7)
    d["x"], d["t"] = d["x"][~cut], d["t"][~cut]
    r = run_qc(d)
    assert st(r, "누락 표본") == "FAIL"
    assert "missing" in r["reasons"][0]


def test_large_amplitude_excluded():
    d, _ = synth(signal=False)
    on = obs_onset(d, 1)
    sl = (d["t"] > on + 0.8) & (d["t"] < on + 0.85)
    d["x"][sl, 0] += 150
    r = run_qc(d)
    assert {"abs", "ptp"} & set(r["reasons"][1])


def test_baseline_amplitude_excluded():
    d, _ = synth(signal=False)
    on = obs_onset(d, 2)
    sl = (d["t"] > on - 1.5) & (d["t"] < on - 1.45)
    d["x"][sl, 3] += 150
    assert "baseline_abs" in run_qc(d)["reasons"][2]


def test_flat_signal_excluded():
    d, _ = synth(signal=False)
    on = obs_onset(d, 3)
    sl = (d["t"] > on - 2.6) & (d["t"] < on + 2.6)
    d["x"][sl, 2] = 1.0
    assert "flat" in run_qc(d)["reasons"][3]


def test_startup_excluded():
    d, _ = synth(signal=False)
    on = obs_onset(d, 0)
    keep = d["t"] >= on - 4.0                  # 녹화가 첫 관찰 4초 전에 시작
    d["x"], d["t"] = d["x"][keep], d["t"][keep]
    assert run_qc(d)["reasons"][0] == ["startup"]


def test_wrong_channel_label():
    d, _ = synth(); d["labels"] = ["Fp1", "Fp2", "P3", "P4"]
    r = run_qc(d)
    assert st(r, "채널 라벨") == "FAIL" and r["X4"] is None


def test_units():
    d, _ = synth(unit_scale=1e-6)                                  # 장비가 V로 출력
    no_unit = cfg_with(raw_unit=None)
    r = run_qc(d, cfg=no_unit)
    assert st(r, "EEG 단위") == "UNVERIFIED"
    assert any("PROVISIONAL" in n for n in r["checks"].notes)
    assert st(run_qc(d, cfg=no_unit, cli_unit="uV"), "EEG 단위") == "FAIL"
    assert st(run_qc(d, cfg=no_unit, cli_unit="V"), "EEG 단위") == "PASS"
    assert st(run_qc(d, cfg=cfg_with(raw_unit="uV")), "EEG 단위") == "FAIL"   # config 단위와 신호 크기 불일치 검출


def test_zero_valid_trials():
    d, _ = synth(signal=False); d["x"][:] = 1.0
    r = run_qc(d)
    assert st(r, "[obs] 유효 시행") == "FAIL" and r["X4"] is None


# ------------------------------------------------------------------ 계획서 일치
def test_filter_is_causal_and_resets():
    flt = CFG["analysis"]["filter"]
    x = np.zeros((2000, 1)); x[1000] = 1.0
    y = q.causal_filter_segments(x, [(0, 2000)], FS, flt)
    assert np.allclose(y[:1000], 0)                                 # 미래 샘플이 과거에 영향 없음
    y2 = q.causal_filter_segments(x, [(0, 1000), (1000, 2000)], FS, flt)
    assert np.allclose(y2[:1000], 0) and not np.allclose(y2[1000:], 0)
    assert flt["order"] == 4 and flt["causal"] is True


def test_bins_half_open():
    an = CFG["analysis"]
    freqs = np.arange(3, 31, 1.0)
    assert [int(m.sum()) for m in protocol.bin_masks(freqs, an["bands_hz"])] == [1, 4, 5, 18]
    times = np.round(-2.5 + np.arange(1250) / FS, 6)
    tm = protocol.bin_masks(times, an["windows_sec"])
    assert times[tm[0]].min() == 0.1 and times[tm[0]].max() < 0.4 and times[tm[-1]].max() == 1.5
    assert an["n_cycles"] == 3 and an["bands_hz"][0] == [3, 4]


def test_stimulus_config_and_seed():
    import stim_rgb
    st_ = CFG["stimulus"]
    assert st_["colors_rgb255"] == {"R": [157, 0, 0], "G": [0, 89, 0], "B": [0, 0, 255]}
    assert st_["gray_rgb255"] == [76, 76, 76]
    assert protocol.seed_for(CFG, "P03", False) == 20261029
    assert protocol.seed_for(CFG, "P03", True) != 20261029
    # 변경3: 세션마다 seed 다름, 세션 1 = 기존 seed, 다른 참가자·연습 seed와 겹치지 않음
    assert protocol.seed_for(CFG, "P03", False, 1) == 20261029
    assert protocol.seed_for(CFG, "P03", False, 2) == 20262029
    d = CFG["design"]
    p1 = protocol.sequence_plan(protocol.seed_for(CFG, "P03", False, 1), d["blocks"], d["per_color_per_block"], d["max_same_color_run"])
    p2 = protocol.sequence_plan(protocol.seed_for(CFG, "P03", False, 2), d["blocks"], d["per_color_per_block"], d["max_same_color_run"])
    assert p1 != p2 and sorted(c for _, c in p1) == sorted(c for _, c in p2)
    seeds = {protocol.seed_for(CFG, f"P{n:02d}", pr, s) for n in range(1, 60) for s in range(1, 6) for pr in (False, True)}
    assert len(seeds) == 59 * 5 * 2
    with pytest.raises(SystemExit):
        stim_rgb.resolve_run(CFG, stim_rgb.parse_args(["--participant", "P03"]))          # 본측정 --session 없음 → 거부
    assert stim_rgb.resolve_run(CFG, stim_rgb.parse_args(["--participant", "P03", "--session", "2"]))["seed"] == 20262029
    # QC: 세션 2 기록도 EXP_START의 seed로 색 순서를 재생성해 대조 → PASS
    data, _ = synth("main", pid="P03", session=2)
    res = run_qc(data)
    assert st(res, "색·블록 순서(seed 재생성)") == "PASS" and st(res, "시퀀스 수") == "PASS"
    a = stim_rgb.parse_args(["--participant", "T00", "--practice"])
    assert len(stim_rgb.resolve_run(CFG, a)["plan"]) == 6
    a = stim_rgb.parse_args(["--participant", "T00", "--practice", "--one-block"])
    assert len(stim_rgb.resolve_run(CFG, a)["plan"]) == 18
    if protocol.missing(CFG, {"monitor"}):
        with pytest.raises(SystemExit):
            stim_rgb.resolve_run(CFG, stim_rgb.parse_args(["--participant", "P01"]))
    full = copy.deepcopy(CFG); full["monitor"].update(width_cm=53.0, resolution_px=[1920, 1080])
    assert len(stim_rgb.resolve_run(full, stim_rgb.parse_args(["--participant", "P01", "--session", "1"]))["plan"]) == 90


# ------------------------------------------------------------------ SVM
def _features(tmp, n_subj=2, pcpb=2):
    cfg = cfg_with(raw_unit=None, per_color_per_block=pcpb)
    paths = []
    for k in range(1, n_subj + 1):
        d, _ = synth("main", pid=f"S{k:02d}", cfg=cfg, seed=k)
        out = os.path.join(tmp, f"S{k:02d}")
        q.run(d, "obs", out, cfg)
        paths.append(next(os.path.join(out, f) for f in os.listdir(out) if f.endswith(".npz")))
    return paths


def test_svm_signal_shuffle_and_provisional_guard():
    tmp = tempfile.mkdtemp()
    npz = _features(tmp)
    assert all("PROVISIONAL" in p for p in npz)                    # 단위 미확정 → PROVISIONAL
    svm = [sys.executable, os.path.join(ROOT, "scripts", "train_svm.py"), *npz, "--ids", "S01", "S02", "--outdir", tmp]
    r = subprocess.run(svm, capture_output=True, text=True)
    assert r.returncode != 0 and "PROVISIONAL" in r.stdout + r.stderr
    r = subprocess.run(svm + ["--dry-run", "--shuffle-check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    print(r.stdout)
    out = next(os.path.join(tmp, d) for d in os.listdir(tmp) if d.startswith("svm_"))
    res = list(csv.DictReader(open(os.path.join(out, "per_subject.csv"), encoding="utf-8")))
    assert all(float(x["ba"]) > 0.6 for x in res)
    assert np.mean([float(x["ba_shuffled"]) for x in res]) < 0.5


# ------------------------------------------------------------------ 환경·현장 도구·마커 시각
def test_flip_to_lsl():
    ts, d, ok = protocol.flip_to_lsl(lsl_now=100.010, ps_now=50.004, flip_t=50.000, frame_dur=1 / 60)
    assert ok and abs(d - 0.004) < 1e-9 and abs(ts - 100.006) < 1e-9          # push 지연 4ms 제거
    assert protocol.flip_to_lsl(100.0, 50.0, 49.0, 1 / 60)[2] is False          # 1프레임 초과 → 보정 안 함
    assert protocol.flip_to_lsl(100.0, 50.0, 50.5, 1 / 60)[2] is False          # 음수 → 보정 안 함
    assert protocol.flip_to_lsl(100.0, 50.0, None, 1 / 60) == (100.0, None, False)


def test_photodiode_blocked_in_main():
    import stim_rgb
    full = copy.deepcopy(CFG); full["monitor"].update(width_cm=53.0, resolution_px=[1920, 1080])
    with pytest.raises(SystemExit):
        stim_rgb.resolve_run(full, stim_rgb.parse_args(["--participant", "P01", "--photodiode"]))


def test_start_block_option():
    import stim_rgb
    full = copy.deepcopy(CFG); full["monitor"].update(width_cm=53.0, resolution_px=[1920, 1080])
    r = stim_rgb.resolve_run(full, stim_rgb.parse_args(["--participant", "P01", "--session", "1", "--start-block", "3"]))
    assert r["start_block"] == 3 and len(r["plan"]) == 90          # 계획(seed)은 전체 그대로
    for bad in (["--start-block", "0"], ["--start-block", str(CFG["design"]["blocks"] + 1)]):
        with pytest.raises(SystemExit):
            stim_rgb.resolve_run(full, stim_rgb.parse_args(["--participant", "P01", *bad]))
    with pytest.raises(SystemExit):                                              # 연습에는 불가
        stim_rgb.resolve_run(full, stim_rgb.parse_args(["--participant", "T00", "--practice", "--start-block", "2"]))


def test_recorder_gate():
    import stim_rgb
    full = copy.deepcopy(CFG); full["monitor"].update(width_cm=53.0, resolution_px=[1920, 1080])
    with pytest.raises(SystemExit):                                              # 본측정은 생략 불가
        stim_rgb.resolve_run(full, stim_rgb.parse_args(["--participant", "P01", "--allow-no-recorder"]))
    assert stim_rgb.recorder_required(stim_rgb.parse_args(["--participant", "P01"]))
    assert stim_rgb.recorder_required(stim_rgb.parse_args(["--participant", "T00", "--practice"]))
    assert not stim_rgb.recorder_required(stim_rgb.parse_args(["--participant", "T00", "--practice", "--windowed"]))
    assert not stim_rgb.recorder_required(
        stim_rgb.parse_args(["--participant", "T00", "--practice", "--allow-no-recorder"]))


def test_find_new_xdf(tmp_path):
    import time
    import stim_rgb
    (tmp_path / "sub-P01_ses-main_run-01.xdf").write_bytes(b"x")            # 실행 전부터 있던 파일
    time.sleep(1.1)
    since = time.time() - 0.05                                                  # 실행 시작(outlet 생성)
    assert stim_rgb.find_new_xdf(str(tmp_path), since) is None                  # 이전 파일은 녹화로 안 봄
    (tmp_path / "notes.txt").write_text("x")
    sub = tmp_path / "sub-P03"; sub.mkdir()
    new = sub / "sub-P03_ses-main_run-01.xdf"; new.write_bytes(b"xdf")
    assert stim_rgb.find_new_xdf(str(tmp_path), since) == str(new)


def test_set_field_values(tmp_path):
    import json
    import shutil
    import set_field_values as sfv
    cfg_p, log_p = tmp_path / "p.json", tmp_path / "CHANGELOG.md"
    shutil.copy(os.path.join(ROOT, "config", "protocol.json"), cfg_p)
    with pytest.raises(ValueError):
        sfv.apply(cfg_p, log_p, "width_cm", "5.3", "줄자 실측")                # 범위 밖
    with pytest.raises(ValueError):
        sfv.apply(cfg_p, log_p, "raw_unit", "uV", "")                          # 근거 없음
    with pytest.raises(ValueError):
        sfv.apply(cfg_p, log_p, "resolution", "1080x1920", "설정")              # 세로 > 가로
    sfv.apply(cfg_p, log_p, "width_cm", "53.1", "줄자 실측")
    sfv.apply(cfg_p, log_p, "resolution", "1920x1080", "Windows 설정")
    sfv.apply(cfg_p, log_p, "raw_unit", "µV", "장비 문서")
    c = json.load(open(cfg_p, encoding="utf-8"))
    assert c["monitor"]["width_cm"] == 53.1 and c["monitor"]["resolution_px"] == [1920, 1080]
    assert c["eeg"]["raw_unit"] == "uV" and protocol.missing(c) == []
    assert c["stimulus"] == CFG["stimulus"] and c["analysis"] == CFG["analysis"]   # 연구 값 불변
    assert open(log_p, encoding="utf-8").read().count("|") > 10


def test_env_check_analysis_runs():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "env_check.py"), "--role", "analysis",
                        "--skip-loopback"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "import mne" in r.stdout and "판정" in r.stdout


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
