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

따라오는 방식 (2026-07-30 재작성, 사용자 지시 "버벅임을 최소화하라"):
    첫 판은 30ms 폴링 + 완화(easing 45%)였다. 그런데 그 둘이 곧 버벅임이었다 —
    폴링은 잠들어 있다 깨어나는 시간(최대 30ms)만큼 늦고, 완화는 **일부러**
    ~150ms 에 걸쳐 따라붙는다. '미끄러지듯'은 곧 '늦게'다.
    이제는 **윈도우 이벤트 훅**(SetWinEventHook, EVENT_OBJECT_LOCATIONCHANGE)
    이다. 우리 창이 1px 이라도 움직이면 OS 가 그 즉시 이벤트를 쏘고, 훅
    스레드는 받은 즉시 완화 없이 **한 번에 스냅**한다. 기다리는 시간 자체가
    없다. 훅 등록이 실패하면 옛 폴링(8ms, 완화 없음)으로 물러난다.
    이벤트가 밀릴 때의 뭉개짐은 걱정할 것 없다 — 목표 좌표를 이벤트가 아니라
    **처리 시점의 GetWindowRect** 에서 다시 읽으므로, 밀린 이벤트는 '이미 맞는
    자리'를 확인만 하고 지나간다 (자연스러운 병합).

좌표 규칙 (실측 2026-07-27, dock_spike):
    이 프로세스는 DPI 미인식이라 winfo_rootx 같은 Tk 좌표는 4K 모니터에서
    배율만큼 어긋날 수 있다. 그래서 **읽기(GetWindowRect)와 쓰기(SetWindowPos)
    를 같은 프로세스 관점**으로 맞춘다 — 같은 가상 좌표계끼리는 상쇄되므로
    주모니터·4K·모니터 사이 빈 구간까지 오차 0px 로 맞았다.
"""

import ctypes
import threading
import time
from ctypes import wintypes

import win32api
import win32con
import win32gui

from hwp_palette.core import applog

# 판을 도킹용으로 넓힐 때의 폭 — 세로 주모니터(가상 폭 1080)에 창 전체가
# 들어가는 상한이다 (사용자 결정 2026-07-27: '둘 다 접기' 안).
EDIT_PANE_W = 1010

_FALLBACK_TICK_S = 0.008  # 훅 실패 시 폴링 주기 — 8ms 면 지연이 눈에 안 띈다
_EASE = 0.45              # restore() 의 되돌아가는 활강에만 쓴다 (추적엔 안 씀)
_SNAP_PX = 2              # 이 안쪽이면 정확히 맞춰 붙인다

# ── 이벤트 훅 상수 (ctypes — pywin32 에 SetWinEventHook 이 없다) ──
_EVENT_OBJECT_LOCATIONCHANGE = 0x800B
_OBJID_WINDOW = 0
_QS_ALLINPUT = 0x04FF
_WINEVENTPROC = ctypes.WINFUNCTYPE(
    None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
    ctypes.c_long, ctypes.c_long, wintypes.DWORD, wintypes.DWORD)
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
# CreateRectRgn 은 pywin32 의 win32gui 에 없다 (실측 2026-07-30)
_gdi32 = ctypes.windll.gdi32
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


# 한글이 **직접 그리는** 제목줄의 높이 (96dpi 기준, 실측 2026-07-30).
#
# WS_CAPTION 을 떼 봤지만 그 줄은 사라지지 않았다 — 화면을 그림으로 떠서
# 확인했다(spikes/dock_fix_spike.py). 한글의 제목줄은 OS 가 그리는 창틀이
# 아니라 **한글이 자기 그림 영역 안에 그리는 것**이라(WPF 식 자체 창틀),
# 스타일을 만져도 그대로 남는다. 그래서 창 자체를 **잘라낸다**(SetWindowRgn):
# 위 CAPTION_H 만큼을 보이는 영역에서 빼고, 그만큼 창을 위로 올려 둔다.
# 잘린 부분은 그려지지도, 눌리지도 않는다.
CAPTION_H = 40


def caption_height(hwnd):
    """그 창의 DPI 에 맞춘 제목줄 높이 (4K 배율에서도 맞게)."""
    try:
        dpi = _user32.GetDpiForWindow(hwnd) or 96
    except Exception:
        dpi = 96
    return int(round(CAPTION_H * dpi / 96.0))


def clear_crop(hwnd):
    """잘라내기를 없앤다 — 창을 원래대로 통째로 보이게."""
    try:
        if win32gui.IsWindow(hwnd):
            win32gui.SetWindowRgn(hwnd, 0, True)
    except Exception as e:
        applog.exc("한글 창 잘라내기 해제 실패 — 창이 잘린 채 남을 수 있음", e)


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

    def __init__(self, toplevel, host_widget, hwnd, crop_top=0):
        self.top = toplevel          # 남겨 둔다 — 호출부가 창 수명 판단에 씀
        self.host = host_widget      # 이 위젯 자리에 붙인다 (_zoom_canvas)
        self.hwnd = hwnd
        # crop_top: 한글이 그리는 제목줄을 잘라낼 높이 (0 이면 안 자른다).
        # 양식 수정 도킹은 0 을 쓴다 — 거기서는 잠깐 쓰는 창이라 제목줄이
        # 보이는 편이 오히려 '한글이 떠 있다'를 말해 준다.
        self.crop = int(crop_top)
        self._placement = None       # 원복용 — 시작할 때의 창 배치
        self._host_hwnd = None
        self._root_hwnd = None       # 우리 최상위 창 — 이벤트 훅이 지켜보는 대상
        self._hook_tid = None        # 훅 스레드의 Win32 스레드 id (WM_QUIT 용)
        self._focus_bind = None      # 우리 창 활성화 → 한글 다시 올리기
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
            # 훅은 **최상위 창**을 지켜본다 — 판(host)은 자식 창이라 부모가
            # 움직여도 자기 좌표는 그대로여서 LOCATIONCHANGE 가 안 온다.
            self._root_hwnd = win32gui.GetAncestor(self._host_hwnd,
                                                   win32con.GA_ROOT)
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._follow_loop,
                                            daemon=True, name="hwp-dock")
            self._thread.start()
            # 우리 창이 앞으로 나올 때마다 한글을 다시 올린다 (2026-07-30).
            #
            # z 를 매 틱 밀어 올리던 것을 그만둔 뒤(_MOVE_FLAGS 설명) 생긴 구멍이다:
            # 우리 창을 한 번 누르면 우리 창이 한글 위로 올라와 **판이 회색으로
            # 덮인다** — 양식 수정 도킹이 "엉망"이 된 정체다(사용자 지적).
            # 활성화될 때 한 번만 올리므로 자리다툼(클릭 가로채기)은 안 생긴다.
            self._focus_bind = self.top.bind("<FocusIn>",
                                             lambda e: self.raise_above(),
                                             add="+")
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
    def _snap(self):
        """한글을 판 자리에 **즉시** 맞춘다. 이미 맞으면 아무것도 안 한다.

        목표 좌표를 부르는 쪽이 아니라 **여기서, 지금** 읽는다 — 이벤트가
        밀려 있어도 늦은 이벤트는 이미 맞는 자리를 확인만 하고 지나간다.
        """
        try:
            if not (win32gui.IsWindow(self.hwnd)
                    and win32gui.IsWindow(self._host_hwnd)):
                return
            # 최소화 중이면 판 좌표가 (-32000…) 쓰레기 값이다 — 건드리지 않는다
            if self._root_hwnd and win32gui.IsIconic(self._root_hwnd):
                return
            l, t, r, b = win32gui.GetWindowRect(self._host_hwnd)
            tw, th = max(r - l, 200), max(b - t, 200)
            # 제목줄을 잘라내는 경우: 창을 그만큼 **위로** 올리고 키운다.
            # 그러면 잘려 안 보이는 부분이 판 위쪽에 얹히고, 보이는 부분이
            # 판을 정확히 채운다.
            ty, thh = t - self.crop, th + self.crop
            cl, ct, cr, cb = win32gui.GetWindowRect(self.hwnd)
            if (cl, ct, cr - cl, cb - ct) != (l, ty, tw, thh):
                win32gui.SetWindowPos(self.hwnd, 0, l, ty, tw, thh, _MOVE_FLAGS)
                if self.crop:
                    self._apply_crop(tw, thh)
            elif self.crop and not self._crop_ok():
                # 한글이 자기 영역을 다시 씌웠다 (최대화·배율 변경 등) —
                # 200ms 안전망이 이때 제목줄을 다시 잘라 준다.
                self._apply_crop(tw, thh)
        except Exception:
            pass                         # 창 파괴 경합 등 — 다음 이벤트에 다시

    def _crop_ok(self):
        """지금 창 영역이 우리가 씌운 그것인가 (위가 crop 만큼 잘려 있는가)."""
        try:
            box = wintypes.RECT()
            if not _user32.GetWindowRgnBox(self.hwnd, ctypes.byref(box)):
                return False                 # 영역이 없다 = 안 잘려 있다
            return box.top >= self.crop - 1
        except Exception:
            return True                      # 못 재면 건드리지 않는다

    def _apply_crop(self, w, h):
        r"""보이는 영역을 '제목줄 아래'로 한정한다.

        오른쪽·아래는 **창보다 훨씬 크게** 잡는다 (실측 2026-07-30): 창 크기를
        그대로 넣었더니 오른쪽과 아래가 잘려 회색 여백이 남았다 — 이 프로세스는
        DPI 미인식이라 SetWindowRgn 의 좌표와 SetWindowPos 의 좌표가 같은 배율이
        아니다. 영역은 창 밖으로 넘겨도 창이 알아서 자기 경계까지만 그리므로,
        넉넉히 잡으면 배율을 계산할 필요가 없다. 잘라낼 것은 **위 한 줄뿐**이다.
        """
        try:
            rgn = _gdi32.CreateRectRgn(0, self.crop, 1 << 15, 1 << 15)
            win32gui.SetWindowRgn(self.hwnd, rgn, True)   # 성공하면 OS 가 소유
        except Exception as e:
            applog.exc("한글 창 잘라내기 실패 — 제목줄이 보인 채로 계속", e)

    def _follow_loop(self):
        r"""이벤트 훅으로 따라간다. 훅이 안 잡히면 8ms 폴링으로 물러난다.

        훅(WINEVENT_OUTOFCONTEXT)의 콜백은 **이 스레드의 메시지 펌프 안**에서
        불린다 — 그래서 GetMessage 대신 MsgWaitForMultipleObjects(200ms) +
        PeekMessage 로 펌프를 돌린다. 200ms 타임아웃은 안전망이다: 이벤트를
        놓치는 일이 있어도(모니터 전환 등) 드리프트가 이내 바로잡힌다.
        """
        self._hook_tid = _kernel32.GetCurrentThreadId()

        @_WINEVENTPROC
        def _on_event(_hook, _event, hwnd, obj_id, _child, _tid, _time):
            # 우리 최상위 창의 '창 자체' 이동만 본다 — 커서(OBJID_CURSOR=-9)
            # 이동도 같은 이벤트로 오므로 거르지 않으면 초당 수백 번 스냅한다.
            if hwnd == self._root_hwnd and obj_id == _OBJID_WINDOW:
                self._snap()

        tk_tid = _user32.GetWindowThreadProcessId(self._root_hwnd, None)
        hook = _user32.SetWinEventHook(
            _EVENT_OBJECT_LOCATIONCHANGE, _EVENT_OBJECT_LOCATIONCHANGE,
            0, _on_event, 0, tk_tid, 0)          # 0 = WINEVENT_OUTOFCONTEXT
        if not hook:
            applog.warn("도킹 이벤트 훅 등록 실패 — 8ms 폴링으로 물러남")
            self._poll_fallback()
            return
        self._snap()                             # 시작하자마자 한 번 맞춘다
        try:
            msg = wintypes.MSG()
            while not self._stop_evt.is_set():
                _user32.MsgWaitForMultipleObjects(0, None, False, 200,
                                                  _QS_ALLINPUT)
                while _user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                    _user32.TranslateMessage(ctypes.byref(msg))
                    _user32.DispatchMessageW(ctypes.byref(msg))
                if not (win32gui.IsWindow(self.hwnd)
                        and win32gui.IsWindow(self._host_hwnd)):
                    break
                self._snap()                     # 200ms 안전망 (드리프트 교정)
        finally:
            _user32.UnhookWinEvent(hook)

    def _poll_fallback(self):
        """훅이 안 잡히는 환경용 — 완화 없이 빠르게 스냅만 반복한다."""
        while not self._stop_evt.is_set():
            if not (win32gui.IsWindow(self.hwnd)
                    and win32gui.IsWindow(self._host_hwnd)):
                break
            self._snap()
            time.sleep(_FALLBACK_TICK_S)

    # ── 멈춤과 원복 (둘로 나뉜 이유: 사이에 '숨기기'가 끼어야 한다) ──
    def stop_follow(self):
        """추적 스레드만 멈춘다. 창은 아직 판 자리에 있다."""
        if self._focus_bind is not None:
            try:
                self.top.unbind("<FocusIn>", self._focus_bind)
            except Exception:
                pass                     # 창이 이미 파괴됐다 — 바인딩도 함께 갔다
            self._focus_bind = None
        self._stop_evt.set()
        if self._hook_tid:               # 대기 중인 펌프를 즉시 깨운다
            try:
                _user32.PostThreadMessageW(self._hook_tid, 0x0012, 0, 0)  # WM_QUIT
            except Exception:
                pass
        t, self._thread = self._thread, None
        if t is not None:
            t.join(timeout=0.5)
        self._hook_tid = None

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
            if self.crop:
                clear_crop(self.hwnd)     # 잘린 채로 되돌리면 창이 반쪽이 된다
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
