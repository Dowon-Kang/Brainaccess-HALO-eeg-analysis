# RGB EEG 연구 — 모든 에이전트 공통 규칙

## 기준 문서 (우선순위 순)
1. 2026-10-26 연구계획서 + 11_실험운영지침_사전분석계획.docx v2.0 (팀 보관본)
2. `config/protocol.json` — 원본 값을 옮긴 **유일한 설정 출처**. 코드에 숫자를 하드코딩하지 않는다.
3. `docs/research_context.md` — 요약본 (원본과 다르면 원본이 우선)

## 절대 규칙
- **IRB**: 승인(또는 기관이 인정한 면제) 확인 전에는 사람(팀원 포함) EEG를 연구 목적으로 기록하지 않는다.
  그 전까지 허용: 합성 데이터 테스트, 소프트웨어·자극·마커·LSL·LabRecorder 시험(장비 미착용).
- config에 null이 있으면 그 값을 추측해 채우지 않는다. 사용자에게 원본 값을 요청한다.
- 결과를 보고 분석 파라미터를 바꾸지 않는다 (사후 조정 금지). 바꿔야 하면 사유·날짜를 계획서 변경 기록에 남긴다.
- 누수 방지: 외부 CV는 블록 단위, 내부 CV는 학습 블록 안에서만, Scaler는 Pipeline 안에서만 fit.
- 선행연구(Rasheed & Marini 2015)의 결과, 우리 계획(가정), 우리 실측 결과를 항상 구분해 표기한다.

## 모든 에이전트의 보고 형식
| 점검 항목 | 상태 | 근거(명령·수치·파일) |
상태는 다음 셋 중 하나만 쓴다.
- **PASS**: 실행 결과가 기준을 충족 (근거 필수)
- **FAIL**: 실행 결과가 기준 미충족
- **UNVERIFIED**: 실행하지 못했거나 기준값(config null)이 없음 — 추정으로 PASS 처리 금지

마지막 줄: `판정: GO / NO-GO / 조건부(남은 UNVERIFIED 목록)`

## 인터프리터
- 자극 python(PsychoPy Standalone): stim_rgb.py — pylsl도 여기에 설치
- 분석 python(.venv): check_streams.py, xdf_qc.py, train_svm.py, tests
- 현장 값(null 3개)은 `scripts/set_field_values.py`로만 기록 (근거 필수, config/CHANGELOG.md에 남음)

## 실행 순서
env-setup → signal-check(승인 전: 미착용 스트림만) → stimulus-builder → lsl-sync → session-runner(승인 후) → pilot-qc
