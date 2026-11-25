# v4 변경 (2026-10-30 오후) — 환경 분리·버전 고정·마커 시각

| 지적 | 조치 | 상태 |
|---|---|---|
| P0 PsychoPy가 설치 대상에 없음 / 환경 구분 | `requirements-stim.txt`(PsychoPy Standalone python에 pylsl 설치) + `requirements-analysis.txt`(.venv) 분리, `requirements.txt`는 분석용을 가리킴 | 코드 완료 · 실습 PC 미검증 |
| P0 모니터 폭·해상도, EEG 단위 null | `set_field_values.py`: 범위 검사, 근거(--source) 필수, `config/CHANGELOG.md` 기록, Windows 해상도·배율 감지(--detect). 연구 값은 변경 불가 | 도구 완료 · **값은 현장 실측 필요** |
| P0 HALO→LSL→XDF 미확인 | `docs/system_test.md`: 미착용 절차·합격 기준·PowerShell 명령 | 절차 완료 · **현장 실행 필요** |
| P1 마커가 flip 이후 전송 | 마커 타임스탬프 = flip(vsync) 시각을 LSL 시계로 환산(`protocol.flip_to_lsl`), push 지연은 CSV에 기록만. QC에 "마커 시각 = flip 시각" 점검. 모니터 자체 지연은 `--photodiode`(연습 전용) + 외부 센서 | 코드 완료 · 화면 지연 UNVERIFIED |
| P1 버전 고정 부족 | `env_check.py --lock` → `locks/<역할>-<PC>-freeze.txt`(실습 PC의 검증된 버전), 클라우드 참고 버전 `locks/reference-linux-py313.txt` | 도구 완료 · 실습 PC에서 생성 |
| P1 PsychoPy 환경에서 pylsl 미확인 | `env_check.py --role stim`: 실제 자극 python에서 psychopy·pylsl import + LSL 루프백 | 도구 완료 · 실습 PC 미검증 |

자동 검증: `python -m pytest tests -q` → **27 passed** (기존 23 + flip→LSL 환산, 포토다이오드 본측정 차단, 현장값 입력 검증, env_check 실행).
env_check(클라우드): analysis 판정 GO (루프백 PASS), stim 판정 NO-GO (psychopy 없음 — 정상 검출).

한계: 클라우드 pip는 Python 3.13 기준이라 PsychoPy 최신판 설치를 검증하지 못함. PsychoPy 버전은 실습 PC의 freeze 파일이 기준.
`flip_to_lsl`은 PsychoPy `win.flip()` 반환값이 `logging.defaultClock` 기준이라고 가정하고, 아니면 보정을 끄고 FAIL로 알린다 → 첫 연습 실행에서 확인.

---

# 수정·검증 보고서 — 2026-10-30 (키트 v3)

기준: 2026-10-26 연구계획서 + `11_실험운영지침_사전분석계획.docx` v2.0 (리뷰 체크리스트·수정 지시서 경유).
검증 환경: Linux 클라우드 샌드박스, 합성 데이터만. **PsychoPy 화면·HALO·LabRecorder·실제 XDF는 미실행 → UNVERIFIED.**

## 1. 수정 파일과 이유

| 파일 | 변경 | 이유(지시서 P0 번호) |
|---|---|---|
| `config/protocol.json` | 계획서 값 입력: RGB (157,0,0)/(0,89,0)/(0,0,255), 회색 76, 중앙 10.5cm(10°)·60cm, sRGB·밝기50%·예열20분, 4차 인과 1–30Hz, 시작 5초 배제, Morlet 3cycles, 반열린 4×4 구간, QC 60/120/0.5µV, seed 20261026+순번. 남은 null: 모니터 가로cm·해상도, EEG 단위 (현장 실측) | P0-1,2,3 |
| `scripts/protocol.py` | seed 규칙, `sequence_plan`(자극·QC 공용 순서 재생성), 반열린 구간 `bin_masks` | P0-4,6 |
| `scripts/stim_rgb.py` | 전체화면 색칠 → 중앙 정사각형(cm→px, 시각도 출력), 계획 RGB, 해상도 불일치·<60Hz·null 시 본측정 거부, seed=20261026+순번, `*_events.csv`(event_id/onset/offset/flip/seed/version) + `.json` 메타(버전·모니터·RGB), BLOCK/REST/PAUSE/RESUME/STOP/EXP_END, 마커 시각=CSV 시각 | P0-1,6 |
| `scripts/xdf_qc.py` | 양방향 → 구간별 인과 SOS(재설정), 시작 5초·경계 시행 제외, 자극전 평균 제거 후 60/120µV, 1초 std<0.5µV, 기준구간 진폭, NaN/누락, V↔µV 명시 확인(모순 시 FAIL), 모드별 기대 6/18/90시퀀스·중복·단계 순서·seed 기반 색 순서·STOP, 마커 0개·유효 시행 0 방어, 채널 라벨 불일치 FAIL, NO-GO 시 종료코드 1 | P0-2,3,4,5 |
| `scripts/train_svm.py` | PROVISIONAL 입력 검증을 출력 생성 전에, 유효 시행 0 참가자 제외 | P0-5 |
| `tests/test_pipeline.py` | 23개: 정상 3모드 + 고장 주입 15종 + 계획서 일치 3 + SVM 누수 1 | 테스트 지시 |
| `CHECKLIST.md` | v3: IRB 게이트, 계획 값, 48/144/720 마커, PowerShell, GO/NO-GO 표 | P0-7 |
| `CLAUDE.md`, `.claude/agents/*.md` | 담당·입력·출력·GO/NO-GO 형식, PASS/FAIL/UNVERIFIED, session-runner는 NO-GO 시 시작 거부, 지시서 순서 | P0-8 |

## 2. 자동 검증 (실제 출력)

```
python -m compileall -q scripts        → 출력 없음 (OK)
python -m pytest tests -v
test_marker_counts_by_mode[practice-6] PASSED      ← 48 단계 마커
test_marker_counts_by_mode[block-18]   PASSED      ← 144
test_marker_counts_by_mode[main-90]    PASSED      ← 720
test_full_pipeline_block_mode          PASSED      ← X4 (36,64), X2 (36,32), 판정 GO
test_missing_whole_sequence            PASSED      ← "시퀀스 수" FAIL, NO-GO
test_missing_single_marker             PASSED      ← "8단계" FAIL
test_duplicate_marker                  PASSED      ← "중복 마커" FAIL
test_wrong_phase_order                 PASSED      ← "단계 순서" FAIL
test_wrong_color_order                 PASSED      ← "색·블록 순서(seed)" FAIL
test_no_exp_start                      PASSED      ← FAIL
test_stop_event_fails                  PASSED      ← "종료/STOP" FAIL
test_missing_samples_excluded          PASSED      ← "누락 표본" FAIL + 시행 사유 missing
test_large_amplitude_excluded          PASSED      ← abs/ptp
test_baseline_amplitude_excluded       PASSED      ← baseline_abs
test_flat_signal_excluded              PASSED      ← flat
test_startup_excluded                  PASSED      ← startup
test_wrong_channel_label               PASSED      ← "채널 라벨" FAIL, 특징 미생성
test_units                             PASSED      ← 미확정 UNVERIFIED+PROVISIONAL / 오선언 FAIL / V PASS
test_zero_valid_trials                 PASSED      ← "유효 시행" FAIL, 예외 없음
test_filter_is_causal_and_resets       PASSED      ← 임펄스 이전 출력 0, 구간 재시작
test_bins_half_open                    PASSED      ← 대역 bin 수 [1,4,5,18], 1.5s 포함
test_stimulus_config_and_seed          PASSED      ← RGB·회색, P03→20261029, 6/18/90, null 시 본측정 거부
test_svm_signal_shuffle_and_provisional_guard PASSED ← PROVISIONAL 거부, 신호 BA 1.0 / 셔플 BA 0.21–0.36
23 passed
```
합성 SVM 수치는 파이프라인 작동 확인용이며 연구 결과가 아니다.

## 3. PowerShell 사용 순서 (초보자용)

```powershell
cd C:\경로\rgb-eeg-lab
python --version
pip install -r requirements.txt
python -m compileall -q scripts
python -c "import pylsl,pyxdf,mne,scipy,sklearn,psychopy; print('imports OK')"
python -m pytest tests -q                                   # 23 passed

# 모니터 가로 cm·해상도 실측 → config\protocol.json 의 monitor 에 입력
python scripts\stim_rgb.py --participant T00 --practice     # 정사각형 10.5cm 자로 확인
# Board 스트리밍 → 위 명령 시작화면 → LabRecorder Update/체크/Start → 스페이스
python scripts\xdf_qc.py data\sub-T00_ses-systemtest_run-01.xdf --stim-csv (Get-ChildItem data\T00_practice_*_events.csv | Select-Object -Last 1).FullName
```

## 4. 에이전트 (지시서 순서)

| 순서 | 에이전트 | 담당 | 입력 | 출력 | GO 기준 |
|---|---|---|---|---|---|
| 1 | env-setup | 설치·테스트 | PC, requirements | 버전·점검표 | import OK, 23 passed |
| 2 | signal-check | 스트림·단위 (착용은 승인 후) | LSL EEG, 장비 문서 | 채널표 | 250Hz, 누락 0, 라벨·단위 확정 |
| 3 | stimulus-builder | 자극 일치 | config, 모니터 실측 | 크기·주사율 확인 | 10.5cm±2mm, ≥60Hz, 드롭 0 |
| 4 | lsl-sync | 녹화·마커 | XDF, events.csv | QC 마커 판정 | 마커 점검 전부 PASS |
| 5 | session-runner | 세션 (승인 후) | IRB 번호, 앞 판정 | 세션 로그 | 앞 단계 NO-GO 없음, EXP_END |
| 6 | pilot-qc | QC·SVM | XDF, config | report, npz, SVM 요약 | QC PASS, 셔플 BA≈0.33 |

## 5. 오늘 GO / NO-GO (이 보고서 작성 시점)

| 영역 | 상태 | 근거 |
|---|---|---|
| Software(분석 코드) | **PASS** | compileall OK, 23 passed (합성 데이터) |
| 자극(PsychoPy 화면) | **UNVERIFIED** | 샌드박스에 디스플레이 없음. 모니터 cm·해상도 미입력 |
| LSL | **UNVERIFIED** | 실제 스트림 미실행 |
| HALO | **UNVERIFIED** | 장비 미연결 |
| EEG 단위 | **UNVERIFIED** | `raw_unit` null — 장비 문서 확인 필요 |
| XDF | **UNVERIFIED** | 실제 녹화 파일 없음 |
| QC 로직 | **PASS** | 고장 주입 15종 모두 FAIL/제외로 검출 |
| IRB | **UNVERIFIED** | 승인 번호 미확인 → 사람 측정 NO-GO |

**판정: 소프트웨어 리허설 GO / 사람 대상 측정 NO-GO** (위 UNVERIFIED 해소 + IRB 확인 전까지)

## 6. 팀 확인이 필요한 구현 관례 (계획서 미기재)
- 고정점 `+`, 상상 단계 cue(작은 원) 표시 여부
- 같은 색 최대 2연속 제약, 연습 seed offset(+100000)
- 기록 끊김(누락 표본)을 '연속 구간 경계'로 보고 필터 재시작·5초 배제를 적용 (지시서 "기록 중단 시 상태 재설정, 시작 5초" 해석)
