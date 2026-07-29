# -*- coding: utf-8 -*-
r"""양식수정 도킹이 "엉망"이 된 원인을 재본다 — 우리 창을 누르면 판이 회색이 되나.

정체 (2026-07-30): z 를 매 틱 밀어 올리던 것을 그만둔 뒤(클릭 가로채기 때문에
그만둘 수밖에 없었다), 우리 창을 한 번 누르면 **우리 창이 한글 위로** 올라와
판을 덮었다. 도킹은 살아 있는데 화면은 빈 회색 판이니 "엉망"으로 보인다.

여기서 재는 것: 우리 창을 활성화한 뒤에도 한글이 우리 창 **위**에 남아 있는가.
EnumWindows 는 z순서(위→아래)로 돌려주므로 두 창의 순번을 비교하면 된다.
"""

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32con
import win32gui

from hwp_palette.hwp import hwp_dock
from dock_fix_spike import spawn, doc_windows, log       # 전용 한글 띄우기 재사용


def z_order(*hwnds):
    """주어진 창들의 z순번 (작을수록 위)."""
    order = []
    win32gui.EnumWindows(lambda h, _: order.append(h), None)
    return {h: (order.index(h) if h in order else 9999) for h in hwnds}


def main():
    com, pid = spawn()
    if not pid:
        log("✗ 전용 한글을 못 띄웠다")
        return
    hwnd = doc_windows(pid)[0][0]

    root = tk.Tk()
    root.title("z순서 스파이크")
    root.geometry("900x700+120+80")
    host = tk.Frame(root, bg="#dddddd")
    host.pack(fill="both", expand=True, padx=10, pady=10)
    root.update()
    root_hwnd = win32gui.GetAncestor(root.winfo_id(), win32con.GA_ROOT)

    dock = hwp_dock.Dock(root, host, hwnd,
                         crop_top=hwp_dock.caption_height(hwnd))
    log(f"start() → {dock.start()}")

    steps = []
    t0 = time.time()

    def at(sec, name, fn):
        steps.append((sec, name, fn))

    def report(tag):
        z = z_order(hwnd, root_hwnd)
        above = "한글" if z[hwnd] < z[root_hwnd] else "우리 창"
        log(f"{tag}: 한글 z={z[hwnd]} 우리 z={z[root_hwnd]} → **{above}가 위** "
            f"(한글이어야 판이 안 덮인다)")

    at(1.5, "붙은 직후", lambda: report("도킹"))
    at(2.0, "우리 창 활성화 (= 사용자가 우리 창을 누른 것)",
       lambda: win32gui.SetForegroundWindow(root_hwnd))
    at(3.5, "누른 뒤", lambda: report("우리 창 누른 뒤"))
    at(4.0, "한글 활성화", lambda: win32gui.SetForegroundWindow(hwnd))
    at(5.0, "한글 누른 뒤", lambda: report("한글 누른 뒤"))
    at(5.5, "떼기", dock.stop)
    at(6.5, "끝", lambda: (root.destroy(), _quit(com)))

    def pump():
        while steps and time.time() - t0 >= steps[0][0]:
            _s, name, fn = steps.pop(0)
            log(f"── {name}")
            try:
                fn()
            except Exception as e:
                log(f"✗ {name} 실패: {e!r}")
        if steps:
            root.after(50, pump)

    root.after(50, pump)
    root.mainloop()


def _quit(com):
    try:
        com.XHwpDocuments.Item(0).Clear(1)
        com.Quit()
    except Exception as e:
        log(f"정리 실패(수동으로 닫을 것): {e}")


if __name__ == "__main__":
    main()
