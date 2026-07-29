# -*- coding: utf-8 -*-
r"""한글 창 도킹 — 편집하는 동안 미리보기 판 자리에 딱 맞춰 붙인다 (2026-07-27).

왜 만들었나 (사용자 결정): 템플릿·양식을 고칠 때 한글 창이 아무 데나 떠서
"불필요한 창이 하나 더 생긴" 느낌이었다. 진짜 임베드(SetParent)는 검토 끝에
버렸다 — 프로세스 경계를 넘는 부모 관계는 입력 큐가 묶여 한글이 멈추면 우리도
멈추고, 우리가 죽으면 한글 창이 통째로 사라지며, IME 조합이 깨질 위험이 있다.
대신 **도킹**한다: 창 이동·크기 조절로 판 자리에 겹쳐 두고, 편집이 끝나면
원래 배치로 되돌린다. 한글은 끝까지 독립된 창이라 서로를 해칠 수 없다.

(2026-07-30 후속) 그 임베드를 결국 만들어 넣었다 — `hwp_embed.py`. 사용자가
둘을 번갈아 써 보고 고르는 중이라 **이 파일은 그대로 산다**. 도구줄의
`⇄` 단추가 두 방식을 갈아 끼운다.

추적은 **별도 스레드**가 한다 (2026-07-28 재작성, 사용자 지적 "창을 놓아야
따라온다"): 제목줄을 끄는 동안 윈도우는 모달 이동 루프에 들어가 Tk 의 after
타이머가 멎는다 — <Configure> 디바운스 방식은 그래서 놓은 뒤에야 따라왔다.
스레드는 Win32 호출만 쓰므로(Tk·COM 금지) 그 루프와 무관하게 계속 돈다.
매 틱 남은 거리의 절반쯤을 다가가는 완화(easing)라 처음 붙을 때도, 끌 때도
미끄러지듯 따라온다.

좌표 규칙 (실측 2026-07-27, dock_spike):
    이 프로세스는 DPI 미인식이라 winfo_rootx 같은 Tk 좌표는 4K 모니터에서
    배율만큼 어긋날 수 있다. 그래서 **읽기(GetWindowRect)와 쓰기(SetWindowPos)
    를 같은 프로세스 관점**으로 맞춘다 — 같은 가상 좌표계끼리는 상쇄되므로
    주모니터·4K·모니터 사이 빈 구간까지 오차 0px 로 맞았다.
"""

import threading
import time

import win32api
import win32con
import win32gui

from hwp_palette.core import applog

# 판을 도킹용으로 넓힐 때의 폭 — 세로 주모니터(가상 폭 1080)에 창 전체가
# 들어가는 상한이다 (사용자 결정 2026-07-27: '둘 다 접기' 안).
EDIT_PANE_W = 1010

_TICK_S = 0.03            # 추적 주기 — 33fps 면 눈에는 연속으로 보인다
_EASE = 0.45              # 매 틱 남은 거리의 45% 씩 접근 (~150ms 에 정착)
_SNAP_PX = 2              # 이 안쪽이면 정확히 맞춰 붙인다
# **z순서를 건드리지 않는다** (실측 2026-07-30, spikes/dock_click_spike.py):
# 여태 매 틱 HWND_TOPMOST 로 밀어 올렸는데, 우리 창도 '항상 위'라 둘이 같은
# 띠에서 자리다툼을 했다. 그 결과 한글이 활성화되는 순간 우리 빈 판이 위로
# 올라와 **마우스·키보드를 가로챘다** — "한글 안이 클릭이 안 되고 글이 안
# 써진다"의 정체다. 이제 z 는 윈도우가 알아서 하게 두고(활성화된 창이 위),
# 우리는 자리와 크기만 맞춘다.
_MOVE_FLAGS = (win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE
               | win32con.SWP_NOZORDER)


def fit_on_screen(hwnd, w, h):
    r"""그 창을 w×h 로 키울 때 **화면 밖으로 안 나가는** 좌상단 좌표.

    왜 필요한가 (2026-07-29, 감싸기 도킹): 평소 창은 화면 오른쪽 위에 선다
    (한글을 가리지 않으려고). 거기서 폭 1180 으로 키우면 오른쪽 절반이 화면
    밖으로 나가 도구줄이 통째로 안 보인다.

    창이 놓인 모니터의 작업 영역 안으로 밀어 넣는다 — 그 모니터가 창보다
    작으면 왼쪽 위에 붙인다(잘려도 왼쪽부터 보이는 편이 낫다).
    """
    try:
        l, t, _r, _b = win32gui.GetWindowRect(hwnd)
        mon = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        wl, wt, wr, wb = win32api.GetMonitorInfo(mon)["Work"]
        x = min(max(l, wl + 8), max(wl + 8, wr - w - 8))
        y = min(max(t, wt + 8), max(wt + 8, wb - h - 8))
        return int(x), int(y)
    except Exception as e:
        applog.exc("감싸기 창 자리 계산 실패 — 있던 자리에서 키운다", e)
        return None


def preposition(hwnd, host_widget):
    r"""**숨어 있는** 한글 창을 미리 판 자리로 옮겨 둔다. 성공 여부.

    왜 (사용자 지적 2026-07-28): 숨은 창을 COM 으로 켜면 **옛 자리에서**
    나타난 뒤 도킹으로 끌려와 '엉뚱한 곳에 생겼다가 붙는' 점프가 보였다.
    숨긴 채로 먼저 옮겨 두면 켜지는 순간 이미 제자리다.

    보이는 창은 건드리지 않는다 — 그쪽은 Dock 의 완화 추적이 미끄러지듯
    데려온다 (순간이동보다 눈에 편하다).
    """
    try:
        if not win32gui.IsWindow(hwnd) or win32gui.IsWindowVisible(hwnd):
            return False
        left, top, right, bottom = win32gui.GetWindowRect(host_widget.winfo_id())
        win32gui.SetWindowPos(hwnd, 0, left, top,
                              max(right - left, 200), max(bottom - top, 200),
                              win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
        return True
    except Exception as e:
        applog.exc("한글 창 미리 배치 실패 (도킹이 끌어온다)", e)
        return False


class Dock:
    """한글 창 하나를 Tk 위젯 자리에 붙였다 되돌리는 한 벌.

    start() → (스레드가 실시간으로 따라감) → stop().
    stop 은 몇 번 불려도 안전하고, 한글이 죽어 있으면 조용히 건너뛴다.

    ⚠ start 전에 반드시 `hwp_engine.ensure_visible()` 로 창을 **COM 차원에서**
    먼저 켜 둘 것 (실측 2026-07-28). 숨은 인스턴스를 SetWindowPos 의
    SWP_SHOWWINDOW 로 먼저 보이게 하면 한글 내부는 여전히 '숨김'이라
    렌더러가 꺼진 채 창만 떠서 **통째로 검게** 나온다.
    """

    def __init__(self, toplevel, host_widget, hwnd):
        self.top = toplevel          # 남겨 둔다 — 호출부가 창 수명 판단에 씀
        self.host = host_widget      # 이 위젯 자리에 붙인다 (_zoom_canvas)
        self.hwnd = hwnd
        self._placement = None       # 원복용 — 시작할 때의 창 배치
        self._host_hwnd = None
        self._stop_evt = threading.Event()
        self._thread = None

    # ── 시작 ─────────────────────────────────────────
    def start(self):
        try:
            if not win32gui.IsWindow(self.hwnd):
                return False
            self._placement = win32gui.GetWindowPlacement(self.hwnd)
            # 최대화·최소화 상태면 SetWindowPos 가 안 먹는다 — 먼저 보통으로
            if (self._placement[1] == win32con.SW_SHOWMAXIMIZED
                    or win32gui.IsIconic(self.hwnd)):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            # 스레드에서는 Tk 를 못 부른다 — 핸들을 지금(주 스레드) 떠 둔다
            self._host_hwnd = self.host.winfo_id()
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._follow_loop,
                                            daemon=True, name="hwp-dock")
            self._thread.start()
            # z 는 이제 추적 스레드가 안 건드리므로(_MOVE_FLAGS 설명), 시작할 때
            # **한 번만** 우리 창 위로 올려 둔다. 이게 없으면 방금 켠 한글이
            # 우리 판 뒤에 깔려 회색 판만 보인다.
            self.raise_above()
            return True
        except Exception as e:
            applog.exc("한글 창 도킹 실패 — 도킹 없이 계속", e)
            self._placement = None
            return False

    def raise_above(self):
        """한글 창을 우리 창 바로 위로 한 번 올린다 (초점은 뺏지 않는다)."""
        try:
            win32gui.SetWindowPos(
                self.hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
        except Exception as e:
            applog.exc("한글 창 올리기 실패 — 우리 판 뒤에 있을 수 있음", e)

    # ── 추적 (별도 스레드 — Win32 호출만, Tk·COM 금지) ──
    def _follow_loop(self):
        while not self._stop_evt.is_set():
            try:
                if not (win32gui.IsWindow(self.hwnd)
                        and win32gui.IsWindow(self._host_hwnd)):
                    break
                l, t, r, b = win32gui.GetWindowRect(self._host_hwnd)
                tw, th = max(r - l, 200), max(b - t, 200)
                cl, ct, cr, cb = win32gui.GetWindowRect(self.hwnd)
                cw, ch = cr - cl, cb - ct
                dl, dt = l - cl, t - ct
                dw, dh = tw - cw, th - ch
                if all(abs(v) <= _SNAP_PX for v in (dl, dt, dw, dh)):
                    if (dl, dt, dw, dh) != (0, 0, 0, 0):
                        win32gui.SetWindowPos(self.hwnd, 0,
                                              l, t, tw, th, _MOVE_FLAGS)
                    time.sleep(0.05)     # 정착 — 천천히 살핀다
                    continue
                win32gui.SetWindowPos(
                    self.hwnd, 0,
                    cl + int(dl * _EASE), ct + int(dt * _EASE),
                    cw + int(dw * _EASE), ch + int(dh * _EASE), _MOVE_FLAGS)
            except Exception:
                pass                     # 창 파괴 경합 등 — 다음 틱에 다시 본다
            time.sleep(_TICK_S)

    # ── 멈춤과 원복 (둘로 나뉜 이유: 사이에 '숨기기'가 끼어야 한다) ──
    def stop_follow(self):
        """추적 스레드만 멈춘다. 창은 아직 판 자리에 있다."""
        self._stop_evt.set()
        t, self._thread = self._thread, None
        if t is not None:
            t.join(timeout=0.5)

    def restore(self):
        r"""한글 창을 원래 자리·상태로 되돌린다.

        보이는 창이면 **미끄러지듯** 되돌린다 (2026-07-28, 사용자 지적
        "저장하면 깜빡거린다") — 순간이동은 '창이 튀었다'로 보인다.
        숨겨진 창이면 그냥 배치만 써 둔다 (아무것도 안 보인다).
        """
        placement, self._placement = self._placement, None
        if placement is None:
            return
        try:
            if not win32gui.IsWindow(self.hwnd):
                return
            visible = win32gui.IsWindowVisible(self.hwnd)
            was_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED
            if visible and not was_maximized:
                tl, tt, tr, tb = placement[4]       # rcNormalPosition
                tw, th = tr - tl, tb - tt
                for _ in range(8):                   # ~130ms 활강
                    cl, ct, cr, cb = win32gui.GetWindowRect(self.hwnd)
                    dl, dt = tl - cl, tt - ct
                    dw, dh = tw - (cr - cl), th - (cb - ct)
                    if all(abs(v) <= _SNAP_PX for v in (dl, dt, dw, dh)):
                        break
                    win32gui.SetWindowPos(
                        self.hwnd, 0,
                        cl + int(dl * _EASE), ct + int(dt * _EASE),
                        (cr - cl) + int(dw * _EASE), (cb - ct) + int(dh * _EASE),
                        win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
                    time.sleep(0.016)
            win32gui.SetWindowPos(
                self.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            if not visible:
                # 이미 숨겨진 창이면 **숨긴 채로** 배치만 되돌린다 (실측
                # 2026-07-28): 원래 배치의 showCmd 가 SW_SHOWNORMAL 이라
                # SetWindowPlacement 가 방금 숨긴 창을 도로 보이게 만들어,
                # 저장·취소 뒤 빈 한글 창이 되살아났다.
                placement = (placement[0], win32con.SW_HIDE,
                             placement[2], placement[3], placement[4])
            win32gui.SetWindowPlacement(self.hwnd, placement)
        except Exception as e:
            applog.exc("한글 창 원복 실패 — 창이 판 자리에 남을 수 있음", e)

    def stop(self):
        """추적을 멈추고 되돌린다 — 한 번에 끝내는 기본 경로."""
        self.stop_follow()
        self.restore()
