# Sustained Attention to Response Task (SART)

PsychoPy 기반 숫자 Go/No-Go 실험입니다. `3`을 제외한 숫자에는 SPACE로 반응하고,
`3`에는 반응하지 않습니다. 숫자 250 ms + 마스크 900 ms를 사용합니다.

![SART task flow](python-sustained-attention-to-response-task-sart.png)

## 실행

프로젝트 폴더에서 PowerShell로 실행합니다. 설치된 환경은 Python 3.10 / PsychoPy 2026.2.4입니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 python_sart.py --phase pre
.\.venv\Scripts\python.exe -X utf8 python_sart.py --phase post
```

`python_sart_eeg_analysis_v2.py`도 같은 명령으로 실행할 수 있습니다.
두 진입점은 동일한 구현을 사용합니다. `--phase`를 생략하면 콘솔에서 pre/post를 묻습니다.
Windows에서 UTF-8 모드 없이 실행한 경우 진입점이 UTF-8 모드로 다시 실행되어,
한국어 PsychoPy 번역 JSON의 cp949 디코딩 오류를 방지합니다.

- PRE: 5회 반복 × 45 = 225 본 시행, 약 4분 19초 + 화면 갱신 지연.
- POST: 12회 반복 × 45 = 540 본 시행, 약 10분 21초 + 화면 갱신 지연.
- 기본값은 연습 없음, 무작위 순서입니다. 설정은 `python_sart_eeg_analysis_v2.py` 상단에 있습니다.
- 참가자 정보의 빈 입력, 미선택 항목, 잘못된 나이/ID는 실험 시작 전에 검사합니다.
- B로 설명 화면을 진행하고, SPACE로 반응합니다. ESC는 진행 중인 실험을 중단합니다.
- 화면 창으로 실행하려면 `--windowed`, 저장 폴더를 지정하려면 `--output 경로`를 사용합니다.

## 결과 파일

기본 저장 위치는 **스크립트가 있는 폴더의 `experiment/`**입니다.
실행한 터미널의 현재 폴더와 관계없이 같은 위치에 저장합니다.

```text
experiment/
├─ participants.csv
├─ sessions.csv
├─ trials.csv
└─ summary.csv
```

| 파일 | 한 행의 의미 | 저장 내용 |
| --- | --- | --- |
| participants.csv | 참가자 한 명 | participant_id, 성별, 나이, 학년, 정상/교정 시력 |
| sessions.csv | 참가자의 방문 세션 한 번 | session_id, participant_id, session, condition, shortform_topic, 최초 실험자 |
| trials.csv | 완료된 시행 하나 | session_id, run_id, phase, 연습 여부, 블록/시행 번호, 숫자/Go·No-Go, 반응 여부, 정오, RT, 글자 크기, 타이밍 |
| summary.csv | 실행의 분석 구간 하나 | run_id, phase, 완료/중단/오류 상태, 실행 날짜, 설정, 구간, 시행 수, 오류율, RT 지표 |

같은 참가자 ID와 session 번호는 같은 `session_id`를 사용합니다.
PRE, POST, 재실행마다 새 `run_id`를 발급하므로 결과가 덮어써지지 않습니다.
참가자 정보 또는 같은 세션의 condition/topic이 기존 값과 다르면 입력 확인을 요청합니다.
변경된 나이/학년을 포함해 기존 참가자 메타데이터를 자동으로 덮어쓰지 않습니다.
실험자는 실행마다 summary에도 기록됩니다.

CSV는 Excel에서 한국어를 읽기 쉬운 UTF-8 BOM 형식입니다.
무응답 RT와 계산할 수 없는 지표는 빈 셀입니다. RT는 ms, 경과시간은 초입니다.
`accuracy`는 정답 1 / 오답 0, `responded`와 `is_practice`는 1 / 0입니다.

완료된 시행은 매번 `trials.csv`에 기록하고 flush합니다.
ESC로 중단된 현재 시행은 저장하지 않으며, 이전에 완료된 시행은 유지합니다.
정상 종료 및 ESC/실행 오류 시 summary를 작성하고 화면을 닫습니다.
프로세스 강제 종료/전원 종료 시 summary 작성은 보장되지 않습니다.
한 저장 폴더에는 한 실험 프로세스만 실행하세요.
기존 `results/*.txt`는 보존되며 자동으로 변환하지 않습니다.

## 지표와 시각 정의

- Go omission rate = Go 무응답 수 / 완료된 Go 시행 수 × 100.
- No-Go commission rate = No-Go 반응 수 / 완료된 No-Go 시행 수 × 100.
- Median/mean/SD/CV RT는 **정답 Go 반응**만 사용합니다. SD는 표본 표준편차입니다.
- Balanced accuracy는 Go 정확도와 No-Go 정확도의 평균입니다. 어느 쪽 시행이 없으면 빈 값입니다.
- 모든 요약에서 연습 시행은 제외합니다. 원자료에는 `is_practice=1`로 보관합니다.
- `summary.csv`의 `window=overall`을 선택하면 **실행당 한 행**입니다.
  `first_4min` 및 `time_bin_1`, `time_bin_2`, …에는 기존 4분/2분 구간 분석을 보관합니다.
  구간은 첫 본 시행의 자극 시작을 0초로 하며, 경계의 시행은 시작 시각으로 분류합니다.
  구간이 짧거나 실험이 중단된 경우 `is_partial`로 구분합니다.
- 실행 날짜/시각은 시간대가 포함된 UTC ISO 8601입니다.
- `stimulus_onset_elapsed_s`와 `trial_end_elapsed_s`는 실행 시작부터의 경과시간입니다.
  `*_perf_s`는 원시 `time.perf_counter()` 값이며 실제 날짜/시각이 아닙니다.
- RT 시계는 자극을 표시하는 `win.flip()` 콜백에서 초기화합니다.
  화면 자극과 EEG의 동기화 트리거는 아직 구현되지 않았습니다.

## 검증

화면 없이 입력 검사, CSV 연결/누적 저장, 요약 계산, 반응 처리, 중단 저장을 검사합니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

실제 Qt 입력창과 PsychoPy 화면을 자동으로 열고 닫는 짧은 통합 검증:

```powershell
.\.venv\Scripts\python.exe -X utf8 tests\gui_smoke.py
```

GUI 검증은 합성 키 반응과 임시 저장 폴더를 사용합니다.
화면 주사율, 실제 키보드 지연 또는 EEG 동기화 정확도의 검증을 대신하지 않습니다.

## Reference

Robertson, H., Manly, T., Andrade, J., Baddeley, B. T., & Yiend, J. (1997).
'Oops!': Performance correlates of everyday attentional failures in traumatic
brain injured and normal subjects. Neuropsychologia, 35(6), 747–758.

Original implementation: Cary Stothart (2015), Python SART (Version 2), MIT license.
The original copyright and license are retained in both entry point files.