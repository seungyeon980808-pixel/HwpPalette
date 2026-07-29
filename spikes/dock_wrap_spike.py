# -*- coding: utf-8 -*-
r"""감싸기 도킹을 앱 통째로 돌려 본다 — 들어갔다 나오는 것이 되는지.

전용 한글 인스턴스를 새로 띄워 그 창만 쓴다 (선생님이 열어 둔 문서는 손대지
않는다). `fn_dock_hwp` 대신 `_enter_dock` 을 직접 부르는 이유도 그것이다.

mainloop 을 잠깐 무력화한 채 app 을 import 한다 — app.py 는 import 하는 순간
mainloop 까지 들어간다.
"""

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32com.client
import win32gui
import win32process

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dock_wrap.log")

_real_mainloop = tk.Tk.mainloop
tk.Tk.mainloop = lambda self, *a, **k: None
from hwp_palette import app                        # noqa: E402
tk.Tk.mainloop = _real_mainloop


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
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
            if found:
                return hwp, pid, found[0]
        time.sleep(0.1)
    return hwp, None, None


def rect(h):
    l, t, r, b = win32gui.GetWindowRect(h)
    return f"({l},{t}) {r-l}x{b-t}"


def main():
    root = app.root
    log(f"앱 뜸 — 평소 {root.winfo_width()}x{root.winfo_height()}")

    hwp, pid, hwnd = spawn()
    if not hwnd:
        log("✗ 전용 한글을 못 띄웠다")
        return
    log(f"전용 한글 pid={pid} {rect(hwnd)}")

    steps = []
    t0 = time.time()

    def at(sec, name, fn):
        steps.append((sec, name, fn))

    def compare(tag):
        host = app._dock["host"]
        hl, ht = host.winfo_rootx(), host.winfo_rooty()
        log(f"{tag}: 판 ({hl},{ht}) {host.winfo_width()}x{host.winfo_height()}"
            f" / 한글 {rect(hwnd)}  ← 겹치면 감싼 것")

    at(1.0, "감싸기", lambda: app._enter_dock(hwnd))
    at(3.0, "감싼 뒤", lambda: compare("도킹"))
    at(3.5, "창 옮기기", lambda: root.geometry("+120+80"))
    at(5.0, "옮긴 뒤", lambda: compare("이동"))
    at(6.0, "떼기", lambda: app._exit_dock())
    at(7.0, "뗀 뒤", lambda: log(
        f"평소 복귀: {root.winfo_width()}x{root.winfo_height()} "
        f"자식 {len(root.pack_slaves())}개 / 한글 {rect(hwnd)}"))
    at(8.0, "끝", lambda: (root.destroy(), _quit(hwp)))

    def pump():
        while steps and time.time() - t0 >= steps[0][0]:
            _, name, fn = steps.pop(0)
            log(f"── {name}")
            try:
                fn()
            except Exception as e:
                log(f"✗ {name} 실패: {e!r}")
        if steps:
            root.after(50, pump)

    root.after(50, pump)
    root.mainloop()


def _quit(hwp):
    try:
        hwp.XHwpDocuments.Item(0).Clear(1)
        hwp.Quit()
    except Exception as e:
        log(f"정리 실패(수동으로 닫을 것): {e}")


if __name__ == "__main__":
    main()
