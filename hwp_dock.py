# -*- coding: utf-8 -*-
r"""한글 창 도킹 — 편집하는 동안 미리보기 판 자리에 딱 맞춰 붙인다 (2026-07-27).

왜 만들었나 (사용자 결정): 템플릿·양식을 고칠 때 한글 창이 아무 데나 떠서
"불필요한 창이 하나 더 생긴" 느낌이었다. 진짜 임베드(SetParent)는 검토 끝에
버렸다 — 프로세스 경계를 넘는 부모 관계는 입력 큐가 묶여 한글이 멈추면 우리도
멈추고, 우리가 죽으면 한글 창이 통째로 사라지며, IME 조합이 깨질 위험이 있다.
대신 **도킹**한다: 창 이동·크기 조절로 판 자리에 겹쳐 두고, 편집이 끝나면
원래 배치로 되돌린다. 한글은 끝까지 독립된 창이라 서로를 해칠 수 없다.

좌표 규칙 (실측 2026-07-27, dock_spike):
    이 프로세스는 DPI 미인식이라 winfo_rootx 같은 Tk 좌표는 4K 모니터에서
    배율만큼 어긋날 수 있다. 그래서 **읽기(GetWindowRect)와 쓰기(SetWindowPos)
    를 같은 프로세스 관점**으로 맞춘다 — 같은 가상 좌표계끼리는 상쇄되므로
    주모니터·4K·모니터 사이 빈 구간까지 오차 0px 로 맞았다.
"""

import tkinter as tk

import win32con
import win32gui

import applog

# 판을 도킹용으로 넓힐 때의 폭 — 세로 주모니터(가상 폭 1080)에 창 전체가
# 들어가는 상한이다 (사용자 결정 2026-07-27: '둘 다 접기' 안).
EDIT_PANE_W = 1010

_FOLLOW_DELAY_MS = 60      # 창 이동 연사를 모아 한 번만 따라간다


class Dock:
    """한글 창 하나를 Tk 위젯 자리에 붙였다 되돌리는 한 벌.

    start() → (설정 창이 움직이면 따라감) → stop().
    stop 은 몇 번 불려도 안전하고, 한글이 죽어 있으면 조용히 건너뛴다.
    """

    def __init__(self, toplevel, host_widget, hwnd):
        self.top = toplevel          # <Configure> 를 받을 설정 창
        self.host = host_widget      # 이 위젯 자리에 붙인다 (_zoom_canvas)
        self.hwnd = hwnd
        self._placement = None       # 원복용 — 시작할 때의 창 배치
        self._job = None
        self._funcid = None

    # ── 시작/추적 ─────────────────────────────────────
    def start(self):
        r"""지금 자리를 기억하고 판 자리로 옮긴다. 성공 여부.

        ⚠ 부르기 전에 반드시 `hwp_engine.ensure_visible()` 로 한글 창을 **COM
        차원에서** 먼저 켜 둘 것 (실측 2026-07-28). 숨은 인스턴스를 여기의
        SWP_SHOWWINDOW 로 먼저 보이게 하면 한글 내부는 여전히 '숨김'이라
        렌더러가 꺼진 채 창만 떠서 **통째로 검게** 나온다 — RedrawWindow,
        WM_EXITSIZEMOVE, 활성화, 숨겼다 펴기, 크기 흔들기 전부 소용없었다.
        """
        try:
            if not win32gui.IsWindow(self.hwnd):
                return False
            self._placement = win32gui.GetWindowPlacement(self.hwnd)
            # 최대화·최소화 상태면 SetWindowPos 가 안 먹는다 — 먼저 보통으로
            if (self._placement[1] == win32con.SW_SHOWMAXIMIZED
                    or win32gui.IsIconic(self.hwnd)):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            self._move()
            self._funcid = self.top.bind("<Configure>", self._on_configure,
                                         add="+")
            return True
        except Exception as e:
            applog.exc("한글 창 도킹 실패 — 도킹 없이 계속", e)
            self._placement = None
            return False

    def _host_rect(self):
        """판의 화면 자리 — Tk 가 아니라 Win32 로 잰다 (머리말 참고)."""
        return win32gui.GetWindowRect(self.host.winfo_id())

    def _move(self):
        # SWP_NOACTIVATE 필수 (실측 2026-07-27, "심각하게 버벅거린다"):
        # 없으면 SetWindowPos 가 옮길 때마다 한글을 **활성화**해서, 설정 창을
        # 끄는 동안 60ms 마다 포커스를 뺏고 뺏기는 싸움이 났다.
        left, top, right, bottom = self._host_rect()
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST,
                              left, top,
                              max(right - left, 200), max(bottom - top, 200),
                              win32con.SWP_SHOWWINDOW
                              | win32con.SWP_NOACTIVATE)

    def _on_configure(self, e):
        # 자식 위젯의 Configure 도 톱레벨 바인딩으로 온다 — 창 자신 것만
        if e.widget is not self.top:
            return
        if self._job is not None:
            try:
                self.top.after_cancel(self._job)
            except Exception:
                pass
        self._job = self.top.after(_FOLLOW_DELAY_MS, self._follow)

    def _follow(self):
        self._job = None
        try:
            if win32gui.IsWindow(self.hwnd):
                self._move()
        except Exception:
            pass                     # 이동 중 경합 — 다음 Configure 가 또 온다

    # ── 원복 ─────────────────────────────────────────
    def stop(self):
        """추적을 멈추고 한글 창을 원래 자리·상태로 되돌린다."""
        if self._funcid is not None:
            try:
                self.top.unbind("<Configure>", self._funcid)
            except Exception:
                pass
            self._funcid = None
        if self._job is not None:
            try:
                self.top.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self._placement is None:
            return
        placement, self._placement = self._placement, None
        try:
            if not win32gui.IsWindow(self.hwnd):
                return               # 한글이 죽었다 — 되돌릴 창이 없다
            win32gui.SetWindowPos(
                self.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            win32gui.SetWindowPlacement(self.hwnd, placement)
        except Exception as e:
            applog.exc("한글 창 원복 실패 — 창이 판 자리에 남을 수 있음", e)
