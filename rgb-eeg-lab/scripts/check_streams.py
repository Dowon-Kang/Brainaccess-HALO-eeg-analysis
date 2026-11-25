#!/usr/bin/env python3
"""LSL 스트림 점검 + EEG 신호 품질 빠른 검사.

데이터 흐름
  입력 : 네트워크상의 LSL 스트림 (BrainAccess Board EEG, RGB_Markers)
  출력 : 콘솔 리포트 (스트림 목록, 실효 srate, 채널별 std/평탄/60Hz 비율),
         --alpha 모드: 눈뜨기/눈감기 O1·O2 알파 파워 비율

사용 예
  python scripts/check_streams.py                       # 목록 + 10초 품질 검사
  python scripts/check_streams.py --alpha               # 알파(Berger) 검증 20s+20s
  python scripts/check_streams.py --blink               # 깜빡임 채널 매핑 검증
  python scripts/check_streams.py --eeg-name BrainAccess --channels Fp1,Fp2,O1,O2
"""
import argparse
import sys

import numpy as np
from pylsl import StreamInlet, resolve_streams
from scipy.signal import welch


def labels_of(info):
    out = []
    ch = info.desc().child("channels").child("channel")
    while not ch.empty():
        out.append(ch.child_value("label"))
        ch = ch.next_sibling()
    return out


def pull(inlet, seconds, srate):
    need = int(seconds * srate)
    data, ts = [], []
    while sum(len(t) for t in ts) < need:
        chunk, t = inlet.pull_chunk(timeout=1.5, max_samples=1024)
        if not t:
            print("[경고] 1.5초 동안 샘플 없음 — 스트림 끊김?")
            continue
        data.append(np.asarray(chunk)); ts.append(np.asarray(t))
    return np.vstack(data), np.concatenate(ts)


def band_power(x, fs, lo, hi):
    f, p = welch(x, fs=fs, nperseg=min(len(x), int(fs * 2)), axis=0)
    m = (f >= lo) & (f <= hi)
    return np.trapezoid(p[m], f[m], axis=0) if hasattr(np, "trapezoid") else np.trapz(p[m], f[m], axis=0)


def pick(labels, wanted, fallback_idx):
    if all(w in labels for w in wanted):
        return [labels.index(w) for w in wanted]
    print(f"[경고] 라벨 {wanted} 를 스트림 라벨 {labels} 에서 못 찾음 → 인덱스 {fallback_idx} 사용. "
          "반드시 깜빡임 테스트로 매핑 확인!")
    return fallback_idx


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eeg-name", default=None, help="EEG 스트림 이름 일부 (기본: type=EEG 첫 스트림)")
    ap.add_argument("--channels", default="Fp1,Fp2,O1,O2")
    ap.add_argument("--index", default="0,1,2,3", help="라벨이 없을 때 쓸 채널 인덱스")
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--line", type=float, default=60.0, help="전원 주파수 (한국 60Hz)")
    ap.add_argument("--alpha", action="store_true")
    ap.add_argument("--blink", action="store_true")
    a = ap.parse_args()

    streams = resolve_streams(wait_time=3.0)
    if not streams:
        sys.exit("[실패] LSL 스트림 없음 — Board 스트리밍/네트워크/방화벽 확인")
    print("=== LSL 스트림 ===")
    for s in streams:
        print(f"- {s.name():25s} type={s.type():8s} ch={s.channel_count():2d} "
              f"srate={s.nominal_srate():6.1f} host={s.hostname()} src={s.source_id()}")
    if not any(s.name() == "RGB_Markers" for s in streams):
        print("[참고] RGB_Markers 없음 (stim_rgb.py 실행 전이면 정상)")

    eeg = [s for s in streams if (a.eeg_name and a.eeg_name.lower() in s.name().lower())
           or (not a.eeg_name and s.type().upper() == "EEG")]
    if not eeg:
        sys.exit("[실패] EEG 스트림 없음 — --eeg-name 지정")
    inlet = StreamInlet(eeg[0], max_buflen=60)
    info = inlet.info()
    fs_nom = info.nominal_srate()
    labels = labels_of(info)
    wanted = a.channels.split(",")
    idx = pick(labels, wanted, [int(i) for i in a.index.split(",")])
    print(f"\n[EEG] {info.name()} 라벨={labels or '(없음)'} → 사용 {dict(zip(wanted, idx))}")
    print(f"[EEG] 시계 보정 offset = {inlet.time_correction(timeout=5):.4f}s")

    if a.alpha:
        input("\n눈 뜨고 화면 중앙 응시 20초 — 준비되면 Enter")
        xo, _ = pull(inlet, 20, fs_nom)
        input("눈 감고 편하게 20초 — 준비되면 Enter (끝나면 소리로 알려주세요)")
        xc, _ = pull(inlet, 20, fs_nom)
        po = band_power(xo[:, idx], fs_nom, 8, 12)
        pc = band_power(xc[:, idx], fs_nom, 8, 12)
        print("\n=== 알파 비율 (눈감기/눈뜨기) ===")
        for n, r in zip(wanted, pc / po):
            print(f"{n:4s} {r:5.2f} {'← 후두 채널 기대: >1' if n.startswith('O') else ''}")
        return

    if a.blink:
        input("\n준비되면 Enter → 10초 동안 2초마다 세게 눈 깜빡이기")
        xb, _ = pull(inlet, 10, fs_nom)
        ptp = np.ptp(xb[:, idx] - np.median(xb[:, idx], axis=0), axis=0)
        print("\n=== 깜빡임 peak-to-peak ===")
        for n, v in zip(wanted, ptp):
            print(f"{n:4s} {v:10.1f}")
        print("기대: Fp1/Fp2 ≫ O1/O2. 반대면 채널 매핑 오류.")
        return

    x, ts = pull(inlet, a.seconds, fs_nom)
    fs_eff = (len(ts) - 1) / (ts[-1] - ts[0])
    gaps = np.sum(np.diff(ts) > 1.5 / fs_nom)
    print(f"\n=== {a.seconds:.0f}초 품질 검사 ===")
    print(f"실효 srate {fs_eff:.2f}Hz (명목 {fs_nom}) / 끊김 {gaps}회 / NaN {np.isnan(x).sum()}개")
    xs = x[:, idx]
    std = xs.std(axis=0)
    line = band_power(xs, fs_nom, a.line - 1, a.line + 1)
    sig = band_power(xs, fs_nom, 1, 30)
    print(f"{'ch':4s} {'std':>10s} {'60Hz/1-30Hz':>12s}  판정")
    for n, s_, l_, g_ in zip(wanted, std, line, sig):
        flag = "평탄!" if s_ < 1e-6 else ("전원잡음↑" if l_ / g_ > 0.5 else "OK")
        print(f"{n:4s} {s_:10.2f} {l_ / g_:12.3f}  {flag}")
    if abs(fs_eff - 250) > 2:
        print("[경고] 실효 srate가 250Hz와 다름")


if __name__ == "__main__":
    main()
