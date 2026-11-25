"""config/protocol.json 로더 + 자극·QC가 공유하는 결정적 로직 (seed, 시퀀스 순서, 구간 규칙).

- 키가 '_'로 시작하면 설명용 (검사 대상 아님).
- null 값은 missing()에 잡힌다. 본측정/본분석은 missing()이 비어 있어야 한다.
- 시퀀스 순서는 seed만으로 재생성 가능해야 한다 → QC가 같은 함수로 색 순서를 대조한다.
"""
import json
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(HERE, "..", "config", "protocol.json")
# v2.0 원안 8단계. EXP_START에 phases= 가 없는 기록(스크립트 3.x 이하)은 이 순서로 검사
LEGACY_PHASES = [("gray", 1), ("obs", 1), ("gray", 2), ("obs", 2), ("gray", 3), ("img", 1), ("gray", 4), ("img", 2)]
COLORS = ["R", "G", "B"]
SCRIPT_VERSION = "4.5"  # 4.3 ESC 3번 / 4.4 EEG 끊김 감시 / 4.5(2026-11-24) 세션별 seed(--session)


def load(path=None):
    with open(path or DEFAULT_PATH, encoding="utf-8") as f:
        return json.load(f)


def _walk(d, prefix=""):
    for k, v in d.items():
        if k.startswith("_"):
            continue
        p = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            yield from _walk(v, p)
        else:
            yield p, v


def missing(cfg, sections=None):
    return [p for p, v in _walk(cfg) if v is None and (not sections or p.split(".")[0] in sections)]


# ------------------------------------------------------------------ 시퀀스 단계
def phases(cfg):
    """config.design.phases ["gray","obs",...] → [("gray",1),("obs",1),("gray",2),...] (단계별 순번 자동)."""
    seen, out = {}, []
    for p in cfg["design"]["phases"]:
        seen[p] = seen.get(p, 0) + 1
        out.append((p, seen[p]))
    return out


def phases_tag(ph):
    """[("gray",1),...] → "gray1,obs1,..." (EXP_START·JSON 기록용)."""
    return ",".join(f"{p}{r}" for p, r in ph)


def parse_phases_tag(s):
    """phases_tag의 역. None/빈 값이면 LEGACY_PHASES (구버전 기록)."""
    if not s:
        return list(LEGACY_PHASES)
    return [(m.group(1), int(m.group(2))) for m in (re.fullmatch(r"([a-z]+)(\d+)", x) for x in s.split(","))]


# ------------------------------------------------------------------ seed / 순서
def participant_number(pid):
    m = re.search(r"(\d+)$", pid)
    if not m:
        raise ValueError(f"참가자 ID는 숫자로 끝나야 함 (예: P03): {pid!r}")
    return int(m.group(1))


def seed_for(cfg, pid, practice, session=1):
    """seed = base + 참가자 번호 + session_offset × (session − 1) [+ practice_offset].
    session 1은 변경3(2026-11-24) 이전 seed와 같음 → 기존 기록과 호환."""
    session = int(session)
    if session < 1:
        raise ValueError(f"세션 번호는 1 이상: {session}")
    n = participant_number(pid)
    off = cfg["seed"].get("session_offset", 0)
    if session > 1 and n >= off:
        raise ValueError(f"참가자 번호 {n} ≥ session_offset {off} → seed 겹침 위험")
    if off * (session - 1) >= cfg["seed"]["practice_offset"]:
        raise ValueError(f"세션 {session}이 너무 큼 → 연습 seed 범위와 겹침")
    s = cfg["seed"]["base"] + n + off * (session - 1)
    return s + cfg["seed"]["practice_offset"] if practice else s


def _max_run(seq):
    best = run = 1
    for x, y in zip(seq, seq[1:]):
        run = run + 1 if x == y else 1
        best = max(best, run)
    return best


def sequence_plan(seed, blocks, per_color, max_run):
    """[(block, color), ...] 전체 시퀀스 순서. 자극과 QC가 같은 함수를 쓴다."""
    rng = random.Random(seed)
    plan = []
    for b in range(1, blocks + 1):
        base = [c for c in COLORS for _ in range(per_color)]
        for _ in range(10000):
            order = base[:]
            rng.shuffle(order)
            if _max_run(order) <= max_run:
                break
        else:
            raise RuntimeError("max_same_color_run 제약 불만족")
        plan += [(b, c) for c in order]
    return plan


# ------------------------------------------------------------------ 마커 시각
def flip_to_lsl(lsl_now, ps_now, flip_t, frame_dur):
    """flip 시각(PsychoPy 시계)을 LSL 시계로 환산.

    flip 직후 두 시계를 연달아 읽어(lsl_now, ps_now) 'flip → 지금' 경과(delay = ps_now − flip_t)를 빼면
    마커 타임스탬프 = 화면 버퍼 교체(vsync) 시각이 된다. push가 늦어져도 타임스탬프는 flip 시각에 고정.
    delay가 음수이거나 1프레임보다 크면 두 시계가 다른 기준이라는 뜻 → 보정하지 않고 lsl_now 사용(ok=False).
    한계: 모니터 자체의 입력 지연(scanout·패널 응답)은 포함되지 않음 → 포토다이오드로만 측정 가능.
    """
    if flip_t is None:
        return lsl_now, None, False
    delay = ps_now - flip_t
    if not (0.0 <= delay <= frame_dur):
        return lsl_now, None, False
    return lsl_now - delay, delay, True


# ------------------------------------------------------------------ 구간 규칙
def bin_masks(values, edges):
    """edges [[lo,hi],...] → 마스크 리스트. [lo,hi) 반열린, 마지막만 [lo,hi]."""
    out = []
    for i, (lo, hi) in enumerate(edges):
        last = i == len(edges) - 1
        out.append((values >= lo) & ((values <= hi) if last else (values < hi)))
    return out
