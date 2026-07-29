# -*- coding: utf-8 -*-
r"""임베드(SetParent) 스파이크 — 도킹 대신 한글 창을 우리 판 '안에' 넣어 본다.

왜 다시 보나: hwp_dock.py 는 2026-07-27 에 임베드를 **검토만 하고** 버렸다
(입력 큐 결합·부모 소멸·IME). 그 판단은 문서로만 남아 있고 실측이 없다.
이 스파이크는 그 세 가지를 **직접 재보기 위한** 일회용 실험 도구다.
앱 코드는 건드리지 않는다 — spikes/ 는 제품에 포함되지 않는다.

안전: 실행 중인 한글에는 절대 손대지 않는다. DispatchEx 로 **전용 인스턴스**를
새로 띄우고 그 창만 실험한다. 선생님이 열어 둔 문서는 위험하지 않다.

실행:
    python spikes\embed_spike.py

측정하는 것 (버튼 순서대로):
    ① 임베드가 되는가 / 그림이 제대로 그려지는가
    ② 우리 Tk 가 계속 도는가 — 좌상단 '심장박동' 숫자가 멈추면 입력 큐가 묶인 것
    ③ 임베드 상태에서 COM 이 살아 있는가 (글자 넣기·저장)
    ④ 우리 창이 죽으면 한글 창도 같이 죽는가 (자식 창은 부모와 함께 파괴된다)
    ⑤ 해제하면 원래대로 돌아오는가
"""

import os
import sys
import time
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32api
import win32con
import win32gui
import win32process
import win32com.client

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "embed_spike.log")


# ── 한글 창 찾기 ────────────────────────────────────────
def _hwp_windows(pid=None):
    """클래스 이름에 hwp.exe 가 든 최상위 창들. pid 를 주면 그 프로세스만."""
    found = []

    def _cb(hwnd, _):
        try:
            if "hwp.exe" not in win32gui.GetClassName(hwnd).lower():
                return
            if pid is not None:
                _, wpid = win32process.GetWindowThreadProcessId(hwnd)
                if wpid != pid:
                    return
            found.append(hwnd)
        except Exception:
            pass

    win32gui.EnumWindows(_cb, None)
    return found


def _pids():
    out = set()

    def _cb(hwnd, _):
        try:
            if "hwp.exe" in win32gui.GetClassName(hwnd).lower():
                out.add(win32process.GetWindowThreadProcessId(hwnd)[1])
        except Exception:
            pass

    win32gui.EnumWindows(_cb, None)
    return out


class Spike(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("임베드 스파이크 — 한글 창을 판 안에 넣어 본다")
        self.geometry("1180x820")

        self.hwp = None            # 전용 COM 인스턴스
        self.hwnd = None           # 그 인스턴스의 창
        self.pid = None
        self.saved_style = None
        self.saved_ex = None
        self.saved_placement = None
        self.embedded = False
        self.beat = 0

        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        self.beat_lbl = ttk.Label(bar, text="심장박동 0", width=14)
        self.beat_lbl.pack(side="left")
        for text, cmd in (
            ("① 전용 한글 띄우기", self.spawn),
            ("② 임베드", self.embed),
            ("③ COM 검사", self.com_check),
            ("④ 해제", self.release),
            ("⑤ 우리 창 파괴 시험", self.destroy_test),
        ):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=3)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        # 한글이 들어갈 자리 — 도킹에서 _zoom_canvas 가 하던 역할
        self.host = tk.Frame(body, bg="#d0d7de", width=780, height=700)
        self.host.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.host.pack_propagate(False)

        self.log_box = tk.Text(body, width=44, wrap="word",
                               font=("Consolas", 9))
        self.log_box.pack(side="right", fill="y", padx=(0, 6), pady=6)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._tick()
        self.log("준비됨. ①부터 순서대로 누른다.")

    # ── 로그 ────────────────────────────────────────────
    def log(self, msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ── 심장박동 — 우리 이벤트 루프가 도는지 ─────────────
    def _tick(self):
        self.beat += 1
        self.beat_lbl.configure(text=f"심장박동 {self.beat}")
        if self.embedded and self.hwnd:
            self._fit()
        self.after(100, self._tick)

    # ── ① 전용 인스턴스 ─────────────────────────────────
    def spawn(self):
        before = _pids()
        self.hwp = win32com.client.DispatchEx("HWPFrame.HwpObject")
        try:
            self.hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception as e:
            self.log(f"보안모듈 등록 실패(무시): {e}")
        self.hwp.XHwpWindows.Item(0).Visible = True
        for _ in range(40):
            new = _pids() - before
            if new:
                self.pid = next(iter(new))
                wins = _hwp_windows(self.pid)
                if wins:
                    self.hwnd = wins[0]
                    break
            time.sleep(0.1)
        if not self.hwnd:
            self.log("✗ 전용 창을 못 찾았다 (기존 인스턴스에 붙었을 수 있다)")
            return
        self.log(f"✓ 전용 한글 pid={self.pid} hwnd={self.hwnd}")

    # ── ② 임베드 ────────────────────────────────────────
    def embed(self):
        if not self.hwnd:
            self.log("먼저 ①")
            return
        self.saved_placement = win32gui.GetWindowPlacement(self.hwnd)
        self.saved_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_STYLE)
        self.saved_ex = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)

        # 제목줄·테두리를 떼고 자식 창으로 바꾼다
        style = self.saved_style
        style &= ~(win32con.WS_POPUP | win32con.WS_CAPTION
                   | win32con.WS_THICKFRAME | win32con.WS_SYSMENU)
        style |= win32con.WS_CHILD
        win32gui.SetWindowLong(self.hwnd, win32con.GWL_STYLE, style)

        host = self.host.winfo_id()
        try:
            old_parent = win32gui.SetParent(self.hwnd, host)
        except Exception as e:
            self.log(f"✗ SetParent 실패: {e}")
            return
        self.embedded = True
        self._fit()
        parent_now = win32gui.GetParent(self.hwnd)
        self.log(f"✓ SetParent old={old_parent} → host={host} "
                 f"(확인 GetParent={parent_now})")
        self.log("→ 지금 한글에 한글로 타자·한자 변환을 해 볼 것 (IME 시험)")
        self.log("→ 한글에서 파일>열기 같은 대화상자를 띄우고 "
                 "심장박동이 멈추는지 볼 것 (입력 큐 결합 시험)")

    def _fit(self):
        try:
            w = max(self.host.winfo_width(), 100)
            h = max(self.host.winfo_height(), 100)
            l, t, r, b = win32gui.GetWindowRect(self.hwnd)
            if (r - l, b - t) != (w, h):
                win32gui.SetWindowPos(self.hwnd, 0, 0, 0, w, h,
                                      win32con.SWP_NOZORDER
                                      | win32con.SWP_NOACTIVATE)
        except Exception:
            pass

    # ── ③ 임베드 상태에서 COM 이 사는가 ──────────────────
    def com_check(self):
        if not self.hwp:
            self.log("먼저 ①")
            return
        try:
            t0 = time.time()
            self.hwp.HAction.GetDefault("InsertText", self.hwp.HParameterSet.HInsertText.HSet)
            self.hwp.HParameterSet.HInsertText.Text = "임베드 상태 COM 검사 "
            self.hwp.HAction.Execute("InsertText", self.hwp.HParameterSet.HInsertText.HSet)
            self.log(f"✓ COM InsertText 성공 ({time.time() - t0:.2f}s)")
        except Exception as e:
            self.log(f"✗ COM 실패: {e}")

    # ── ④ 해제 ──────────────────────────────────────────
    def release(self):
        if not self.embedded:
            self.log("임베드 상태가 아니다")
            return
        try:
            win32gui.SetParent(self.hwnd, 0)
            win32gui.SetWindowLong(self.hwnd, win32con.GWL_STYLE, self.saved_style)
            win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, self.saved_ex)
            win32gui.SetWindowPlacement(self.hwnd, self.saved_placement)
            win32gui.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                                  | win32con.SWP_NOZORDER
                                  | win32con.SWP_FRAMECHANGED)
            self.embedded = False
            self.log("✓ 해제 — 원래 창으로 돌아왔는지, 그림이 깨지지 않는지 확인")
        except Exception as e:
            self.log(f"✗ 해제 실패: {e}")

    # ── ⑤ 부모가 죽으면 자식도 죽는가 ────────────────────
    def destroy_test(self):
        """host 프레임만 파괴해 본다 (앱 창이 닫히는 상황의 축소판)."""
        if not self.embedded:
            self.log("먼저 ②")
            return
        self.log("host 프레임을 파괴한다 …")
        self.host.destroy()
        self.after(600, self._after_destroy)

    def _after_destroy(self):
        for i in range(10):        # 파괴는 프로세스를 넘어가므로 비동기다
            alive_win = bool(win32gui.IsWindow(self.hwnd))
            alive_proc = self._proc_alive()
            self.log(f"+{0.6 + i * 0.3:.1f}s 창={alive_win} 프로세스={alive_proc}")
            if not alive_proc:
                break
            time.sleep(0.3)
        try:
            self.hwp.HAction.Run("Cancel")
            self.log("COM 아직 응답함")
        except Exception as e:
            self.log(f"COM 죽음: {e}")

    def _proc_alive(self):
        try:
            h = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION,
                                     False, self.pid)
            code = win32process.GetExitCodeProcess(h)
            win32api.CloseHandle(h)
            return code == 259     # STILL_ACTIVE
        except Exception:
            return False

    # ── 정리 ────────────────────────────────────────────
    def on_close(self):
        if self.embedded:
            self.release()
        try:
            if self.hwp:
                self.hwp.Quit()
        except Exception:
            pass
        self.destroy()


def _auto(app):
    r"""사람 손 없이 ①②③⑤④ 를 순서대로 돌린다 (구조적 사실만 잰다).

    IME·대화상자처럼 사람이 봐야 하는 항목은 여기서 못 잰다 — 그건 손으로.
    """
    if "--clean" in sys.argv:      # 정상 경로: 임베드 → 해제 → 종료
        steps = [
            (500, app.spawn),
            (2500, app.embed),
            (1500, app.com_check),
            (1500, app.release),
            (1500, app.com_check),
            (1500, lambda: app.log(
                f"해제 뒤 창 살아있음={bool(win32gui.IsWindow(app.hwnd))} "
                f"프로세스={app._proc_alive()}")),
            (1500, app.on_close),
        ]
    else:
        steps = [
            (500, app.spawn),
            (2500, app.embed),
            (1500, app.com_check),
            (1200, lambda: app.log(f"임베드 중 심장박동={app.beat} "
                                   f"(계속 늘고 있으면 우리 루프는 살아 있다)")),
            (800, app.destroy_test),
            (2500, app.on_close),
        ]
    delay = 0
    for d, fn in steps:
        delay += d
        app.after(delay, fn)


if __name__ == "__main__":
    app = Spike()
    if "--auto" in sys.argv:
        _auto(app)
    app.mainloop()
