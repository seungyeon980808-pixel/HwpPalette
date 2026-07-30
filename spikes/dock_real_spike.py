# -*- coding: utf-8 -*-
r"""**지금 떠 있는 한글**에 실제로 도킹해 보고 무엇이 어긋나는지 잰다.

사용자 화면에서는 "감쌌습니다"라고 뜨는데 판이 하얗게 비어 있었다. 전용
인스턴스로는 잘 됐으므로, 차이는 **선생님 컴퓨터의 실제 상황**에 있다 —
숨은 COM 인스턴스, 왼쪽 모니터(음수 좌표), 배율, z순서 중 하나다.

빈 문서에만 붙는다: 문서에 내용이 있으면 그냥 멈춘다 (남의 원고를 안 건드린다).
끝나면 반드시 뗀다.
"""

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32con
import win32gui
import win32process

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "dock_real.log")

_real_mainloop = tk.Tk.mainloop
tk.Tk.mainloop = lambda self, *a, **k: None
from hwp_palette import app                            # noqa: E402
from hwp_palette.hwp import hwp_engine, engine_library  # noqa: E402
tk.Tk.mainloop = _real_mainloop


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("cp949", "replace").decode("cp949"))
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def rect(h):
    l, t, r, b = win32gui.GetWindowRect(h)
    return f"({l},{t}) {r-l}x{b-t}"


def _topmost(h):
    return bool(win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE)
                & win32con.WS_EX_TOPMOST)


def zpos(*hwnds):
    order = []
    win32gui.EnumWindows(lambda h, _: order.append(h), None)
    return {h: (order.index(h) if h in order else 9999) for h in hwnds}


def shot(name):
    hwnd = win32gui.GetAncestor(app.root.winfo_id(), win32con.GA_ROOT)
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    import win32ui
    w, h = r - l, b - t
    src = win32ui.CreateDCFromHandle(
        win32gui.GetWindowDC(win32gui.GetDesktopWindow()))
    dst = src.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(src, w, h)
    dst.SelectObject(bmp)
    dst.BitBlt((0, 0), (w, h), src, (l, t), win32con.SRCCOPY)
    path = os.path.join(HERE, f"real_{name}.bmp")
    bmp.SaveBitmapFile(dst, path)
    src.DeleteDC()
    dst.DeleteDC()
    win32gui.DeleteObject(bmp.GetHandle())
    log(f"그림: {path}")


def main():
    if not app.ensure_hwp():
        log("✗ 한글 연결 실패")
        return
    if not engine_library.doc_is_empty():
        log("⚠ 지금 문서에 내용이 있다 — 남의 원고는 안 건드린다. 멈춘다.")
        return
    hwnd0 = hwp_engine.connected_hwnd()
    log(f"붙기 전 한글 {rect(hwnd0)} 보임={win32gui.IsWindowVisible(hwnd0)} "
        f"pid={win32process.GetWindowThreadProcessId(hwnd0)[1]}")
    app.messagebox.ask_choice = lambda *a, **k: "keep"

    steps = []
    t0 = time.time()

    def at(s, name, fn):
        steps.append((s, name, fn))

    def look(tag):
        hwnd = hwp_engine.connected_hwnd()
        root_hwnd = win32gui.GetAncestor(app.root.winfo_id(), win32con.GA_ROOT)
        host = app._dock["host"]
        if hwnd is None:
            log(f"{tag}: 한글 창이 사라졌다")
            return
        z = zpos(hwnd, root_hwnd)
        log(f"{tag}: 한글 {rect(hwnd)} 보임={win32gui.IsWindowVisible(hwnd)} "
            f"| 판(GetWindowRect) {rect(host.winfo_id())} "
            f"| 판(Tk) ({host.winfo_rootx()},{host.winfo_rooty()}) "
            f"{host.winfo_width()}x{host.winfo_height()} "
            f"| 우리 창 {rect(root_hwnd)} "
            f"| z: 한글={z[hwnd]} 우리={z[root_hwnd]}"
            f"| topmost: 한글={_topmost(hwnd)} 우리={_topmost(root_hwnd)}"
            f"| 한글 아래 창={win32gui.GetWindow(hwnd, win32con.GW_HWNDNEXT)}"
            f" 우리={root_hwnd}")
        # 판 한가운데를 눌렀을 때 **어느 창이 받는가** — 구멍이 뚫렸는지의 증거.
        hl, ht, hr, hb = win32gui.GetWindowRect(host.winfo_id())
        at = win32gui.WindowFromPoint(((hl + hr) // 2, (ht + hb) // 2))
        owner = win32gui.GetAncestor(at, win32con.GA_ROOT) if at else None
        who = "한글 ✓" if owner == hwnd else ("우리 창 ✗" if owner == root_hwnd
                                              else "제3의 창 ?")
        log(f"   판 가운데의 주인: {owner} {who} "
            f"class={win32gui.GetClassName(owner) if owner else '-'} "
            f"title={win32gui.GetWindowText(owner)[:30] if owner else '-'} "
            f"pid={win32process.GetWindowThreadProcessId(owner)[1] if owner else '-'}")

    at(0.5, "도킹", app.fn_dock_hwp)
    at(2.5, "붙은 뒤", lambda: look("도킹"))
    at(3.0, "우리 창 활성화 (= 선생님이 우리 창을 누른 것)",
       lambda: win32gui.SetForegroundWindow(
           win32gui.GetAncestor(app.root.winfo_id(), win32con.GA_ROOT)))
    at(3.8, "활성화 뒤", lambda: look("활성화 뒤"))
    # 활성화는 윈도우가 막을 수 있다(포그라운드 권한) — 올리는 기능 자체를 직접 시험
    at(4.2, "한글 올리기 직접 호출",
       lambda: app._dock["dock"].raise_above())
    at(4.8, "올린 뒤", lambda: look("올린 뒤"))
    at(5.4, "떼기", app._exit_dock)
    at(6.6, "뗀 뒤", lambda: log(f"뗀 뒤 한글 {rect(hwp_engine.connected_hwnd())}"))
    at(7.6, "끝", app.root.destroy)

    def pump():
        while steps and time.time() - t0 >= steps[0][0]:
            _s, name, fn = steps.pop(0)
            log(f"── {name}")
            try:
                fn()
            except Exception as e:
                log(f"✗ {name} 실패: {e!r}")
        if steps:
            app.root.after(50, pump)

    app.root.after(50, pump)
    app.root.mainloop()


if __name__ == "__main__":
    main()
