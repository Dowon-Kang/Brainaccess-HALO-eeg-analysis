#!/usr/bin/env python3
"""인터프리터별 환경 점검 + 버전 고정 기록. 표준 라이브러리만 사용 (어느 python으로도 실행 가능).

왜: PsychoPy Standalone의 python과 분석용 python은 서로 다른 인터프리터다.
    pylsl을 '분석 환경'에만 설치하면 stim_rgb.py는 자극 PC에서 import 오류가 나거나,
    다른 python으로 실행돼 PsychoPy 설정이 달라진다. 그래서 '실제로 실행할 그 python'으로 이 스크립트를 돌린다.

입력 : --role stim | analysis   [--lock]
처리 : 1) 인터프리터 경로·버전·비트
       2) 역할별 필수 패키지 import + 버전
       3) pylsl: liblsl 버전 + 루프백(outlet → resolve → inlet 1샘플)
       4) stim: psychopy.visual import (창은 열지 않음)
출력 : 콘솔 PASS/FAIL/UNVERIFIED 표
       --lock: locks/<role>-<호스트>.json (전체 결과) + locks/<role>-<호스트>-freeze.txt (pip freeze)
종료코드 : FAIL이 있으면 1

예 (PowerShell)
  & "C:\\Program Files\\PsychoPy\\python.exe" scripts\\env_check.py --role stim --lock
  .venv\\Scripts\\python.exe scripts\\env_check.py --role analysis --lock
"""
import argparse
import importlib
import json
import os
import platform
import socket
import struct
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = {
    "stim": ["psychopy", "pylsl", "numpy"],
    "analysis": ["numpy", "scipy", "mne", "sklearn", "pyxdf", "pylsl", "matplotlib", "pytest"],
}
STIM_PY_OK = ((3, 8), (3, 10))       # PsychoPy 권장 범위 (Standalone 기준). 벗어나면 UNVERIFIED


def check(rows, name, status, evidence):
    rows.append({"check": name, "status": status, "evidence": evidence})


def lsl_loopback(timeout=5.0):
    from pylsl import StreamInfo, StreamInlet, StreamOutlet, resolve_byprop
    sid = f"envcheck-{os.getpid()}-{int(time.time())}"
    out = StreamOutlet(StreamInfo("ENVCHECK", "Markers", 1, 0, "string", sid))
    found = resolve_byprop("source_id", sid, timeout=timeout)
    if not found:
        return False, "자기 자신의 스트림을 찾지 못함 (방화벽/네트워크 어댑터/멀티캐스트 확인)"
    inlet = StreamInlet(found[0])
    inlet.open_stream(timeout=timeout)
    time.sleep(0.2)
    out.push_sample(["ping"])
    s, ts = inlet.pull_sample(timeout=timeout)
    del out
    return (s == ["ping"]), f"수신 {s}, timestamp {ts}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--role", choices=list(REQUIRED), required=True)
    ap.add_argument("--lock", action="store_true", help="locks/ 에 버전 기록")
    ap.add_argument("--skip-loopback", action="store_true")
    a = ap.parse_args()

    rows, versions = [], {}
    pyv = sys.version_info[:2]
    check(rows, "인터프리터", "PASS", f"{sys.executable} | Python {platform.python_version()} "
          f"{struct.calcsize('P') * 8}bit | {platform.platform()}")
    if a.role == "stim":
        ok = STIM_PY_OK[0] <= pyv <= STIM_PY_OK[1]
        check(rows, "Python 버전(PsychoPy)", "PASS" if ok else "UNVERIFIED",
              f"{pyv[0]}.{pyv[1]} (권장 {STIM_PY_OK[0][0]}.{STIM_PY_OK[0][1]}–{STIM_PY_OK[1][0]}.{STIM_PY_OK[1][1]})")
    else:
        check(rows, "Python 버전(분석)", "PASS" if pyv >= (3, 10) else "FAIL", f"{pyv[0]}.{pyv[1]} (≥3.10)")

    for mod in REQUIRED[a.role]:
        try:
            m = importlib.import_module(mod)
            versions[mod] = getattr(m, "__version__", "?")
            check(rows, f"import {mod}", "PASS", versions[mod])
        except Exception as e:  # noqa: BLE001
            hint = ""
            if mod == "pylsl" and a.role == "stim":
                hint = f' → 이 python에 설치: "{sys.executable}" -m pip install -r requirements-stim.txt'
            check(rows, f"import {mod}", "FAIL", f"{type(e).__name__}: {e}{hint}")

    if "pylsl" in versions:
        import pylsl
        versions["liblsl"] = pylsl.library_version()
        check(rows, "liblsl", "PASS", str(versions["liblsl"]))
        if a.skip_loopback:
            check(rows, "LSL 루프백", "UNVERIFIED", "--skip-loopback")
        else:
            try:
                ok, ev = lsl_loopback()
                check(rows, "LSL 루프백", "PASS" if ok else "FAIL", ev)
            except Exception as e:  # noqa: BLE001
                check(rows, "LSL 루프백", "FAIL", f"{type(e).__name__}: {e}")

    if a.role == "stim" and "psychopy" in versions:
        try:
            from psychopy import visual  # noqa: F401
            from psychopy import logging as plog
            check(rows, "psychopy.visual import", "PASS", f"defaultClock={plog.defaultClock.getTime():.3f}s (창 미생성)")
        except Exception as e:  # noqa: BLE001
            check(rows, "psychopy.visual import", "FAIL", f"{type(e).__name__}: {e}")
        check(rows, "화면·주사율", "UNVERIFIED", "stim_rgb.py --practice 실행으로 확인")

    w = max(len(r["check"]) for r in rows)
    print(f"[{a.role}] 환경 점검")
    for r in rows:
        print(f"{r['check']:{w}s}  {r['status']:10s}  {r['evidence']}")
    fail = any(r["status"] == "FAIL" for r in rows)
    unv = [r["check"] for r in rows if r["status"] == "UNVERIFIED"]
    verdict = "NO-GO" if fail else (f"조건부 (UNVERIFIED: {', '.join(unv)})" if unv else "GO")
    print(f"판정: {verdict}")

    if a.lock:
        os.makedirs(os.path.join(ROOT, "locks"), exist_ok=True)
        host = socket.gethostname()
        base = os.path.join(ROOT, "locks", f"{a.role}-{host}")
        try:
            freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True,
                                    text=True, timeout=120).stdout
        except Exception as e:  # noqa: BLE001
            freeze = f"# pip freeze 실패: {e}\n"
        with open(base + "-freeze.txt", "w", encoding="utf-8") as fh:
            fh.write(f"# {a.role} | {sys.executable} | Python {platform.python_version()} | "
                     f"{datetime.now():%Y-%m-%d %H:%M} | 판정 {verdict}\n" + freeze)
        with open(base + ".json", "w", encoding="utf-8") as fh:
            json.dump(dict(role=a.role, host=host, executable=sys.executable, python=platform.python_version(),
                           platform=platform.platform(), versions=versions, checks=rows, verdict=verdict,
                           recorded=datetime.now().isoformat(timespec="seconds")), fh, ensure_ascii=False, indent=2)
        print(f"[기록] {base}.json / {base}-freeze.txt")
        print("       → 이 freeze 파일이 해당 PC의 '검증된 버전 고정'이다. 재설치: python -m pip install -r <freeze>")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
