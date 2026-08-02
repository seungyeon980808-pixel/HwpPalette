# -*- coding: utf-8 -*-
r"""도킹의 '위계' 실측 — 구멍 없이 되는가, 항상 위와 같이 쓸 수 있는가.

사용자 물음 (2026-08-02):
  ③ "도킹을 할 때 뒷자리가 비는게 좀 신경쓰이는데 저렇게 구멍을 뚫지 않고는
     해결을 할 수 없나? 명확한 위계를 세우면 되는거잖아"
  ④ "도킹 중에는 항상 위가 왜 안먹히는거야"

재 볼 것 — 창 넷을 실제로 띄워 눈이 아니라 좌표·z순서로 판정한다:

  A. 구멍 없이 z 순서만으로 판이 안 가려지는가
     (SetWindowPos 로 한글을 위, 우리를 바로 아래)
  B. 우리 창이 topmost 이면 한글(보통 창)이 그 위에 올 수 있는가
     → 못 오면 그것이 ④의 원인이다
  C. **둘 다 topmost** 로 만들면 순서가 유지되는가
     → 되면 ④는 "한글도 같이 topmost 로" 로 풀린다
  D. 소유자(GWLP_HWNDPARENT)로 진짜 위계를 세우면 순서가 저절로 지켜지는가
     → 되더라도 소유 창은 소유자가 죽을 때 함께 죽는다(원고 위험) — 확인만.

판정 방법: 화면의 그 지점에서 WindowFromPoint 로 **실제로 누가 보이는지**
읽는다. 사람 눈에 의존하지 않는다.

원본은 건드리지 않는다 — 한글 문서는 열지도 만들지도 않는다.
"""

import ctypes
import io
import pathlib
import sys
import tkinter as tk

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import win32con
import win32gui

from hwp_palette.hwp import hwp_engine

OUT = pathlib.Path(__file__).with_suffix(".log")
_lines = []
_user32 = ctypes.windll.user32


def say(*a):
    _lines.append(" ".join(str(x) for x in a))


def who_is_at(x, y):
    """그 점에 실제로 보이는 창의 **뿌리** 핸들."""
    h = _user32.WindowFromPoint(ctypes.wintypes.POINT(int(x), int(y)))
    if not h:
        return 0
    return win32gui.GetAncestor(h, 2)      # GA_ROOT


def name_of(h, ours, hwp):
    if h == ours:
        return "우리 창"
    if h == hwp:
        return "한글"
    if not h:
        return "없음"
    try:
        return f"남의 창({win32gui.GetWindowText(h)[:18]!r})"
    except Exception:
        return f"남의 창({h})"


def order(ours, hwp):
    """z 순서에서 누가 위인가 — 위에서부터 훑어 먼저 나오는 쪽."""
    h = win32gui.GetTopWindow(0)
    seen = []
    while h and len(seen) < 4000:
        if h in (ours, hwp):
            seen.append(h)
            if len(seen) == 2:
                break
        h = win32gui.GetWindow(h, win32con.GW_HWNDNEXT)
    if len(seen) < 2:
        return "판정 불가"
    return "한글이 위" if seen[0] == hwp else "우리가 위"


def main():
    if not hwp_engine.connect():
        say("한글에 연결하지 못했습니다.")
        return
    hwp_engine.ensure_visible()
    hwnd = hwp_engine.connected_hwnd()
    if not hwnd:
        say("한글 창을 찾지 못했습니다.")
        return
    say(f"한글 hwnd={hwnd}")

    # 한글의 원래 자리·순서를 기억했다가 끝에 돌려놓는다
    was_rect = win32gui.GetWindowRect(hwnd)
    was_ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    was_top = bool(was_ex & win32con.WS_EX_TOPMOST)
    say(f"한글 원래 자리={was_rect} topmost={was_top}")

    root = tk.Tk()
    root.title("위계 실측")
    root.geometry("900x620+120+120")
    tk.Label(root, text="도구줄 자리", bg="#dfe6ee").pack(fill="x", ipady=10)
    pane = tk.Frame(root, bg="#ffd0d0")        # 여기에 한글이 들어간다
    pane.pack(fill="both", expand=True)
    root.update()
    ours = win32gui.GetAncestor(pane.winfo_id(), 2)
    say(f"우리 창 hwnd={ours}")

    px, py = pane.winfo_rootx(), pane.winfo_rooty()
    pw, ph = pane.winfo_width(), pane.winfo_height()
    cx, cy = px + pw // 2, py + ph // 2
    say(f"판 자리=({px},{py}) {pw}x{ph} 가운데=({cx},{cy})")

    flags = (win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
    win32gui.SetWindowPos(hwnd, 0, px, py, pw, ph,
                          win32con.SWP_NOZORDER | flags)
    root.update()

    def check(tag):
        root.update()
        h = who_is_at(cx, cy)
        say(f"  {tag}: 판 가운데에 보이는 것 = {name_of(h, ours, hwp=hwnd)}"
            f" · z순서 = {order(ours, hwnd)}")
        return h == hwnd

    # ── A. 구멍 없이 z 순서만 ──
    say("\n[A] 구멍 없이 z 순서만으로")
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
    win32gui.SetWindowPos(ours, hwnd, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
    a1 = check("순서 맞춘 직후")
    # 우리 창을 활성화해 본다 — 예전에 판이 하얘지던 그 동작
    root.focus_force()
    _user32.SetForegroundWindow(ours)
    a2 = check("우리 창을 활성화한 뒤 (여기서 밀리던 것)")

    # ── B. 우리만 topmost ──
    say("\n[B] 우리 창만 '항상 위' 로")
    win32gui.SetWindowPos(ours, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
    b = check("한글을 위로 올려 보려 해도")

    # ── C. 둘 다 topmost ──
    say("\n[C] 한글도 함께 '항상 위' 로")
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
    win32gui.SetWindowPos(ours, hwnd, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
    c1 = check("둘 다 항상 위 + 순서 맞춤")
    _user32.SetForegroundWindow(ours)
    c2 = check("그 상태에서 우리 창을 활성화")

    # ── D. 소유자로 진짜 위계 ──
    say("\n[D] 소유자(GWLP_HWNDPARENT)로 위계 세우기")
    d1 = d2 = None
    try:
        old_owner = _user32.GetWindowLongPtrW(hwnd, -8)   # GWLP_HWNDPARENT
        _user32.SetWindowLongPtrW(hwnd, -8, ours)
        say(f"  소유자 {old_owner} -> {ours}")
        # topmost 를 풀고 순서를 흩어 본 뒤, 저절로 위에 남는지 본다
        win32gui.SetWindowPos(ours, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
        _user32.SetForegroundWindow(ours)
        d1 = check("소유 관계만으로 (순서를 안 맞춰도)")
        win32gui.SetWindowPos(ours, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
        d2 = check("소유 + 우리만 항상 위")
        _user32.SetWindowLongPtrW(hwnd, -8, old_owner)
        say("  소유자 원복")
    except Exception as e:
        say("  소유자 실험 실패:", type(e).__name__, e)

    # ── 원복 ──
    win32gui.SetWindowPos(ours, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
    if not was_top:
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | flags)
    l, t, r, b_ = was_rect
    win32gui.SetWindowPos(hwnd, 0, l, t, r - l, b_ - t,
                          win32con.SWP_NOZORDER | flags)
    say("\n한글 자리·항상위 원복 완료")
    root.destroy()

    say("\n=== 판정 ===")
    say(f"A 구멍 없이 z 순서만: 맞춘 직후={a1} · 우리 창 활성 뒤={a2}"
        "   ← 활성 뒤가 False 면 구멍이 필요한 이유가 그대로 살아 있다")
    say(f"B 우리만 항상 위: 한글이 보이나={b}"
        "   ← False 면 ④(도킹 중 항상 위 금지)의 원인 확정")
    say(f"C 둘 다 항상 위: 맞춤 직후={c1} · 우리 창 활성 뒤={c2}"
        "   ← True 면 ④는 '한글도 같이 올린다'로 풀린다")
    say(f"D 소유자 위계: 순서 안 맞춰도={d1} · 우리만 항상 위={d2}"
        "   ← True 면 위계로 z 순서 폴링이 없어진다(다만 원고 위험은 별도)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        say("예외:", type(e).__name__, e)
        say(traceback.format_exc())
    finally:
        io.open(OUT, "w", encoding="utf-8").write("\n".join(_lines))
        print("done")
