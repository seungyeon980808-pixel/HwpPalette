# -*- coding: utf-8 -*-
r"""연결 판정·부착 테스트.

증상: **변환을 누르면 한글 창이 작아졌다 다시 커진다** (2026-07-19).

실측으로 확인한 원인:
  pyhwpx 의 Hwp() 생성자가 `XHwpWindows.Active_XHwpWindow.Visible = visible` 을
  실행하는데, 이 대입이 최대화된 창을 보통 크기로 되돌린다
  (측정: 최대 1094x1934 → 보통 1080x802). 예전엔 창 배치를 저장했다 복원해서
  막으려 했지만, 그건 '되돌리기'라 깜빡임 자체는 남는다.

그래서 지키려는 것 두 가지:
  1. 살아 있는 연결이면 Hwp() 를 다시 만들지 않는다
  2. 한글이 이미 떠 있으면 생성자를 아예 거치지 않고 붙는다
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hwp_engine        # noqa: E402


class FakeCom:
    """원시 COM 객체 흉내. Version 은 문자열."""

    def __init__(self, version="13, 0, 0, 2151"):
        self.Version = version


class FakeHwp:
    """pyhwpx.Hwp 흉내."""

    def __init__(self, version_property_raises=False, com_version="13, 0, 0, 2151"):
        self.hwp = FakeCom(com_version)
        self._raises = version_property_raises

    @property
    def Version(self):
        # pyhwpx 의 진짜 동작: 문자열을 파싱하므로 표기가 다르면 터진다
        if self._raises:
            raise ValueError("invalid literal for int()")
        return [int(i) for i in self.hwp.Version.split(", ")]


class ConnectionAliveTest(unittest.TestCase):

    def tearDown(self):
        hwp_engine.hwp = None

    def test_연결이_없으면_죽은_것으로_본다(self):
        self.assertIsNotNone(hwp_engine._connection_error(None))

    def test_살아있으면_None(self):
        self.assertIsNone(hwp_engine._connection_error(FakeHwp()))

    def test_Version_파싱이_실패해도_살아있다고_본다(self):
        r"""핵심 회귀 테스트.

        pyhwpx 의 Version 프로퍼티는 터지지만 COM 은 멀쩡한 상황.
        예전 코드(`_ = hwp.Version`)는 여기서 '죽었다'고 판단했다.
        """
        fake = FakeHwp(version_property_raises=True)
        self.assertIsNone(hwp_engine._connection_error(fake))

    def test_COM이_죽으면_그때는_죽은_것으로_본다(self):
        fake = FakeHwp()
        del fake.hwp.Version            # COM 접근 자체가 실패하는 상황
        self.assertIsNotNone(hwp_engine._connection_error(fake))


class ConnectReuseTest(unittest.TestCase):
    """connect() 가 살아 있는 연결에 손대지 않는지."""

    def tearDown(self):
        hwp_engine.hwp = None

    def _connect_with_fake(self, existing):
        """Hwp() 생성을 감시하면서 connect() 를 부른다. 반환: (결과, 생성횟수)"""
        hwp_engine.hwp = existing
        made = {"n": 0}

        def _spy(*a, **kw):
            made["n"] += 1
            return FakeHwp()

        with mock.patch.object(hwp_engine, "Hwp", side_effect=_spy):
            result = hwp_engine.connect()
        return result, made["n"]

    def test_살아있으면_Hwp를_다시_만들지_않는다(self):
        """Hwp() 를 다시 만드는 순간 창 최대화가 풀린다 = 깜빡임."""
        fake = FakeHwp()
        result, made = self._connect_with_fake(fake)
        self.assertIs(result, fake)
        self.assertEqual(made, 0, "살아 있는 연결인데 Hwp() 를 다시 만들었다")

    def test_Version_파싱_실패로_재연결하지_않는다(self):
        """이것이 '변환할 때마다 창이 깜빡이던' 그 상황이다."""
        fake = FakeHwp(version_property_raises=True)
        result, made = self._connect_with_fake(fake)
        self.assertIs(result, fake)
        self.assertEqual(made, 0, "Version 파싱 실패를 연결 끊김으로 오판했다")

    def test_정말_죽었으면_다시_연결한다(self):
        fake = FakeHwp()
        del fake.hwp.Version
        with mock.patch.object(hwp_engine, "_attach_without_resize",
                               return_value=None):
            _, made = self._connect_with_fake(fake)
        self.assertEqual(made, 1)

    def test_한글이_떠_있으면_생성자를_거치지_않는다(self):
        """핵심 회귀 테스트 — 생성자를 타는 순간 창 최대화가 풀린다."""
        hwp_engine.hwp = None
        attached = FakeHwp()
        made = {"n": 0}

        def _spy(*a, **kw):
            made["n"] += 1
            return FakeHwp()

        with mock.patch.object(hwp_engine, "_attach_without_resize",
                               return_value=attached), \
             mock.patch.object(hwp_engine, "Hwp", side_effect=_spy):
            result = hwp_engine.connect()
        self.assertIs(result, attached)
        self.assertEqual(made["n"], 0, "창을 보존하는 경로가 있는데 Hwp() 를 만들었다")


class AttachWithoutResizeTest(unittest.TestCase):
    """생성자 우회가 채워야 할 필드 — pyhwpx 가 바뀌면 여기서 먼저 깨진다."""

    def tearDown(self):
        hwp_engine.hwp = None

    def test_한글이_안_떠_있으면_None(self):
        with mock.patch.object(hwp_engine, "_running_hwp_com", return_value=None):
            self.assertIsNone(hwp_engine._attach_without_resize())

    def test_pyhwpx의_init이_세팅하는_필드는_셋뿐이다(self):
        """우회는 이 셋만 채운다. 늘어나면 우회가 불완전해지므로 알아채야 한다."""
        import inspect
        import re
        from pyhwpx import Hwp as RealHwp
        src = inspect.getsource(RealHwp.__init__)
        fields = set(re.findall(r'self\.(\w+)\s*=', src))
        self.assertEqual(fields, {"hwp", "on_quit", "htf_fonts"},
                         f"pyhwpx.Hwp.__init__ 이 세팅하는 필드가 바뀌었다: {fields}")


class FakeWindow:
    """XHwpWindows.Active_XHwpWindow 흉내 — Visible 대입 횟수를 센다."""

    def __init__(self, visible=True, handle=1234):
        self._visible = visible
        self.WindowHandle = handle
        self.visible_writes = 0

    @property
    def Visible(self):
        return self._visible

    @Visible.setter
    def Visible(self, v):
        self.visible_writes += 1
        self._visible = v


class HiddenInstanceTest(unittest.TestCase):
    r"""숨은 COM 인스턴스 회귀 테스트 (2026-07-27).

    증상: "양식 고치기를 눌러도 한글 창이 안 뜬다."
    원인: 다른 자동화가 숨겨 둔 HwpObject 에 붙으면 문서가 **안 보이는 창**에
    열린다. ensure_visible 이 그 창을 켜고, bring_to_front 는 아무 한글 창이
    아니라 **연결된 인스턴스의 창**을 앞으로 가져와야 한다.
    """

    def tearDown(self):
        hwp_engine.hwp = None

    def _wrap(self, window):
        fake = FakeHwp()
        fake.hwp.XHwpWindows = type("W", (), {})()
        fake.hwp.XHwpWindows.Active_XHwpWindow = window
        return fake

    def test_숨은_창이면_ensure_visible이_켠다(self):
        win = FakeWindow(visible=False)
        hwp_engine.hwp = self._wrap(win)
        with mock.patch.object(hwp_engine, "_hwp_window_handles",
                               return_value=[42]):
            self.assertTrue(hwp_engine.ensure_visible())
        self.assertTrue(win.Visible)
        self.assertEqual(win.visible_writes, 1)

    def test_이미_보이는_창은_건드리지_않는다(self):
        """Visible 대입은 최대화를 푸는 부작용이 있다 — 켜져 있으면 안 만진다."""
        win = FakeWindow(visible=True)
        hwp_engine.hwp = self._wrap(win)
        with mock.patch.object(hwp_engine, "_hwp_window_handles",
                               return_value=[42]):
            self.assertTrue(hwp_engine.ensure_visible())
        self.assertEqual(win.visible_writes, 0,
                         "이미 보이는 창의 Visible 을 다시 대입했다 (최대화가 풀린다)")

    def test_connected_hwnd는_연결된_인스턴스의_핸들을_쓴다(self):
        """한글이 여럿일 때 엉뚱한(문서 없는) 창을 올리면 안 된다."""
        win = FakeWindow(visible=True, handle=777)
        hwp_engine.hwp = self._wrap(win)
        with mock.patch.object(hwp_engine, "_hwp_window_handles",
                               return_value=[42]):
            self.assertEqual(hwp_engine._connected_hwnd(), 777)

    def test_핸들을_모르면_보이는_창으로_대신한다(self):
        hwp_engine.hwp = None
        with mock.patch.object(hwp_engine, "_hwp_window_handles",
                               return_value=[42]):
            self.assertEqual(hwp_engine._connected_hwnd(), 42)


if __name__ == "__main__":
    unittest.main()
