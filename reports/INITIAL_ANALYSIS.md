# INITIAL ANALYSIS — RGB 시각자극 EEG 분류 프로젝트 초기 연구환경 분석

- 작성: 2026-11-25, 자율 연구 에이전트 (클라우드 컨테이너, Linux, Python 3.13)
- 분석 대상: 저장소 `Brainaccess-HALO-eeg-analysis` commit `ad39d1d` (브랜치 `ccr-d40e6ea0-c4mtak`)
- 표기: **[사실]** 파일·실행 결과로 확인 / **[추론]** 근거에서 논리적으로 도출했으나 원본으로 확인 못 함 / **UNKNOWN** 확인 불가
- 근거 실행: `reports/EXPERIMENT_LOG.md`의 V-01 ~ V-04c (원본 EEG 미사용), 독립 감사(5개 영역 감사 + 영역별 반박 검증, §15, `reports/AUDIT_FINDINGS.md`)

---

## 0. 요약

| 항목 | 판정 | 근거 |
|---|---|---|
| 원본 EEG 데이터 접근 | **불가 (UNKNOWN 다수 발생 원인)** | 컨테이너·`/mnt/user-data`·git 이력 어디에도 `.db`/XDF/`events.csv` 없음. 사용자 PC 연결 폴더 없음(`list_computer_folders` = 빈 목록) |
| 저장된 결과 CSV 내부 산술 일관성 | **PASS** (28/28) | V-01 |
| 기존 분석 코드의 기본 누수 방지(스케일러·선택·튜닝을 학습 fold 안에서) | **PASS (합성 데이터 기준)** | 코드 검토 + [합성] V-03 + V-03c(저장된 19개 전부, 각 20회, null 평균 0.331–0.347) + V-03b(핵심 2개 200회, 95% CI가 1/3 포함) |
| 저장된 within-subject CV·순열검정이 실험 설계의 의존 구조를 반영하는가 | **FAIL (구조적 불일치) · 실제 영향 UNKNOWN** | 반복 세션 동일 색 순서(쌍둥이 블록) 미반영, 시행 단위 셔플 (§9). [합성] V-04의 매끄러운 드리프트 메커니즘에서는 BA 상승 없음; 순열 보정 검사(20회)는 검정력 부족으로 판단 보류 |
| 색 순서 설계의 예측 가능성 | **위험 (설계 사실)** | 직전 색만으로 BA 상한 39.4%, 블록 내 이력으로 51.4%, 블록 마지막 시퀀스 100% 결정 (V-04, V-04b) |
| 사전등록 분석계획 준수 | **FAIL (전면 이탈)** — 저장된 결과는 모두 탐색 분석 | §7–8 |
| EEG–마커 시간 정합성 | **UNKNOWN** (위험 요인 식별) | §6 |
| 연구윤리(IRB) 기록 | **UNKNOWN — 확인 필요** | §12 |

**결론:** 데이터 품질과 평가 프로토콜을 검증하기 전에는 Baseline을 확립할 수 없다. 이 환경에서는 원본이 없어 데이터 검증 자체를 실행할 수 없다. 저장된 평가 방식에는 구조적 결함(사전등록 이탈, 모델 선택 편향, 무작위화 구조와 맞지 않는 CV·순열)이 있고, 색 순서 설계에는 이력 예측 가능성이 있다. IRB 기록도 확인되지 않는다. 연구 프로토콜 §9의 자동 중단 조건(평가 프로토콜 결함, 원본 없이 판단 불가, 윤리 확인 필요)에 해당하므로 원본 EEG 실험은 시작하지 않고 중단 보고한다 (`reports/STOP_REPORT.md`).

---

## 1. 프로젝트의 목적과 현재 연구 진행 상태

**[사실]** 저장소에는 세 갈래의 내용이 있다.

| 경로 | 내용 | 상태 |
|---|---|---|
| `/python_sart.py`, `sart_data.py`, `tests/` | SART(Go/No-Go) PsychoPy 과제 — 2017년 원저작 코드를 2026-09~10에 수정 | RGB 연구와 무관. 이번 분석 범위 밖 |
| `rgb-eeg-lab/` | RGB EEG 실험 키트: 사전등록 설정(`config/protocol.json`), PsychoPy 자극(`stim_rgb.py`), LSL·XDF QC(`xdf_qc.py`), 사전등록 SVM 평가(`train_svm.py`), 변경 기록(`docs/plan_changes.md`), 합성 데이터 테스트 | 테스트 **33 passed** (이 환경에서 실행, T-01 23.1 s, 기록 `reports/runs/T01`). 실제 XDF로 실행된 결과는 저장소에 없음 |
| `rgb-ml-analysis/` | BrainAccess `.db` 기반 탐색 분석: 19개 파이프라인("9가지 ML 기법"), 다른 날·다른 사람 일반화, gray1 대조, 순열검정 | 2026-11-25 커밋(79f7a48). 결과 CSV 5개 + ERP 그림만 저장. 중간 산출물(`cache/*.npz`, `epochs.npz`)과 원본 없음 |

**연구 목적 [사실, research_context.md]:** BrainAccess HALO 4채널(Fp1, Fp2, O1, O2, 250 Hz)로 R/G/B 관찰 시 EEG의 색 분류 가능성 평가.
RQ1 관찰 EEG로 색 분류 가능? RQ2 O1/O2 vs 4채널 차이? RQ3 참가자 간 일반화? Rasheed & Marini(2015, 원 배치 P3/P4/O1/O2)의 조건 변경 재현.

**진행 상태 [사실]:** 측정은 2026-11-03 ~ 11-25에 이뤄졌다(sessions.csv). 설계 변경 3건(11-13 시퀀스 단축, 11-21 시작 전 신호 점검 기준, 11-24 세션별 seed)과 Board 3.0.0→3.1.0(11-22) 변경이 있었다. 사전등록 주분석(ERSP + RBF-SVM)의 실데이터 결과는 저장소에 없다. `plan_changes.md`의 미결 결정 — v2.0 데이터 병합("미결정"), P003 블록 결합("팀 승인 전" Claude 제안), 반복 세션 사용 방식("미결") — 은 모두 팀 결정 대기 상태다.

## 2. 데이터 파일 구조 및 실제 데이터 샘플

**원본 데이터: 이 환경에 없음 → 실제 데이터 샘플 UNKNOWN.**

| 데이터 | 위치(코드 기준) | 저장소에 있음? | 구조 (출처) |
|---|---|---|---|
| BrainAccess Board `.db` (SQLite) | `/mnt/user-data/uploads/BrainAccessData/sub-001/ses-001/*_eeg.db` (분석 환경), 팀 PC `C:\Users\<user>\Documents\BrainAccessData` | 없음 | `data_<uid>`: data(npy blob, shape (11, n)), time(npy blob, LSL 타임스탬프), local_clock, clock_offset / `meta_<uid>`: channels, sf, metadata / `annotations_<uid>`: "sync n=…" (`ba_io.py:3-8` docstring, "verified on real files" — 이전 작성자의 주장, 이번에 재확인 불가) |
| 자극 이벤트 `*_events.csv/.json` | `/mnt/user-data/uploads/data/` | 없음 | event_id, participant, mode, seed, version, block, seq, phase, rep, color, marker, onset_lsl, offset_est_lsl, flip_psychopy, n_frames, … (`stim_rgb.py:388-389`) |
| LabRecorder XDF | 팀 PC `rgb-eeg-lab/data/` | 없음 | 사전등록 경로(`xdf_qc.py`)의 입력. 탐색 분석은 XDF를 쓰지 않음 |
| 저장된 결과 | `rgb-ml-analysis/results/` | **있음** | methods(19×9), subjects(4×10), sessions(10×7), controls(6×5), generalization(16×4) CSV + `erp_by_colour.png` |
| 스트림 참조 | `rgb-eeg-lab/data/board_v3.0.0_stream_reference.json` | 있음 | Board 3.0.0 스트림 메타데이터. 출처: P003 본측정 run-05 XDF(2026-11-21, 착용 기록) — 채널 라벨·단위·srate, 원시 EEG SD |

**저장소에 있는 실제 데이터 파일의 샘플** [사실; 원본 EEG·이벤트 샘플은 UNKNOWN]

```text
rgb-ml-analysis/results/sessions.csv
session,subject,date,total,kept,keep_pct,used
P001_1103,P001,11/03,180,44,24.0,사용
P001_1112,P001,11/12,180,39,22.0,사용

rgb-ml-analysis/results/subjects.csv
subject,sessions,trials,bacc,null_mean,null95,p,n_perm,p_bonf,verdict
P002,3,533,44.7,32.9,37.1,0.001,1000,0.019,유의 (보정 후에도)

rgb-eeg-lab/data/board_v3.0.0_stream_reference.json (발췌, 호스트명 생략)
name "BA HALO 114_HALO_BrainAccess", type EEG, nominal_srate 250.0, measured_srate 250.002, channel_count 11,
channels O1/O2/Fp2/Fp1 (unit microvolts), contact_O1..contact_Fp1, Sample, Streaming, Battery (pct),
raw_eeg_sd_uV [14525.4, 14287.8, 7945.4, 15971.1]  (필터 전 원시 SD: 큰 DC 오프셋 포함)
```

## 3. 입력·출력 데이터의 의미와 Shape

[사실: 코드 상수에서 계산] / 원본 값의 실제 크기 n은 UNKNOWN.

| 단계 | 입력 | 출력 | Shape / 의미 |
|---|---|---|---|
| `ba_io.load_db` | `.db` | dict | eeg (4, n) float — 채널 순서 **O1, O2, Fp2, Fp1** (`EEG_CH`), t (n,) LSL 시각, contact (4, n), sample (n,) 카운터, sfreq 250 |
| `build_cache.py` | `.db` | `cache/<tag>.npz` | eeg float32 (4, n), t, contact int8, sfreq |
| `build_epochs.py` | cache + events.csv | `epochs.npz` | X (N, 4, 840) float32 = [−0.28, +3.08] s (분석 구간 −0.2~3.0 s + 양쪽 0.08 s 증강 여유), color, subject, session, block, seq, phase(obs1/obs2/gray1), ptp (N, 4), contact_bad |
| 시행 수 | | | obs 전체 1,608 (P001_1119 포함), 사용 세션 1,428 중 유효 995 [사실, sessions.csv]. gray1 유효 시행 P002 115, P003 87, P08 60 [사실, controls.csv]; 정제 전 gray1 전체 수와 P001의 gray1 수는 UNKNOWN |
| 특징 (예) | X | | ERP 창 평균 0.05–0.5 s, 50 ms × 9창: 4채널 36차원 / O1·O2 18차원. 로그 밴드파워 5대역 × 4채널 = 20차원. 사전등록 ERSP: 채널당 16 → 32 / 64차원 |
| 라벨 | events.csv `color` | | {R, G, B}, 3클래스 균형(블록당 색별 6시퀀스 × obs 2회) |

## 4. 참가자·세션·시행·윈도우별 데이터 수

[사실: sessions.csv, subjects.csv, erp_by_colour.png 범례] · 설계·seed 열은 [추론: 날짜와 plan_changes.md 기준]

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

### 6.0 자극 명세 [사실: config/protocol.json, stim_rgb.py, plan_changes.md]

| 항목 | 값 |
|---|---|
| 자극 | 회색 배경 중앙 정사각형 10.5 cm(60 cm에서 10°), 관찰 단계에서만 색. 고정점 `+`·상상 cue(작은 원)는 config에 있으나 계획서 미기재(팀 확인 필요, protocol.json `_unconfirmed`) |
| 색 (sRGB, 0–255) | R (157, 0, 0), G (0, 89, 0), B (0, 0, 255), 회색 (76, 76, 76) — 명목 등휘도(V-02) |
| 단계 길이 | 각 3 s (`phase_sec`, 프레임 수 기반으로 표시; 실제 화면 지연은 미측정) |
| v2.0 시퀀스 (2026-11-13 이전) | gray1 obs1 gray2 obs2 gray3 img1 gray4 img2 (24 s), 블록 사이 휴식 120 s |
| 변경1 시퀀스 (2026-11-13 이후) | gray1 obs1 gray2 obs2 gray3 img1 (18 s), 휴식 30 s |
| 블록 구성 | 5블록 × 색별 6시퀀스 = 90시퀀스, 같은 색 최대 2연속, 순서 = `sequence_plan(seed)` |
| 모니터 | 70.8 cm, 1920 × 1080, 최소 60 Hz 요구, 밝기 50%, 예열 20분 (config). 실제 주사율·화면 지연 UNVERIFIED |
| config ↔ 자극 코드 일치 | `stim_rgb.py`는 색·회색·단계를 config에서 읽는다(`stim_rgb.py:239-242`, `:496`). 저장소 테스트가 계획 값 일치를 검사(T-01, `test_stimulus_config_and_seed`) |

### 6.1 마커와 시간 정합

**[사실]**
- 마커 형식 `b{block}|s{seq:03d}|{phase}{rep}|{color}` (`stim_rgb.py:495`), 타임스탬프 = flip(vsync) 시각을 LSL 시계로 환산(`protocol.flip_to_lsl`), CSV `onset_lsl`과 같은 값.
- 색 순서 = `protocol.sequence_plan(seed)` — 블록마다 R/G/B 각 6시퀀스, 같은 색 최대 2연속, `random.Random(seed)`로 결정적 재생성(`protocol.py:94-108`). V-04에서 seed base+1/2/3/8의 순서를 재구성했다.
- 탐색 분석의 정합: `searchsorted(t, onset_lsl)` 후 가장 가까운 다음 샘플과의 차이가 10 ms 넘으면 버림(`build_epochs.py:33-34`). 즉 "근처에 샘플이 있는가"만 확인하며 실제 지연(latency)은 검증하지 않는다.
- Board LSL 스트림은 장치 시계가 없어 **도착 시각**을 타임스탬프로 보낸다("no device clock … sending arrival times"). 2026-11-22 점검(XDF·실시간 스트림)에서 샘플 간격 SD 약 15.7 ms와 **음수 간격**이 보고되었다(plan_changes.md). `.db` time 열에도 같은 지터가 있는지는 UNKNOWN.
- `ba_io.load_db`는 블록을 local_clock 순으로 읽은 뒤 타임스탬프 `t`로 **argsort 재정렬**한다(`ba_io.py:43-55`). Sample 카운터와 `clock_offset`은 순서·시각 보정에 쓰지 않는다. XDF 경로는 pyxdf dejitter를 쓰지만 `.db` 경로에는 dejitter가 없다.
- 화면 자체 지연(scanout·패널 응답)은 포토다이오드로만 측정 가능하며 미측정(REPORT.md v4 "화면 지연 UNVERIFIED").

**[추론 / 위험]**
1. 타임스탬프가 비단조(음수 간격)라면 argsort가 인접 청크의 샘플을 섞어 파형을 훼손할 수 있다. 실제로 `.db`의 `t`가 비단조인지는 **UNKNOWN** (E01로 확인).
2. `.db` 타임스탬프에 LSL 스트림과 같은 수준(간격 SD 약 16 ms)의 지터가 있다면 50 ms 창 ERP 특징(0.05–0.5 s)을 흐릴 수 있다(SNR 저하, 누수는 아님). 단 10 ms 정합 검사에서 대부분의 마커가 통과했다는 점(사용 세션의 시행 수가 설계와 일치)으로 보아 마커 위치의 시각 오차는 대부분 10 ms 미만일 수 있다.
3. 세션마다 Bluetooth 전송 지연이 다르면 VEP 잠복기 특징이 세션 간에 이동 → 세션 간 일반화 저하의 한 원인일 수 있다(가설).
4. 기록 끊김(gap) 처리 없음 [사실]: `build_cache.py:11`은 0.1 s 넘는 간격 수를 출력만 하고, `build_epochs.py:20`은 녹화 전체를 한 번에 필터링하며, epoch는 샘플 개수로 잘라낸다(`build_epochs.py:34-35`). 끊김을 가로지르는 epoch는 실제 시간 길이가 다르고 필터 과도응답이 섞일 수 있다. 사전등록 QC는 누락 표본을 구간 경계로 보고 필터를 재시작한다. 실제 끊김 빈도는 UNKNOWN(P003 run-08처럼 장치가 꺼진 사례는 기록됨).

## 7. 전처리 및 특징 추출 파이프라인 — 계획 vs 실제

| 항목 | 사전등록 계획 (research_context.md, protocol.json) | 탐색 분석 실제 (rgb-ml-analysis) | 이탈 |
|---|---|---|---|
| 데이터 경로 | XDF (LabRecorder) | Board `.db` | 예 |
| 대역통과 | 1–30 Hz, 4차 Butterworth, **인과**, 구간별 재시작 | 0.5–30 Hz, 4차 Butterworth, **영위상** `sosfiltfilt`, 녹화 전체에 1회 | 예 |
| Notch | 없음 (`notch: false`) | 60 Hz iirnotch (Q=30), 영위상 | 예 |
| 시작 구간 제외 | 5 s | 없음 (edge만 제외) | 예 |
| Epoch | −1 ~ +2 s | −0.2 ~ +3.0 s (+0.08 s 여유) | 예 |
| 기준 구간 | −1.8 ~ −1.0 s | −0.2 ~ 0 s | 예 |
| 불량 시행 | 자극전 평균 제거 후 abs 60 µV, PTP 120 µV, 1 s std < 0.5 µV 평탄, 누락 샘플 | 4채널 중 하나라도 PTP > 150 µV (−0.2~3.0 s) 또는 접촉 끊김. 코드는 100/150/200/300 µV별 유효율을 출력하지만(`build_epochs.py:46-49`, 라벨 미사용), 150 µV는 `rgb_pipeline.epoch`의 기본값이기도 해 언제 정했는지는 기록이 없다 | 예 |
| 특징 | ERSP (Morlet 3 cycles, 3–30 Hz, 4대역 × 4구간 0.1–1.5 s, 시행별 기준 정규화) | ERP 창 평균, 로그 밴드파워, xDAWN-TS, 지속 공분산 등 | 예 |
| 분류기 | RBF-SVM (C, γ 격자 nested) | sLDA, LDA(무수축), 로지스틱 회귀, 선형·RBF SVM, MDM, 소프트 보팅, 스태킹 (19개 파이프라인) | 예 |
| 외부 CV | 블록 5-fold (참가자 내) | 참가자 내 모든 세션의 블록을 합쳐 leave-one-block-out (P002 15블록) | 부분 |
| 주지표·보조 | BA / Macro-F1, MCC, 혼동행렬, 95% CI, 참가자 부트스트랩 10,000 | BA만 (CI·Macro-F1·MCC·혼동행렬 없음) | 예 |
| 병합 결정 | v2.0 데이터 병합·P003 결합·반복 세션: 팀 결정 대기 | 모두 병합 | 예 (미결 결정 선행) |

`run_extra.py:12`의 주석 "PRIMARY … pre-specified, theory-driven"과 달리, 해당 파이프라인(ERP O1·O2 + sLDA)은 사전등록 주분석이 아니며 methods.csv에서 19개 중 평균 최고값이다.

## 8. 기존 모델 및 평가 방식

- 19개 파이프라인(`rgb_pipeline.pipelines` 16개 + EA 변형 3개)을 참가자별 leave-one-block-out으로 비교(`run_within.py`). 지표: 외부 fold 예측을 모은 BA.
- 다른 날: 세션 단위 LOGO (P002, P003, P001), 다른 사람: 참가자 단위 LOGO(4명), ± per-session EA (`run_extra.py` A, B).
- gray1 대조: 색이 없는 gray1 구간을 다음 색으로 라벨링(`run_extra.py` C).
- 순열검정: 블록 안에서 **시행 단위** 라벨 셔플, 외부 CV 재실행. 200회(전체), 1,000회(주요 3개) + Bonferroni ×19 (`perm_fine.py`).
- 주요 저장 결과 [사실]: 기준선(ERP 4채널 + sLDA) 평균 33.8%(우연 수준), 최고 평균 ERP O1·O2 + sLDA 39.6%. 참가자별 O1·O2: P002 44.7% (p=0.001, Bonferroni 0.019), P003 39.4% (p=0.038, 보정 후 0.72), P08 36.0% (p=0.28), P001 38.2% (p=0.14). 다른 날 33.3–40.6% (P002·P003, 세션 단위), 다른 사람 31.0–36.2% (4명 LOSO, 시행 합산), gray1 대조 28.6–33.4%.

## 9. 데이터 누수 가능성

| # | 위험 | 판정 | 근거 |
|---|---|---|---|
| L1 | 스케일러·특징선택·xDAWN·튜닝·증강이 테스트 fold를 보는가 | **누수 없음 (확인)** | 모두 Pipeline/estimator 안에서 학습 fold에만 fit (`rgb_pipeline.py:171-235`). [합성] V-03 + V-03c: 색 정보 없는 합성 데이터에서 저장된 19개 파이프라인(각 20회) null 평균 0.331–0.347(1/3 + 3 SE 초과 없음). V-03b: 핵심 ERP 2개 200회 평균 0.334/0.335. 예외(라벨 누수 아님): EA 변형은 테스트 블록을 포함한 세션 전체 공분산 사용(L5), 스태킹 내부 CV 그룹 미지정(L9) |
| L2 | 같은 시퀀스의 obs1/obs2가 학습·검증에 나뉘는가 | 없음 | 블록 단위 그룹 → 같은 시퀀스는 같은 블록 |
| L3 | **반복 세션의 동일 색 순서(쌍둥이 블록)** | **평가 설계 결함 (확인), 실제 영향 UNKNOWN** | 2026-11-24까지의 모든 기록은 세션1 seed(plan_changes.md:55)이고 P003 11-25 run-09도 `--session 1`로 실행(plan_changes.md:75) → P001 2세션, P002 최소 2세션(1111·1124), P003 3기록이 같은 순서. 그룹 = `subj_session_bN`(`build_epochs.py:38`)이라 테스트 블록의 쌍둥이(같은 순서)가 학습에 포함. 세션 간 재현되는 시행 단위 EEG 변화(순서 의존 반응, 순서 학습에 따른 기대)가 있으면 색과 무관한 정보로 색을 맞힐 수 있다. [합성] V-04 B: 매끄러운 시간 경과(VEP 습관화·추세) 메커니즘은 동일 스케줄에서도 BA를 올리지 않았다(동일 스케줄 0.327–0.335). 순서 의존·기대 메커니즘은 미검증. [설계] V-04c: 위치를 정확히 부호화하는 특징이 있으면 저장 CV에서 P001·P003 0.93–1.00까지 가능(상한) |
| L4 | 순열 null의 교환가능성 | **결함 (구조적 사실), 영향 INCONCLUSIVE** | 시행 단위 셔플은 obs1/obs2(같은 색)를 갈라놓고 쌍둥이 블록 간 공유 순서를 재현하지 않는다. [합성] V-04 C: 시행 잡음이 독립인 조건에서 위양성 0/20–2/20 — 20회라 5%와 약 15%를 구분하지 못하고(Clopper–Pearson 상한 17–32%), obs1·obs2 상관을 모델링하지 않았다. 실제 데이터에서의 영향은 UNKNOWN. 사전등록 코드(`train_svm.py:65-71`)는 이미 시퀀스 단위 셔플을 쓴다 |
| L5 | EA 정렬이 테스트 세션 데이터를 사용 | 라벨 누수 아님 (transductive) | 세션 전체 공분산으로 백색화(`apply_ea_per_group`) — 온라인 상황보다 낙관적일 수 있음. 보고 시 표기 필요 |
| L6 | 영위상 필터의 시간 번짐 | 위험 (영향 UNKNOWN) | 녹화 전체 `sosfiltfilt` → 자극 후 반응이 기준 구간(−0.2~0 s)과 직전 gray 구간으로 번짐. 인과성 위반이지만 라벨 누수는 아님. 기준 보정이 색별 반응의 일부를 제거·왜곡할 수 있음 |
| L7 | 모델 선택 편향 | **있음 (확인)** | 19개를 같은 CV로 비교 후 최고값 보고, 독립 검증 없음. V-01 |
| L8 | 불량 임계값 선택 | 라벨 미사용 → 누수 아님 | 150 µV 결정 과정은 기록 없음(유효율 출력 코드와 기본값 150이 함께 있어 결정 순서 불명). 사전등록 기준과 다름 |
| L9 | 스태킹 내부 cv=3 그룹 미지정 | 테스트 누수 아님 | 학습 fold 내부 메타특징만 낙관적 |
| L10 | 색 순서의 이력 의존성 (직전 색 이월, 기대) | **설계상 위험 (확인), EEG 영향 UNKNOWN** | V-04 A: P(현재 = 직전) = 0.206 → 직전 색만으로 BA 상한 39.4%. V-04b: 블록 내 이력(남은 개수 + 연속 제약)으로 51.4%, 블록 마지막 시퀀스는 100% 결정. 분류기는 시행 EEG만 보지만, 참가자의 기대·적응이 EEG에 반영되면 현재 색이 아닌 이력 정보로 맞힐 수 있다. V-04 D: 2 µV 이월 성분만으로는 영향 미미(0.339). 저장된 gray1 대조는 색 직전 구간을 검사하지 않았다 |

## 10. 기존 실험의 문제점 및 미검증 가정

**문제점 [사실]**
1. 저장된 모든 결과가 사전등록에서 이탈한 탐색 분석이며, 사전등록 주분석 결과가 없다.
2. 기준선 4채널 sLDA 평균 33.8%는 우연 수준이다. 19개 파이프라인 간 차이(−3.3 ~ +5.8 %p)는 참가자별 순열 null SD(2.6–5.9 %p, V-01)와 같은 크기다.
3. 유일하게 보정 후 유의한 P002 결과는 무작위화 구조와 맞지 않는 CV·순열검정(L3·L4)에서 나왔다. V-04 시뮬레이션은 이 불일치가 그 자체로 위양성을 만든다는 근거를 주지 않았지만, 이력 의존(L10)·필터 번짐(L6)·선택 편향(L7)을 배제하지 못한 상태다.
4. 불확실성(CI)·Macro-F1·MCC·혼동행렬·Dummy 기준이 보고되지 않았다.
5. 다중비교 보정은 파이프라인 19개만 반영하고 참가자 4명, 추가 분석(EA, 다른 날, 다른 사람)은 반영하지 않았다.
6. 이항 우연 임계값(`controls.csv` chance95)은 실제 순열 null보다 좁다(V-01: 순열 SD가 iid 이항 SD의 1.14–1.29배). 시행 잡음이 독립인 합성 데이터에서도 같은 비율(1.11–1.28배, V-03b)이 나오므로, 이는 시행 의존성보다 CV에서 fold마다 달라지는 모델의 분산 때문이다. 어느 경우든 이항 임계값으로 유의성을 판정하면 안 된다.
7. 재현 불가: 경로가 `/home/claude/...`, `/mnt/user-data/...`로 하드코딩되어 있고, 중간 산출물과 ML 환경 버전 고정이 없다. 커밋된 결과 표 5개(methods, subjects, sessions, controls, generalization)를 쓰는 코드가 없다 — 코드가 쓰는 파일은 `results_within_*.csv`, `results_extra.csv`, `results_perm.csv`, `results_perm_fine.csv`뿐이다(grep 확인). subjects.csv는 1,000회 순열(P002, P003; `perm_fine.py`)과 200회 순열(P08, P001; `run_extra.py`)을 섞었다. 저장된 수치는 원본 없이는 재생성할 수 없다.
8. v2.0(8단계, 상상 2회, 휴식 120 s)과 변경1(6단계, 휴식 30 s) 데이터, Board 3.0.0/3.1.0 데이터를 팀 결정 없이 합쳤다.
9. 계획은 "참가자별 1회 방문"(research_context.md:39)인데 P001·P002·P003은 3–4회 측정되었다. 반복 세션의 분석 사용 방식은 미결정이다(plan_changes.md:56).
10. gray1 대조는 gray 시작 후 0.05–0.5 s(색 시작 2.5–2.95 s 전)만 검사했고, 유지율이 obs보다 크게 낮으며(P002 약 43% vs 99%), 순열검정 없이 이항 임계값으로 판정했다. 색 직전 기대 활동과 작은 효과는 검사하지 못한다.

**미검증 가정**
- `.db` 타임스탬프와 events.csv `onset_lsl`이 같은 LSL 시계이며 지연이 세션 간 일정하다.
- `.db` 시각 정렬이 샘플 순서를 보존한다.
- 명목 sRGB 등휘도가 실제 모니터에서도 성립한다(측광 미실시).
- Fp 채널의 EOG가 색과 무관하다.
- contact == 0이 "접촉 불량"을 뜻한다(`build_epochs.py:40`).
- 피험자가 반복 세션에서 색 순서를 학습·예측하지 않았다.

## 11. 데이터 품질 요약 (저장 수치 기반)

- 유효율이 참가자 간 극단적으로 다르다(P002 98–99% vs P001 22–24%). P001의 낮은 유효율이 4채널 PTP 150 µV 기준 때문인지 접촉 끊김(contact == 0) 때문인지는 제외 사유별 집계가 저장되지 않아 구분할 수 없다. O1·O2만 기준이면 달라질 수 있다(`build_epochs.py:48-49`가 계산했으나 결과는 미저장).
- P003_1120: 탐색 기준 43% vs 사전등록 QC 25%(plan_changes, 주원인 O1 60%·O2 54% 불량).
- ERP 그림(`erp_by_colour.png`) 관찰: P002는 색 무관 onset VEP가 뚜렷하다. P001·P08은 색별 평균이 0 s 부근부터 갈라지며(시행 24–46개/색), 0.1 s 이전 차이는 생리적 VEP로 설명하기 어렵다 — 잡음, 영위상 필터의 번짐, 또는 세션 간 기저선 차이 가능성(해석, 미검증).

## 12. 연구윤리 및 개인정보

- [사실] 저장소 규칙(CLAUDE.md, CHECKLIST.md)은 IRB 승인 확인 전 사람 EEG 기록을 금지한다. 마지막 IRB 상태 기록은 REPORT.md(2026-10-30) "UNVERIFIED → 사람 대상 측정 NO-GO"이다. 저장소 어디에도 IRB 승인 번호·날짜가 없고, 측정은 2026-11-03부터 존재한다. P02(11/03)는 "IRB·착용 미확인 기록" 때문에 제외되었다.
- [사실] `config/CHANGELOG.md`의 2026-11-03 저녁 항목은 "신호 검증(알파·깜빡임)은 **IRB 승인 후** 착용 측정에서 확인 **예정**"이라고 적었다. 같은 날 그보다 이른 시각에 기록된 P01 본측정(정확한 시각은 `build_epochs.py:5`)은 P001_1103으로 분석에 사용되었고, 같은 날 P02는 "IRB·착용 미확인 기록"으로 제외되었다(`rgb-ml-analysis/README.md:22`). 같은 날 기록에 서로 다른 제외 기준이 적용되었다.
- 판정: **위반을 확인한 것이 아니라, 승인 시점과 측정 시점의 관계를 저장소로 확인할 수 없다(UNKNOWN).** CHANGELOG 문구는 오래된 메모일 수도 있다. 추가 분석·외부 공개 전에 팀이 IRB 승인 번호·승인일과 각 측정일(특히 2026-11-03 P01/P02)을 확인해야 한다.
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

### 15.1 검증 실행 요약 (상세: EXPERIMENT_LOG.md)

| ID | 데이터 종류 | 질문 | 핵심 결과 (관찰된 사실) | 판정 |
|---|---|---|---|---|
| V-01 | 실데이터 집계(재생성 불가) | 저장 CSV가 일관되고, 파이프라인 차이가 잡음 이상인가 | 일관성 28/28. 순열 null SD(null95에서 역산) 2.6–5.9 %p. null95 초과 파이프라인: P002 16/19, P003 2/19, P08·P001 0/19. 교차-참가자 선택은 4회 모두 ERP O1·O2 + sLDA, 빠진 참가자 점수 평균 39.6%. Kendall's W 0.41 (p = 0.043, 근사) | 일관성 KEEP / 차이 INCONCLUSIVE |
| V-02 | 설계 계산 | 자극이 등휘도인가 | 명목 sRGB에서 회색 대비 Michelson 대비 ≤ 0.6% (휘도비 차 ≤ 1.2%, G). B의 S-원뿔 대비 +11.1 | KEEP (명목), 물리값 UNKNOWN |
| V-03 + V-03c | 합성 시뮬레이션 | 저장된 19개 파이프라인이 null에서 1/3인가 | 19개 × 20회: null 평균 0.331–0.347, 1/3 + 3 SE 초과 없음 (V-03은 18개였고 V-03c로 보완) | KEEP (누수 증거 없음) |
| V-03b | 합성 시뮬레이션 | 핵심 2개의 null 편향·민감도 | null 0.334 / 0.335 (200회, CI가 1/3 포함). 3 µV 주입 시 0.385 / 0.394 | KEEP |
| V-04 | 설계 계산(A) + 합성 시뮬레이션(B–D) | 스케줄 교란 | 직전 색만으로 BA 상한 0.394. 매끄러운 시간 경과 + 동일 스케줄은 BA 상승 없음. 순열 위양성 0/20–2/20(검정력 부족, obs 쌍 상관 미모델). 2 µV 이월은 영향 미미 | 상한 KEEP / 드리프트 DISCARD / 순열 INCONCLUSIVE / 이월 INCONCLUSIVE |
| V-04b | 설계 계산 | 이력만으로 예측 가능성 | 블록 내 이력 규칙(남은 개수 + 연속 제약) 0.514 — 최적 관찰자는 약 0.52(감사), 블록 마지막 시퀀스 1.000 | KEEP (설계 위험) |
| V-04c | 설계 계산(추론된 세션 구성, 시행 제외 미반영) | 저장 CV에서 위치만 아는 해독기 | 동점 처리 기대값: P001 1.000, P002 1.000(1125 세션1 seed일 때) / 0.578(세션2 seed일 때), P003 0.931, P08 0.333, 서로 다른 seed 대조 0.307 | KEEP (구조적 취약성 상한) |

### 15.2 독립 감사 (상세: AUDIT_FINDINGS.md)

- 5개 영역 감사자 + 영역별 반박 검증자, 총 10개 에이전트(읽기 전용). 감사자에게는 이 보고서의 결론을 주지 않았다.
- 발견 37건: **CONFIRMED 21, PLAUSIBLE 16, REFUTED 0.** 조정 심각도: critical 1, major 17, minor 19.
- 유일한 critical(statistics-01, CONFIRMED): 코드가 "pre-specified"라고 부르는 주 파이프라인은 같은 CV에서 19개 중 최고값이며, 사전등록 ERSP + nested RBF-SVM 분석은 실행되지 않았다.
- 이 보고서의 분석과 독립적으로 같은 결론에 도달한 항목: 쌍둥이 블록과 순열 교환가능성(major, PLAUSIBLE: cv-leakage-01·02, statistics-05), 모델 선택 편향, 사전등록 전면 이탈, P003 결합 방식이 팀 승인 전 결합 제안(plan_changes.md:81-92, 'Claude 제안')과 다름, v2.0 데이터 병합, 결과 CSV 생성 코드 없음, IRB 기록 부재와 11-03 기준 불일치(major, PLAUSIBLE).
- 감사로 새로 추가된 사실:
  - gray1 대조 시행의 유지율이 obs보다 훨씬 낮다(P002: 115개 = 시퀀스당 gray1 1개 가정 시 42.6%, obs 98.7%). 제외 사유는 기록되지 않았다(회색 구간의 깜빡임 집중 가능성). 대조 표본이 선택된 부분집합이다.
  - gray1 대조는 P003·P08 크기의 효과(36–39%)를 검출할 검정력이 없다(n = 87 / 60). 누수 점검 이상의 의미로 해석하면 안 된다.
  - 같은 참가자가 3–4회 측정되었는데, 연구계획은 "참가자별 1회 방문"이다(research_context.md:39). 변경1·변경3의 IRB 변경 신청 확인 항목은 미체크 상태다(plan_changes.md:29, 57).
  - 사전등록 SVM 코드(`train_svm.py:65-71`)는 이미 시퀀스 단위 셔플을 구현했으나 탐색 분석은 시행 단위 셔플을 썼다.
  - 저장소의 기존 파일(`rgb-ml-analysis/README.md`, `rgb-eeg-lab/locks/`, `labrecorder/`, 스트림 참조 JSON)에 실험 PC 호스트명과 Windows 사용자 폴더명이 있고, 가명 ID가 정확한 측정 시각과 연결된다. 외부 공개 전 익명화가 필요하다. (이 보고서들에서는 해당 값을 가렸다. 기존 파일과 git 이력은 수정하지 않았다.)
