# config 변경 기록 (현장 실측값)

| 일시 | 항목 | 이전 | 새 값 | 근거 | 입력자 |
|---|---|---|---|---|---|
| 2026-10-30 17:37 | monitor.width_cm | None | 70.8 | 줄자 실측, 표시 영역 가로 70.8cm (세로 39.8cm) | 운영자 |
| 2026-10-30 17:37 | monitor.resolution_px | None | [1920, 1080] | Windows 감지(배율 100%), 실측 가로/세로 70.8/39.8=1.779 ≈ 16:9 일치 | 운영자 |
| 2026-11-03 21:02 | eeg.raw_unit | None | uV | 1) LSL/XDF 채널 메타데이터 unit=microvolts (BA HALO 114, Fp1/Fp2/O1/O2; sub-T00_ses-systemtest_run-10.xdf) 2) BrainAccess Board utils.py _get_units_conversion: microvolts=1e-6 V. MAN-HALO-01 p14에는 출력 단위 미기재. 신호 검증(알파·깜빡임)은 IRB 승인 후 착용 측정에서 확인 예정 | Claude(사용자 지시) |
| 2026-11-13 | design.phases (신규) | v2.0 8단계 gray obs gray obs gray img gray img (코드 고정) | ["gray","obs","gray","img"] → 같은 날 ["gray","obs","gray","obs","gray","img"]로 재수정(관찰 2회 유지, 상상만 1회) | 설계 변경1: 본측정 44분 → 29분. 집중도 저하로 양질의 데이터 측정 곤란 (운영자 판단). 상세 docs/plan_changes.md | Claude(사용자 지시) |
| 2026-11-13 | design.rest_sec | 120 | 30 | 설계 변경1 (위와 같음) | Claude(사용자 지시) |
| 2026-11-13 | plan_version | 2026-10-26 v2.0 | 2026-10-26 v2.0 + 변경1(2026-11-13) | 설계 변경1 표시 (EXP_START·특징 파일에 기록됨) | Claude(사용자 지시) |
| 2026-11-24 | seed.session_offset (신규) | 없음 (seed = base + 참가자 번호) | 1000 → seed = base + 참가자 번호 + 1000×(세션−1) | 변경3: 같은 참가자 반복 세션마다 다른 색 순서. 세션 1 = 기존 seed. 상세 docs/plan_changes.md | Claude(사용자 지시) |
| 2026-11-21 | qc.precheck_min_battery_pct (신규) | 없음 | 50.0 | 운영 기준, **Claude 제안값(사용자 확인 필요)**. 실측 소모 0.30–0.37%p/분(run-010·05·08) → 본측정+점검 약 13%p. P003 run-08: 25%→21%에서 EEG 끊김(원인 미확정). 분석 파라미터 아님 | Claude(사용자 지시) |
| 2026-11-21 | qc.precheck_min_valid_pct (신규) | 없음 | 70.0 | 운영 기준(변경2): 시작 전 착용 신호 점검 하한. P003 2026-11-20 본측정 관찰 시행 75% 제외(유효 45/180, 주원인 O1·O2)로 도입. SVM 결과 보기 전 결정. 분석 제외 기준 아님. 상세 docs/plan_changes.md | Claude(사용자 지시) |
