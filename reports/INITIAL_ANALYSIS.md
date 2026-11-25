# INITIAL ANALYSIS — RGB 시각자극 EEG 분류 프로젝트 초기 연구환경 분석

- 작성: 2026-11-25, 자율 연구 에이전트 (클라우드 컨테이너, Linux, Python 3.13)
- 분석 대상: 저장소 `Brainaccess-HALO-eeg-analysis` commit `ad39d1d` (브랜치 `ccr-d40e6ea0-c4mtak`)
- 표기: **[사실]** 파일·실행 결과로 확인 / **[추론]** 근거에서 논리적으로 도출했으나 원본으로 확인 못 함 / **UNKNOWN** 확인 불가
- 근거 실행: `reports/EXPERIMENT_LOG.md`의 V-01 ~ V-04 (원본 EEG 미사용), 독립 감사 워크플로(5개 영역 감사 + 영역별 반박 검증, §15)

---

## 0. 요약

| 항목 | 판정 | 근거 |
|---|---|---|
| 원본 EEG 데이터 접근 | **불가 (UNKNOWN 다수 발생 원인)** | 컨테이너·`/mnt/user-data`·git 이력 어디에도 `.db`/XDF/`events.csv` 없음. 사용자 PC 연결 폴더 없음(`list_computer_folders` = 빈 목록) |
| 저장된 결과 CSV 내부 산술 일관성 | **PASS** (28/28) | V-01 |
| 기존 분석 코드의 기본 누수 방지(스케일러·선택·튜닝을 학습 fold 안에서) | **PASS (합성 데이터 기준)** | 코드 검토 + V-03 |
| 저장된 within-subject CV·순열검정이 실험 설계의 의존 구조를 반영하는가 | **FAIL** | 반복 세션 동일 색 순서(쌍둥이 블록) 미반영, 시행 단위 셔플 (§9, V-04) |
| 사전등록 분석계획 준수 | **FAIL (전면 이탈)** — 저장된 결과는 모두 탐색 분석 | §7–8 |
| EEG–마커 시간 정합성 | **UNKNOWN** (위험 요인 식별) | §6 |
| 연구윤리(IRB) 기록 | **UNKNOWN — 확인 필요** | §12 |

**결론:** 데이터 품질과 평가 프로토콜을 검증하기 전에는 Baseline을 확립할 수 없다. 이 환경에서는 원본이 없어 검증 자체를 실행할 수 없고, 저장된 평가 방식에는 결함이 확인되었다. 연구 프로토콜 §9의 자동 중단 조건(평가 프로토콜 결함 발견, 원본 없이 판단 불가)에 해당하므로, 원본 EEG 실험은 시작하지 않고 중단 보고한다 (`reports/STOP_REPORT.md`).

---

## 1. 프로젝트의 목적과 현재 연구 진행 상태

**[사실]** 저장소에는 세 갈래의 내용이 있다.

| 경로 | 내용 | 상태 |
|---|---|---|
| `/python_sart.py`, `sart_data.py`, `tests/` | SART(Go/No-Go) PsychoPy 과제 — 2017년 원저작 코드를 2026-09~10에 수정 | RGB 연구와 무관. 이번 분석 범위 밖 |
| `rgb-eeg-lab/` | RGB EEG 실험 키트: 사전등록 설정(`config/protocol.json`), PsychoPy 자극(`stim_rgb.py`), LSL·XDF QC(`xdf_qc.py`), 사전등록 SVM 평가(`train_svm.py`), 변경 기록(`docs/plan_changes.md`), 합성 데이터 테스트 | 테스트 **33 passed** (이 환경에서 실행, 26.6 s). 실제 XDF로 실행된 결과는 저장소에 없음 |
| `rgb-ml-analysis/` | BrainAccess `.db` 기반 탐색 분석: 19개 파이프라인("9가지 ML 기법"), 다른 날·다른 사람 일반화, gray1 대조, 순열검정 | 2026-11-25~26 커밋. 결과 CSV 5개 + ERP 그림만 저장. 중간 산출물(`cache/*.npz`, `epochs.npz`)과 원본 없음 |

**연구 목적 [사실, research_context.md]:** BrainAccess HALO 4채널(Fp1, Fp2, O1, O2, 250 Hz)로 R/G/B 관찰 시 EEG의 색 분류 가능성 평가.
RQ1 관찰 EEG로 색 분류 가능? RQ2 O1/O2 vs 4채널 차이? RQ3 참가자 간 일반화? Rasheed & Marini(2015, 원 배치 P3/P4/O1/O2)의 조건 변경 재현.

**진행 상태 [사실]:** 측정은 2026-11-03 ~ 11-25에 이뤄졌다(sessions.csv). 설계 변경 3건(11-13 시퀀스 단축, 11-21 시작 전 신호 점검 기준, 11-24 세션별 seed)과 Board 3.0.0→3.1.0(11-22) 변경이 있었다. 사전등록 주분석(ERSP + RBF-SVM)의 실데이터 결과는 저장소에 없다. `plan_changes.md`의 미결 결정(v2.0 데이터 병합, P003 블록 결합, 반복 세션 사용 방식)은 "팀 승인 전" 상태로 남아 있다.

## 2. 데이터 파일 구조 및 실제 데이터 샘플

**원본 데이터: 이 환경에 없음 → 실제 데이터 샘플 UNKNOWN.**

| 데이터 | 위치(코드 기준) | 저장소에 있음? | 구조 (출처) |
|---|---|---|---|
| BrainAccess Board `.db` (SQLite) | `/mnt/user-data/uploads/BrainAccessData/sub-001/ses-001/*_eeg.db` (분석 환경), 팀 PC `C:\Users\IM\Documents\BrainAccessData` | 없음 | `data_<uid>`: data(npy blob, shape (11, n)), time(npy blob, LSL 타임스탬프), local_clock, clock_offset / `meta_<uid>`: channels, sf, metadata / `annotations_<uid>`: "sync n=…" (`ba_io.py:3-8` docstring, "verified on real files" — 이전 작성자의 주장, 이번에 재확인 불가) |
| 자극 이벤트 `*_events.csv/.json` | `/mnt/user-data/uploads/data/` | 없음 | event_id, participant, mode, seed, version, block, seq, phase, rep, color, marker, onset_lsl, offset_est_lsl, flip_psychopy, n_frames, … (`stim_rgb.py:388-389`) |
| LabRecorder XDF | 팀 PC `rgb-eeg-lab/data/` | 없음 | 사전등록 경로(`xdf_qc.py`)의 입력. 탐색 분석은 XDF를 쓰지 않음 |
| 저장된 결과 | `rgb-ml-analysis/results/` | **있음** | methods(19×9), subjects(4×10), sessions(10×7), controls(6×5), generalization(16×4) CSV + `erp_by_colour.png` |
| 스트림 참조 | `rgb-eeg-lab/data/board_v3.0.0_stream_reference.json` | 있음 | Board 3.0.0 스트림 메타데이터(장비 미착용) |

## 3. 입력·출력 데이터의 의미와 Shape

[사실: 코드 상수에서 계산] / 원본 값의 실제 크기 n은 UNKNOWN.

| 단계 | 입력 | 출력 | Shape / 의미 |
|---|---|---|---|
| `ba_io.load_db` | `.db` | dict | eeg (4, n) float — 채널 순서 **O1, O2, Fp2, Fp1** (`EEG_CH`), t (n,) LSL 시각, contact (4, n), sample (n,) 카운터, sfreq 250 |
| `build_cache.py` | `.db` | `cache/<tag>.npz` | eeg float32 (4, n), t, contact int8, sfreq |
| `build_epochs.py` | cache + events.csv | `epochs.npz` | X (N, 4, 840) float32 = [−0.28, +3.08] s (분석 구간 −0.2~3.0 s + 양쪽 0.08 s 증강 여유), color, subject, session, block, seq, phase(obs1/obs2/gray1), ptp (N, 4), contact_bad |
| 시행 수 | | | obs 전체 1,608 (P001_1119 포함), 사용 세션 1,428 중 유효 995 [사실, sessions.csv]. gray1 수 UNKNOWN |
| 특징 (예) | X | | ERP 창 평균 0.05–0.5 s, 50 ms × 9창: 4채널 36차원 / O1·O2 18차원. 로그 밴드파워 5대역 × 4채널 = 20차원. 사전등록 ERSP: 채널당 16 → 32 / 64차원 |
| 라벨 | events.csv `color` | | {R, G, B}, 3클래스 균형(블록당 색별 6시퀀스 × obs 2회) |

## 4. 참가자·세션·시행·윈도우별 데이터 수

[사실: sessions.csv, subjects.csv, erp_by_colour.png 범례] · 설계·seed·Board 열은 [추론: 날짜와 plan_changes.md 기준]

| 세션 | 측정일 | obs 전체 | 유효(PTP<150 µV, 접촉 정상) | 유효율 | 사용 | 설계(추론) | 색 순서 seed(추론) |
|---|---|---|---|---|---|---|---|
| P001_1103 (파일명 P01) | 11/03 | 180 | 44 | 24% | 사용 | v2.0 8단계 | base+1 (세션1) |
| P001_1112 | 11/12 | 180 | 39 | 22% | 사용 | v2.0 8단계 | base+1 (세션1) — **P001_1103과 동일 순서** |
| P001_1119 | 11/19 | 180 | 2 | 1% | 제외 | 변경1 6단계 | base+1 |
| P002_1111 | 11/11 | 180 | 176 | 98% | 사용 | v2.0 8단계 | base+2 (세션1) |
| P002_1124 | 11/24 | 180 | 179 | 99% | 사용 | 변경1 | base+2 (세션1) — **P002_1111과 동일 순서** |
| P002_1125 | 11/25 | 180 | 178 | 99% | 사용 | 변경1 | UNKNOWN (변경3 기록상 "다음 측정은 Session 2부터" → base+2+1000일 가능성. events.csv `seed` 열로 확인 필요) |
| P003_1120 | 11/20 | 180 | 77 | 43% | 사용 | 변경1 | base+3 (세션1) |
| P003_1121 | 11/21 | 60 | 60 | 100% | 사용 | 변경1 | base+3 — run-08(블록 2 + 블록 3의 s037–s048)로 추론(60 = 36 + 24) |
| P003_1125 | 11/25 | 108 | 106 | 98% | 사용 | 변경1 | base+3 (`--session 1 --start-block 3`) — 블록 3–5 |
| P08_1109 (1109a + 1109b) | 11/09 | 180 | 136 | 76% | 사용 | v2.0 8단계 (plan_changes 명시) | base+8 |

- 참가자 4명(사용), 사용 세션 9개, 유효 obs 시행 995 (P002 533, P003 243, P08 136, P001 83). 클래스 균형: P002 177/178/178, P003 79/84/80, P08 45/45/46, P001 30/24/29 (R/G/B).
- 윈도우: 시행당 epoch 1개(슬라이딩 윈도우 없음).
- 제외: P02(11/03, IRB·착용 미확인 기록), P001_1119(유효 2개). 두 제외 기준 모두 사후 결정(사전 기준 없음).
- **중복 의심 [추론]:** P003_1121(run-08)의 블록 3 일부(s037–s048)와 P003_1125(run-09)의 블록 3이 같은 시퀀스이다. `plan_changes.md`의 제안("run-08 블록 3 일부 제외")과 달리 탐색 분석은 둘 다 사용한 것으로 보인다(관측 수 일치 기반).

## 5. 채널 구성 및 샘플링 주파수

- [사실] HALO 4 EEG 채널 Fp1, Fp2, O1, O2 (장치 순서 O1, O2, Fp2, Fp1) + contact 4 + Sample, Streaming, Battery = 11채널, 250 Hz (Board 3.1.0 검증 실측 250.0 Hz, plan_changes.md).
- [사실] 단위 µV: `config/CHANGELOG.md` 2026-11-03 (LSL 메타데이터 unit=microvolts, Board 소스의 변환 계수). 착용 신호 크기 점검은 2026-11-25 P003 run-09에서 PASS로 기록.
- [사실] 기준 전극: "device default". 재참조·CAR·ICA 없음(계획).
- 참고: 원 연구 배치(P3/P4/O1/O2)와 달리 Fp1/Fp2는 안구 운동·깜빡임(EOG)을 크게 받는 위치다.

## 6. RGB 자극과 이벤트 마커 정합성

**[사실]**
- 마커 형식 `b{block}|s{seq:03d}|{phase}{rep}|{color}` (`stim_rgb.py:495`), 타임스탬프 = flip(vsync) 시각을 LSL 시계로 환산(`protocol.flip_to_lsl`), CSV `onset_lsl`과 같은 값.
- 색 순서 = `protocol.sequence_plan(seed)` — 블록마다 R/G/B 각 6시퀀스, 같은 색 최대 2연속, `random.Random(seed)`로 결정적 재생성(`protocol.py:94-108`). V-04에서 seed base+1/2/3/8의 순서를 재구성했다.
- 탐색 분석의 정합: `searchsorted(t, onset_lsl)` 후 가장 가까운 다음 샘플과의 차이가 10 ms 넘으면 버림(`build_epochs.py:33-34`). 즉 "근처에 샘플이 있는가"만 확인하며 실제 지연(latency)은 검증하지 않는다.
- Board 스트림은 장치 시계가 없어 **도착 시각**을 타임스탬프로 보냄("no device clock … sending arrival times"), 간격 SD 약 15.7 ms, **음수 간격 존재** (plan_changes.md, 2026-11-22 검증).
- `ba_io.load_db`는 블록을 local_clock 순으로 읽은 뒤 타임스탬프 `t`로 **argsort 재정렬**한다(`ba_io.py:43-55`). Sample 카운터와 `clock_offset`은 순서·시각 보정에 쓰지 않는다. XDF 경로는 pyxdf dejitter를 쓰지만 `.db` 경로에는 dejitter가 없다.
- 화면 자체 지연(scanout·패널 응답)은 포토다이오드로만 측정 가능하며 미측정(REPORT.md v4 "화면 지연 UNVERIFIED").

**[추론 / 위험]**
1. 타임스탬프가 비단조(음수 간격)라면 argsort가 인접 청크의 샘플을 섞어 파형을 훼손할 수 있다. 실제로 `.db`의 `t`가 비단조인지는 **UNKNOWN** (E01로 확인).
2. 약 16 ms 지터는 50 ms 창 ERP 특징(0.05–0.5 s)을 흐리게 한다(SNR 저하, 누수는 아님).
3. 세션마다 Bluetooth 전송 지연이 다르면 VEP 잠복기 특징이 세션 간에 이동 → 세션 간 일반화 저하의 한 원인일 수 있다(가설).

## 7. 전처리 및 특징 추출 파이프라인 — 계획 vs 실제

| 항목 | 사전등록 계획 (research_context.md, protocol.json) | 탐색 분석 실제 (rgb-ml-analysis) | 이탈 |
|---|---|---|---|
| 데이터 경로 | XDF (LabRecorder) | Board `.db` | 예 |
| 대역통과 | 1–30 Hz, 4차 Butterworth, **인과**, 구간별 재시작 | 0.5–30 Hz, 4차 Butterworth, **영위상** `sosfiltfilt`, 녹화 전체에 1회 | 예 |
| Notch | 없음 (`notch: false`) | 60 Hz iirnotch (Q=30), 영위상 | 예 |
| 시작 구간 제외 | 5 s | 없음 (edge만 제외) | 예 |
| Epoch | −1 ~ +2 s | −0.2 ~ +3.0 s (+0.08 s 여유) | 예 |
| 기준 구간 | −1.8 ~ −1.0 s | −0.2 ~ 0 s | 예 |
| 불량 시행 | 자극전 평균 제거 후 abs 60 µV, PTP 120 µV, 1 s std < 0.5 µV 평탄, 누락 샘플 | 4채널 중 하나라도 PTP > 150 µV (−0.2~3.0 s) 또는 접촉 끊김. 임계값은 100/150/200/300 µV 유효율 출력 후 선택(`build_epochs.py:46-49`, 라벨 미사용) | 예 |
| 특징 | ERSP (Morlet 3 cycles, 3–30 Hz, 4대역 × 4구간 0.1–1.5 s, 시행별 기준 정규화) | ERP 창 평균, 로그 밴드파워, xDAWN-TS, 지속 공분산 등 | 예 |
| 분류기 | RBF-SVM (C, γ 격자 nested) | sLDA 외 18종 | 예 |
| 외부 CV | 블록 5-fold (참가자 내) | 참가자 내 모든 세션의 블록을 합쳐 leave-one-block-out (P002 15블록) | 부분 |
| 주지표·보조 | BA / Macro-F1, MCC, 혼동행렬, 95% CI, 참가자 부트스트랩 10,000 | BA만 (CI·Macro-F1·MCC·혼동행렬 없음) | 예 |
| 병합 결정 | v2.0 데이터 병합·P003 결합·반복 세션: 팀 결정 대기 | 모두 병합 | 예 (미결 결정 선행) |

`run_extra.py:12`의 주석 "PRIMARY … pre-specified, theory-driven"과 달리, 해당 파이프라인(ERP O1·O2 + sLDA)은 사전등록 주분석이 아니며 methods.csv에서 19개 중 평균 최고값이다.

## 8. 기존 모델 및 평가 방식

- 19개 파이프라인(`rgb_pipeline.pipelines` 16개 + EA 변형 3개)을 참가자별 leave-one-block-out으로 비교(`run_within.py`). 지표: 외부 fold 예측을 모은 BA.
- 다른 날: 세션 단위 LOGO (P002, P003, P001), 다른 사람: 참가자 단위 LOGO(4명), ± per-session EA (`run_extra.py` A, B).
- gray1 대조: 색이 없는 gray1 구간을 다음 색으로 라벨링(`run_extra.py` C).
- 순열검정: 블록 안에서 **시행 단위** 라벨 셔플, 외부 CV 재실행. 200회(전체), 1,000회(주요 3개) + Bonferroni ×19 (`perm_fine.py`).
- 주요 저장 결과 [사실]: 기준선(ERP 4채널 + sLDA) 평균 33.8%(우연 수준), 최고 평균 ERP O1·O2 + sLDA 39.6%. 참가자별 O1·O2: P002 44.7% (p=0.001, Bonferroni 0.019), P003 39.4% (p=0.038, 보정 후 0.72), P08 36.0% (p=0.28), P001 38.2% (p=0.14). 다른 날 36.0–40.6%, 다른 사람 31.0–36.2%, gray1 대조 28.6–33.4%.

## 9. 데이터 누수 가능성

| # | 위험 | 판정 | 근거 |
|---|---|---|---|
| L1 | 스케일러·특징선택·xDAWN·튜닝·증강이 테스트 fold를 보는가 | **누수 없음 (확인)** | 모두 Pipeline/estimator 안에서 학습 fold에만 fit (`rgb_pipeline.py:171-235`). V-03: 색 정보 없는 합성 데이터에서 null 보정 결과 (§15 참조) |
| L2 | 같은 시퀀스의 obs1/obs2가 학습·검증에 나뉘는가 | 없음 | 블록 단위 그룹 → 같은 시퀀스는 같은 블록 |
| L3 | **반복 세션의 동일 색 순서(쌍둥이 블록)** | **평가 결함 (확인), 영향 크기 UNKNOWN** | 2026-11-24 이전 모든 기록은 세션1 seed (plan_changes 변경3) → P001 2세션, P002 최소 2세션, P003 3기록이 같은 순서. 그룹 = `subj_session_bN`(`build_epochs.py:38`)이라 테스트 블록의 쌍둥이(같은 순서)가 학습에 포함. 위치·시간에 따라 변하는 EEG 상태가 세션 간 재현되면 색과 무관한 정보로 색을 맞힐 수 있다. V-04 시뮬레이션 (§15) |
| L4 | 순열 null의 교환가능성 | **결함 (확인)** | 시행 단위 셔플은 obs1/obs2(같은 색)를 갈라놓고 쌍둥이 블록 간 공유 순서를 재현하지 않음 → 실제 무작위화 구조보다 null이 좁을 수 있음(반보수적). V-01: 순열 null SD가 iid 이항 SD의 1.14–1.29배 |
| L5 | EA 정렬이 테스트 세션 데이터를 사용 | 라벨 누수 아님 (transductive) | 세션 전체 공분산으로 백색화(`apply_ea_per_group`) — 온라인 상황보다 낙관적일 수 있음. 보고 시 표기 필요 |
| L6 | 영위상 필터의 시간 번짐 | 위험 (영향 UNKNOWN) | 녹화 전체 `sosfiltfilt` → 자극 후 반응이 기준 구간(−0.2~0 s)과 직전 gray 구간으로 번짐. 인과성 위반이지만 라벨 누수는 아님. 기준 보정이 색별 반응의 일부를 제거·왜곡할 수 있음 |
| L7 | 모델 선택 편향 | **있음 (확인)** | 19개를 같은 CV로 비교 후 최고값 보고, 독립 검증 없음. V-01 |
| L8 | 불량 임계값 선택 | 라벨 미사용 → 누수 아님 | 유효율만 보고 선택. 사전등록 기준과 다름 |
| L9 | 스태킹 내부 cv=3 그룹 미지정 | 테스트 누수 아님 | 학습 fold 내부 메타특징만 낙관적 |
| L10 | 직전 시퀀스 색의 이월 | 교란 가능 (영향 UNKNOWN) | 최대 2연속 제약 → 직전 색이 현재 색에 대해 약한 정보. V-04 |

## 10. 기존 실험의 문제점 및 미검증 가정

**문제점 [사실]**
1. 저장된 모든 결과가 사전등록에서 이탈한 탐색 분석이며, 사전등록 주분석 결과가 없다.
2. 기준선 4채널 sLDA 평균 33.8%는 우연 수준이다. 19개 파이프라인 간 차이(−3.3 ~ +5.8 %p)는 참가자별 순열 null SD(2.6–5.9 %p, V-01)와 같은 크기다.
3. 유일하게 보정 후 유의한 P002 결과는 L3·L4 결함의 영향을 받는 CV와 순열검정에서 나왔다.
4. 불확실성(CI)·Macro-F1·MCC·혼동행렬·Dummy 기준이 보고되지 않았다.
5. 다중비교 보정은 파이프라인 19개만 반영하고 참가자 4명, 추가 분석(EA, 다른 날, 다른 사람)은 반영하지 않았다.
6. 이항 우연 임계값(`controls.csv` chance95)은 시행 독립을 가정하지만 null 분산이 그보다 크다(V-01).
7. 재현 불가: 경로가 `/home/claude/...`, `/mnt/user-data/...`로 하드코딩되어 있고, 중간 산출물과 ML 환경 버전 고정이 없다. 저장된 수치는 원본 없이는 재생성할 수 없다.
8. v2.0(8단계, 상상 2회, 휴식 120 s)과 변경1(6단계, 휴식 30 s) 데이터, Board 3.0.0/3.1.0 데이터를 팀 결정 없이 합쳤다.

**미검증 가정**
- `.db` 타임스탬프와 events.csv `onset_lsl`이 같은 LSL 시계이며 지연이 세션 간 일정하다.
- `.db` 시각 정렬이 샘플 순서를 보존한다.
- 명목 sRGB 등휘도가 실제 모니터에서도 성립한다(측광 미실시).
- Fp 채널의 EOG가 색과 무관하다.
- contact == 0이 "접촉 불량"을 뜻한다(`build_epochs.py:40`).
- 피험자가 반복 세션에서 색 순서를 학습·예측하지 않았다.

## 11. 데이터 품질 요약 (저장 수치 기반)

- 유효율이 참가자 간 극단적으로 다르다(P002 98–99% vs P001 22–24%). P001의 낮은 유효율은 4채널 기준 PTP 150 µV 때문이며 O1·O2만 기준이면 달라질 수 있다(`build_epochs.py:48-49`가 계산했으나 결과는 미저장).
- P003_1120: 탐색 기준 43% vs 사전등록 QC 25%(plan_changes, 주원인 O1 60%·O2 54% 불량).
- ERP 그림(`erp_by_colour.png`) 관찰: P002는 색 무관 onset VEP가 뚜렷하다. P001·P08은 색별 평균이 0 s 부근부터 갈라지며(시행 24–46개/색), 0.1 s 이전 차이는 생리적 VEP로 설명하기 어렵다 — 잡음, 영위상 필터의 번짐, 또는 세션 간 기저선 차이 가능성(해석, 미검증).

## 12. 연구윤리 및 개인정보

- [사실] 저장소 규칙(CLAUDE.md, CHECKLIST.md)은 IRB 승인 확인 전 사람 EEG 기록을 금지한다. 마지막 IRB 상태 기록은 REPORT.md(2026-10-30) "UNVERIFIED → 사람 대상 측정 NO-GO"이다. 저장소 어디에도 IRB 승인 번호·날짜가 없고, 측정은 2026-11-03부터 존재한다. P02(11/03)는 "IRB·착용 미확인 기록" 때문에 제외되었다.
- 판정: **위반을 확인한 것이 아니라, 승인 시점과 측정 시점의 관계를 저장소로 확인할 수 없다(UNKNOWN).** 추가 분석·외부 공개 전에 팀이 IRB 승인 번호·승인일과 각 측정일을 확인해야 한다.
- 개인정보: 참가자는 가명 코드(P001 등)로만 등장한다. 측정 일시가 파일명에 있다(`build_epochs.py:5-15`). 실험 PC 호스트명과 Windows 사용자 폴더명이 `locks/`·README에 있다. 이름·연락처 등 직접 식별 정보는 확인되지 않았다(§15 감사 결과 참조).
- 이번 작업에서 원본 데이터와 결과를 외부 서비스로 보내지 않았다(웹 검색은 논문 서지 확인용 공개 제목만).

## 13. UNKNOWN 목록 (원본 접근 시 확인할 것)

| 항목 | 확인 방법 |
|---|---|
| `.db` 타임스탬프 단조성, Sample 카운터 연속성, 손실 샘플 | E01 |
| 마커–EEG 지연과 세션 간 차이, `.db` vs XDF 일치 | E02 |
| 각 세션의 실제 seed (특히 P002_1125) | events.csv `seed` 열, EXP_START 마커 |
| P08 1109a/1109b의 관계(이어하기 vs 재시작), 블록 번호 중복 | events.csv `block`·`seq` |
| P003_1121의 실행 구성과 블록 3 중복 | events.csv + session_P003 기록 |
| gray1 대조 시행 수가 obs보다 크게 적은 이유 | events.csv 마커 이름(구버전 형식 여부)·유효 기준 |
| 설계 버전(8/6단계)과 Board 버전 세션별 확정 | EXP_START `phases=`, JSON 메타 |
| 물리적 휘도·색도 | 측광기/색채계 측정 |
| IRB 승인 번호·날짜 | 팀 문서 |

## 14. 참고문헌 (실제 확인 범위 명시)

| 문헌 | 확인 내용 | 이 문서에서의 용도 |
|---|---|---|
| Rasheed S., Marini D. (2015) *Classification of EEG signals produced by RGB colour stimuli.* Journal of Biomedical Engineering and Medical Imaging. | 2차 인용(arXiv:2008.07092 참고문헌)으로 서지정보만 확인. **원문 미확인** — 원 연구의 수치는 이 문서에서 인용하지 않음 | 프로젝트가 재현하려는 선행연구 |
| Li R. et al. (2021) *The Perils and Pitfalls of Block Design for EEG Classification Experiments.* IEEE TPAMI 43(1):316–333. DOI 10.1109/TPAMI.2020.2973153 | 서지정보·초록 확인: 같은 블록·시간 근접 시행이 학습/테스트에 섞이면 자극이 아닌 장시간 뇌 상태를 분류할 수 있음(반론 논문 존재) | L3(시간·순서 구조 교란)의 선례 |
| Varoquaux G. (2018) *Cross-validation failure: small sample sizes lead to large error bars.* NeuroImage 180:68–77. DOI 10.1016/j.neuroimage.2017.06.061 | 초록 확인: 소표본 CV 정확도의 오차막대가 큼, fold 간 표준오차는 이를 과소추정 | CI 필수 근거 |
| Combrisson E., Jerbi K. (2015) *Exceeding chance level by chance.* J Neurosci Methods 250:126–136. DOI 10.1016/j.jneumeth.2015.01.010 | 초록 확인: 이론적 우연 수준은 무한 표본에서만 성립 | 우연 수준 판정 근거 |
| Cawley G.C., Talbot N.L.C. (2010) *On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation.* JMLR 11:2079–2107 | JMLR 초록 확인: 모델 선택 과적합과 선택 편향 | L7 근거 |
| He H., Wu D. (2020) *Transfer Learning for Brain-Computer Interfaces: A Euclidean Space Data Alignment Approach.* IEEE TBME 67(2):399–410. DOI 10.1109/TBME.2019.2913914 | 서지정보 확인 | 기존 코드의 EA 출처 |

## 15. 검증 실행과 독립 감사 결과

(V-03, V-04 및 감사 결과는 실행 완료 후 이 절에 기입)
