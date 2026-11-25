#!/usr/bin/env python3
"""사전분석계획 주분석: StandardScaler + RBF SVM, 블록 단위 중첩 교차검증.

데이터 흐름
  입력 : xdf_qc.py가 만든 features_obs.npz (참가자당 1개). 파일명 앞 토큰 또는 --ids로 참가자 ID.
  처리 :
    1) 불량 시행 제외 (bad 마스크, 2ch·4ch 공통 → 동일 유효 시행 비교)
    2) 참가자 내: 외부 = 블록 Leave-One-Block-Out(5블록 → 5-fold)
                  내부 = 남은 4블록에서 Leave-One-Block-Out GridSearch (C × gamma, balanced accuracy)
       Scaler는 Pipeline 안 → fold별 학습 데이터로만 fit. 같은 시퀀스의 시행(구설계 obs1/obs2)은 같은 블록이라 분리 안 됨.
    3) 지표: Balanced Accuracy(주), Macro-F1, MCC, Confusion Matrix (외부 fold 예측 합산)
    4) 누수 점검: 시퀀스 단위로 라벨을 섞은 데이터에 같은 절차 → BA ≈ 0.333 이어야 함
    5) 집단: 참가자별 BA의 평균 + 참가자 단위 부트스트랩 95% CI (n_boot), 우연 0.333 비교
    6) LOSO: 유효 참가자 ≥ loso_min_subjects 일 때만 (탐색적), 내부 CV는 참가자 그룹
  출력 : results/svm_<시각>/summary.txt, per_subject.csv, confusion_<id>_<ch>.csv

  PROVISIONAL 특징 파일은 --dry-run 없이는 거부 (계획서 값이 아닌 특징으로 결과를 만들지 않기 위함).

예
  python scripts/train_svm.py data/qc_*/features_obs.npz --ids P01 P02 P03
  python scripts/train_svm.py tests/out/features_obs_PROVISIONAL.npz --dry-run --shuffle-check
"""
import argparse
import csv
import os
import sys
from datetime import datetime

import numpy as np
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, matthews_corrcoef
from sklearn.model_selection import GridSearchCV, LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol  # noqa: E402


def make_search(svm_cfg, n_jobs):
    pipe = make_pipeline(StandardScaler(), SVC(kernel="rbf", class_weight=svm_cfg["class_weight"]))
    grid = {"svc__C": svm_cfg["C"], "svc__gamma": svm_cfg["gamma"]}
    return GridSearchCV(pipe, grid, cv=LeaveOneGroupOut(), scoring="balanced_accuracy",
                        n_jobs=n_jobs, error_score="raise")


def nested_cv(X, y, groups, svm_cfg, n_jobs=1):
    """외부 LOGO(groups) + 내부 LOGO(학습 groups). 반환 y_pred(외부 합산), 선택된 파라미터 목록."""
    y_pred = np.empty_like(y)
    chosen = []
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        assert not set(groups[tr]) & set(groups[te]), "누수: 학습/평가 그룹 중복"
        gs = make_search(svm_cfg, n_jobs)
        gs.fit(X[tr], y[tr], groups=groups[tr])
        y_pred[te] = gs.predict(X[te])
        chosen.append(gs.best_params_)
    return y_pred, chosen


def metrics(y, yp):
    return dict(ba=balanced_accuracy_score(y, yp), f1=f1_score(y, yp, average="macro"),
                mcc=matthews_corrcoef(y, yp), cm=confusion_matrix(y, yp, labels=[0, 1, 2]))


def shuffle_by_sequence(y, seq, rng):
    """같은 시퀀스의 시행은 같은 라벨 유지한 채 시퀀스 단위로 라벨 섞기."""
    useq = np.unique(seq)
    lab = {s: y[seq == s][0] for s in useq}
    perm = rng.permutation([lab[s] for s in useq])
    m = dict(zip(useq, perm))
    return np.array([m[s] for s in seq])


def bootstrap_ci(vals, n_boot, rng):
    vals = np.asarray(vals)
    if len(vals) < 2:
        return (np.nan, np.nan)
    bs = rng.choice(vals, size=(n_boot, len(vals)), replace=True).mean(axis=1)
    return tuple(np.percentile(bs, [2.5, 97.5]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("npz", nargs="+")
    ap.add_argument("--ids", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true", help="PROVISIONAL 특징 허용 (결과 보고 금지)")
    ap.add_argument("--shuffle-check", action="store_true", help="시퀀스 단위 라벨 셔플 누수 점검")
    ap.add_argument("--min-blocks", type=int, default=None, help="기본: config design.blocks")
    ap.add_argument("--n-jobs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = protocol.load(a.config)
    sv = cfg["svm"]
    rng = np.random.default_rng(a.seed)
    min_blocks = a.min_blocks or cfg["design"]["blocks"]
    ids = a.ids or [os.path.basename(os.path.dirname(os.path.abspath(p))) for p in a.npz]
    if len(ids) != len(a.npz) or len(set(ids)) != len(ids):
        sys.exit("[거부] --ids 개수/중복 확인")

    for path in a.npz:                                    # 입력 검증을 출력 폴더 생성보다 먼저
        with np.load(path, allow_pickle=False) as d0:
            if bool(d0["provisional"]) and not a.dry_run:
                sys.exit(f"[거부] {path} 는 PROVISIONAL 특징 — 단위·계획서 값 확정 후 xdf_qc 재실행, 또는 --dry-run")
    out = os.path.join(a.outdir, f"svm_{datetime.now():%Y%m%d_%H%M%S}{'_DRYRUN' if a.dry_run else ''}")
    os.makedirs(out, exist_ok=True)
    lines = [f"plan_version={cfg['plan_version']}  dry_run={a.dry_run}  seed={a.seed}",
             "주지표 Balanced Accuracy, 우연 수준 0.333", ""]
    per = []
    subj_data = {}
    for sid, path in zip(ids, a.npz):
        d = np.load(path, allow_pickle=False)
        keep = ~d["bad"]
        if keep.sum() == 0:
            lines.append(f"[{sid}] 유효 시행 0 → 제외")
            continue
        y, blk, seq = d["y"][keep], d["block"][keep], d["seq"][keep]
        nb = len(np.unique(blk))
        if nb < min_blocks:
            lines.append(f"[{sid}] 유효 블록 {nb} < {min_blocks} → 참가자 내 주분석 제외")
            continue
        for ch in ("X2", "X4"):
            X = d[ch][keep]
            yp, chosen = nested_cv(X, y, blk, sv, a.n_jobs)
            m = metrics(y, yp)
            row = dict(id=sid, ch=ch, n=len(y), blocks=nb, ba=m["ba"], f1=m["f1"], mcc=m["mcc"],
                       params=";".join(f"C={c['svc__C']},g={c['svc__gamma']}" for c in chosen))
            if a.shuffle_check:
                ys = shuffle_by_sequence(y, seq, rng)
                yps, _ = nested_cv(X, ys, blk, sv, a.n_jobs)
                row["ba_shuffled"] = balanced_accuracy_score(ys, yps)
            per.append(row)
            np.savetxt(os.path.join(out, f"confusion_{sid}_{ch}.csv"), m["cm"], fmt="%d", delimiter=",",
                       header="rows=true R,G,B; cols=pred R,G,B")
        subj_data[sid] = (d, keep)

    with open(os.path.join(out, "per_subject.csv"), "w", newline="", encoding="utf-8") as fh:
        if per:
            w = csv.DictWriter(fh, fieldnames=list(per[0].keys())); w.writeheader(); w.writerows(per)

    for ch in ("X2", "X4"):
        rows = [r for r in per if r["ch"] == ch]
        if not rows:
            continue
        lines.append(f"== 참가자 내 ({'O1/O2' if ch == 'X2' else 'Fp1/Fp2/O1/O2'}) ==")
        for r in rows:
            sh = f"  셔플BA {r['ba_shuffled']:.3f}" if "ba_shuffled" in r else ""
            lines.append(f"{r['id']}: n={r['n']} BA {r['ba']:.3f}  F1 {r['f1']:.3f}  MCC {r['mcc']:.3f}{sh}")
        bas = [r["ba"] for r in rows]
        lo, hi = bootstrap_ci(bas, sv["n_boot"], rng)
        lines.append(f"집단 평균 BA {np.mean(bas):.3f}, 참가자 부트스트랩 95% CI "
                     f"{'n<2 계산 불가' if np.isnan(lo) else f'[{lo:.3f}, {hi:.3f}]'} (우연 {sv['chance_ba']})")
        if a.shuffle_check:
            sb = [r["ba_shuffled"] for r in rows]
            lines.append(f"누수 점검: 셔플 BA 평균 {np.mean(sb):.3f} (≈0.333이어야 함; 크게 높으면 누수 의심)")
        lines.append("")

    if len(subj_data) >= sv["loso_min_subjects"]:
        lines.append("== LOSO (탐색적) ==")
        for ch in ("X2", "X4"):
            Xs, ys, gs = [], [], []
            for sid, (d, keep) in subj_data.items():
                Xs.append(d[ch][keep]); ys.append(d["y"][keep]); gs += [sid] * int(keep.sum())
            X, y, g = np.vstack(Xs), np.concatenate(ys), np.array(gs)
            yp, _ = nested_cv(X, y, g, sv, a.n_jobs)
            per_s = [balanced_accuracy_score(y[g == s], yp[g == s]) for s in subj_data]
            lo, hi = bootstrap_ci(per_s, sv["n_boot"], rng)
            lines.append(f"{ch}: 참가자별 BA {np.round(per_s, 3).tolist()}, 평균 {np.mean(per_s):.3f}, CI [{lo:.3f}, {hi:.3f}]")
    else:
        lines.append(f"LOSO 생략: 유효 참가자 {len(subj_data)} < {sv['loso_min_subjects']}")
    if a.dry_run:
        lines.append("\n⚠️ DRY-RUN: 파이프라인 작동 확인용. 이 수치는 보고하지 않는다.")

    txt = "\n".join(lines)
    with open(os.path.join(out, "summary.txt"), "w", encoding="utf-8") as fh:
        fh.write(txt + "\n")
    print(txt)
    print(f"\n[결과] {out}")


if __name__ == "__main__":
    main()
