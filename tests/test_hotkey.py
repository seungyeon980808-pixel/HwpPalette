# -*- coding: utf-8 -*-
"""전역 단축키의 순수 규칙 (2026-07-25) — 창·윈도우 API 없이 검증.

등록 자체는 윈도우가 필요하지만, 조합을 읽는 부분은 순수 함수라 여기서 덮는다.
등록·해제의 생명주기는 win32 를 가짜로 바꿔 검사한다 (2026-07-31).
"""

import pathlib
import sys
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import hotkey        # noqa: E402

CTRL, ALT, SHIFT = 0x0002, 0x0001, 0x0004
NOREPEAT = hotkey.MOD_NOREPEAT


class ParseComboTest(unittest.TestCase):

    def test_기본_조합(self):
        mods, vk = hotkey.parse_combo("ctrl+alt+t")
        self.assertEqual(mods, CTRL | ALT | NOREPEAT)
        self.assertEqual(vk, ord("T"))

    def test_대소문자와_공백을_가리지_않는다(self):
        self.assertEqual(hotkey.parse_combo(" Ctrl + Alt + T "),
                         hotkey.parse_combo("ctrl+alt+t"))

    def test_숫자_키도_된다(self):
        mods, vk = hotkey.parse_combo("ctrl+shift+1")
        self.assertEqual(mods, CTRL | SHIFT | NOREPEAT)
        self.assertEqual(vk, ord("1"))

    def test_자동반복_막기가_항상_붙는다(self):
        # 누르고 있을 때 변환이 수십 번 실행되면 문서가 엉망이 된다
        mods, _ = hotkey.parse_combo("ctrl+alt+t")
        self.assertTrue(mods & NOREPEAT)

    def test_수정키가_없으면_거부한다(self):
        # 맨 글자 키를 전역으로 잡으면 다른 프로그램에서 타자를 칠 수 없다
        with self.assertRaises(ValueError):
            hotkey.parse_combo("t")

    def test_글자_키가_없으면_거부한다(self):
        with self.assertRaises(ValueError):
            hotkey.parse_combo("ctrl+alt")

    def test_모르는_키는_거부한다(self):
        with self.assertRaises(ValueError):
            hotkey.parse_combo("ctrl+F13")

    def test_빈_값은_거부한다(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError):
                hotkey.parse_combo(bad)


class _FakeWinApi:
    """win32api 흉내 — 스레드 id 만 필요하다."""

    @staticmethod
    def GetCurrentThreadId():
        return 4242


class _FakeWinGui:
    """win32gui 흉내 — 등록·해제·메시지 루프의 호출만 기록한다.

    register_gate 를 주면 RegisterHotKey 가 그 이벤트가 열릴 때까지 멈춘다 —
    '등록이 응답하지 않는' 상황을 만들기 위해서다.
    """

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
        return 0, (0, 0)                    # rc=0 → WM_QUIT 처럼 끝난다

    def PostThreadMessage(self, tid, msg, wparam, lparam):
        self._quit.set()


class CancelPathTest(unittest.TestCase):
    r"""start() 가 기다리다 포기한 뒤의 등록은 **도로 풀려야** 한다 (2026-07-31).

    풀지 않으면: 조합(예: Ctrl+Alt+T)을 시스템 전체에서 가로채는데 아무도
    받아 가지 않는다 — 다른 모든 프로그램에서 그 키가 죽고, 되살릴 길은
    재부팅뿐이다.
    """

    def setUp(self):
        self._orig = (hotkey.win32gui, hotkey.win32api, hotkey._READY_TIMEOUT_S)

    def tearDown(self):
        hotkey.win32gui, hotkey.win32api, hotkey._READY_TIMEOUT_S = self._orig

    def _use(self, fake, timeout=None):
        hotkey.win32gui = fake
        hotkey.win32api = _FakeWinApi()
        if timeout is not None:
            hotkey._READY_TIMEOUT_S = timeout

    def test_기다리다_포기한_뒤의_등록은_도로_푼다(self):
        gate = threading.Event()
        fake = _FakeWinGui(register_gate=gate)
        self._use(fake, timeout=0.05)
        hk = hotkey.GlobalHotkey("ctrl+alt+t")
        ok, err = hk.start()                # 등록이 게이트에 걸려 응답이 없다
        self.assertFalse(ok)
        self.assertIn("응답", err)
        gate.set()                          # 이제야 등록이 끝난다
        hk._thread.join(timeout=5)
        self.assertFalse(hk._thread.is_alive())
        self.assertEqual(fake.registered, [hk._id])
        self.assertEqual(fake.unregistered, [hk._id],
                         "임자 없는 등록이 시스템에 남았다")

    def test_정상_시작_뒤_stop_은_여러_번_불러도_안전(self):
        fake = _FakeWinGui()
        self._use(fake)
        hk = hotkey.GlobalHotkey("ctrl+alt+t")
        ok, err = hk.start()
        self.assertTrue(ok)
        self.assertIsNone(err)
        hk.stop()
        hk._thread.join(timeout=5)
        hk.stop()                           # 두 번째 — 예외 없이 지나가야 한다
        self.assertEqual(fake.unregistered, [hk._id])

    def test_등록이_끝나기_전에_stop_해도_해제된다(self):
        """앱 종료가 등록 지연과 겹치는 경우 — 취소 표시가 대신 풀어 준다."""
        gate = threading.Event()
        fake = _FakeWinGui(register_gate=gate)
        self._use(fake, timeout=0.05)
        hk = hotkey.GlobalHotkey("ctrl+alt+t")
        hk.start()                          # 포기하고 돌아온다
        hk.stop()                           # 종료 경로 — 이미 취소돼 있어도 무해
        gate.set()
        hk._thread.join(timeout=5)
        self.assertEqual(fake.unregistered, [hk._id])


if __name__ == "__main__":
    unittest.main()
