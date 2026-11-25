#!/usr/bin/env python3
"""RGB 색상 관찰/상상 자극 (PsychoPy + LSL 마커). 모든 수치는 config/protocol.json.

데이터 흐름
  입력 : config/protocol.json, CLI(참가자 ID, 모드)
  출력 : 1) LSL 'RGB_Markers' (LabRecorder → XDF)
         2) data/<ID>_<mode>_<시각>_events.csv  — 이벤트 1행씩 (마커와 '같은' LSL 시각)
         3) 같은 이름의 .json — seed, 실제 RGB, 모니터 설정, fps, 소프트웨어 버전 등 메타데이터

화면     : gray 배경 + 중앙 정사각형 (square_cm, 시청거리 60cm에서 10°). 관찰 단계만 정사각형에 색.
시퀀스   : config.design.phases 순서 (현재 gray1 obs1 gray2 obs2 gray3 img1, 각 phase_sec, 프레임 수 기반)
           EXP_START·JSON에 phases= 로 기록 → QC가 기록된 순서로 검사 (구버전 8단계 기록도 검사 가능)
seed     : base + 참가자 순번 + session_offset×(세션−1) (연습은 + practice_offset). 본측정은 --session 필수 (변경3, 2026-11-24).
           순서는 protocol.sequence_plan(seed)로 재생성 가능. seed·session은 EXP_START·JSON에 기록 → QC는 기록된 seed로 대조.
마커     : 단계 "b{block}|s{seq:03d}|{phase}{rep}|{color}"
           이벤트 "EXP_START|key=val..." "BLOCK_START|b1" "BLOCK_END|b1" "REST_START|b2" "REST_END|b2"
                  "PAUSE|s012" "RESUME|s012" "STOP|b2|s031" "EXP_END"
           마커 시각 = flip(vsync) 시각을 LSL 시계로 환산한 값(protocol.flip_to_lsl)을 push_sample에 명시.
                      push가 늦어도 타임스탬프는 flip 시각. CSV: onset_lsl(=마커 시각), push_lsl, flip_to_push_ms, clock_ok
           모니터 자체 입력 지연은 소프트웨어로 측정 불가 → --photodiode(연습 전용)로 외부 센서 측정

모드
  --practice           : 연습 6시퀀스(1블록×색2). 모니터 cm 미측정이면 PROVISIONAL 크기 허용.
  --practice --one-block: 1블록 18시퀀스 리허설
  --practice --photodiode: 왼쪽 아래 패치(관찰=흰색, 그 외=검정)로 화면 지연 측정용. 본측정 불가
  (기본) 본측정        : 90시퀀스(현재 설계 약 29분). config.stimulus/monitor/design에 null이면 실행 거부.
  --start-block N      : 본측정 이어 하기. 같은 seed 계획의 블록 N부터 (시퀀스 번호 유지). 별도 XDF·CSV로 저장되며
                         계획서 외 진행이므로 세션 로그·계획서 변경 기록에 사유를 남긴다.
키       : ESC 3번(3초 안) = STOP(중단) — 실수 1회로 세션이 끝나지 않게 (P003 2026-11-21 블록 2 전 중단)
           자극 단계 중에는 화면 변화 없이 단계 끝에 판정, 안내·휴식 화면에는 "ESC 1/3" 표시
           P = 현재 시퀀스 끝난 뒤 PAUSE (스페이스로 RESUME)
           stop_reason: "ESC×3 (자극 창)" / "콘솔 Ctrl+C 또는 예외" / 녹화 끊김 사유
녹화 확인: LabRecorder가 '이번 실행의' RGB_Markers를 녹화 중인지 두 가지로 확인.
           a) outlet.have_consumers() — 실행마다 source_id(rgb-stim-<ID>_<mode>_<시각>)가 새로 생기므로 이전 녹화는 감지 안 됨
           b) --xdf-dir(기본 data = rgb_eeg.cfg StudyRoot)에 이번 실행 이후 새 XDF가 생김 — 연결만 잠깐 생기고
              파일은 안 써지는 경우(4.0 초기 P003 2회)를 걸러냄. 경로는 JSON xdf_file에 기록
           1) 창 열기 전: a 1초 이상 유지 + b 가 될 때까지 콘솔에서 대기 (Ctrl+C 취소)
           2) 각 블록 시작 전: 연결이 끊겼거나 XDF 크기가 직전 블록 이후 늘지 않았으면 STOP (사유는 콘솔·JSON stop_reason)
EEG 감시: 시작 전 EEG LSL 스트림이 없거나 샘플이 안 들어오면 실행 거부(녹화 확인 필수 실행). 실행 중 단계(3s) 끝마다·블록 시작 전
           마지막 EEG 샘플이 EEG_STALE_SEC(3s)보다 오래되면 STOP, stop_reason "EEG 스트림 끊김 (...)".
           XDF 크기 확인만으로는 못 잡음: EEG가 끊겨도 마커가 계속 써져 XDF는 커짐 (P003 2026-11-21 run-08, 블록 3 중 끊김)
드롭 방지: 실험 중 프로세스 우선순위 상승(core.rush), 가비지 컬렉션 정지.
           CSV 디스크 쓰기·GC는 시간 측정이 없는 안내·휴식 화면(screen)에서만 → 단계 전환 프레임에 끼지 않음.
           강제 종료(프로세스 kill) 시 마지막 화면 이후 CSV 행은 유실될 수 있음 (마커는 XDF에 있음).
           예외: --windowed, 연습 전용 --allow-no-recorder. 본측정은 예외 없음.

예 (PowerShell)
  python scripts\\stim_rgb.py --participant T00 --practice --windowed
  python scripts\\stim_rgb.py --participant P01
"""
import argparse
import csv
import gc
import json
import math
import os
import platform
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol  # noqa: E402
import ui  # noqa: E402

# 운영 키 설정 (프로토콜 값 아님 → config 대상 아님)
ESC_PRESSES = 3        # ESC를 이 횟수만큼
ESC_WINDOW_SEC = 3.0   # 이 시간 안에 눌러야 중단


class EscCounter:
    """ESC 연타 판정. feed()에 getKeys(timeStamped=True) 결과 [(key, t)]를 넣는다.
    시각은 같은 시계(psychopy core.getTime)끼리만 비교 → 자극 단계 끝에 몰아 읽어도 실제 누른 간격으로 판정."""

    def __init__(self, n=ESC_PRESSES, window=ESC_WINDOW_SEC):
        self.n, self.window, self.times, self.triggered = n, window, [], False

    def feed(self, timed_keys):
        for k, t in timed_keys:
            if k == "escape":
                self.times.append(t)
        self.times = self.times[-self.n:]
        self.triggered = len(self.times) >= self.n and self.times[-1] - self.times[0] <= self.window
        return self.triggered

    def pending(self, now):
        """now 기준 window 안에 누른 횟수 (화면 표시용)."""
        return sum(1 for t in self.times if now - t <= self.window)


EEG_STALE_SEC = 3.0    # 운영 설정: 마지막 EEG 샘플이 이보다 오래되면 '끊김' → STOP (P003 2026-11-21 세션 중 장치 끊김)


class EegWatch:
    """세션 중 EEG 스트림이 계속 들어오는지 감시. 단계(3s) 끝마다 check() — 버퍼를 비우고(비차단)
    마지막 샘플 시각(송신 시계 + time_correction)과 현재 LSL 시각 차이로 판정. 수신 시각이 아니라 샘플 시각을 써서
    버퍼에 남아 있던 옛 샘플을 '살아 있음'으로 오인하지 않는다."""

    def __init__(self, info, pylsl, stale=EEG_STALE_SEC):
        self.pylsl, self.stale, self.name = pylsl, stale, info.name()
        self.inlet = pylsl.StreamInlet(info, max_buflen=60)
        self.inlet.open_stream(5.0)
        try:
            self.corr = self.inlet.time_correction(timeout=5.0)
        except Exception:
            self.corr = 0.0
        self.last_ts = None
        self.age = None

    def check(self):
        """반환 True=정상. False면 self.age(초)에 마지막 샘플 경과 시간 (샘플 없음이면 None)."""
        while True:
            _, ts = self.inlet.pull_chunk(timeout=0.0, max_samples=4096)
            if not ts:
                break
            self.last_ts = ts[-1] + self.corr
        if self.last_ts is None:
            self.age = None
            return False
        self.age = self.pylsl.local_clock() - self.last_ts
        return self.age <= self.stale

    def reason(self):
        return (f"EEG 스트림 끊김 ({self.name}: 샘플 없음)" if self.age is None
                else f"EEG 스트림 끊김 ({self.name}: 마지막 샘플 {self.age:.1f}s 전)")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--participant", required=True, help="숫자로 끝나는 ID (T00, P01 …). 이름 금지")
    p.add_argument("--practice", action="store_true")
    p.add_argument("--one-block", action="store_true", help="--practice와 함께: 1블록 18시퀀스")
    p.add_argument("--screen", type=int, default=0)
    p.add_argument("--windowed", action="store_true", help="화면 검토용 창 모드 (본측정 불가)")
    p.add_argument("--font", default="Malgun Gothic")
    p.add_argument("--outdir", default="data")
    p.add_argument("--config", default=None)
    p.add_argument("--photodiode", action="store_true", help="연습 전용: 지연 측정용 모서리 패치")
    p.add_argument("--photodiode-px", type=int, default=60)
    p.add_argument("--allow-no-recorder", action="store_true", help="연습 전용: LabRecorder 녹화 확인 생략")
    p.add_argument("--start-block", type=int, default=1, help="본측정 이어 하기: 이 블록부터 (기본 1)")
    p.add_argument("--session", type=int, default=None,
                   help="같은 참가자의 세션 번호(1,2,3…) → seed가 달라져 색 순서가 바뀜. 본측정 필수, 연습 기본 1. "
                        "이어 하기(--start-block)는 중단된 실행과 같은 번호")
    p.add_argument("--xdf-dir", default=None,
                   help="LabRecorder 저장 폴더 (기본 --outdir = rgb_eeg.cfg의 StudyRoot). 여기에 새 XDF가 생겨야 시작")
    return p.parse_args(argv)


def recorder_required(a):
    """LabRecorder 녹화 확인 없이는 시작 불가인지. 창 모드·연습 생략 옵션만 예외 (본측정은 resolve_run에서 거부)."""
    return not (a.windowed or a.allow_no_recorder)


def find_new_xdf(root, since):
    """root 아래에서 since(epoch 초) 이후 생기거나 수정된 .xdf 중 가장 최근 경로, 없으면 None.
    os.stat은 파일을 직접 열어 읽으므로 LabRecorder가 쓰는 중인 파일도 크기·시각이 최신."""
    best = None
    for dp, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".xdf"):
                p = os.path.join(dp, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                m = max(st.st_mtime, st.st_ctime)
                if m >= since and (best is None or m > best[1]):
                    best = (p, m)
    return best[0] if best else None


def has_focus(win):
    """자극 창이 키보드 포커스를 가졌는지 (Windows 외에는 항상 True)."""
    if sys.platform != "win32":
        return True
    import ctypes
    hwnd = getattr(win.winHandle, "_hwnd", None)
    return bool(hwnd) and ctypes.windll.user32.GetForegroundWindow() == hwnd


def force_focus(win):
    """자극 창으로 키보드 포커스 가져오기. 반환: 성공 여부.
    Windows는 뒤에서 실행된 프로세스의 새 창이 포커스를 가져가는 것을 막는다 → 창은 맨 앞에 보여도
    키는 LabRecorder(Start 후 포커스 = Stop 버튼)로 가서 스페이스가 녹화를 멈춤 (P003 2026-11-13).
    현재 포그라운드 스레드에 입력을 잠시 연결(AttachThreadInput)한 뒤 SetForegroundWindow."""
    if sys.platform != "win32" or has_focus(win):
        return True
    import ctypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    hwnd = win.winHandle._hwnd
    fg_tid = u.GetWindowThreadProcessId(u.GetForegroundWindow(), None)
    me = k.GetCurrentThreadId()
    attached = bool(fg_tid) and fg_tid != me and bool(u.AttachThreadInput(fg_tid, me, True))
    try:
        u.ShowWindow(hwnd, 5)                 # SW_SHOW
        u.BringWindowToTop(hwnd)
        u.SetForegroundWindow(hwnd)
        u.SetFocus(hwnd)
    finally:
        if attached:
            u.AttachThreadInput(fg_tid, me, False)
    return has_focus(win)


def resolve_run(cfg, a):
    """모드·설계·자극 파라미터 확정. 반환 dict. 본측정 조건 불충족이면 SystemExit."""
    d, st, mon = cfg["design"], cfg["stimulus"], cfg["monitor"]
    provisional = []
    if a.practice:
        if a.start_block != 1:
            sys.exit("[거부] --start-block은 본측정 전용")
        mode = "block" if a.one_block else "practice"
        blocks, pcpb = 1, (d["per_color_per_block"] if a.one_block else 2)
    else:
        if a.one_block:
            sys.exit("[거부] --one-block은 --practice와 함께만")
        if a.windowed:
            sys.exit("[거부] 본측정은 전체화면만 (--windowed 불가)")
        if a.photodiode:
            sys.exit("[거부] --photodiode는 연습 전용 (패치가 시각 자극을 바꿈)")
        if a.allow_no_recorder:
            sys.exit("[거부] 본측정은 LabRecorder 녹화 확인을 생략할 수 없음")
        miss = protocol.missing(cfg, sections={"stimulus", "monitor", "design", "seed"})
        if miss:
            sys.exit("[거부] 본측정 불가 — config 값 없음(현장 실측 필요):\n  " + "\n  ".join(miss))
        mode, blocks, pcpb = "main", d["blocks"], d["per_color_per_block"]
        if not 1 <= a.start_block <= blocks:
            sys.exit(f"[거부] --start-block은 1~{blocks}")
    if mon["width_cm"] is None or mon["resolution_px"] is None:
        provisional.append("monitor.width_cm/resolution_px 미측정 → 정사각형 크기 화면높이 30% 대체")
    if a.session is None and not a.practice:
        sys.exit("[거부] 본측정은 --session N 필요 (같은 참가자 첫 세션 1, 다음 2 …; 이어 하기는 중단된 실행과 같은 번호)")
    session = a.session or 1
    try:
        seed = protocol.seed_for(cfg, a.participant, a.practice, session)
    except ValueError as e:
        sys.exit(f"[거부] {e}")
    plan = protocol.sequence_plan(seed, blocks, pcpb, d["max_same_color_run"])
    return dict(mode=mode, blocks=blocks, pcpb=pcpb, seed=seed, session=session, plan=plan, provisional=provisional,
                start_block=a.start_block, phases=protocol.phases(cfg),
                colors={c: tuple(v) for c, v in st["colors_rgb255"].items()}, gray=tuple(st["gray_rgb255"]))


def square_px(cfg, win_w, win_h):
    mon, st = cfg["monitor"], cfg["stimulus"]
    if mon["width_cm"] and mon["resolution_px"]:
        px = st["square_cm"] / mon["width_cm"] * mon["resolution_px"][0]
        deg = 2 * math.degrees(math.atan(st["square_cm"] / 2 / mon["distance_cm"]))
        return px, f"{st['square_cm']}cm = {px:.1f}px, 시청거리 {mon['distance_cm']}cm에서 {deg:.2f}° (계획 {st['square_deg']}°)"
    return 0.3 * win_h, "PROVISIONAL: 모니터 cm 미측정 → 화면높이 30%"


def main(argv=None):
    a = parse_args(argv)
    cfg = protocol.load(a.config)
    run = resolve_run(cfg, a)

    import psychopy
    import pylsl
    from pylsl import StreamInfo, StreamOutlet, local_clock
    from psychopy import core, event, visual
    from psychopy import logging as plog

    os.makedirs(a.outdir, exist_ok=True)
    xdf_dir = a.xdf_dir or a.outdir
    t_created = time.time() - 1.0
    run_id = f"{a.participant}_{run['mode']}_{datetime.now():%Y%m%d_%H%M%S}"
    stem = os.path.join(a.outdir, run_id)
    # source_id를 실행마다 다르게: 같으면 이전 녹화의 inlet이 새 outlet에 자동 재연결되어 녹화 확인이 무력화됨
    outlet = StreamOutlet(StreamInfo("RGB_Markers", "Markers", 1, 0, "string", f"rgb-stim-{run_id}"))
    need_rec = recorder_required(a)
    n_seq = len(run["plan"])
    first_seq = (run["start_block"] - 1) * n_seq // run["blocks"] + 1
    ui.sub("자극 프로그램")
    ui.kv("모드", {"main": "본측정", "practice": "연습"}.get(run["mode"], run["mode"]))
    ui.kv("참가자", a.participant)
    ui.kv("세션 / seed", f"{run['session']} / {run['seed']}")
    ui.kv("시작 블록", f"{run['start_block']} / {run['blocks']}" + (f"  (이어 하기, 시퀀스 {first_seq}부터)" if run["start_block"] > 1 else ""),
          color="yellow" if run["start_block"] > 1 else None)
    ui.kv("녹화 확인", "필수" if need_rec else "생략", color=None if need_rec else "yellow")
    xdf_path, xdf_size = None, 0
    # EEG 감시: 녹화 확인 필수 실행(본측정 포함)에서는 EEG 스트림이 없으면 시작 안 함, 생략 모드는 있으면 감시
    eeg_found = pylsl.resolve_byprop("type", "EEG", 1, 5.0)
    if not eeg_found and need_rec:
        ui.fail_exit("EEG LSL 스트림 없음", "BrainAccess Board에서 장치 연결·스트리밍 확인 후 다시 실행")
    eeg_watch = EegWatch(eeg_found[0], pylsl) if eeg_found else None
    if eeg_watch:
        time.sleep(1.0)
        if not eeg_watch.check():
            if need_rec:
                ui.fail_exit(eeg_watch.reason(), "장치 연결·배터리 확인 후 다시 실행")
            ui.tag("warn", f"{eeg_watch.reason()} — 생략 모드라 감시 끔"); eeg_watch = None
    if eeg_watch:
        ui.tag("ok", f"EEG 감시 켬: {eeg_watch.name}", f"단계마다 확인, {EEG_STALE_SEC:.0f}초 이상 끊기면 자동 STOP")
    else:
        ui.tag("skip", "EEG 감시 안 함")
    if need_rec:
        # 연결(have_consumers)만으로는 부족: 잠깐 붙었다 떨어지는 연결·저장 실패를 녹화로 오인함
        # → 저장 폴더에 이번 실행 이후 새 XDF가 생기고 연결이 1초 이상 유지돼야 시작
        ui.tag("wait", ui.c("LabRecorder 녹화 시작을 기다리는 중", "bold"),
               "1) 파일명 확인  2) Update  3) EEG·RGB_Markers 체크  4) Start",
               f"저장 폴더: {os.path.abspath(xdf_dir)}",
               ui.c("취소: Ctrl+C", "gray"))
        warned, t_wait, stable = False, time.time(), 0
        try:
            while True:
                stable = stable + 1 if outlet.have_consumers() else 0
                xdf_path = find_new_xdf(xdf_dir, t_created) if stable else None
                if stable >= 5 and xdf_path:
                    break
                if stable >= 25 and not xdf_path and not warned:
                    ui.tag("warn", f"마커 연결은 있지만 새 XDF가 없음 ({os.path.abspath(xdf_dir)})",
                           "LabRecorder를 닫고 바탕 화면 'LabRecorder (RGB EEG)' 바로 가기로 다시 열기")
                    warned = True
                if time.time() - t_wait > 120 and not warned:
                    ui.tag("warn", "2분째 녹화 미감지", "LabRecorder에서 Start를 눌렀는지, RGB_Markers가 체크됐는지 확인")
                    warned = True
                time.sleep(0.2)
        except KeyboardInterrupt:
            ui.tag("stop", "녹화 대기 중 취소 — 자극 창 열지 않음, 기록 파일 없음")
            sys.exit(1)
        xdf_size = os.path.getsize(xdf_path)
        ui.tag("ok", f"LabRecorder 녹화 감지: {ui.c(os.path.basename(xdf_path), 'bold')}", "자극 창을 엽니다")

    win = visual.Window(fullscr=not a.windowed, size=(1280, 720), screen=a.screen,
                        color=run["gray"], colorSpace="rgb255", units="pix",
                        allowGUI=a.windowed, waitBlanking=True)
    win.mouseVisible = False
    if force_focus(win):
        ui.tag("ok", "키보드 포커스: 자극 창")
    else:
        ui.tag("warn", "키보드 포커스 확보 실패 → 화면 안내에 따라 자극 창 클릭")
    fps = win.getActualFrameRate(nIdentical=20, nMaxFrames=300, nWarmUpFrames=30)
    if fps is None:
        win.close(); sys.exit("[FAIL] 주사율 측정 실패")
    if fps < cfg["monitor"]["min_refresh_hz"] - 1:
        win.close(); sys.exit(f"[FAIL] 주사율 {fps:.1f}Hz < {cfg['monitor']['min_refresh_hz']}Hz")
    n_frames = int(round(cfg["stimulus"]["phase_sec"] * fps))
    win_w, win_h = win.size
    res = cfg["monitor"]["resolution_px"]
    if res and not a.windowed and (int(res[0]), int(res[1])) != (int(win_w), int(win_h)):
        win.close(); sys.exit(f"[FAIL] config 해상도 {res} ≠ 실제 {win_w}x{win_h} — 디스플레이 배율/해상도 확인")
    side, size_note = square_px(cfg, win_w, win_h)
    ui.tag("info", f"화면 {fps:.3f}Hz → 단계 {n_frames}프레임 = {n_frames / fps:.4f}s", f"정사각형 {size_note}")
    if run["provisional"]:
        print("[PROVISIONAL]", "; ".join(run["provisional"]))
    ui.tag("info", "진행은 자극 창에서 (콘솔에는 블록 시작만 표시)", ui.c("중단: 자극 창에서 ESC 3번(3초 안)  |  일시정지: P", "gray"))

    square = visual.Rect(win, width=side, height=side, fillColor=run["gray"], colorSpace="rgb255", lineWidth=0)
    fix = visual.TextStim(win, text="+", height=side * 0.12, color="white", font=a.font) \
        if cfg["stimulus"]["fixation"] else None
    cue = visual.Circle(win, radius=side * 0.04, edges=64, lineColor="white", fillColor=None, lineWidth=3)
    msg = visual.TextStim(win, text="", height=28, color="white", font=a.font, wrapWidth=win_w * 0.8)
    tag = visual.TextStim(win, text="PROVISIONAL" if run["provisional"] else "", height=18, color="yellow",
                          pos=(0, -win_h / 2 + 30))
    pd_px = a.photodiode_px
    pd = visual.Rect(win, width=pd_px, height=pd_px, pos=(-win_w / 2 + pd_px / 2, -win_h / 2 + pd_px / 2),
                     fillColor="black", lineWidth=0) if a.photodiode else None
    # 첫 그리기 지연 방지: 자극을 뒤 버퍼에 한 번 그려 GPU 자원을 미리 준비 (flip 없음 → 화면 변화 없음)
    for stim in (square, fix, cue, pd):
        if stim is not None:
            stim.draw()
    win.clearBuffer()
    frame_dur = 1.0 / fps

    meta = dict(participant=a.participant, mode=run["mode"], session=run["session"], seed=run["seed"], blocks=run["blocks"],
                pcpb=run["pcpb"], n_sequences=len(run["plan"]), plan_version=cfg["plan_version"],
                script_version=protocol.SCRIPT_VERSION, fps=round(fps, 4), n_frames=n_frames,
                window=[int(win_w), int(win_h)], fullscreen=not a.windowed, square_px=round(side, 2),
                square_note=size_note, colors_rgb255=cfg["stimulus"]["colors_rgb255"],
                gray_rgb255=cfg["stimulus"]["gray_rgb255"], color_mode=cfg["stimulus"]["color_mode"],
                monitor=cfg["monitor"], eeg=cfg["eeg"], provisional=run["provisional"],
                photodiode=bool(a.photodiode), marker_timestamp="flip→LSL 환산(protocol.flip_to_lsl)",
                recorder_check=need_rec, xdf_file=xdf_path,
                eeg_watch=(dict(stream=eeg_watch.name, stale_sec=EEG_STALE_SEC, time_correction=round(eeg_watch.corr, 6))
                           if eeg_watch else None), start_block=run["start_block"], phases=protocol.phases_tag(run["phases"]),
                rest_sec=cfg["design"]["rest_sec"],
                versions=dict(python=platform.python_version(), psychopy=psychopy.__version__,
                              pylsl=getattr(pylsl, "__version__", "?"), liblsl=pylsl.library_version(),
                              os=platform.platform()),
                started=datetime.now().isoformat(timespec="seconds"))
    with open(stem + "_events.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    fcsv = open(stem + "_events.csv", "w", newline="", encoding="utf-8")
    w = csv.writer(fcsv)
    w.writerow(["event_id", "participant", "mode", "seed", "version", "block", "seq", "phase", "rep", "color",
                "marker", "onset_lsl", "offset_est_lsl", "flip_psychopy", "n_frames",
                "push_lsl", "flip_to_push_ms", "clock_ok"])
    eid = [0]
    version = f"{cfg['plan_version']}|stim{protocol.SCRIPT_VERSION}"

    timing = dict(n=0, bad=0, delays=[])

    def push(marker, flip_t=None):
        """flip_t가 있으면 flip 시각으로 환산한 타임스탬프로 push. 반환 (ts, push_lsl, delay, ok)."""
        lsl_now = local_clock()
        ps_now = plog.defaultClock.getTime()
        ts, delay, ok = protocol.flip_to_lsl(lsl_now, ps_now, flip_t, frame_dur) if flip_t is not None \
            else (lsl_now, None, True)
        outlet.push_sample([marker], ts)        # CSV에 같은 ts 기록 → 마커 시각 = 로그 시각
        if flip_t is not None:
            timing["n"] += 1
            timing["bad"] += 0 if ok else 1
            if delay is not None:
                timing["delays"].append(delay)
        return ts, lsl_now, delay, ok

    def row(marker, t, block="", seq="", phase="EVENT", rep="", color="", flip=None, offset=None, nf="",
            push_lsl=None, delay=None, ok=True):
        eid[0] += 1
        w.writerow([eid[0], a.participant, run["mode"], run["seed"], version, block, seq, phase, rep, color,
                    marker, f"{t:.6f}", "" if offset is None else f"{offset:.6f}",
                    "" if flip is None else f"{flip:.6f}", nf,
                    "" if push_lsl is None else f"{push_lsl:.6f}",
                    "" if delay is None else f"{delay * 1000:.3f}", int(ok)])

    def emit(marker, block="", seq=""):
        t, *_ = push(marker)
        row(marker, t, block, seq)
        return t

    esc = EscCounter()

    def screen(text, seconds=None):
        fcsv.flush()                    # 디스크 쓰기·GC는 시간 측정 없는 화면에서만
        gc.collect()
        event.clearEvents()
        timer = core.CountdownTimer(seconds) if seconds else None
        n = 0
        while True:
            focused = has_focus(win)
            if not focused and n % 30 == 0:          # 0.5초마다 다시 시도 (스페이스가 LabRecorder로 가지 않게)
                focused = force_focus(win)
            n += 1
            k_esc = esc.pending(core.getTime())
            msg.text = (text if timer is None else f"{text}\n\n{int(timer.getTime()) + 1}초") \
                + ("" if focused else "\n\n[운영자] 키 입력이 이 화면으로 오지 않음 — 화면을 마우스로 한 번 클릭") \
                + (f"\n\n[중단] ESC {k_esc}/{esc.n} — {esc.window:.0f}초 안에 {esc.n}번 누르면 중단" if k_esc else "")
            msg.draw(); tag.draw(); win.flip()
            keys = event.getKeys(["space", "escape"], timeStamped=True)
            if esc.feed(keys):
                raise KeyboardInterrupt
            names = [k for k, _ in keys]
            if (timer is not None and timer.getTime() <= 0) or (timer is None and "space" in names):
                return

    win.recordFrameIntervals = True
    win.refreshThreshold = 1.0 / fps * 1.5
    cur_b, cur_s, aborted, stop_reason = 0, 0, False, "콘솔 Ctrl+C 또는 예외"
    done_s, stim_drops = 0, 0          # 완료 시퀀스 수, 자극 단계 중 드롭 (안내·휴식 화면 드롭은 판정 제외)
    rushed = core.rush(True)
    gc.disable()
    meta.update(priority_raised=bool(rushed), gc_disabled=True)
    try:
        screen(f"[{run['mode']}] 참가자 {a.participant}\n\n"
               "가운데 사각형이 색으로 바뀌면 바라보고,\n작은 원(○)이 보이면 직전 색을 떠올리세요.\n"
               "가운데를 보고, 사각형에 색이 있는 동안 깜빡임을 줄여주세요.\n\n[스페이스] 시작")
        emit(f"EXP_START|mode={run['mode']}|blocks={run['blocks']}|pcpb={run['pcpb']}|seed={run['seed']}|session={run['session']}"
             f"|nseq={len(run['plan'])}|fps={fps:.3f}|frames={n_frames}"
             f"|provisional={int(bool(run['provisional']))}|photodiode={int(bool(a.photodiode))}"
             f"|start_block={run['start_block']}|phases={protocol.phases_tag(run['phases'])}|version={version}")
        prev_block = 0
        pause_req = False
        for seq_i, (b, color) in enumerate(run["plan"], start=1):
            if b < run["start_block"]:              # 이어 하기: 앞 블록 건너뜀 (시퀀스 번호는 계획 그대로)
                continue
            if b != prev_block:
                if prev_block:
                    emit(f"BLOCK_END|b{prev_block}", prev_block)
                    emit(f"REST_START|b{b}", b)
                    screen("휴식 중입니다", seconds=cfg["design"]["rest_sec"])
                    emit(f"REST_END|b{b}", b)
                cur_b = b
                screen(f"블록 {b}/{run['blocks']}\n\n준비되면 [스페이스]")
                if eeg_watch is not None and not eeg_watch.check():
                    stop_reason = eeg_watch.reason()
                    raise KeyboardInterrupt
                if need_rec:                                   # 실행 중 Stop·LabRecorder 종료 → 파일이 나뉘므로 중단
                    size_now = os.path.getsize(xdf_path) if os.path.exists(xdf_path) else -1
                    if not outlet.have_consumers():
                        stop_reason = "LabRecorder 녹화 끊김 (마커 연결 없음)"
                        raise KeyboardInterrupt
                    if b > run["start_block"] and size_now <= xdf_size:
                        stop_reason = f"XDF 파일이 커지지 않음 ({os.path.basename(xdf_path)})"
                        raise KeyboardInterrupt
                    xdf_size = size_now
                # 진행 표시 (안내 화면 직후·자극 전이라 타이밍 영향 없음)
                ui.tag("info", f"블록 {b}/{run['blocks']} 시작  {datetime.now():%H:%M:%S}  (시퀀스 {seq_i}부터)")
                emit(f"BLOCK_START|b{b}", b)
                prev_block = b
            cur_s = seq_i
            for phase, rep in run["phases"]:
                marker = f"b{b}|s{seq_i:03d}|{phase}{rep}|{color}"
                square.fillColor = run["colors"][color] if phase == "obs" else run["gray"]
                d0 = win.nDroppedFrames
                for fr in range(n_frames):
                    square.draw()
                    if phase == "img":
                        cue.draw()
                    elif fix is not None:
                        fix.draw()
                    if run["provisional"]:
                        tag.draw()
                    if pd is not None:
                        pd.fillColor = "white" if phase == "obs" else "black"
                        pd.draw()
                    tf = win.flip()
                    if fr == 0:
                        flip0 = tf
                        onset, push_lsl, delay, ok = push(marker, tf)
                stim_drops += win.nDroppedFrames - d0
                # offset 추정 = 마지막 프레임 flip 직후 + 1프레임 (다음 단계 onset과 대조 가능)
                row(marker, onset, b, seq_i, phase, rep, color, flip=flip0,
                    offset=local_clock() + frame_dur, nf=n_frames, push_lsl=push_lsl, delay=delay, ok=ok)
                if eeg_watch is not None and not eeg_watch.check():     # 비차단, 단계 사이 (다음 첫 flip 전)
                    stop_reason = eeg_watch.reason()
                    raise KeyboardInterrupt
                keys = event.getKeys(["escape", "p"], timeStamped=True)
                if esc.feed(keys):
                    raise KeyboardInterrupt
                pause_req = pause_req or any(k == "p" for k, _ in keys)
            done_s = seq_i
            if pause_req:
                emit(f"PAUSE|s{seq_i:03d}", b, seq_i)
                screen("일시정지\n\n[스페이스] 계속")
                emit(f"RESUME|s{seq_i:03d}", b, seq_i)
                pause_req = False
        emit(f"BLOCK_END|b{prev_block}", prev_block)
        emit("EXP_END")
        screen("끝났습니다. 수고하셨습니다.\n\n[스페이스] 종료")
    except KeyboardInterrupt:
        aborted = True
        if esc.triggered:
            stop_reason = f"ESC×{esc.n} (자극 창)"
        emit(f"STOP|b{cur_b}|s{cur_s:03d}", cur_b, cur_s)
        ui.tag("stop", f"{stop_reason} — 로그 저장됨",
               f"이어 하려면 새 XDF 파일명으로 --start-block {cur_b} (블록 {cur_b} 처음부터)")
    finally:
        fcsv.close()
        gc.enable()
        core.rush(False)
        dl = sorted(timing["delays"])
        tstat = dict(n=timing["n"], clock_mismatch=timing["bad"],
                     flip_to_push_ms_median=round(dl[len(dl) // 2] * 1000, 3) if dl else None,
                     flip_to_push_ms_max=round(dl[-1] * 1000, 3) if dl else None)
        meta.update(ended=datetime.now().isoformat(timespec="seconds"), aborted=aborted,
                    stop_reason=stop_reason if aborted else None,
                    dropped_frames=int(win.nDroppedFrames), dropped_frames_stim=int(stim_drops),
                    dropped_frames_screens=int(win.nDroppedFrames - stim_drops),
                    completed_sequences=done_s, marker_timing=tstat)
        with open(stem + "_events.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
        ui.sub("자극 결과")
        ui.kv("완료 시퀀스", f"{done_s}/{len(run['plan'])}"
              + (f"  (STOP, s{cur_s:03d} 진행 중 중단)" if aborted and cur_s > done_s else "  (STOP)" if aborted else ""),
              color="yellow" if aborted else "green")
        drop_ok = stim_drops == 0
        ui.kv("드롭 프레임", f"{'PASS' if drop_ok else 'FAIL'}  자극 단계 {stim_drops}"
              f"  (안내·휴식 화면 {win.nDroppedFrames - stim_drops}, 참고)", color="green" if drop_ok else "red")
        clk_ok = bool(tstat["n"]) and tstat["clock_mismatch"] == 0
        ui.kv("마커 시각 보정", f"{'PASS' if clk_ok else 'FAIL (시계 기준 불일치: flip 직후 시각 사용)'}"
              f"  {tstat['n']}개, 불일치 {tstat['clock_mismatch']}, flip→push 중앙 {tstat['flip_to_push_ms_median']}ms"
              f" / 최대 {tstat['flip_to_push_ms_max']}ms", color="green" if clk_ok else "red")
        ui.kv("기록 파일", f"{os.path.basename(stem)}_events.csv / .json")
        ui.tag("note", "모니터 입력 지연은 미측정(UNVERIFIED) — --photodiode + 외부 센서로만 측정 가능")
        win.close()
        core.quit()


if __name__ == "__main__":
    main()
