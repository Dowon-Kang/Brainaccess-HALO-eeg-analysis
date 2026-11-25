# RGB EEG 분류 — 9가지 ML 기법 적용 코드와 결과

## 실행 순서
1. `build_cache.py` — BrainAccess `.db`(SQLite)를 읽어 세션별 `cache/*.npz`로 저장 (`ba_io.load_db` 사용)
2. `build_epochs.py` — events.csv 마커(onset_lsl)와 DB의 LSL 시각을 맞춰 obs·gray1 구간 에포크 생성 → `epochs.npz`
3. `run_within.py` — 참가자별 19개 파이프라인 비교 (블록 단위 교차검증)
4. `run_extra.py` — 다른 날·다른 사람 검증, gray1 대조, 순열검정(200회)
5. `perm_fine.py` — 주요 결과 순열검정 1000회 + Bonferroni 보정
6. `plot_erp.py` — 색별 후두엽 평균 파형 그림

`rgb_pipeline.py`에 9가지 요소가 모두 들어 있어요(전처리, 특징, 특징 선택, 분류기, 증강, nested 튜닝, EA, 앙상블, 평가).
`synthetic_check.py`는 실제 배경 EEG에 가짜 마커를 얹어 평가 누수가 없는지 확인하는 점검용이에요.

## 경로
스크립트 안의 경로(`/home/claude/work/...`, `/mnt/user-data/uploads/...`)는 분석 환경 기준이에요.
PC에서 돌릴 때는 `C:\Users\IM\Documents\BrainAccessData`와 `C:\braineeg\Experiment\rgb-eeg-lab-v4\rgb-eeg-lab\data`로 바꿔 주세요.
필요 패키지: numpy, scipy, pandas, scikit-learn, pyriemann, matplotlib, joblib

## 분석 기준
- 0.5–30 Hz 대역통과 + 60 Hz 노치, obs 구간 −0.2–3.0초, 기준선 −0.2–0초
- 4채널 중 하나라도 진폭 150 µV 초과이거나 접촉 끊김이면 제외
- P001 11/19 세션은 깨끗한 시행이 2개뿐이라 제외, P02(11/03)는 IRB·착용 미확인 기록 때문에 제외

## results/
- `methods.csv` 기법별 정확도 · `subjects.csv` 참가자별 결과·순열검정
- `generalization.csv` 다른 날·다른 사람 · `controls.csv` 회색 화면 대조 · `sessions.csv` 세션별 품질
- `erp_by_colour.png` 색별 평균 파형
