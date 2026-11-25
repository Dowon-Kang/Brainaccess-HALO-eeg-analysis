#!/usr/bin/env python3
"""BrainAccess Board 업데이트 후: 지금 송출 중인 EEG LSL 스트림을 기준 파일과 비교 (장비 미착용 가능).

입력 : 기준 data/board_v3.0.0_stream_reference.json (Board 3.0.0, 2026-11-21 XDF에서 추출), 실시간 LSL EEG 스트림
비교 : 이름·type·source_id·채널 수·형식·명목/실측 srate·채널 라벨/단위/type, LabRecorder RequiredStreams 이름
출력 : PASS/FAIL 표, 종료코드 0(전부 일치)/1
주의 : 원신호 크기(SD)는 착용 상태에 따라 달라 참고로만 표시 (단위 변화는 채널 unit과 SD 자릿수로 함께 판단)

예  .venv\\Scripts\\python.exe scripts\\check_board_stream.py
"""
import json
import os
import sys
import time

import numpy as np
import pylsl

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "data", "board_v3.0.0_stream_reference.json")


def main():
    ref = json.load(open(sys.argv[1] if len(sys.argv) > 1 else REF, encoding="utf-8"))
    ss = pylsl.resolve_byprop("type", "EEG", 1, 5.0) or [s for s in pylsl.resolve_streams(3.0)
                                                         if s.name() == ref["name"]]
    if not ss:
        sys.exit("[FAIL] EEG LSL 스트림 없음 — Board에서 HALO 연결·스트리밍 후 다시 실행")
    inlet = pylsl.StreamInlet(ss[0], max_buflen=30)
    info = inlet.info()
    ch = info.desc().child("channels").child("channel")
    chans = []
    for _ in range(info.channel_count()):
        chans.append(dict(label=ch.child_value("label"), unit=ch.child_value("unit"), type=ch.child_value("type")))
        ch = ch.next_sibling()
    inlet.open_stream(5.0)
    time.sleep(10)
    x, ts = inlet.pull_chunk(timeout=2.0, max_samples=100000)
    x, ts = np.asarray(x), np.asarray(ts)
    srate = (len(ts) - 1) / (ts[-1] - ts[0]) if len(ts) > 1 else 0.0
    rows = []

    def chk(name, now, want, ok=None):
        ok = (now == want) if ok is None else ok
        rows.append((name, "PASS" if ok else "FAIL", f"지금 {now} / 기준 {want}"))

    chk("스트림 이름", info.name(), ref["name"])
    chk("type", info.type(), ref["type"])
    chk("source_id", info.source_id(), ref["source_id"])
    chk("채널 수", info.channel_count(), ref["channel_count"])
    fmt = {pylsl.cf_float32: "float32", pylsl.cf_double64: "double64", pylsl.cf_int32: "int32"}.get(info.channel_format(),
                                                                                                    str(info.channel_format()))
    # 형식: Board 3.1.0은 double64(3.0.0 float32). XDF·pyxdf·분석은 float64로 읽어 영향 없음(정밀도↑, 파일 크기↑) → 참고
    rows.append(("형식", "PASS" if fmt == ref["channel_format"] else "참고",
                 f"지금 {fmt} / 기준 {ref['channel_format']}" + ("" if fmt == ref["channel_format"]
                                                                else " — 분석 영향 없음(모두 float64로 읽음)")))
    chk("명목 srate", info.nominal_srate(), ref["nominal_srate"])
    chk("실측 srate(10s)", round(srate, 2), ref["measured_srate"], ok=abs(srate - ref["nominal_srate"]) <= 0.5)
    for i, rc in enumerate(ref["channels"]):
        now = chans[i] if i < len(chans) else {}
        chk(f"채널{i} 라벨/단위/type", f"{now.get('label')}/{now.get('unit')}/{now.get('type')}",
            f"{rc.get('label')}/{rc.get('unit')}/{rc.get('type')}",
            # type은 대소문자 무시: 3.1.0이 보조 채널 type을 대문자로 바꿈(contact→CONTACT 등). 코드는 라벨만 사용
            ok=now.get("label") == rc.get("label") and now.get("unit") == rc.get("unit")
            and (now.get("type") or "").upper() == (rc.get("type") or "").upper())
    req = ref["labrecorder_required"]
    chk("LabRecorder 필수 스트림 이름", f"{info.name()} ({info.hostname()})", req, ok=f"{info.name()} ({info.hostname()})" == req)
    labels = [c["label"] for c in chans]
    eeg_i = [labels.index(c) for c in ("O1", "O2", "Fp2", "Fp1") if c in labels]
    if len(eeg_i) == 4 and len(x):
        sd = [round(float(v), 1) for v in x[:, eeg_i].std(0)]
        rows.append(("원신호 SD(µV, 참고)", "참고", f"지금 {sd} / 기준 {ref.get('raw_eeg_sd_uV')} — 자릿수가 1000배 다르면 단위 변화 의심"))
    if "Battery" in labels and len(x):
        rows.append(("배터리(참고)", "참고", f"{x[-1, labels.index('Battery')]:.0f}%"))

    print(f"{'점검 항목':<28}{'상태':<6}근거")
    for r in rows:
        print(f"{r[0]:<28}{r[1]:<6}{r[2]}")
    fails = [r[0] for r in rows if r[1] == "FAIL"]
    print(f"\n판정: {'GO' if not fails else 'NO-GO (' + ', '.join(fails) + ')'}  — 기준: Board {ref['board_version']}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
