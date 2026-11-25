# VS Code의 Claude Code에 붙여 넣을 세팅 프롬프트 (v4)

````
너는 이 폴더(rgb-eeg-lab)의 Windows 실습 환경을 세팅하고 오류를 해결하는 담당이야.
먼저 CLAUDE.md, REPORT.md, config/protocol.json, requirements-stim.txt, requirements-analysis.txt, docs/system_test.md를 읽어.

## 핵심 구조
- 인터프리터가 둘이다.
  - 자극 python: PsychoPy Standalone 내장 python (또는 Python 3.10 + psychopy 가상환경)
  - 분석 python: 프로젝트 .venv (Python ≥3.10)
- 각 스크립트는 정해진 python으로만 실행한다.
  - 자극 python: stim_rgb.py
  - 분석 python: check_streams.py, xdf_qc.py, train_svm.py, tests
- set_field_values.py와 env_check.py는 표준 라이브러리만 쓰므로 어느 쪽이든 가능하다.

## 절대 규칙
1. config/protocol.json의 연구 값(RGB, 크기, 필터, ERSP, QC 기준, seed)은 바꾸지 마.
   null 3개(monitor.width_cm, monitor.resolution_px, eeg.raw_unit)는 내가 준 실측값이나 문서 근거로만, set_field_values.py를 통해 기록해.
2. 테스트 기대값이나 검사 기준을 완화하지 마. 코드 수정이 필요하면 먼저 원인·diff·이유를 설명하고 승인받아.
3. 전역 설치, 파일 삭제, Python 버전 변경 전에는 확인받아.
4. 사람 EEG 착용 측정은 하지 마 (IRB 승인 전).
5. 실행하지 못한 항목은 UNVERIFIED로 적어.

## 단계
1. 인터프리터 찾기
   - `where python`, `py -0p`, PsychoPy Standalone 경로(보통 C:\Program Files\PsychoPy\python.exe) 확인
2. 분석 환경
   - `py -3.10 -m venv .venv` (3.10이 없으면 설치된 ≥3.10 버전)
   - `.venv\Scripts\python.exe -m pip install -r requirements-analysis.txt`
   - `.venv\Scripts\python.exe scripts\env_check.py --role analysis --lock` → 판정 GO
   - `.venv\Scripts\python.exe -m pytest tests -q` → 27 passed
3. 자극 환경
   - `& "<PsychoPy python>" -m pip install -r requirements-stim.txt`
   - `& "<PsychoPy python>" scripts\env_check.py --role stim --lock` → import psychopy, pylsl, LSL 루프백 PASS
   - 실패 시 원인을 구분해서 보고: 다른 python에 설치됨 / 권한 문제 / 방화벽
4. 현장 값
   - `python scripts\set_field_values.py --detect` → 해상도·배율 출력. 배율이 100%가 아니면 알려줘
   - 내가 알려주는 가로 cm·해상도·단위를 `--source`와 함께 기록
5. 자극 확인
   - `& "<PsychoPy python>" scripts\stim_rgb.py --participant T00 --practice`
   - 기록할 것: 주사율, 정사각형 px와 각도, 드롭 프레임, 마커 시각 보정 결과
   - 화면은 내가 자로 재서 알려줄게
6. 미착용 시스템 테스트: docs/system_test.md 절차대로 안내하고 xdf_qc 결과 해석
7. locks\ 폴더에 생긴 freeze 파일 두 개를 보고, 버전 고정 상태를 요약해

## 최종 보고
| 단계 | 상태(PASS/FAIL/UNVERIFIED) | 근거(명령·출력 요약) |
- 수정한 파일과 이유
- 내가 할 일
- `판정: GO / NO-GO / 조건부(UNVERIFIED 목록)`
````
