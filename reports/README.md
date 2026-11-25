# reports/ — 자율 연구 기록 (RGB EEG)

| 문서 | 내용 |
|---|---|
| [STOP_REPORT.md](STOP_REPORT.md) | **먼저 읽을 것.** 중단 사유, 결론(검증된 사실 / 근거 기반 해석 / 미검증 가설), 필요한 결정과 다음 행동 |
| [INITIAL_ANALYSIS.md](INITIAL_ANALYSIS.md) | 초기 연구환경 분석 10개 항목 (데이터 구조, Shape, 데이터 수, 채널, 마커 정합성, 파이프라인, 평가, 누수, 문제점, UNKNOWN) |
| [RESEARCH_MAP.md](RESEARCH_MAP.md) | 14개 연구 영역의 문제점·실험 가능성·기대 효과·비용·우선순위, 실험 후보 E01–E20과 예산 배분 |
| [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md) | 평가 프로토콜 제안 v0.1 (승인 전, 동결 아님) |
| [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) | 실행한 모든 검증 실행(V-01, V-02, V-03, V-03b, V-04, V-04b, V-04c)의 가설·설계·결과·판정 |
| [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md) | 독립 감사 37건(5개 영역, 반박 검증 포함)의 판정 표와 정정 진술 |
| `figures/` | V-01, V-03, V-04 그림 (각 그림 하단에 데이터 출처·한계 표기) |
| `runs/AUDIT/` | 독립 감사 원자료(JSON, 근거 줄 번호·인용 포함) |
| `runs/<ID>/` | 실행별 `run.json`(명령, 시각, 소요 시간, commit, 패키지 버전, 입력 파일 SHA-256, 출력, Shape, 지표) + `stdout.log` + 결과 CSV |

## 재현 방법

원본 EEG 없이 실행되는 검증만 포함한다 (Linux, Python 3.13에서 확인).

```bash
python -m venv .venv && . .venv/bin/activate
pip install numpy scipy pandas scikit-learn pyriemann matplotlib joblib
python research/validation/v01_results_audit.py          # 저장된 결과 CSV 감사 (<1 s)
python research/validation/v02_stimulus_luminance.py     # 자극 명목 측광 (<1 s)
python research/validation/v03_synthetic_leakage.py 20 5 # 19개 파이프라인 합성 null 보정 (4코어 약 12분)
python research/validation/v03b_null_precision.py 200 30  # 핵심 ERP 2개 null 정밀 추정 (약 2분)
python research/validation/v04_schedule_confounds.py 30 20 100  # 스케줄 교란 시뮬레이션 (4코어 약 10.5분)
python research/validation/v04b_sequence_predictability.py 20000  # 색 이력 예측 가능성 (약 4초)
python research/validation/v04c_position_oracle.py      # 저장 CV에서 위치만 아는 해독기 (<1초)
```

이 실행에 사용한 패키지 버전은 각 `runs/<ID>/run.json`의 `versions`에 있다.
`rgb-eeg-lab` 테스트: `cd rgb-eeg-lab && python -m pytest tests -q` (이 환경에서 33 passed; 추가 패키지 mne, pyxdf, pylsl, pytest 필요).

원본 데이터가 필요한 실험(E01–E20)은 실행하지 않았다. 팀 PC에서 데이터 버전을 고정하려면
`python research/protocol/make_manifest.py <원본 폴더> --out data_manifest.csv`.
