# RGB EEG 실습 키트

```
CLAUDE.md                 모든 에이전트 공통 규칙 (IRB, config 우선, PASS/FAIL/UNVERIFIED)
REPORT.md                 수정·검증 보고서 (변경 이유, 테스트 출력, GO/NO-GO)
CHECKLIST.md              실습 체크리스트 v4 (PowerShell)
config/protocol.json      계획서 v2.0 값 (null = 모니터 cm·해상도, EEG 단위 — 현장 실측)
.claude/agents/           단계별 Claude Code 에이전트 6개
scripts/stim_rgb.py       PsychoPy 자극 + LSL 마커 'RGB_Markers'
scripts/check_streams.py  LSL 스트림·신호 품질 (--blink, --alpha)
scripts/xdf_qc.py         XDF QC(마커·EEG 무결성) + 필터→epoch→불량→ERSP 특징
scripts/train_svm.py      RBF SVM 블록 중첩 CV, BA/F1/MCC/CM, 부트스트랩 CI, 셔플 누수 점검, LOSO
scripts/protocol.py       config 로더, seed·순서·구간·flip→LSL 시각 환산
scripts/env_check.py      인터프리터별 import·pylsl 루프백 점검 + locks/ 버전 고정
scripts/set_field_values.py 현장 실측값(모니터 cm·해상도, EEG 단위) 검증·기록
requirements-stim.txt     자극 python(PsychoPy Standalone)에 설치
requirements-analysis.txt 분석 python(.venv)에 설치
locks/                    버전 기록 (실습 PC에서 생성)
docs/system_test.md       HALO→LSL→XDF 미착용 테스트 절차
docs/vscode_setup_prompt.md VS Code Claude Code 세팅 프롬프트
tests/test_pipeline.py    합성 데이터 정상·고장 주입·도구 테스트 27개
templates/session_log.md  세션 기록 양식
docs/research_context.md  연구계획 원문
```

## 사용법
`REPORT.md` 3·4절 (PowerShell 명령, 에이전트 순서) 참고.
