# -*- coding: utf-8 -*-
r"""런타임 안전장치 회귀 테스트 (2026-07-31 안전 감사).

'앱이 굳거나 시스템을 망가뜨리는' 세 경로를 못박는다:

  · 전역 단축키 — start() 가 기다리다 포기한 뒤에야 등록이 끝나면 **도로
    푼다**. 안 풀면 아무도 받지 않는 가로채기가 남아 그 조합이 모든
    프로그램에서 죽은 키가 된다.
  · 튜토리얼 — 단계 dict 에 title/text 가 빠져도 터지지 않고, 그리다
    실패하면 흐림 패널을 **반드시 걷는다**. 흐림 패널은 클릭을 다 삼키는
    창이라, 정리 없이 남으면 프로그램을 강제 종료하는 길밖에 없다.
  · 도킹 — 한글이 '응답 없음'이면 원복을 건너뛴다. 멈춘 창에 동기 호출을
    보내면 Tk 주 스레드가 같이 멈춰 사용자가 창을 닫을 수도 없다.
    멀쩡할 때의 활강 이동은 **동기**로 보낸다 — ASYNC 로 부치면 늦게
    처리된 이동이 마지막 SetWindowPlacement 확정을 도로 밀어낸다.

전부 가짜(win32·ctypes·Tk)로 돌린다 — 한글도 COM 도 화면도 안 띄운다.
"""

import pathlib
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import hotkey            # noqa: E402
from hwp_palette.hwp import hwp_dock           # noqa: E402
from hwp_palette.ui import tutorial            # noqa: E402


# ── 1. 전역 단축키: 포기한 등록은 남기지 않는다 ─────────


class _FakeWinApi:
    @staticmethod
    def GetCurrentThreadId():
        return 4242


class _FakeWinGui:
    """win32gui 흉내 — register_gate 로 '등록이 응답 없는' 상황을 만든다."""

    def __init__(self, register_gate=None):
        self.register_gate = register_gate
        self.registered = []
        self.unregistered = []
        self._quit = threading.Event()

    def RegisterHotKey(self, hwnd, hid, mods, vk):
        if self.register_gate is not None:
            if not self.register_gate.wait(timeout=5):
                raise RuntimeError("테스트 게이트가 열리지 않음")
        self.registered.append(hid)

    def UnregisterHotKey(self, hwnd, hid):
        self.unregistered.append(hid)

    def GetMessage(self, hwnd, lo, hi):
        self._quit.wait(timeout=5)
        return 0, (0, 0)

    def PostThreadMessage(self, tid, msg, wparam, lparam):
        self._quit.set()


class HotkeyTimeoutTest(unittest.TestCase):

    def setUp(self):
        self._orig = (hotkey.win32gui, hotkey.win32api, hotkey._READY_TIMEOUT_S)

    def tearDown(self):
        hotkey.win32gui, hotkey.win32api, hotkey._READY_TIMEOUT_S = self._orig

    def test_start_가_포기하면_늦은_등록은_스레드가_해제한다(self):
        gate = threading.Event()
        fake = _FakeWinGui(register_gate=gate)
        hotkey.win32gui = fake
        hotkey.win32api = _FakeWinApi()
        hotkey._READY_TIMEOUT_S = 0.05
        hk = hotkey.GlobalHotkey("ctrl+alt+t")
        ok, _err = hk.start()               # 등록이 게이트에 걸려 시간 초과
        self.assertFalse(ok)
        gate.set()                          # 이제야 RegisterHotKey 가 끝난다
        hk._thread.join(timeout=5)
        self.assertEqual(fake.registered, fake.unregistered,
                         "등록 수와 해제 수가 다르다 — 시스템에 가로채기가 남는다")
        self.assertEqual(fake.unregistered, [hk._id])


# ── 2. 튜토리얼: 흐림 패널을 남긴 채 죽지 않는다 ────────


class _FakeRoot:
    """Tutorial 이 root 에게 부르는 것만 흉내 낸다 (Tk 창 없이)."""

    def attributes(self, *a):
        return False

    def after(self, ms, fn=None):
        return "job"

    def after_cancel(self, job):
        pass

    def bind(self, ev, fn=None, add=None):
        return "fid"

    def unbind(self, ev, fid=None):
        pass

    def winfo_exists(self):
        return True

    def winfo_rootx(self):
        return 0

    def winfo_rooty(self):
        return 0

    def winfo_width(self):
        return 300

    def winfo_height(self):
        return 500

    def update_idletasks(self):
        pass


def _stubbed(steps):
    """그리기를 기록만 하는 가짜로 바꾼 Tutorial — 좌표·창 없이 흐름만 본다."""
    t = tutorial.Tutorial(_FakeRoot(), steps)
    drawn = []
    t._draw_dim = lambda w: drawn.append(("dim", w))
    t._draw_halo = lambda w: drawn.append(("halo", w))
    t._draw_coach = (lambda w, title, text, last:
                     drawn.append(("coach", title, text)))
    t._track = lambda: None
    t._geo = lambda: (0, 0, 300, 500)
    return t, drawn


class TutorialStepGuardTest(unittest.TestCase):

    def test_제목_설명이_빠진_단계도_터지지_않는다(self):
        t, drawn = _stubbed([{"widget": None}])     # title/text 없음
        t._show(0)                                  # KeyError 가 나면 여기서 터진다
        self.assertIn(("coach", "", ""), drawn)
        self.assertFalse(t._done)
        t._finish()

    def test_그리다_터지면_흐림_패널을_걷고_끝낸다(self):
        t, _drawn = _stubbed([{"title": "제목", "text": "설명"}])
        destroyed = []

        class _Panel:
            def __init__(self, name):
                self.name = name

            def destroy(self):
                destroyed.append(self.name)

        t._dim = [_Panel("d1"), _Panel("d2")]       # 이미 떠 있는 흐림 패널

        def boom(*a, **k):
            raise RuntimeError("코치 창 그리기 실패")
        t._draw_coach = boom
        t._show(0)                                  # 예외가 밖으로 새면 안 된다
        self.assertTrue(t._done, "실패했으면 튜토리얼이 끝난 상태여야 한다")
        self.assertEqual(sorted(destroyed), ["d1", "d2"],
                         "흐림 패널이 화면에 남아 클릭을 삼킨다")
        self.assertEqual(t._dim, [])

    def test_흐림_패널에도_Escape_탈출구가_걸린다(self):
        t = tutorial.Tutorial(_FakeRoot(), [])
        with mock.patch.object(tutorial, "tk") as fake_tk:
            fake_tk.Toplevel.side_effect = lambda master=None: mock.MagicMock()
            t._draw_dim(None)                       # 창 전체를 덮는 패널 하나
        self.assertEqual(len(t._dim), 1)
        events = [c.args[0] for c in t._dim[0].bind.call_args_list]
        self.assertIn("<Escape>", events)


# ── 3. 도킹: 멈춘 한글을 붙잡고 같이 멈추지 않는다 ──────


class _FakeUser32:
    def __init__(self, hung):
        self._hung = hung

    def IsHungAppWindow(self, hwnd):
        return 1 if self._hung else 0

    def GetWindowRgnBox(self, hwnd, box):
        return 0                                    # 영역 없음 = 안 잘림


class _FakeDockGui:
    """win32gui 흉내 — restore() 가 부르는 것만, 호출을 기록한다."""

    def __init__(self):
        self.setpos = []
        self.placements = []

    def IsWindow(self, hwnd):
        return True

    def IsWindowVisible(self, hwnd):
        return True

    def GetWindowRect(self, hwnd):
        return (0, 0, 100, 100)

    def SetWindowPos(self, *args):
        self.setpos.append(args)

    def SetWindowPlacement(self, hwnd, placement):
        self.placements.append(placement)


class DockHungRestoreTest(unittest.TestCase):

    def _dock(self):
        d = hwp_dock.Dock(toplevel=None, host_widget=None, hwnd=1111)
        d._placement = (0, 1, (-1, -1), (-1, -1), (0, 0, 100, 100))
        d._rect0 = (0, 0, 100, 100)                 # 이미 제자리 → 활강 생략
        return d

    def test_응답_없는_한글은_원복을_건너뛴다(self):
        gui = _FakeDockGui()
        with mock.patch.object(hwp_dock, "win32gui", gui), \
             mock.patch.object(hwp_dock, "_user32", _FakeUser32(hung=True)):
            d = self._dock()
            d.restore()
        self.assertEqual(gui.setpos, [],
                         "멈춘 창에 SetWindowPos 를 보내면 우리도 멈춘다")
        self.assertEqual(gui.placements, [])
        self.assertIsNone(d._placement)

    def test_멀쩡한_한글은_평소대로_원복한다(self):
        gui = _FakeDockGui()
        with mock.patch.object(hwp_dock, "win32gui", gui), \
             mock.patch.object(hwp_dock, "_user32", _FakeUser32(hung=False)):
            d = self._dock()
            d.restore()
        self.assertEqual(len(gui.placements), 1)    # 배치 원복은 그대로 산다
        self.assertTrue(gui.setpos, "NOTOPMOST 되돌리기가 사라졌다")
        for call in gui.setpos:                     # 제자리면 Z순서만 되돌린다
            nomove_nosize = 0x0002 | 0x0001         # SWP_NOMOVE | SWP_NOSIZE
            self.assertEqual(call[-1] & nomove_nosize, nomove_nosize,
                             f"제자리인데 위치·크기를 건드렸다: {call}")

    def test_활강_이동은_동기로_보내_확정_배치가_항상_이긴다(self):
        r"""활강 SetWindowPos 에 SWP_ASYNCWINDOWPOS 가 붙으면 안 된다.

        ASYNC 로 부친 이동은 한글이 잠깐 바빴다 깨어나면 SetWindowPlacement
        의 보낸 메시지보다 **늦게** 처리돼, 확정된 원래 배치를 활강 중간
        지점으로 도로 밀어낸다. 위 제자리 테스트는 활강 루프에 아예 안
        들어가므로(_rect0 == 현재 rect) 여기서 따로 못박는다.
        """
        gui = _FakeDockGui()
        with mock.patch.object(hwp_dock, "win32gui", gui), \
             mock.patch.object(hwp_dock, "_user32", _FakeUser32(hung=False)), \
             mock.patch.object(hwp_dock.time, "sleep"):   # 활강 틱 대기 생략
            d = self._dock()
            d._rect0 = (300, 300, 700, 700)         # 제자리 아님 → 활강 진입
            d.restore()
        glides = [c for c in gui.setpos             # 위치·크기를 옮기는 호출만
                  if not (c[-1] & (0x0002 | 0x0001))]
        self.assertTrue(glides, "활강 루프가 SetWindowPos 를 한 번도 안 불렀다")
        for call in glides:
            self.assertFalse(call[-1] & 0x4000,     # SWP_ASYNCWINDOWPOS
                             f"활강 이동이 ASYNC 로 부쳐졌다 — 늦게 처리되면 "
                             f"확정 배치를 도로 밀어낸다: {call}")
        self.assertEqual(len(gui.placements), 1,
                         "활강 끝에 SetWindowPlacement 확정이 사라졌다")


if __name__ == "__main__":
    unittest.main()
