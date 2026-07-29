# -*- coding: utf-8 -*-
r"""2026-07-30 손질을 한꺼번에 확인한다 — 화면을 그림으로 떠서 눈으로 본다.

확인 항목 (사용자 지적 순서대로):
  ① 한글 제목줄이 안 보이는가 (hide_caption)
  ② 모드가 '도킹'으로 뜨는가
  ③ 감싼 테두리가 눈에 보이는가 (두께)
  ④ 떼기·방식 단추가 위 도구줄에 있는가
  ⑤ 물감 도구줄이 기본 세 줄인가
  ⑥ **새 문서가 하나만 열리는가** (빈 문서 1 밖에 남던 것)

선생님이 열어 둔 한글에는 손대지 않는다: 전용 인스턴스를 새로 띄워 그것을
hwp_engine 에 끼워 넣고, 앱은 그 인스턴스만 보게 한다.

화면 그림은 spikes/dock_shot_*.png 로 남는다 (화면에서 그대로 떠 오므로
한글이 판 안에 든 모습까지 찍힌다 — PrintWindow 로는 우리 창만 찍혀 안 된다).
"""

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32con
import win32gui
import win32ui
import win32com.client
import win32process

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "dock_fix.log")

_real_mainloop = tk.Tk.mainloop
tk.Tk.mainloop = lambda self, *a, **k: None
from hwp_palette import app                            # noqa: E402
from hwp_palette.hwp import hwp_engine                 # noqa: E402
tk.Tk.mainloop = _real_mainloop


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("cp949", "replace").decode("cp949"))
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


class Shim:
    """pyhwpx 래퍼 흉내 — `.hwp` 로 COM 을, 나머지는 그대로 넘긴다."""

    def __init__(self, com):
        self.hwp = com

    def __getattr__(self, name):
        return getattr(self.hwp, name)

    # pyhwpx 만 가진 편의 메서드 — COM 에는 없다(실측 2026-07-30: 이게 없어
    # doc_is_empty 가 예외를 먹고 '문서 있음'으로 오판, 스파이크가 헛 결과를 냈다)
    def MoveDocBegin(self):
        return self.hwp.HAction.Run("MoveDocBegin")

    def MoveDocEnd(self):
        return self.hwp.HAction.Run("MoveDocEnd")


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


def doc_windows(pid):
    """그 프로세스의 **문서 창**들 (제목이 있는 보이는 최상위 창)."""
    found = []

    def cb(h, _):
        try:
            if ("hwp.exe" in win32gui.GetClassName(h).lower()
                    and win32process.GetWindowThreadProcessId(h)[1] == pid
                    and win32gui.IsWindowVisible(h)
                    and win32gui.GetWindowText(h)):
                found.append((h, win32gui.GetWindowText(h)))
        except Exception:
            pass

    win32gui.EnumWindows(cb, None)
    return found


def spawn():
    before = _pids()
    com = win32com.client.DispatchEx("HWPFrame.HwpObject")
    try:
        com.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception:
        pass
    com.XHwpWindows.Item(0).Visible = True
    for _ in range(50):
        new = _pids() - before
        if new:
            pid = next(iter(new))
            if doc_windows(pid):
                return com, pid
        time.sleep(0.1)
    return com, None


def shot(name):
    """우리 창이 있는 화면 조각을 그대로 떠서 PNG 로 남긴다."""
    hwnd = win32gui.GetAncestor(app.root.winfo_id(), win32con.GA_ROOT)
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    w, h = r - l, b - t
    desk = win32gui.GetDesktopWindow()
    src = win32ui.CreateDCFromHandle(win32gui.GetWindowDC(desk))
    dst = src.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(src, w, h)
    dst.SelectObject(bmp)
    dst.BitBlt((0, 0), (w, h), src, (l, t), win32con.SRCCOPY)
    path = os.path.join(HERE, f"dock_shot_{name}.bmp")
    bmp.SaveBitmapFile(dst, path)
    src.DeleteDC()
    dst.DeleteDC()
    win32gui.DeleteObject(bmp.GetHandle())
    log(f"화면 그림: {path} ({w}x{h})")
    return path


def crop_top(hwnd):
    """창 영역의 위쪽이 얼마나 잘려 있는가 (0 이면 제목줄이 그대로 보인다)."""
    import ctypes
    from ctypes import wintypes
    box = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRgnBox(hwnd, ctypes.byref(box)):
        return 0
    return box.top


def main():
    com, pid = spawn()
    if not pid:
        log("✗ 전용 한글을 못 띄웠다")
        return
    before = doc_windows(pid)
    log(f"전용 한글 pid={pid} 문서창 {len(before)}개: "
        f"{[t for _h, t in before]}")

    hwp_engine.hwp = Shim(com)              # 앱이 이 인스턴스만 보게 한다
    app.ensure_hwp = lambda: True
    app.messagebox.ask_choice = lambda *a, **k: "new"

    steps = []
    t0 = time.time()

    def at(sec, name, fn):
        steps.append((sec, name, fn))

    at(0.5, "도킹 버튼 누르기", app.fn_dock_hwp)
    at(3.0, "확인", lambda: _check(pid))
    at(3.5, "그림 뜨기", lambda: shot("docked"))
    at(4.5, "떼기", app._exit_dock)
    at(6.0, "뗀 뒤 확인", lambda: _after(pid))
    at(7.0, "끝", lambda: (app.root.destroy(), _quit(com)))

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


def _check(pid):
    wins = doc_windows(pid)
    log(f"⑥ 문서창 {len(wins)}개: {[t for _h, t in wins]}  "
        f"(1개여야 한다 — 두 개면 빈 문서가 또 생긴 것)")
    hwnd = hwp_engine.connected_hwnd()
    log(f"① 제목줄 잘라낸 높이: {crop_top(hwnd)}px  (40 안팎이어야 한다)")
    log(f"② 모드: {app._dock['mode']}  (dock 이어야 한다)")
    bar = app._dock["bar"]
    log(f"⑤ 도구줄 높이 {bar.winfo_height()}px "
        f"(칩 26px × 3줄 + 여백이면 100px 안팎)")
    packed = [str(w) for w in app.misc_row.pack_slaves()]
    log(f"④ 위 도구줄 위젯 {len(packed)}개 — 떼기 보임="
        f"{app._undock_btn.winfo_ismapped()} 방식 보임="
        f"{app._mode_btn.winfo_ismapped()}")


def _after(pid):
    hwnd = hwp_engine.connected_hwnd()
    log(f"뗀 뒤 잘라내기 남았나: {crop_top(hwnd) if hwnd else '창 없음'}px"
        f"  (0 이어야 한다)")
    log(f"평소 창 {app.root.winfo_width()}x{app.root.winfo_height()} / "
        f"떼기 보임={app._undock_btn.winfo_ismapped()} (False 여야 한다)")


def _quit(com):
    try:
        com.XHwpDocuments.Item(0).Clear(1)
        com.Quit()
    except Exception as e:
        log(f"정리 실패(수동으로 닫을 것): {e}")


if __name__ == "__main__":
    main()
