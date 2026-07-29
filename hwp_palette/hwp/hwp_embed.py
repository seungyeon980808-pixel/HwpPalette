# -*- coding: utf-8 -*-
r"""한글 창 임베드(SetParent) — 한글을 우리 판 **안에** 넣는다 (2026-07-30).

도킹(`hwp_dock.py`)과 같은 자리를 노리지만 방식이 다르다.

    도킹  = 남남인 두 창. 우리가 매 틱 좌표를 재서 한글을 끌고 다닌다.
    임베드 = 한글 창을 우리 프레임의 **자식 창**으로 만든다. 창 하나가 된다.

임베드는 따라다닐 필요가 없다 — 부모가 움직이면 자식은 윈도우가 공짜로
같이 옮겨 준다. 그래서 버벅임·짤림이 원리적으로 없다. 대신 **부모가 죽으면
자식도 파괴된다**는 윈도우 규칙을 그대로 뒤집어쓴다 (실측은
`docs/EMBED_검토.md`). 그래서 이 모듈은 떼어내기(detach)를 집요하게 건다:

    · 정상 해제 — `stop()`
    · 앱이 예외로 죽거나 인터프리터가 내려갈 때 — `atexit`
    · 호출부가 stop 을 잊고 판을 destroy 하려 할 때 — `<Destroy>` 바인딩

이 셋으로도 못 막는 것이 하나 있다: **작업관리자 강제 종료**(`taskkill /F`).
그때는 우리 코드가 한 줄도 못 돌아 한글 문서 창이 사라지고 프로세스만 유령으로
남는다. 임베드를 쓰기로 한다면 그 위험을 아는 채로 쓰는 것이다.
"""

import atexit

import win32con
import win32gui

from hwp_palette.core import applog

# 살아 있는 임베드들. 인터프리터가 내려갈 때 전부 떼어낸다.
_LIVE = set()

_STRIP = (win32con.WS_POPUP | win32con.WS_CAPTION | win32con.WS_THICKFRAME
          | win32con.WS_SYSMENU | win32con.WS_MINIMIZEBOX
          | win32con.WS_MAXIMIZEBOX)


@atexit.register
def _detach_all():
    """인터프리터가 내려갈 때 남은 임베드를 전부 떼어낸다.

    창이 파괴되기 전에 부모를 끊어야 한글이 살아남는다. 예외로 죽는 경로도
    파이썬이 정상적으로 내려가는 한 여기를 지나간다.
    """
    for emb in list(_LIVE):
        try:
            emb.stop()
        except Exception:
            pass


class Embed:
    """한글 창 하나를 Tk 위젯 **안에** 넣었다 되돌리는 한 벌.

    `hwp_dock.Dock` 과 같은 얼굴을 한다 (start/stop_follow/restore/stop) —
    호출부가 둘을 바꿔 끼울 수 있어야 하기 때문이다.

    ⚠ start 전에 `hwp_engine.ensure_visible()` 로 창을 COM 차원에서 먼저
    켜 둘 것. 숨은 인스턴스를 그냥 자식으로 만들면 렌더러가 꺼진 채라
    통째로 검게 나온다 (도킹에서 겪은 것과 같은 함정).
    """

    def __init__(self, toplevel, host_widget, hwnd):
        self.top = toplevel
        self.host = host_widget
        self.hwnd = hwnd
        self._style = None
        self._exstyle = None
        self._placement = None
        self._host_hwnd = None
        self._binds = []

    # ── 시작 ─────────────────────────────────────────
    def start(self):
        try:
            if not win32gui.IsWindow(self.hwnd):
                return False
            self._placement = win32gui.GetWindowPlacement(self.hwnd)
            if (self._placement[1] == win32con.SW_SHOWMAXIMIZED
                    or win32gui.IsIconic(self.hwnd)):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)

            self._style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_STYLE)
            self._exstyle = win32gui.GetWindowLong(self.hwnd,
                                                   win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                self.hwnd, win32con.GWL_STYLE,
                (self._style & ~_STRIP) | win32con.WS_CHILD)

            self._host_hwnd = self.host.winfo_id()
            win32gui.SetParent(self.hwnd, self._host_hwnd)
            _LIVE.add(self)

            # 판 크기가 바뀌면 자식도 맞춘다. 위치는 손대지 않는다 —
            # 부모가 움직이면 윈도우가 알아서 데려간다 (도킹의 추적 스레드가
            # 통째로 필요 없어지는 지점이다).
            self._binds.append((self.host, "<Configure>",
                                self.host.bind("<Configure>", self._on_resize,
                                               add="+")))
            # 호출부가 stop 을 잊고 판을 지우려 해도 그 전에 떼어낸다.
            self._binds.append((self.host, "<Destroy>",
                                self.host.bind("<Destroy>", self._on_destroy,
                                               add="+")))
            self._fit()
            return True
        except Exception as e:
            applog.exc("한글 창 임베드 실패 — 임베드 없이 계속", e)
            self.restore()
            return False

    # ── 크기 맞추기 ──────────────────────────────────
    def _on_resize(self, _e=None):
        self._fit()

    def _on_destroy(self, e=None):
        # <Destroy> 는 자식 위젯에서도 올라온다 — 판 자신일 때만 뗀다
        if e is not None and e.widget is not self.host:
            return
        self.stop()

    def _fit(self):
        try:
            if not (win32gui.IsWindow(self.hwnd)
                    and win32gui.IsWindow(self._host_hwnd)):
                return
            l, t, r, b = win32gui.GetWindowRect(self._host_hwnd)
            w, h = max(r - l, 200), max(b - t, 200)
            cl, ct, cr, cb = win32gui.GetWindowRect(self.hwnd)
            if (cr - cl, cb - ct) != (w, h) or (cl, ct) != (l, t):
                win32gui.SetWindowPos(self.hwnd, 0, 0, 0, w, h,
                                      win32con.SWP_NOZORDER
                                      | win32con.SWP_NOACTIVATE)
        except Exception:
            pass                     # 파괴 경합 — 다음 기회에

    # ── 멈춤과 원복 (Dock 과 같은 이름·같은 계약) ─────
    def stop_follow(self):
        """임베드에는 추적 스레드가 없다. 자리를 지킨다."""

    def restore(self):
        """부모를 끊고 원래 창으로 되돌린다. 여러 번 불려도 안전하다."""
        if self not in _LIVE and self._style is None:
            return
        _LIVE.discard(self)
        for widget, seq, fid in self._binds:
            try:
                widget.unbind(seq, fid)
            except Exception:
                pass
        self._binds = []
        style, self._style = self._style, None
        exstyle, self._exstyle = self._exstyle, None
        placement, self._placement = self._placement, None
        try:
            if not win32gui.IsWindow(self.hwnd):
                return
            win32gui.SetParent(self.hwnd, 0)     # ← 이 한 줄이 문서를 살린다
            if style is not None:
                win32gui.SetWindowLong(self.hwnd, win32con.GWL_STYLE, style)
            if exstyle is not None:
                win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, exstyle)
            if placement is not None:
                win32gui.SetWindowPlacement(self.hwnd, placement)
            win32gui.SetWindowPos(self.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                                  | win32con.SWP_FRAMECHANGED
                                  | win32con.SWP_SHOWWINDOW)
        except Exception as e:
            applog.exc("한글 창 임베드 해제 실패 — 창이 이상하게 남을 수 있음", e)

    def stop(self):
        self.stop_follow()
        self.restore()
