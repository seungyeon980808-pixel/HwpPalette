# -*- coding: utf-8 -*-
r"""앱 통째로 도킹 모드에 넣었다 빼 본다 — 화면 전환이 되돌아오는지가 핵심.

`fn_dock_hwp` 대신 `_enter_dock` 을 직접 부른다: 앞의 것은 **실행 중인 한글**에
붙어 새 문서를 만드는데, 그러면 선생님이 열어 둔 문서를 건드리게 된다.
여기서는 전용 인스턴스를 새로 띄워 그 창 핸들만 넘긴다.

mainloop 을 잠깐 무력화한 채 app 을 import 해서, 창이 다 만들어진 뒤 우리가
직접 순서를 돌린다 (app.py 는 import 하는 순간 mainloop 까지 들어간다).
"""

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32gui

from side_dock_spike import spawn, log, rect          # 전용 한글 띄우기 재사용

_real_mainloop = tk.Tk.mainloop
tk.Tk.mainloop = lambda self, *a, **k: None           # import 가 여기서 멈추지 않게
from hwp_palette import app                            # noqa: E402
tk.Tk.mainloop = _real_mainloop


def main():
    root = app.root
    log(f"앱 뜸 — 도킹 버튼 있음={app._dock_btn is not None} "
        f"평소 크기 {root.winfo_width()}x{root.winfo_height()}")
    log("도킹 전 자식: " + ", ".join(str(w) for w in root.pack_slaves()))

    hwp, pid, hwnd = spawn()
    if not hwnd:
        log("✗ 전용 한글을 못 띄웠다")
        return
    log(f"전용 한글 pid={pid} {rect(hwnd)}")

    steps = []

    def at(sec, name, fn):
        steps.append((sec, name, fn))

    def show(tag):
        h = app.side_dock.top_hwnd(root.winfo_id())
        log(f"{tag}: 한글 {rect(hwnd)} / 띠 {rect(h)} "
            f"| 창틀없음={bool(root.overrideredirect())}")

    at(1.0, "도킹 시작", lambda: app._enter_dock(hwnd))
    at(2.0, "붙은 뒤", lambda: show("도킹"))
    at(3.0, "띠에서 최대화", lambda: app._dock["eng"].maximize())
    at(4.0, "최대화 뒤", lambda: show("최대화"))
    at(5.0, "떼기", lambda: app._exit_dock())
    at(6.0, "뗀 뒤", lambda: log(
        f"평소 복귀: 창 {root.winfo_width()}x{root.winfo_height()} "
        f"창틀없음={bool(root.overrideredirect())} "
        f"자식 {len(root.pack_slaves())}개 / 한글 {rect(hwnd)}"))
    at(6.2, "자식 목록", lambda: log(
        "뗀 뒤 자식: " + ", ".join(str(w) for w in root.pack_slaves())))
    at(7.0, "끝", lambda: (root.destroy(), _quit(hwp)))

    t0 = time.time()

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
