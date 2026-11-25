#!/usr/bin/env python3
"""현장 실측값 3개(모니터 가로 cm, 해상도, EEG 단위)를 검증해서 config에 기록. 표준 라이브러리만 사용.

왜: 이 3개는 계획서가 아니라 '이 PC·이 장비'에서 정해지는 값이다. 손으로 JSON을 고치면
    오타(53 → 5.3)나 출처 누락이 생기므로, 범위 검사 + 출처 필수 + 변경 기록을 강제한다.

입력 : --width-cm 53.1 --source "줄자 실측(표시 영역)"
       --resolution 1920x1080 --source "Windows 디스플레이 설정"   (또는 --detect)
       --raw-unit uV --source "BrainAccess 문서 p.12"
       --show   : 현재 값·남은 null·감지 정보만 출력
출력 : config/protocol.json 갱신 + config/CHANGELOG.md에 날짜·이전값·새값·출처 추가
규칙 : 연구 값(RGB, 크기, 필터, QC 등)은 이 도구로 바꿀 수 없다.

예 (PowerShell)
  python scripts\\set_field_values.py --show
  python scripts\\set_field_values.py --detect
  python scripts\\set_field_values.py --width-cm 53.1 --source "줄자 실측, 표시 영역 가로"
"""
import argparse
import json
import os
import platform
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "protocol.json")
LOG = os.path.join(ROOT, "config", "CHANGELOG.md")
FIELDS = {"width_cm": ("monitor", "width_cm"), "resolution": ("monitor", "resolution_px"),
          "raw_unit": ("eeg", "raw_unit")}
UNITS = ["V", "mV", "uV"]


def validate(field, value):
    """검증 통과 시 저장할 값 반환, 실패 시 ValueError."""
    if field == "width_cm":
        v = float(value)
        if not 20 <= v <= 120:
            raise ValueError(f"화면 가로 {v}cm는 범위(20–120cm) 밖 — 단위(cm) 확인")
        return round(v, 2)
    if field == "resolution":
        try:
            w, h = (int(x) for x in str(value).lower().replace(" ", "").split("x"))
        except Exception:
            raise ValueError("해상도 형식은 1920x1080") from None
        if not (640 <= w <= 7680 and 480 <= h <= 4320 and w > h):
            raise ValueError(f"해상도 {w}x{h} 비정상")
        return [w, h]
    if field == "raw_unit":
        v = str(value).replace("µ", "u")
        if v not in UNITS:
            raise ValueError(f"단위는 {UNITS} 중 하나")
        return v
    raise ValueError(field)


def detect_windows_display():
    """Windows: 물리 해상도와 배율(%). 그 외 OS는 None."""
    if platform.system() != "Windows":
        return None
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        ctypes.windll.user32.SetProcessDPIAware()
    u = ctypes.windll.user32
    w, h = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    try:
        scale = round(u.GetDpiForSystem() / 96 * 100)
    except Exception:  # noqa: BLE001
        scale = None
    return dict(resolution=[w, h], scale_percent=scale)


def apply(cfg_path, log_path, field, value, source, who=""):
    if not source or len(source.strip()) < 3:
        raise ValueError("--source(근거) 필수 — 예: '줄자 실측', '장비 문서 p.12'")
    new = validate(field, value)
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    sec, key = FIELDS[field]
    old = cfg[sec][key]
    cfg[sec][key] = new
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    first = not os.path.exists(log_path)
    with open(log_path, "a", encoding="utf-8") as fh:
        if first:
            fh.write("# config 변경 기록 (현장 실측값)\n\n| 일시 | 항목 | 이전 | 새 값 | 근거 | 입력자 |\n|---|---|---|---|---|---|\n")
        fh.write(f"| {datetime.now():%Y-%m-%d %H:%M} | {sec}.{key} | {old} | {new} | {source} | {who} |\n")
    return old, new


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width-cm")
    ap.add_argument("--resolution")
    ap.add_argument("--raw-unit")
    ap.add_argument("--source", help="근거 (필수)")
    ap.add_argument("--who", default="", help="입력자 (역할명 등, 실명 불필요)")
    ap.add_argument("--detect", action="store_true", help="Windows 해상도·배율 감지 후 해상도 기록 제안")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()

    with open(CFG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    det = detect_windows_display()
    if a.show or a.detect or not any([a.width_cm, a.resolution, a.raw_unit]):
        print("현재 값:")
        for f, (sec, key) in FIELDS.items():
            print(f"  {sec}.{key:14s} = {cfg[sec][key]}")
        if det:
            print(f"감지: 물리 해상도 {det['resolution'][0]}x{det['resolution'][1]}, 배율 {det['scale_percent']}%")
            if det["scale_percent"] not in (None, 100):
                print("  [경고] 배율이 100%가 아님 → PsychoPy 창 크기가 달라질 수 있음. 설정 > 디스플레이 > 배율 100% 권장")
            if a.detect:
                print(f"  기록하려면: python scripts\\set_field_values.py --resolution "
                      f"{det['resolution'][0]}x{det['resolution'][1]} --source \"Windows 감지(배율 {det['scale_percent']}%)\"")
        elif a.detect:
            print("감지: Windows가 아니어서 생략")
        print("가로 cm: 화면 '표시 영역'(검은 테두리 제외)을 줄자로 측정")
        print("EEG 단위: BrainAccess 문서·Board 설정에서 확인 (추정 금지)")
        return
    for field, val in (("width_cm", a.width_cm), ("resolution", a.resolution), ("raw_unit", a.raw_unit)):
        if val is None:
            continue
        try:
            old, new = apply(CFG, LOG, field, val, a.source, a.who)
        except ValueError as e:
            sys.exit(f"[거부] {field}: {e}")
        print(f"[기록] {FIELDS[field][0]}.{FIELDS[field][1]}: {old} → {new}  (근거: {a.source})")
    print("다음: python -m pytest tests -q  →  stim_rgb.py --practice 로 크기 실측 확인")


if __name__ == "__main__":
    main()
