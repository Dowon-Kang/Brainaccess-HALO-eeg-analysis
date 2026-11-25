# 실습 체크리스트 v4 — 2026-10-30 (기준: 2026-10-26 계획서 v2.0)

> **오늘 범위**: 소프트웨어 설치 → 자극·마커 → LSL/XDF 저장 → QC 드라이런 (합성 데이터 + 장비 미착용).
> **IRB**: 승인/면제와 지도교수 확인 전에는 팀원 포함 **사람 EEG를 기록하지 않는다.** 명칭을 바꿔 우회하지 않는다.
> 모든 항목은 **PASS / FAIL / UNVERIFIED + 근거**. 실행하지 않은 것은 UNVERIFIED (`CLAUDE.md`).
> 명령은 Windows PowerShell, 프로젝트 폴더(`rgb-eeg-lab`)에서 실행.

역할: **A 운영자**(자극 PC) / **B 신호**(Board·LabRecorder) / **C 기록**(세션 로그)

---

## 0. 차단 게이트 (하나라도 미충족이면 사람 측정 NO-GO)
- [ ] IRB 승인/면제 번호·날짜, 지도교수 확인 → 세션 로그
- [ ] `config/protocol.json` 남은 null 0개 (지금 남은 것: `monitor.width_cm`, `monitor.resolution_px`, `eeg.raw_unit`)
  ```powershell
  python -c "import sys; sys.path.insert(0,'scripts'); import protocol as p; print(p.missing(p.load()))"
  ```
- [ ] 계획서 미기재 항목 팀 확인: 고정점 `+`, 상상 cue(작은 원), 같은 색 최대 2연속, 연습 seed offset

## 1. 소프트웨어 — `env-setup` (인터프리터 2개)
- [ ] **분석 python** (.venv, ≥3.10)
  ```powershell
  py -3.10 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements-analysis.txt
  .venv\Scripts\python.exe scripts\env_check.py --role analysis --lock     # 판정 GO
  .venv\Scripts\python.exe -m pytest tests -q                                # 32 passed
  ```
- [ ] **자극 python** (PsychoPy Standalone 내장) — pylsl을 *이* python에 설치하고 확인
  ```powershell
  & "C:\Program Files\PsychoPy\python.exe" -m pip install -r requirements-stim.txt
  & "C:\Program Files\PsychoPy\python.exe" scripts\env_check.py --role stim --lock   # psychopy·pylsl·루프백 PASS
  ```
- [ ] `locks\` 에 생긴 `*-freeze.txt` 2개 = 이 PC의 검증된 버전 고정 (재설치 시 사용)
- [ ] BrainAccess Board, LabRecorder 실행·버전 기록

## 2. 디스플레이·자극 — `stimulus-builder` (착용 불필요)
- [ ] 모니터 sRGB 모드, 밝기 50%, 20분 예열, HDR/Night Light/자동밝기/알림 OFF, 조명 일정
- [ ] Windows 디스플레이 배율 100% 권장(아니면 해상도 불일치로 실행 거부됨)
- [ ] 드롭 프레임 방지: 전원 옵션 고성능(노트북은 충전기), 게임 모드 ON, 집중 모드(알림 OFF), Windows 업데이트 일시 중지,
      측정 중 VS Code·브라우저·메신저 종료, 가능하면 LabRecorder는 다른 PC. 자극 스크립트 3.1부터 우선순위 상승·GC 정지 내장
- [ ] **현장 값 기록** (직접 JSON 편집 금지 — 범위 검사·근거·변경기록)
  ```powershell
  python scripts\set_field_values.py --detect                                   # 해상도·배율 감지
  python scripts\set_field_values.py --resolution 1920x1080 --source "Windows 감지(배율 100%)"
  python scripts\set_field_values.py --width-cm 53.1 --source "줄자 실측, 표시 영역"
  ```
- [ ] `& "C:\Program Files\PsychoPy\python.exe" scripts\stim_rgb.py --participant T00 --practice` (전체화면)
  - 출력의 "10.5cm = Npx, 60cm에서 10.00°" 확인, **자로 화면 정사각형 실측 10.5cm ±2mm**
  - 주사율 ≥60Hz, 드롭 프레임 0 → PASS
  - "마커 시각 보정 … PASS" (flip 시각 = 마커 시각, 시계 불일치 0)
  - 색: R(157,0,0) G(0,89,0) B(0,0,255), 회색(76,76,76) 육안 확인 (등휘도 검증은 별도)
- [ ] 본측정 차단 확인: config null 상태에서 `--practice` 없이 실행 → "[거부]" 메시지

## 3. LSL·XDF — `lsl-sync` (EEG 장비 켜기만, 미착용) — 상세: `docs\system_test.md`
- [ ] LabRecorder는 바탕 화면 **"LabRecorder (RGB EEG)"** 바로 가기로 실행 (`rgb_eeg.cfg`: 필수 스트림 빨간색 표시·Start 경고)
- [ ] 순서: Board 스트리밍 → `stim_rgb.py --practice` 시작화면 대기 → LabRecorder **Update** → EEG + `RGB_Markers` 체크 → **Start** → 스페이스
- [ ] **실행 1번 = XDF 1개.** `stim_rgb.py`는 콘솔에 `[대기]`를 띄우고 LabRecorder Start가 감지돼야 자극 창을 연다. 4.1부터 **data 폴더에 새 XDF가 생겨야** 감지됨 → LabRecorder는 반드시 바로 가기로(저장 위치 data).
      4.2부터 자극 창이 열리면 키보드 포커스를 자동으로 가져옴 (LabRecorder Start 후 포커스가 Stop 버튼에 있어 스페이스가 녹화를 멈추던 문제). 화면에 '[운영자] 키 입력이 … 클릭'이 보이면 화면을 한 번 클릭 끝나면 Stop → 다음 실행은 새 파일명
- [ ] 실행 중 녹화가 끊기면 다음 블록 시작 전에 자동 STOP (`[중단] LabRecorder 녹화 끊김`) → 처음부터 다시
- [ ] 명령은 **한 줄씩** 실행 (여러 줄을 한 번에 붙여넣으면 다음 실행이 바로 이어짐)
- [ ] 파일명 `sub-T00_ses-systemtest_run-01.xdf`
- [ ] QC 실행:
  ```powershell
  python scripts\xdf_qc.py data\sub-T00_ses-systemtest_run-01.xdf --stim-csv (Get-ChildItem data\T00_practice_*_events.csv | Select-Object -Last 1).FullName
  ```
  - 단계 마커 **연습 36 / 1블록 108 / 본측정 540** (6/18/90시퀀스 × 6단계, 변경1 2026-11-13. 이전 8단계 기록은 48/144/720)
  - 모드별 설계·중복·시퀀스 수·시퀀스 내부 단계·단계 순서·색 순서·종료·단계 간격·CSV↔XDF = PASS
  - 실효 srate 250, 누락 표본 0
  - "마커 시각 = flip 시각" PASS
  - 미착용 신호라 불량 시행·단위는 FAIL/UNVERIFIED가 정상 → 기록만
  - "모니터 입력 지연" UNVERIFIED → 포토다이오드가 있으면 `--photodiode` (docs\system_test.md)
- [ ] ESC 중단 테스트 → `STOP` 마커 기록 + QC NO-GO
- [ ] P 키 일시정지 → `PAUSE/RESUME` 기록
- [ ] `--practice --one-block`(18시퀀스, 휴식 없음) 1회

## 4. 분석 드라이런 — `pilot-qc`
- [ ] `tests`의 SVM 테스트 통과 = 블록 중첩 CV·셔플 누수 점검 작동
- [ ] 결과를 보고 임계값·구간을 바꾸지 않는다 (사후 조정 금지)

## 5. [IRB 승인 후] 신호·단위 — `signal-check`
- [ ] HALO 채널 맵 Fp1/Fp2/O1/O2, 기준전극 장치 기본, 250Hz
- [ ] EEG 출력 단위(V/µV) 장비 문서로 확인 → `python scripts\set_field_values.py --raw-unit uV --source "문서명 p.N"` → QC "EEG 단위" PASS
- [ ] 깜빡임(Fp 우세)·알파(O 증가)는 보조 확인. 알파 비율 하나로 매핑 확정 금지

## 6. [IRB 승인 후] 세션 — `session-runner`
- [ ] 앞 단계 판정이 NO-GO면 세션 시작 금지
- [ ] 연습 → 본측정, 블록별 이벤트 기록, 중단 기준(드롭 프레임·스트림 끊김·불편 호소) 즉시 ESC

## 7. 오늘 GO / NO-GO
| 영역 | 기준 | 상태 |
|---|---|---|
| Software | 분석 env_check GO, 27 passed | |
| 자극 환경 | stim env_check: psychopy·pylsl·루프백 PASS | |
| 버전 고정 | locks\ freeze 2개 | |
| 자극 | 10.5cm 실측, ≥60Hz, 드롭 0 | |
| LSL | 두 스트림 보임 | |
| XDF | 마커 36/36 등 PASS, CSV 대조·flip 시각 PASS | |
| 화면 지연 | 포토다이오드 측정 또는 '미측정' 한계 기록 | |
| HALO | 250Hz, 누락 0 | |
| EEG 단위 | raw_unit 확정 | |
| QC | 고장 주입 테스트 FAIL 정상 검출 | |
| IRB | 승인 번호 확인 | |
