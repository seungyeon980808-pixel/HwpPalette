# -*- coding: utf-8 -*-
r"""세로 띠 도킹 — 우리 창이 한글 창 **왼쪽 옆구리에 붙어** 한 창처럼 움직인다.

`hwp_dock.py` 와 주객이 반대다. 저쪽은 한글을 우리 미리보기 판 안으로 끌어오고
(양식을 고치는 잠깐), 이쪽은 **한글이 주인공**이고 우리가 얇은 도구 띠가 된다
(글을 쓰는 내내).

부모-자식(SetParent)은 쓰지 않는다. 2026-07-29 실측(`docs/EMBED_검토.md`)에서
부모가 죽으면 한글이 저장도 못 물어보고 죽었고, 강제 종료 때는 문서 창 없는
유령 프로세스가 남았다. 여기서는 창 둘이 끝까지 남남이다 — 우리가 어떻게 죽든
한글은 제자리에 그대로 있다. 겉모습만 한 창처럼 맞춘다.

추적은 **Tk 의 after 로** 한다 (hwp_dock 은 스레드를 쓴다). 창을 끄는 모달 이동
루프에 우리 타이머가 멎는 문제는 *우리 창을 끌 때* 생기는데, 이 모드에서 끄는
것은 한글 창이라 우리 타이머는 멀쩡히 돈다. 스레드를 안 쓰면 그만큼 덜 위험하다.

최대화는 **가짜로** 한다: 진짜 최대화(SW_MAXIMIZE)를 두면 한글이 작업 영역을
꽉 채워 띠를 덮는다. 그래서 최대화를 감지하면 곧바로 풀고 '작업 영역에서 띠
폭만 뺀 자리'로 앉힌다 — 눈에는 최대화된 것과 같고 띠는 옆에 남는다.
"""

import win32api
import win32con
import win32gui

from hwp_palette.core import applog

_SNAP = 2                    # 이 안쪽 차이는 맞춘 것으로 본다
_FLAGS = win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER


def top_hwnd(widget_id):
    r"""Tk 위젯 핸들 → 그 창의 **최상위** 핸들.

    Tk 는 토플레벨에도 안쪽 자식 창을 하나 두므로 `winfo_id()` 가 곧 창틀이
    아니다. 그대로 SetWindowPos 하면 창틀은 그대로인 채 안쪽만 움직인다.
    """
    parent = win32gui.GetParent(widget_id)
    return parent or widget_id


def _is_maximized(hwnd):
    r"""최대화 상태인가 — `win32gui.IsZoomed` 는 이 pywin32 에 없다(실측 2026-07-29).

    GetWindowPlacement 의 showCmd 로 본다. hwp_dock 도 같은 방식이다.
    """
    return win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED


def _work_area(hwnd):
    """그 창이 놓인 모니터의 작업 영역 (작업표시줄을 뺀 자리)."""
    try:
        mon = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        return win32api.GetMonitorInfo(mon)["Work"]
    except Exception:
        return (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))


class SideDock:
    """한글 창 하나와 우리 띠 창 하나를 옆구리로 묶는다.

    `start()` 뒤로 호출부가 `tick()` 을 주기적으로 부른다. tick 은 상태를
    돌려준다 — "ok" | "min"(한글이 최소화됨) | "gone"(한글이 사라짐).
    """

    def __init__(self, strip_hwnd, hwp_hwnd, width):
        self.strip = strip_hwnd
        self.hwp = hwp_hwnd
        self.w = int(width)
        self._placement = None      # 원복용 — 도킹 전 한글 창 배치

    # ── 시작 ─────────────────────────────────────────
    def start(self):
        """한글을 띠 폭만큼 오른쪽으로 밀고 자리를 만든다. 성공 여부."""
        try:
            if not win32gui.IsWindow(self.hwp):
                return False
            self._placement = win32gui.GetWindowPlacement(self.hwp)
            if win32gui.IsIconic(self.hwp):
                win32gui.ShowWindow(self.hwp, win32con.SW_RESTORE)
            if _is_maximized(self.hwp):
                self._fake_maximize()
            else:
                self._make_room()
            return True
        except Exception as e:
            applog.exc("세로 띠 도킹 시작 실패", e)
            self._placement = None
            return False

    def _make_room(self):
        r"""한글을 옮겨 왼쪽에 띠 자리를 낸다.

        화면 왼쪽 끝에 여유가 있으면 한글은 그대로 두고 띠만 옆에 세운다 —
        창이 안 움직이는 편이 눈에 편하다. 여유가 없을 때만 한글을 민다.
        """
        l, t, r, b = win32gui.GetWindowRect(self.hwp)
        wl, wt, wr, wb = _work_area(self.hwp)
        if l - self.w >= wl:
            return                        # 이미 자리가 있다
        new_l = wl + self.w
        new_w = min(r - l, wr - new_l)    # 오른쪽으로 밀다 화면 밖으로 나가지 않게
        win32gui.SetWindowPos(self.hwp, 0, new_l, t, new_w, b - t, _FLAGS)

    def _fake_maximize(self):
        """작업 영역에서 띠 폭만 뺀 자리 — 눈에는 최대화, 띠는 살아 있다."""
        wl, wt, wr, wb = _work_area(self.hwp)
        win32gui.ShowWindow(self.hwp, win32con.SW_RESTORE)
        win32gui.SetWindowPos(self.hwp, 0, wl + self.w, wt,
                              wr - wl - self.w, wb - wt, _FLAGS)

    # ── 추적 ─────────────────────────────────────────
    def tick(self):
        try:
            if not win32gui.IsWindow(self.hwp):
                return "gone"
            if win32gui.IsIconic(self.hwp):
                return "min"
            if _is_maximized(self.hwp):
                # 사용자가 한글 제목줄의 ▢ 를 눌렀다 — 가짜 최대화로 바꿔 준다
                self._fake_maximize()
            l, t, r, b = win32gui.GetWindowRect(self.hwp)
            wl = _work_area(self.hwp)[0]
            if l - self.w < wl:           # 왼쪽으로 밀렸다 — 다시 자리를 낸다
                self._make_room()
                l, t, r, b = win32gui.GetWindowRect(self.hwp)
            self._place_strip(l - self.w, t, b - t)
            return "ok"
        except Exception as e:
            applog.exc("세로 띠 추적 실패 — 이번 틱 건너뜀", e)
            return "ok"

    def _place_strip(self, x, y, h):
        sl, st, sr, sb = win32gui.GetWindowRect(self.strip)
        if (abs(sl - x) <= _SNAP and abs(st - y) <= _SNAP
                and abs((sb - st) - h) <= _SNAP):
            return                        # 이미 맞다 — 매 틱 SetWindowPos 하지 않는다
        win32gui.SetWindowPos(self.strip, 0, x, y, self.w, h, _FLAGS)

    # ── 창 단추 ──────────────────────────────────────
    def maximize(self):
        """띠에서 누르는 최대화 — 한글을 '띠 뺀 작업 영역'으로 채운다."""
        try:
            self._fake_maximize()
        except Exception as e:
            applog.exc("도킹 최대화 실패", e)

    def minimize(self):
        try:
            win32gui.ShowWindow(self.hwp, win32con.SW_MINIMIZE)
        except Exception as e:
            applog.exc("도킹 최소화 실패", e)

    def restore_hwp(self):
        """최소화된 한글을 다시 편다 (띠를 눌렀을 때)."""
        try:
            if win32gui.IsIconic(self.hwp):
                win32gui.ShowWindow(self.hwp, win32con.SW_RESTORE)
        except Exception as e:
            applog.exc("한글 복원 실패", e)

    def focus_hwp(self):
        try:
            win32gui.SetForegroundWindow(self.hwp)
        except Exception:
            pass                          # 포그라운드 전환은 실패해도 그만이다

    # ── 끝내기 ───────────────────────────────────────
    def stop(self):
        """한글을 도킹 전 자리로 되돌린다. 한글이 죽었으면 조용히 지나간다."""
        placement, self._placement = self._placement, None
        if placement is None:
            return
        try:
            if win32gui.IsWindow(self.hwp):
                win32gui.SetWindowPlacement(self.hwp, placement)
        except Exception as e:
            applog.exc("도킹 해제 후 한글 창 원복 실패", e)
