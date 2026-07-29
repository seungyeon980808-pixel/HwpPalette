# -*- coding: utf-8 -*-
r"""세로 띠 도킹 실측 — app.py 없이 SideDock + DockStrip 만 돌려 본다.

전용 한글 인스턴스를 새로 띄워 실험한다 (열어 둔 문서는 건드리지 않는다).
`--auto` 를 주면 붙기 → 최대화 → 최소화 → 복귀 → 떼기를 스스로 밟고
각 단계의 창 좌표를 찍는다. 사람이 볼 것은 '띠와 한글이 한 창처럼 붙어 있나'뿐.
"""

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32com.client
import win32con
import win32gui
import win32process

from hwp_palette.hwp import side_dock
from hwp_palette.ui import dock_strip
from hwp_palette.design import theme
from hwp_palette.model import palette

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "side_dock.log")


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    try:
        print(line)
    except UnicodeEncodeError:      # cp949 콘솔 — 로그 파일에는 그대로 남는다
        print(line.encode("cp949", "replace").decode("cp949"))
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _pids():
    out = set()

    def cb(h, _):
        try:
            if "hwp.exe" in win32gui.GetClassName(h).lower():
                out.add(win32process.GetWindowThreadProcessId(h)[1])
        except Exception:
            pass

    win32gui.EnumWindows(cb, None)
    return out


def _hwnd_of(pid):
    found = []

    def cb(h, _):
        try:
            if ("hwp.exe" in win32gui.GetClassName(h).lower()
                    and win32process.GetWindowThreadProcessId(h)[1] == pid
                    and win32gui.IsWindowVisible(h)
                    and win32gui.GetWindowText(h)):
                found.append(h)
        except Exception:
            pass

    win32gui.EnumWindows(cb, None)
    return found[0] if found else None


def spawn():
    before = _pids()
    hwp = win32com.client.DispatchEx("HWPFrame.HwpObject")
    try:
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception:
        pass
    hwp.XHwpWindows.Item(0).Visible = True
    for _ in range(50):
        new = _pids() - before
        if new:
            pid = next(iter(new))
            h = _hwnd_of(pid)
            if h:
                return hwp, pid, h
        time.sleep(0.1)
    return hwp, None, None


def rect(h):
    l, t, r, b = win32gui.GetWindowRect(h)
    return f"({l},{t}) {r-l}x{b-t}"


def main():
    hwp, pid, hwnd = spawn()
    if not hwnd:
        log("✗ 전용 한글 창을 못 찾았다")
        return
    log(f"✓ 전용 한글 pid={pid} hwnd={hwnd} {rect(hwnd)}")

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    w = dock_strip.strip_width(1.0)
    root.geometry(f"{w}x600")
    strip = dock_strip.DockStrip(
        root, scale=1.0, font_fn=lambda n: (theme.FONT, theme.fs(n)),
        run_block=lambda b: log(f"블럭 눌림: {b.get('name')}"),
        label_fn=lambda b: b.get("name", "?"),
        block_color_fn=theme.block_color,
        tabs_fn=palette.load_tabs, tab_index_fn=lambda: 0,
        on_pick_tab=lambda i: None,
        on_undock=lambda: log("떼기 눌림"),
        on_minimize=lambda: eng.minimize(),
        on_maximize=lambda: eng.maximize())
    strip.pack(fill="both", expand=True)
    root.update()

    eng = side_dock.SideDock(side_dock.top_hwnd(root.winfo_id()), hwnd, w)
    log(f"start() → {eng.start()}")

    steps = []

    def tick():
        st = eng.tick()
        if steps and time.time() >= steps[0][0]:
            _, name, fn = steps.pop(0)
            log(f"── {name}")
            fn()
        if steps:
            root.after(40, tick)
        else:
            root.after(40, tick)

    def show(tag):
        log(f"{tag}: 한글 {rect(hwnd)} / 띠 "
            f"{rect(side_dock.top_hwnd(root.winfo_id()))} "
            f"(같은 높이·맞닿음이면 성공)")

    now = time.time()
    steps.extend([
        (now + 1.0, "붙은 직후", lambda: show("도킹")),
        (now + 2.0, "최대화", lambda: (eng.maximize(), root.after(400, lambda: show("최대화")))),
        (now + 4.0, "최소화", lambda: (eng.minimize(), root.after(400, lambda: log(
            f"최소화: IsIconic={win32gui.IsIconic(hwnd)} tick={eng.tick()}")))),
        (now + 6.0, "복귀", lambda: (eng.restore_hwp(), root.after(400, lambda: show("복귀")))),
        (now + 8.5, "떼기", lambda: (eng.stop(), root.after(400, lambda: (
            show("해제 후"), root.destroy(), _quit(hwp))))),
    ])
    root.after(200, tick)
    root.mainloop()


def _quit(hwp):
    try:
        hwp.XHwpDocuments.Item(0).Clear(1)      # 저장 묻지 않게 비운다
        hwp.Quit()
    except Exception as e:
        log(f"정리 실패(수동으로 닫을 것): {e}")


if __name__ == "__main__":
    main()
