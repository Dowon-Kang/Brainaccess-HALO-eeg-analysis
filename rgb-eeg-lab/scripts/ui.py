"""콘솔 출력 모양 — 색, 상태 태그, 한글 폭 맞춤 정렬. 표준 라이브러리만 사용(자극 python·분석 python 공용).

- 화면(콘솔)에 직접 출력할 때만 색을 쓴다. 파이프·파일로 캡처되면 색 코드 없이 글자만 (QC·테스트가 출력을 읽어도 안전).
- NO_COLOR 환경 변수가 있으면 색 끔.
- 태그는 모두 화면 폭 6칸으로 맞춤 → 메시지 시작 위치가 줄마다 같다.
- 숫자 기준값은 여기 없음 (모양만 담당).
"""
import os
import sys
import unicodedata


def _enable_vt():
    if os.name != "nt":
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        return bool(k.SetConsoleMode(h, mode.value | 0x0004))  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        return False


try:
    USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and _enable_vt()
except Exception:
    USE_COLOR = False

_C = dict(red="91", green="92", yellow="93", blue="94", magenta="95", cyan="96", gray="90", bold="1")

# 종류: (화면 폭 6칸 라벨, 색)
TAGS = {
    "ok": ("  OK  ", "green"), "go": ("  GO  ", "green"), "pass": (" PASS ", "green"),
    "nogo": ("NO-GO ", "red"), "fail": (" FAIL ", "red"), "stop": (" 중단 ", "red"), "deny": (" 거부 ", "red"),
    "warn": (" 주의 ", "yellow"), "uv": ("미확인", "yellow"),
    "info": (" 정보 ", "cyan"), "result": (" 결과 ", "cyan"),
    "wait": (" 대기 ", "magenta"), "todo": (" 할일 ", "magenta"), "next": (" 다음 ", "magenta"),
    "skip": (" 생략 ", "gray"), "note": (" 참고 ", "gray"),
}
INDENT = " " * 11  # "  [xxxxxx] " 길이 → 이어지는 줄 들여쓰기
LINE = 64


def c(text, color):
    return f"\033[{_C[color]}m{text}\033[0m" if USE_COLOR else str(text)


def width(s):
    """화면 폭 (한글·전각 2칸)."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(s))


def ljust(s, w):
    return str(s) + " " * max(0, w - width(s))


def rjust(s, w):
    return " " * max(0, w - width(s)) + str(s)


def tag(kind, msg, *more):
    """  [ 라벨 ] 메시지 (+ 들여쓴 추가 줄)."""
    label, col = TAGS[kind]
    print(f"  [{c(label, col)}] {msg}", flush=True)
    for m in more:
        print(INDENT + str(m), flush=True)


def header(title):
    print()
    print(c("=" * LINE, "cyan"))
    print(c(" " + title, "bold"))
    print(c("=" * LINE, "cyan"), flush=True)


def sub(title):
    print("\n" + c(f"-- {title} " + "-" * max(0, LINE - 4 - width(title)), "cyan"), flush=True)


def kv(key, value, kw=14, color=None):
    """정렬된 '항목  값' 한 줄."""
    print("  " + ljust(key, kw) + (c(value, color) if color else str(value)), flush=True)


def verdict_color(v):
    v = str(v)
    if v.startswith(("NO-GO", "FAIL")):
        return "red"
    if v.startswith(("GO", "PASS", "OK")):
        return "green"
    return "yellow"


def fail_exit(msg, *more):
    """[거부] 메시지 출력 후 종료코드 1 (sys.exit(str)과 같은 효과, 모양만 정리)."""
    tag("deny", msg, *more)
    sys.exit(1)
