#!/usr/bin/env python3
"""XDF 품질검사 + 사전분석계획(v2.0) 특징 추출.

데이터 흐름
  입력 : LabRecorder XDF (EEG + RGB_Markers), [선택] 자극 *_events.csv, config/protocol.json
  처리 :
    1) 마커 — EXP_START의 mode/seed로 기대 시퀀스 수(연습 6 / 1블록 18 / 본측정 90)와
              시퀀스 내부 단계(EXP_START phases=, 없으면 v2.0 8단계),
              색 순서(protocol.sequence_plan)를 재생성해 대조: 누락·중복·단계 순서·색/블록 순서·
              종료/STOP·단계 간격·CSV↔XDF
    2) EEG  — 채널 라벨, 단위(V/µV 명시 확인 후 µV 변환), 실효 srate, 누락 표본, NaN, 연속 평탄
    3) 필터 — 연속 구간(누락 표본에서 분할)마다 4차 Butterworth 1–30Hz 인과 SOS, 구간마다 상태 재설정.
              구간 시작 5초 이내·구간 경계를 걸치는 시행은 제외(boundary)
    4) 불량 — epoch(−1~+2s)를 자극 전(−1~0s) 평균으로 보정 후 |x|>60µV 또는 PTP>120µV,
              1초 창 std<0.5µV, NaN/누락, 기준구간(−1.8~−1.0s) 진폭·누락. 4채널 기준 → 2ch·4ch 동일 시행
    5) ERSP — Morlet 3 cycles, 3–30Hz/1Hz, 시행별 baseline 대비 10·log10,
              [3,4)[4,8)[8,13)[13,30] Hz × [0.1,0.4)[0.4,0.8)[0.8,1.2)[1.2,1.5] s
  출력 : <xdf 폴더>/qc_<이름>/report.txt, checks.csv, psd.png, features_<cond>[_PROVISIONAL].npz
  종료코드 : NO-GO(FAIL 존재) → 1, 그 외 0

예 (PowerShell)
  python scripts\\xdf_qc.py data\\sub-T00_ses-systemtest_run-01.xdf --stim-csv data\\T00_practice_..._events.csv
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi, welch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol  # noqa: E402

MARKER_RE = re.compile(r"^b(\d+)\|s(\d+)\|(gray|obs|img)(\d)\|([RGB])$")
COLOR_TO_Y = {"R": 0, "G": 1, "B": 2}
UNIT_FACTOR = {"V": 1e6, "mV": 1e3, "uV": 1.0, "µV": 1.0}


class Checks:
    def __init__(self):
        self.rows, self.notes = [], []

    def add(self, name, status, evidence):
        assert status in ("PASS", "FAIL", "UNVERIFIED")
        self.rows.append((name, status, evidence))

    def note(self, s):
        self.notes.append(s)

    def status(self, name):
        return next((s for n, s, _ in self.rows if n == name), None)

    def verdict(self):
        if any(r[1] == "FAIL" for r in self.rows):
            return "NO-GO"
        unv = [r[0] for r in self.rows if r[1] == "UNVERIFIED"]
        return f"조건부 (UNVERIFIED: {', '.join(unv)})" if unv else "GO"

    def text(self):
        w = max((len(r[0]) for r in self.rows), default=10)
        out = [f"{'점검':{w}s}  {'상태':10s}  근거"] + [f"{n:{w}s}  {s:10s}  {e}" for n, s, e in self.rows]
        return "\n".join(out + [""] + self.notes + ["", f"판정: {self.verdict()}"])


# ================================================================== 로드
def _labels(st):
    try:
        return [c["label"][0] for c in st["info"]["desc"][0]["channels"][0]["channel"]]
    except (KeyError, IndexError, TypeError):
        return []


def _unit(st):
    try:
        return st["info"]["desc"][0]["channels"][0]["channel"][0]["unit"][0]
    except (KeyError, IndexError, TypeError):
        return None


def load_xdf(path, eeg_name=None):
    import pyxdf
    streams, _ = pyxdf.load_xdf(path)
    eeg = mk = None
    for st in streams:
        name, typ = st["info"]["name"][0], st["info"]["type"][0]
        if name == "RGB_Markers":
            mk = st
        elif (eeg_name and eeg_name.lower() in name.lower()) or (not eeg_name and typ.upper() == "EEG"):
            eeg = st
    found = [s["info"]["name"][0] for s in streams]
    if eeg is None:
        sys.exit(f"[FAIL] EEG 스트림 없음 (스트림: {found}) — LabRecorder에서 EEG 체크 여부 확인")
    if mk is None or len(mk["time_stamps"]) == 0:
        sys.exit(f"[FAIL] RGB_Markers 스트림 없음 또는 마커 0개 (스트림: {found}) — 녹화 순서 확인")
    if len(eeg["time_stamps"]) < 2:
        sys.exit("[FAIL] EEG 샘플 없음")
    return dict(x=np.asarray(eeg["time_series"], float), t=np.asarray(eeg["time_stamps"], float),
                labels=_labels(eeg), unit=_unit(eeg),
                markers=[m[0] for m in mk["time_series"]], mt=np.asarray(mk["time_stamps"], float))


# ================================================================== 마커
def parse_markers(markers, mt):
    rows, events = [], []
    for m, tt in zip(markers, mt):
        g = MARKER_RE.match(m)
        if g:
            b, s, ph, rep, c = g.groups()
            rows.append(dict(t=float(tt), block=int(b), seq=int(s), phase=ph, rep=int(rep), color=c, marker=m))
        else:
            events.append((m, float(tt)))
    return rows, events


def expected_by_mode(cfg, mode):
    d = cfg["design"]
    return {"practice": (1, 2), "block": (1, d["per_color_per_block"]),
            "main": (d["blocks"], d["per_color_per_block"])}.get(mode)


def check_markers(rows, events, cfg, ck, stim_csv=None):
    names = [m.split("|")[0] for m, _ in events]
    start = next((m for m, _ in events if m.startswith("EXP_START")), None)
    if start is None:
        ck.add("EXP_START 기록", "FAIL", "없음 → 녹화를 실험 시작 뒤에 켰거나 구버전 스크립트. 기대값·seed 확인 불가")
        return {}
    meta = dict(p.split("=", 1) for p in start.split("|")[1:] if "=" in p)
    ck.add("EXP_START 기록", "PASS", f"mode={meta.get('mode')}, session={meta.get('session', '1(기록 없음, 변경3 이전)')}, "
                                    f"seed={meta.get('seed')}, version={meta.get('version')}")
    mode = meta.get("mode")
    exp = expected_by_mode(cfg, mode)
    blocks, pcpb, seed = int(meta["blocks"]), int(meta["pcpb"]), int(meta["seed"])
    n_exp = blocks * pcpb * 3
    phases = protocol.parse_phases_tag(meta.get("phases"))       # 기록된 단계 순서 (구버전 기록 = v2.0 8단계)
    n_ph = len(phases)
    if exp is None or exp != (blocks, pcpb) or int(meta.get("nseq", n_exp)) != n_exp:
        ck.add("모드별 설계", "FAIL", f"mode={mode}: 기록 blocks={blocks}, pcpb={pcpb} ≠ config 기대 {exp}")
    else:
        ck.add("모드별 설계", "PASS", f"{mode}: {n_exp}시퀀스 × {n_ph} = {n_exp * n_ph} 단계 마커 기대")
    if phases != protocol.phases(cfg):
        ck.note(f"[참고] 기록된 단계 {protocol.phases_tag(phases)} ≠ 현재 config {protocol.phases_tag(protocol.phases(cfg))}"
                " → 이전 설계 데이터. 현재 설계 데이터와 합칠 때 주의 (docs/plan_changes.md)")
    if meta.get("provisional") == "1" or mode != "main":
        ck.note(f"[참고] mode={mode}, provisional={meta.get('provisional')} → 본 분석 사용 불가 데이터")
    start_block = int(meta.get("start_block", 1))
    first = (start_block - 1) * pcpb * 3 + 1          # 이어 하기 파트는 블록 start_block의 첫 시퀀스부터 기대
    if start_block > 1:
        ck.note(f"[참고] 이어 하기 파트: 블록 {start_block}–{blocks} (시퀀스 {first}–{n_exp}). "
                f"블록 1–{start_block - 1}은 별도 파일 — 계획서 외 진행, 변경 기록 필요")

    dup = [m for m, k in Counter(r["marker"] for r in rows).items() if k > 1]
    ck.add("중복 마커", "PASS" if not dup else "FAIL", f"{len(dup)}개 {dup[:5]}")

    seqs = {}
    for r in sorted(rows, key=lambda r: r["t"]):
        seqs.setdefault(r["seq"], []).append(r)
    want = set(range(first, n_exp + 1))
    miss = sorted(want - set(seqs))
    extra = sorted(set(seqs) - want)
    ck.add("시퀀스 수", "PASS" if not miss and not extra else "FAIL",
           f"{len(seqs)}/{len(want)}; 누락 {miss[:10]}{'…' if len(miss) > 10 else ''}; 범위밖 {extra[:10]}")

    order = [f"{p}{r}" for p, r in phases]
    incomplete = {s: len(v) for s, v in seqs.items() if len({x['marker'] for x in v}) != n_ph}
    wrong_order = [s for s, v in seqs.items() if s not in incomplete and [f"{x['phase']}{x['rep']}" for x in v] != order]
    ck.add("시퀀스 내부 단계", "PASS" if not incomplete else "FAIL",
           f"기대 {n_ph}단계({','.join(order)}); 불완전 {dict(list(incomplete.items())[:5]) or '없음'}")
    ck.add("단계 순서", "PASS" if not wrong_order else "FAIL", f"순서 오류 시퀀스 {wrong_order[:10] or '없음'}")

    plan = protocol.sequence_plan(seed, blocks, pcpb, cfg["design"]["max_same_color_run"])
    mism = []
    for s, v in seqs.items():
        if 1 <= s <= n_exp:
            eb, ec = plan[s - 1]
            if any(x["color"] != ec or x["block"] != eb for x in v):
                mism.append((s, f"기대 b{eb}{ec}", f"실제 {sorted({(x['block'], x['color']) for x in v})}"))
    ck.add("색·블록 순서(seed 재생성)", "PASS" if not mism else "FAIL", f"불일치 {mism[:3] or '없음'}")

    ends = "EXP_END" in names
    stops = [m for m, _ in events if m.startswith("STOP")]
    ck.add("종료/STOP", "PASS" if ends and not stops else "FAIL", f"EXP_END={'있음' if ends else '없음'}, STOP={stops or '없음'}")
    for b in range(start_block + 1, blocks + 1):
        for ev in (f"REST_START|b{b}", f"REST_END|b{b}"):
            if ev not in [m for m, _ in events]:
                ck.note(f"[참고] {ev} 없음")
    pauses = Counter(n for n in names if n in ("PAUSE", "RESUME"))
    if pauses:
        ck.note(f"[참고] 일시정지 {dict(pauses)}")

    d = np.array([b["t"] - a["t"] for v in seqs.values() for a, b in zip(v, v[1:])])
    if len(d):
        frame = 1.0 / float(meta.get("fps", 60))
        spread = float(d.max() - d.min())
        ck.add("단계 간격", "PASS" if spread < frame else "FAIL",
               f"중앙값 {np.median(d):.4f}s, max−min {spread * 1000:.1f}ms (기준 < 1프레임 {frame * 1000:.1f}ms)")
    else:
        ck.add("단계 간격", "FAIL", "계산 가능한 단계 없음")

    if stim_csv:
        with open(stim_csv, encoding="utf-8") as fh:
            crow = [r for r in csv.DictReader(fh) if r["phase"] in ("gray", "obs", "img")]
        xdf_t = {r["marker"]: r["t"] for r in rows}
        lost = [r["marker"] for r in crow if r["marker"] not in xdf_t]
        diffs = np.array([xdf_t[r["marker"]] - float(r["onset_lsl"]) for r in crow if r["marker"] in xdf_t])
        off = f", XDF−CSV 시각차 중앙값 {np.median(diffs) * 1000:.2f}ms, 범위 {np.ptp(diffs) * 1000:.2f}ms" if len(diffs) else ""
        ck.add("CSV↔XDF 마커 대조", "PASS" if not lost and crow else "FAIL", f"CSV {len(crow)}개 중 XDF 누락 {len(lost)} {lost[:3]}{off}")
        if len(diffs):
            ck.note("[참고] 시각차 '범위'가 크면 동기화 지터. 중앙값은 PC 간 시계 offset(같은 PC면 ≈0).")
        if crow and "clock_ok" in crow[0]:
            bad = [r["marker"] for r in crow if r.get("clock_ok") == "0"]
            dl = sorted(float(r["flip_to_push_ms"]) for r in crow if r.get("flip_to_push_ms"))
            med = f"{dl[len(dl) // 2]:.3f}ms, 최대 {dl[-1]:.3f}ms" if dl else "기록 없음"
            ck.add("마커 시각 = flip 시각", "PASS" if not bad else "FAIL",
                   f"보정 실패 {len(bad)}/{len(crow)}; flip→push 지연 중앙값 {med} (보정으로 제거됨)")
        ck.add("모니터 입력 지연", "UNVERIFIED", "포토다이오드 측정 필요 (stim_rgb.py --practice --photodiode)")
    else:
        ck.add("CSV↔XDF 마커 대조", "UNVERIFIED", "--stim-csv 미지정")
    return seqs


# ================================================================== EEG
def pick_channels(labels, chs, ck):
    if not labels:
        ck.add("채널 라벨", "UNVERIFIED", f"스트림에 라벨 없음 → 앞 {len(chs)}채널 가정. 깜빡임 등으로 매핑 확인 필요")
        return list(range(len(chs)))
    if all(c in labels for c in chs):
        ck.add("채널 라벨", "PASS", str({c: labels.index(c) for c in chs}))
        return [labels.index(c) for c in chs]
    ck.add("채널 라벨", "FAIL", f"필요 {chs} 중 없음 {[c for c in chs if c not in labels]} (스트림 {labels})")
    return None


def to_uv(x, cfg_unit, meta_unit, cli_unit, ck):
    unit = cli_unit or cfg_unit or meta_unit
    src = "CLI" if cli_unit else "config" if cfg_unit else "XDF 메타" if meta_unit else None
    sd = float(np.nanmedian(np.nanstd(x, axis=0)))
    looks_v = sd < 1e-2
    if unit not in UNIT_FACTOR:
        ck.add("EEG 단위", "UNVERIFIED", f"미확정({unit!r}). SD 중앙값 {sd:.3g} → {'V' if looks_v else 'µV'}로 임시 변환. "
               "장비 문서 확인 후 config.eeg.raw_unit 입력")
        return x * (1e6 if looks_v else 1.0), False
    ok = (unit == "V") == looks_v
    ck.add("EEG 단위", "PASS" if ok else "FAIL",
           f"{unit} (출처 {src}); SD 중앙값 {sd:.3g} {'일치' if ok else '→ 값 크기가 선언 단위와 불일치'}")
    return x * UNIT_FACTOR[unit], ok


def segments(t, fs, finite=None):
    """연속 구간 [(i0, i1), ...] (i1 exclusive). 누락 표본(간격 > 1.5/fs)과 NaN 행에서 분할, NaN 구간은 제외."""
    ok = np.ones(len(t), bool) if finite is None else finite
    brk = np.zeros(len(t), bool)
    brk[1:] = np.diff(t) > 1.5 / fs
    segs, i0 = [], None
    for i in range(len(t)):
        if not ok[i]:
            if i0 is not None:
                segs.append((i0, i)); i0 = None
            continue
        if i0 is None:
            i0 = i
        elif brk[i]:
            segs.append((i0, i)); i0 = i
    if i0 is not None:
        segs.append((i0, len(t)))
    return segs


def check_eeg(x_uv, t, fs, segs, ck):
    fs_eff = (len(t) - 1) / (t[-1] - t[0])
    ck.add("실효 srate", "PASS" if abs(fs_eff - fs) <= 0.5 else "FAIL", f"{fs_eff:.3f}Hz (명목 {fs}, 허용 ±0.5)")
    gaps = int(np.sum(np.diff(t) > 1.5 / fs))
    lost = int(np.sum(np.round(np.diff(t)[np.diff(t) > 1.5 / fs] * fs) - 1))
    ck.add("누락 표본", "PASS" if gaps == 0 else "FAIL",
           f"끊김 {gaps}회, 추정 누락 {lost}샘플 → 해당 시행 제외, 구간별 필터 재시작")
    nan = int((~np.isfinite(x_uv)).sum())
    ck.add("NaN/Inf", "PASS" if nan == 0 else "FAIL", f"{nan}개")
    n = len(x_uv) // int(fs)
    if n:
        sd1 = np.nanstd(x_uv[: n * int(fs)].reshape(n, int(fs), -1), axis=1)
        frac = (sd1 < 0.5).mean(axis=0)
        ck.add("평탄 채널(연속)", "PASS" if (frac < 0.01).all() else "FAIL", f"1초 std<0.5µV 비율 {np.round(frac, 3).tolist()}")
    return fs_eff


# ================================================================== 신호처리
def causal_filter_segments(x, segs, fs, flt):
    sos = butter(flt["order"], [flt["l_freq"], flt["h_freq"]], btype="bandpass", fs=fs, output="sos")
    if not flt["causal"]:
        raise ValueError("계획서는 인과 필터 — config.analysis.filter.causal=true 이어야 함")
    y = np.full_like(x, np.nan)
    for i0, i1 in segs:
        seg = x[i0:i1]
        zi = sosfilt_zi(sos)[:, :, None] * seg[0][None, None, :]      # 구간마다 상태 재설정
        y[i0:i1], _ = sosfilt(sos, seg, axis=0, zi=zi)
    return y


def cut(y, t, fs, on, win, segs, startup):
    """on 기준 win 구간 → ((ch, n), None) 또는 (None, 사유). 사유: missing(구간 경계/누락/NaN 걸침),
    startup(구간 시작 후 startup초 이내), out_of_range(녹화 범위 밖)."""
    n = int(round((win[1] - win[0]) * fs))
    if on + win[0] < t[0] or on + win[1] > t[-1]:
        return None, "out_of_range"
    i0 = int(np.searchsorted(t, on + win[0] - 0.5 / fs))
    for s0, s1 in segs:
        if s0 <= i0 < s1:
            if i0 + n > s1:
                return None, "missing"
            if t[i0] < t[s0] + startup:
                return None, "startup"
            return y[i0:i0 + n].T, None
    return None, "missing"


def bad_reasons(ep, base, fs, an, qc):
    """ep (ch, n) epoch, base (ch, m) baseline 구간. 반환 사유 리스트."""
    r = []
    if not np.isfinite(ep).all() or not np.isfinite(base).all():
        return ["missing"]
    times = an["epoch_sec"][0] + np.arange(ep.shape[1]) / fs
    pre = (times >= qc["prestim_demean_sec"][0]) & (times < qc["prestim_demean_sec"][1])
    d = ep - ep[:, pre].mean(axis=1, keepdims=True)
    if (np.abs(d) > qc["abs_uv"]).any():
        r.append("abs")
    if (np.ptp(d, axis=1) > qc["ptp_uv"]).any():
        r.append("ptp")
    w = int(round(qc["flat_window_sec"] * fs))
    k = ep.shape[1] // w
    if k and (ep[:, : k * w].reshape(ep.shape[0], k, w).std(axis=2) < qc["flat_std_uv"]).any():
        r.append("flat")
    if qc["baseline_check"]:
        bd = base - base.mean(axis=1, keepdims=True)
        if (np.abs(bd) > qc["abs_uv"]).any():
            r.append("baseline_abs")
    return r


def ersp_features(ep_pad, fs, an):
    from mne.time_frequency import tfr_array_morlet
    freqs = np.arange(an["freq_range"][0], an["freq_range"][1] + 1e-9, an["freq_step"], dtype=float)
    pw = tfr_array_morlet(ep_pad, sfreq=fs, freqs=freqs, n_cycles=float(an["n_cycles"]),
                          output="power", verbose=False)                      # complex Morlet → |·|²
    times = np.round(an["tfr_pad_sec"][0] + np.arange(ep_pad.shape[-1]) / fs, 6)
    b0, b1 = an["baseline_sec"]
    base = pw[..., (times >= b0) & (times < b1)].mean(axis=-1, keepdims=True)
    db = 10 * np.log10(pw / base)
    fmask = protocol.bin_masks(freqs, an["bands_hz"])
    tmask = protocol.bin_masks(times, an["windows_sec"])
    feats = [db[:, :, fm][..., tm].mean(axis=(-1, -2)) for fm in fmask for tm in tmask]
    F = np.stack(feats, axis=-1)                                               # (n, ch, 16)
    return F.reshape(F.shape[0], -1)


def feature_names(chs, an):
    return [f"{c}_{lo}-{hi}Hz_{t0}-{t1}s" for c in chs for lo, hi in an["bands_hz"] for t0, t1 in an["windows_sec"]]


# ================================================================== 메인
def run(data, cond, outdir, cfg, stim_csv=None, cli_unit=None):
    os.makedirs(outdir, exist_ok=True)
    ck = Checks()
    an, qc, eegc = cfg["analysis"], cfg["qc"], cfg["eeg"]
    fs = float(eegc["fs"])
    chs, occ = eegc["channels"], eegc["occipital"]

    rows, events = parse_markers(data["markers"], data["mt"])
    if not rows:
        ck.add("단계 마커", "FAIL", f"단계 마커 0개 (전체 마커 {len(data['markers'])}개)")
    check_markers(rows, events, cfg, ck, stim_csv)

    idx = pick_channels(data["labels"], chs, ck)
    result = dict(X4=None, X2=None, bad=None)
    if idx is None:
        return _finish(ck, outdir, result)
    x, unit_ok = to_uv(data["x"][:, idx], eegc["raw_unit"], data["unit"], cli_unit, ck)
    t = data["t"]
    segs = segments(t, fs, np.isfinite(x).all(axis=1))
    check_eeg(x, t, fs, segs, ck)
    _psd(x, fs, chs, an, outdir, ck)

    y = causal_filter_segments(x, segs, fs, an["filter"])          # NaN 행은 구간 밖 → NaN 유지
    trials = sorted([r for r in rows if r["phase"] == cond], key=lambda r: r["t"])
    eps, pads, reasons, keep_rows = [], [], [], []
    n_ep = int(round((an["epoch_sec"][1] - an["epoch_sec"][0]) * fs))
    n_pad = int(round((an["tfr_pad_sec"][1] - an["tfr_pad_sec"][0]) * fs))
    n_base = int(round((an["baseline_sec"][1] - an["baseline_sec"][0]) * fs))
    for r in trials:
        pad, why = cut(y, t, fs, r["t"], an["tfr_pad_sec"], segs, an["startup_exclude_sec"])
        if pad is None:
            pads.append(np.zeros((len(chs), n_pad))); eps.append(np.zeros((len(chs), n_ep)))
            reasons.append([why]); keep_rows.append(r); continue
        o_ep = int(round((an["epoch_sec"][0] - an["tfr_pad_sec"][0]) * fs))
        o_b = int(round((an["baseline_sec"][0] - an["tfr_pad_sec"][0]) * fs))
        ep, base = pad[:, o_ep:o_ep + n_ep], pad[:, o_b:o_b + n_base]
        reasons.append(bad_reasons(ep, base, fs, an, qc))
        pads.append(np.nan_to_num(pad)); eps.append(ep); keep_rows.append(r)
    bad = np.array([bool(rs) for rs in reasons], dtype=bool)
    cnt = Counter(x for rs in reasons for x in rs)
    n_valid = int((~bad).sum())
    ck.add(f"[{cond}] 유효 시행", "PASS" if n_valid > 0 else "FAIL",
           f"{n_valid}/{len(bad)} 유효 ({(bad.mean() if len(bad) else 0):.1%} 제외), 사유 {dict(cnt)}")
    per_c = {c: int(sum(b for b, r in zip(bad, keep_rows) if r["color"] == c)) for c in "RGB"}
    skew = bad.sum() >= 3 and max(per_c.values()) > 2 * (min(per_c.values()) + 1)
    ck.add(f"[{cond}] 불량의 색 편중", "FAIL" if skew else "PASS",
           f"{per_c}{' → 제외가 라벨과 상관됨, 원인 확인 필요' if skew else ''}")

    if n_valid == 0:
        ck.note("유효 시행 0 → 특징 추출 생략")
        return _finish(ck, outdir, result)
    nf = len(an["bands_hz"]) * len(an["windows_sec"])
    X4 = np.full((len(keep_rows), len(chs) * nf), np.nan)           # 불량 시행은 NaN (bad 마스크로 제외)
    X4[~bad] = ersp_features(np.array(pads)[~bad], fs, an)
    oi = [chs.index(c) for c in occ]
    X2 = X4.reshape(len(keep_rows), len(chs), nf)[:, oi].reshape(len(keep_rows), -1)
    fin = np.isfinite(X4[~bad]).all()
    ok_shape = X4.shape[1] == len(chs) * nf and X2.shape[1] == len(occ) * nf
    ck.add("특징 행렬", "PASS" if ok_shape and fin else "FAIL",
           f"X4 {X4.shape}, X2 {X2.shape}, 유효시행 비유한값 {int((~np.isfinite(X4[~bad])).sum())}")
    provisional = (not unit_ok) or bool(protocol.missing(cfg, {"analysis", "qc"}))
    suffix = "_PROVISIONAL" if provisional else ""
    out = os.path.join(outdir, f"features_{cond}{suffix}.npz")
    np.savez(out, X4=X4, X2=X2, y=np.array([COLOR_TO_Y[r["color"]] for r in keep_rows]),
             block=np.array([r["block"] for r in keep_rows]), seq=np.array([r["seq"] for r in keep_rows]),
             rep=np.array([r["rep"] for r in keep_rows]), bad=bad,
             bad_reason=np.array([",".join(rs) for rs in reasons]),
             feature_names_4ch=np.array(feature_names(chs, an)), feature_names_2ch=np.array(feature_names(occ, an)),
             label_map=np.array(["R", "G", "B"]), provisional=provisional, plan_version=cfg["plan_version"])
    ck.note(f"저장: {out} (y: 0=R 1=G 2=B; bad는 4채널 기준 → 2ch·4ch 동일 시행)")
    if provisional:
        ck.note("PROVISIONAL: EEG 단위 미확정 → µV 기준 불량 판정 신뢰 불가. 본 분석 사용 금지")
    result.update(X4=X4, X2=X2, bad=bad, reasons=reasons, rows=keep_rows)
    return _finish(ck, outdir, result)


def _psd(x, fs, chs, an, outdir, ck):
    xx = np.nan_to_num(x - np.nanmean(x, 0))
    f, p = welch(xx, fs=fs, nperseg=min(len(xx), int(fs * 4)), axis=0)
    a_m, b_m = (f >= 8) & (f <= 12), (f >= 1) & (f <= 30)
    ck.note("[참고] PSD 8–12Hz 비중: " + ", ".join(f"{c}={p[a_m, i].sum() / max(p[b_m, i].sum(), 1e-20):.2f}" for i, c in enumerate(chs)))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 4))
        for i, c in enumerate(chs):
            ax.semilogy(f, p[:, i] + 1e-20, label=c)
        ax.axvspan(an["filter"]["l_freq"], an["filter"]["h_freq"], alpha=0.08)
        ax.axvline(60, ls="--", lw=0.8, c="k")
        ax.set(xlabel="Hz", ylabel="PSD (µV²/Hz)", xlim=(0, 70), title="Raw PSD")
        ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(outdir, "psd.png"), dpi=120); plt.close(fig)
    except Exception as e:  # noqa: BLE001
        ck.note(f"(PSD 그림 생략: {e})")


def _finish(ck, outdir, result):
    rep = ck.text()
    with open(os.path.join(outdir, "report.txt"), "w", encoding="utf-8") as fh:
        fh.write(rep + "\n")
    with open(os.path.join(outdir, "checks.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("check", "status", "evidence"), *ck.rows])
    print(rep)
    result["checks"] = ck
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xdf")
    ap.add_argument("--cond", choices=["obs", "img"], default="obs", help="obs=주분석, img=탐색")
    ap.add_argument("--stim-csv", default=None)
    ap.add_argument("--raw-unit", choices=list(UNIT_FACTOR), default=None)
    ap.add_argument("--eeg-name", default=None)
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = protocol.load(a.config)
    stem = os.path.splitext(os.path.basename(a.xdf))[0]
    outdir = os.path.join(os.path.dirname(os.path.abspath(a.xdf)), f"qc_{stem}")
    res = run(load_xdf(a.xdf, a.eeg_name), a.cond, outdir, cfg, a.stim_csv, a.raw_unit)
    sys.exit(1 if res["checks"].verdict() == "NO-GO" else 0)


if __name__ == "__main__":
    main()
