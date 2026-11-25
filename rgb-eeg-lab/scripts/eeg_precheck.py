#!/usr/bin/env python3
"""세션 시작 전 착용 신호 점검 — xdf_qc.py와 '같은 기준'으로 시행이 몇 % 살아남을지 미리 추정.

데이터 흐름
  입력 : LSL EEG 스트림(BrainAccess Board 송출), config/protocol.json (analysis.filter, analysis.epoch_sec, qc.*)
  처리 : 1) 단위 변환(eeg.raw_unit → µV)
         2) 1–30Hz 4차 Butterworth 인과 SOS (QC와 동일), 처음 startup_exclude_sec 버림
         3) epoch 길이(epoch_sec, 기본 3초) 창으로 자름 → 각 창의 앞 1초(prestim_demean_sec 길이) 평균으로 보정
         4) 창마다 |x|>abs_uv, PTP>ptp_uv, 1초 std<flat_std_uv → 불량
  출력 : 콘솔 표 (채널별 불량 %, 4채널 기준 유효 %), 녹화·파일 저장 없음
  판정 : 4채널 기준 유효 창 % ≥ qc.precheck_min_valid_pct 그리고 배터리(LSL 'Battery' 채널) ≥ qc.precheck_min_battery_pct
         → GO, 하나라도 미만 → NO-GO. 배터리 채널이 없으면 배터리는 UNVERIFIED(신호만으로 판정). --once 종료코드 0/1
  주의 : 실제 QC는 자극 onset 기준 epoch·baseline 구간 검사도 하므로 이 값은 '추정'이다 (운영 기준, 분석 제외 기준 아님).

예 (PowerShell, 분석 python)
  .venv\\Scripts\\python.exe scripts\\eeg_precheck.py              # 10초마다 갱신 (Ctrl+C 종료)
  .venv\\Scripts\\python.exe scripts\\eeg_precheck.py --once 60    # 60초 한 번 측정
"""
import argparse
import os
import sys
import time

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol  # noqa: E402
import ui  # noqa: E402

UNIT = {"V": 1e6, "mV": 1e3, "uV": 1.0, "µV": 1.0}


def window_flags(x, fs, cfg):
    """x: (n, ch) 필터된 µV. 반환 dict(abs, ptp, flat) 각 (n_win, ch) bool."""
    q, an = cfg["qc"], cfg["analysis"]
    win = int(round((an["epoch_sec"][1] - an["epoch_sec"][0]) * fs))
    pre = int(round((q["prestim_demean_sec"][1] - q["prestim_demean_sec"][0]) * fs))
    fw = int(round(q["flat_window_sec"] * fs))
    n_win = len(x) // win
    if n_win == 0:
        return None
    ep = x[: n_win * win].reshape(n_win, win, -1)
    ep = ep - ep[:, :pre].mean(axis=1, keepdims=True)
    f_abs = np.abs(ep).max(axis=1) > q["abs_uv"]
    f_ptp = np.ptp(ep, axis=1) > q["ptp_uv"]
    nf = win // fw
    f_flat = ep[:, : nf * fw].reshape(n_win, nf, fw, -1).std(axis=2).min(axis=1) < q["flat_std_uv"]
    return dict(abs=f_abs, ptp=f_ptp, flat=f_flat)


def report(flags, labels, secs, min_pct=None):
    """표 출력. 반환: 4채널 기준 유효 창 %."""
    bad = flags["abs"] | flags["ptp"] | flags["flat"]
    n = bad.shape[0]
    ui.sub(f"신호 점검  최근 {secs:.0f}초, {n}개 창")
    print("  " + ui.ljust("채널", 6) + ui.rjust("불량", 7) + ui.rjust("abs", 6) + ui.rjust("ptp", 6) + ui.rjust("flat", 6))
    worst_i = int(bad.mean(axis=0).argmax())
    for i, lb in enumerate(labels):
        pct = 100 * bad[:, i].mean()
        # 색: 0% 초록, 채널 하나만으로 기준을 못 넘기는 수준(> 100 − 기준%)이면 빨강, 그 사이 노랑
        col = "green" if pct == 0 else "red" if min_pct is not None and pct > 100 - min_pct else "yellow"
        print("  " + ui.ljust(lb, 6) + ui.c(ui.rjust(f"{pct:.0f}%", 7), col)
              + ui.rjust(flags["abs"][:, i].sum(), 6) + ui.rjust(flags["ptp"][:, i].sum(), 6)
              + ui.rjust(flags["flat"][:, i].sum(), 6)
              + (ui.c("  ← 가장 나쁨", "gray") if pct > 0 and i == worst_i else ""))
    ok = (~bad.any(axis=1)).mean() * 100
    print(ui.c("  유효 = 4채널 모두 정상인 창 (QC는 하나라도 불량이면 시행 제외)", "gray"))
    if ok < 100:
        print(ui.c(f"  가장 나쁜 채널 {labels[worst_i]}: 전극 접촉·머리카락·움직임 확인 (Fp는 눈 깜빡임)", "gray"))
    if min_pct is not None:
        if ok >= min_pct:
            ui.tag("go", f"신호   유효 {ok:.0f}%  (기준 ≥{min_pct:.0f}%)")
        else:
            ui.tag("nogo", f"신호   유효 {ok:.0f}%  (기준 ≥{min_pct:.0f}%)", "전극 재조정 후 다시 점검")
    else:
        ui.tag("uv", f"신호   유효 {ok:.0f}%  (기준 없음 → 판정 안 함)")
    return ok


def battery_verdict(batt, min_batt):
    """배터리 줄 출력. 반환: True=GO, None=판정 불가(채널 없음·기준 없음)."""
    if batt is None:
        ui.tag("uv", "배터리 — 스트림에 'Battery' 채널 없음", "BrainAccess Board 화면에서 직접 확인")
        return None
    if min_batt is None:
        ui.tag("uv", f"배터리 {batt:.0f}%  (기준 없음 → 판정 안 함)")
        return None
    go = batt >= min_batt
    note = "본측정 약 29분에 약 11%p 소모"
    if go:
        ui.tag("go", f"배터리 {batt:.0f}%  (기준 ≥{min_batt:.0f}%)", ui.c(note, "gray"))
    else:
        ui.tag("nogo", f"배터리 {batt:.0f}%  (기준 ≥{min_batt:.0f}%)", "충전 후 진행", ui.c(note, "gray"))
    return go


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eeg-name", default=None, help="EEG 스트림 이름 일부 (기본: type=EEG 첫 스트림)")
    ap.add_argument("--once", type=float, default=None, help="이 초만큼 한 번 측정하고 종료")
    ap.add_argument("--window", type=float, default=30, help="반복 모드: 최근 몇 초로 계산 (기본 30)")
    ap.add_argument("--every", type=float, default=10, help="반복 모드: 갱신 간격 초 (기본 10)")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = protocol.load(a.config)
    min_pct = cfg["qc"].get("precheck_min_valid_pct")
    if min_pct is None:
        ui.tag("uv", "config qc.precheck_min_valid_pct 없음 → 수치만 표시, 판정 안 함")
    min_batt = cfg["qc"].get("precheck_min_battery_pct")
    import pylsl

    streams = [s for s in pylsl.resolve_streams(3.0) if s.type() == "EEG"
               and (a.eeg_name is None or a.eeg_name in s.name())]
    if not streams:
        ui.tag("fail", "EEG LSL 스트림 없음", "BrainAccess Board에서 장치 연결·스트리밍 중인지 확인")
        sys.exit(1)
    info = streams[0]
    inlet = pylsl.StreamInlet(info, max_buflen=120)
    full = inlet.info()
    ch = full.desc().child("channels").child("channel")
    labels = []
    for _ in range(full.channel_count()):
        labels.append(ch.child_value("label") or f"ch{len(labels)}")
        ch = ch.next_sibling()
    want = cfg["eeg"]["channels"]
    idx = [labels.index(c) for c in want if c in labels]
    if len(idx) != len(want):
        ui.tag("warn", f"라벨 {labels}에서 {want}를 다 찾지 못함 → 앞 {len(want)}채널 사용")
        idx = list(range(len(want)))
    bi = labels.index("Battery") if "Battery" in labels else None
    batt = None
    fs = info.nominal_srate()
    scale = UNIT[cfg["eeg"]["raw_unit"]]
    f = cfg["analysis"]["filter"]
    sos = butter(f["order"], [f["l_freq"], f["h_freq"]], btype="band", fs=fs, output="sos")
    zi = None
    skip = int(cfg["analysis"]["startup_exclude_sec"] * fs)
    keep = int((a.once or a.window) * fs)
    buf = np.empty((0, len(idx)))
    ui.tag("ok", f"연결: {info.name()}  {fs:.0f}Hz  채널 {', '.join(want)}",
           ui.c(f"기준 abs>{cfg['qc']['abs_uv']}µV  PTP>{cfg['qc']['ptp_uv']}µV  flat std<{cfg['qc']['flat_std_uv']}µV", "gray"))
    ui.tag("wait", f"측정 중… 약 {(a.once or a.window) + skip / fs:.0f}초 (필터 안정화 {skip / fs:.0f}초 포함)"
           + ("" if a.once else f", 이후 {a.every:.0f}초마다 갱신 | 종료 Ctrl+C"))
    t_last = time.time()
    try:
        while True:
            chunk, _ = inlet.pull_chunk(timeout=0.5)
            if chunk:
                if bi is not None:
                    batt = float(chunk[-1][bi])
                x = np.asarray(chunk)[:, idx] * scale
                if zi is None:
                    zi = sosfilt_zi(sos)[:, :, None] * x[0]
                y, zi = sosfilt(sos, x, axis=0, zi=zi)
                if skip > 0:
                    cut = min(skip, len(y)); y = y[cut:]; skip -= cut
                buf = np.vstack([buf, y])[-keep:]
            if a.once:
                if len(buf) >= keep:
                    fl = window_flags(buf, fs, cfg)
                    ok = report(fl, want, len(buf) / fs, min_pct)
                    bgo = battery_verdict(batt, min_batt)
                    sig_go = min_pct is None or ok >= min_pct
                    go = sig_go and bgo is not False
                    bat_s = "GO" if bgo else "NO-GO" if bgo is False else "UNVERIFIED"
                    print()
                    print("  " + ui.c(f"사전 점검 판정: {'GO' if go else 'NO-GO'}", ui.verdict_color("GO" if go else "NO-GO"))
                          + ui.c(f"   (신호 {'GO' if sig_go else 'NO-GO'}, 배터리 {bat_s})", "gray"), flush=True)
                    sys.exit(0 if go else 1)
            elif time.time() - t_last >= a.every and len(buf) >= fs * 6:
                t_last = time.time()
                fl = window_flags(buf, fs, cfg)
                if fl is not None:
                    report(fl, want, len(buf) / fs, min_pct)
                    battery_verdict(batt, min_batt)
    except KeyboardInterrupt:
        print()
        ui.tag("stop", "사전 점검 종료")


if __name__ == "__main__":
    main()
