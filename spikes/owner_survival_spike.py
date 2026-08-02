# -*- coding: utf-8 -*-
r"""소유자 위계의 **유일한 위험**을 잰다 — 우리가 죽으면 한글도 죽는가.

앞선 dock_hierarchy_spike 가 알려준 것: 소유자(GWLP_HWNDPARENT)를 세우면
z 순서가 **저절로** 지켜진다(폴링도 구멍도 필요 없다). 사용자 직관이 맞다.

그런데 윈도우 규칙상 **소유 창은 소유자가 파괴될 때 함께 파괴된다.**
그것이 임베드(SetParent)를 버린 이유와 같은 위험이다 — 우리 앱이 강제
종료되면 선생님의 원고가 함께 날아간다.

여기서 재는 것은 딱 하나: **소유자를 세운 채 우리 프로세스를 강제로 죽이면
한글이 살아남는가.** 되돌릴 수 없는 판단이라 눈이 아니라 실측으로 정한다.

한글 문서는 열지도 만들지도 않는다 — 창 관계만 만졌다가 되돌린다.
"""

import ctypes
import io
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import win32gui

OUT = pathlib.Path(__file__).with_suffix(".log")
GWLP_HWNDPARENT = -8
_user32 = ctypes.windll.user32


def _child(hwnd):
    r"""자식 프로세스 — 소유자를 우리 창으로 세운 **뒤 곧바로 강제 종료**한다.

    os._exit 는 정리 코드를 하나도 안 돌린다. 강제 종료(작업 관리자)와
    같은 조건을 만들려는 것이다.
    """
    import tkinter as tk
    root = tk.Tk()
    root.geometry("300x200+50+50")
    root.update()
    ours = win32gui.GetAncestor(root.winfo_id(), 2)
    old = _user32.GetWindowLongPtrW(hwnd, GWLP_HWNDPARENT)
    _user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, ours)
    print(f"소유자 {old} -> {ours}", flush=True)
    time.sleep(0.8)
    os._exit(1)                 # 정리 없이 즉사


def main():
    from hwp_palette.hwp import hwp_engine
    lines = []

    def say(*a):
        lines.append(" ".join(str(x) for x in a))

    if not hwp_engine.connect():
        say("한글에 연결하지 못했습니다.")
        return lines
    hwp_engine.ensure_visible()
    hwnd = hwp_engine.connected_hwnd()
    say(f"한글 hwnd={hwnd} · 살아있음={bool(win32gui.IsWindow(hwnd))}")

    say("\n자식 프로세스가 소유자를 세운 뒤 즉사한다 …")
    p = subprocess.run(
        [sys.executable, __file__, "--child", str(hwnd)],
        capture_output=True, text=True, timeout=60)
    say("  자식 출력:", (p.stdout or "").strip())

    for i in range(6):
        time.sleep(0.5)
        alive = bool(win32gui.IsWindow(hwnd))
        say(f"  +{(i + 1) * 0.5:.1f}s  한글 창 살아있음={alive}")
        if not alive:
            break

    alive = bool(win32gui.IsWindow(hwnd))
    say("\n=== 판정 ===")
    if alive:
        say("한글이 살아남았다 — 소유자를 세운 프로세스가 즉사해도 안전.")
        say("남은 확인: 소유자 값이 죽은 창을 가리킨 채 남지 않는가 (아래).")
        owner = _user32.GetWindowLongPtrW(hwnd, GWLP_HWNDPARENT)
        say(f"  지금 소유자 값={owner} · 그 창이 살아있음="
            f"{bool(win32gui.IsWindow(owner)) if owner else '없음'}")
        if owner and not win32gui.IsWindow(owner):
            say("  ⚠ 죽은 창을 소유자로 물고 있다 — 다음 실행에서 반드시 0 으로 풀어야 한다")
            _user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, 0)
            say("  → 0 으로 풀었다. 다시 읽으니:",
                _user32.GetWindowLongPtrW(hwnd, GWLP_HWNDPARENT))
    else:
        say("한글이 함께 죽었다 — 소유자 위계는 **쓸 수 없다**(원고 위험).")
    return lines


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--child":
        _child(int(sys.argv[2]))
    else:
        out = []
        try:
            out = main()
        except Exception as e:
            import traceback
            out = [f"예외: {type(e).__name__} {e}", traceback.format_exc()]
        io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
        print("done")
