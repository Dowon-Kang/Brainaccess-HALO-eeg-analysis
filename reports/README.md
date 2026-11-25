# reports/ — 자율 연구 기록 (RGB EEG)

| 문서 | 내용 |
|---|---|
| [STOP_REPORT.md](STOP_REPORT.md) | **먼저 읽을 것.** 중단 사유, 결론(검증된 사실 / 근거 기반 해석 / 미검증 가설), 필요한 결정과 다음 행동 |
| [INITIAL_ANALYSIS.md](INITIAL_ANALYSIS.md) | 초기 연구환경 분석 (§0 요약 + §1–15: 목적, 데이터 구조·샘플, Shape, 데이터 수, 채널, 자극 명세·마커 정합성, 파이프라인, 평가, 누수, 문제점, 데이터 품질, 연구윤리·개인정보, UNKNOWN, 참고문헌, 검증 실행·독립 감사 결과) |
| [RESEARCH_MAP.md](RESEARCH_MAP.md) | 14개 연구 영역의 문제점·실험 가능성·기대 효과·비용·우선순위, 실험 후보 E01–E20과 예산 배분 |
| [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md) | 평가 프로토콜 제안 v0.2 (승인 전, 동결 아님) |
| [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) | 모든 실행(V-01, V-02, V-03, V-03b, V-03c, V-04, V-04b, V-04c, T-01, F-01)의 가설·설계·결과·판정, 그림 설명, 사실 확인 후 정정 내역 |
| [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md) | 독립 감사 37건(5개 영역, 반박 검증 포함)의 판정 표와 정정 진술 |
| `figures/` | V-01, V-03, V-04 그림 (각 그림 하단에 데이터 출처·한계 표기) |
| `runs/AUDIT/`, `runs/FACTCHECK/` | 독립 감사·보고서 사실 확인의 원자료(JSON), 에이전트 지시문(workflow_script.js), run.json |
| `runs/<ID>/` | 실행별 `run.json`(명령, 시각, 소요 시간, commit, 패키지 버전, 입력 파일 SHA-256, 설정, 출력, Shape, 지표; 개정 로거는 경고 수·종료 상태 포함) + `stdout.log`(+ `stderr.log`, `warnings.log`) + 결과 CSV |

## 재현 방법

원본 EEG 없이 실행되는 검증만 포함한다 (Linux, Python 3.13에서 확인).

```bash
python -m venv .venv && . .venv/bin/activate
pip install numpy scipy pandas scikit-learn pyriemann matplotlib joblib
python research/validation/v01_results_audit.py          # 저장된 결과 CSV 감사 (<1 s)
python research/validation/v02_stimulus_luminance.py     # 자극 명목 측광 (<1 s)
python research/validation/v03_synthetic_leakage.py 20 5 # 저장된 19개 중 18개 파이프라인 합성 null 보정 (4코어 약 12분)
python research/validation/v03c_complete_null.py 20       # 누락된 EA + 지속반응, F6 반복 3–19 보완 (4코어, 연산 집약)
python research/validation/v03b_null_precision.py 200 30  # 핵심 ERP 2개 null 정밀 추정 (약 2분)
python research/validation/v04_schedule_confounds.py 30 20 100  # 스케줄 교란 시뮬레이션 (4코어 약 10.5분)
python research/validation/v04b_sequence_predictability.py 20000  # 색 이력 예측 가능성 (약 4초)
python research/validation/v04c_position_oracle.py      # 저장 CV에서 위치만 아는 해독기 (<1초)
python research/validation/t01_rgb_eeg_lab_tests.py      # 기존 rgb-eeg-lab 테스트 실행 기록 (약 25초; mne, pyxdf, pylsl, pytest 필요)
python research/validation/make_figures.py               # 그림 재생성 (V-03c 이후)
```

이 실행에 사용한 패키지 버전은 각 `runs/<ID>/run.json`의 `versions`에 있다.
`rgb-eeg-lab` 테스트는 T-01로 기록했다(33 passed).

원본 데이터가 필요한 실험(E01–E20)은 실행하지 않았다. 팀 PC에서 데이터 버전을 고정하려면
`python research/protocol/make_manifest.py <원본 폴더> --out data_manifest.csv`.
