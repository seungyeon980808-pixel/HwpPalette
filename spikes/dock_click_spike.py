# -*- coding: utf-8 -*-
r"""도킹 중 '한글이 클릭·입력을 못 받는' 문제 재현 스파이크 (2026-07-30).

앱 전체를 띄우지 않고 **도킹 기제만** 똑같이 재현한다:
  · Tk 창 하나 (-topmost 켬 — 앱 기본값과 같게)
  · 그 안의 host 프레임
  · hwp_dock.Dock 으로 한글을 그 자리에 끌어옴

그리고 매 초 다음을 찍는다.
  1) 한글 영역 한복판을 클릭하면 **어느 창이 받는가** (WindowFromPoint)
  2) 지금 앞에 있는 창은 무엇인가 (GetForegroundWindow)
  3) 한글 창을 **활성화할 수 있는가** (SetForegroundWindow 시도 후 확인)
  4) 한글이 키보드 초점을 쥐고 있는가 (AttachThreadInput + GetFocus)

실행: python spikes/dock_click_spike.py
"""

import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
import win32api
import win32con
import win32gui
import win32process

from hwp_palette.hwp import hwp_engine, hwp_dock

DOCK_W, DOCK_H = 1180, 900
SECONDS = 20


def desc(h):
    if not h:
        return "None"
    try:
        _, pid = win32process.GetWindowThreadProcessId(h)
        return f"{h}(pid={pid} {win32gui.GetClassName(h)[:28]!r})"
    except Exception:
        return f"{h}(<죽은 핸들>)"


def focus_owner(hwnd):
    """그 창의 스레드가 쥐고 있는 키보드 초점 창 (AttachThreadInput 필요)."""
    try:
        me = win32api.GetCurrentThreadId()
        tid, _ = win32process.GetWindowThreadProcessId(hwnd)
        win32process.AttachThreadInput(me, tid, True)
        try:
            return win32gui.GetFocus()
        finally:
            win32process.AttachThreadInput(me, tid, False)
    except Exception as e:
        return f"<측정 실패: {e}>"


def probe(hwnd, host_hwnd, root_hwnd, n):
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    mid = ((l + r) // 2, (t + b) // 2)
    hit = win32gui.WindowFromPoint(mid)
    root_of_hit = win32gui.GetAncestor(hit, 2) if hit else 0
    who = ("한글" if root_of_hit == hwnd else
           "우리창" if root_of_hit == root_hwnd else f"제3자{desc(root_of_hit)}")
    fg = win32gui.GetForegroundWindow()
    fg_who = ("한글" if fg == hwnd else "우리창" if fg == root_hwnd else desc(fg))
    print(f"[{n:2d}] 한글rect={l},{t},{r},{b}")
    print(f"     한복판{mid} 클릭 → {who}  (실제 {desc(hit)})")
    print(f"     앞에 있는 창 = {fg_who}")
    print(f"     한글이 쥔 키보드 초점 = {desc(focus_owner(hwnd))}")


def main():
    print("한글 연결 중...")
    hwp_engine.connect()
    hwp_engine.new_document()
    hwp_engine.ensure_visible()
    hwnd = hwp_engine.connected_hwnd()
    print("한글 창 =", desc(hwnd))

    root = tk.Tk()
    root.title("도킹 스파이크")
    root.attributes("-topmost", True)          # 앱 기본값과 같게
    spot = hwp_dock.fit_on_screen(root.winfo_id(), DOCK_W, DOCK_H)
    root.geometry(f"{DOCK_W}x{DOCK_H}+{spot[0]}+{spot[1]}" if spot
                  else f"{DOCK_W}x{DOCK_H}")
    tk.Label(root, text="도킹 스파이크 — 이 아래에 한글이 들어옵니다",
             font=("맑은 고딕", 10)).pack(fill="x", pady=6)
    host = tk.Frame(root, bg="#dddddd")
    host.pack(fill="both", expand=True, padx=6, pady=(4, 6))
    root.update_idletasks()

    dock = hwp_dock.Dock(root, host, hwnd)
    if not dock.start():
        print("도킹 실패")
        return

    root_hwnd = root.winfo_id()
    host_hwnd = host.winfo_id()
    print(f"우리창 = {desc(root_hwnd)}  host = {desc(host_hwnd)}\n")

    def worker():
        time.sleep(2.0)                         # 정착 대기
        for n in range(SECONDS):
            try:
                probe(hwnd, host_hwnd, root_hwnd, n)
                if n == 5:
                    print("     ── 활성화 시도(SetForegroundWindow) ──")
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                    except Exception as e:
                        print("     SetForegroundWindow 거절:", e)
                    time.sleep(0.3)
                    print("     시도 후 앞에 있는 창 =",
                          desc(win32gui.GetForegroundWindow()))
            except Exception as e:
                print(f"[{n:2d}] 측정 실패: {e}")
            time.sleep(1.0)
        print("\n정리 중...")
        dock.stop()
        try:
            root.after(0, root.destroy)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()
    root.mainloop()
    print("끝.")


if __name__ == "__main__":
    main()
