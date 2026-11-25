# HALO → LSL → XDF 미착용 시스템 테스트

목적: 사람 착용 없이 "장비 스트림이 250Hz로 끊김 없이 나오고, 자극 마커와 같은 XDF에 저장되는가"를 확인한다.
IRB 승인 전에도 가능 (생체 신호 기록 아님). 신호 내용(뇌파 품질)은 판단하지 않는다.

## 준비
| 항목 | 확인 |
|---|---|
| HALO 충전·전원, 블루투스 연결 | ☐ |
| BrainAccess Board에서 LSL 스트리밍 켬 | ☐ |
| 자극 PC: `env_check.py --role stim` 판정 GO/조건부 | ☐ |
| 분석 PC: `env_check.py --role analysis` 판정 GO | ☐ |
| 두 PC가 다르면 같은 네트워크, 방화벽에서 Python·LabRecorder 허용 | ☐ |

## 절차 (약 10분)
1. **스트림 확인** (분석 python)
   ```powershell
   .venv\Scripts\python.exe scripts\check_streams.py --seconds 30
   ```
   - PASS: EEG 스트림 보임, 실효 srate 250±0.5, 끊김 0, NaN 0
   - 채널 라벨이 Fp1/Fp2/O1/O2가 아니거나 채널이 4개보다 많으면 → 라벨·순서를 기록 (signal-check)
2. **자극 시작화면 대기** (자극 python)
   ```powershell
   & "C:\Program Files\PsychoPy\python.exe" scripts\stim_rgb.py --participant T00 --practice
   ```
3. **LabRecorder**: Update → EEG 스트림 + `RGB_Markers` 체크 → 파일명 `sub-T00_ses-systemtest_run-01.xdf` → Start
4. 자극 화면에서 스페이스 → 약 2.5분 진행 → 종료
5. LabRecorder Stop
6. **QC** (분석 python)
   ```powershell
   $csv = (Get-ChildItem data\T00_practice_*_events.csv | Select-Object -Last 1).FullName
   .venv\Scripts\python.exe scripts\xdf_qc.py data\sub-T00_ses-systemtest_run-01.xdf --stim-csv $csv
   ```

## 합격 기준
| 점검 | 기대 |
|---|---|
| EXP_START, 모드별 설계, 시퀀스 수 6/6, 단계 48개, 순서·색 순서, 종료 | PASS |
| CSV↔XDF 마커 대조, 마커 시각 = flip 시각 | PASS |
| 실효 srate, 누락 표본, NaN | PASS |
| 단계 간격 max−min < 1프레임 | PASS |
| 불량 시행, 단위, 평탄 | 미착용이라 FAIL/UNVERIFIED 정상 → 기록만 |
| 모니터 입력 지연 | UNVERIFIED (아래 선택 항목) |

추가 확인: ESC 3번(3초 안)으로 중간 중단 → `STOP` 기록 + QC 판정 NO-GO (종료코드 1).

## 선택: 모니터 입력 지연 (포토다이오드)
소프트웨어 마커는 vsync(flip) 시각이다. 실제로 화면에 빛이 나오는 시각과의 차이는 센서로만 잴 수 있다.
1. `stim_rgb.py --participant T00 --practice --photodiode` → 왼쪽 아래 60px 패치 (관찰=흰색, 그 외=검정)
2. 포토다이오드 센서를 패치에 붙이고, 그 출력을 LSL로 기록할 수 있는 장치(또는 AUX 입력)로 녹화
3. 센서 상승 시각 − obs 마커 시각 = 지연. 평균·표준편차를 세션 로그에 기록
4. 장비가 없으면 "모니터 입력 지연 미측정. 세 색에 공통인 상수 지연으로 가정, 절대 잠복기 해석 안 함"을 한계로 기록
`--photodiode`는 화면 자극을 바꾸므로 본측정에서는 스크립트가 거부한다.
