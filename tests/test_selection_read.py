# -*- coding: utf-8 -*-
r"""선택 읽기 회귀 테스트 (2026-07-26).

막으려는 증상: **한글에 선택이 멀쩡히 있는데 "선택 없음" 이라며 변환이 거부됨.**

실측으로 잡은 원인은 클립보드였다. Tk 의 clipboard_append 는 값을 담는 것이
아니라 '내가 주인' 등록(지연 렌더링)이라, 그 뒤 같은 프로세스에서
OpenClipboard 가 '액세스가 거부되었습니다' 로 막힌다. 튜토리얼 [복사] 를 누른
뒤 변환을 누르면 정확히 그 길로 들어갔다.

그래서 지켜야 할 규칙 두 개를 여기서 못박는다:
  1) 선택 읽기는 **클립보드를 거치지 않는다** (한글에서 직접 받는다)
  2) 선택이 없으면 클립보드를 **아예 읽지 않는다** (남의 글이 둔갑하지 않게)
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import clipboard            # noqa: E402
from hwp_palette.hwp import hwp_engine           # noqa: E402


class FakeHwp:
    r"""선택 관련만 흉내 낸 한글.

    block=None 은 '선택 없음'(한글이 실제로 None 을 준다).
    mode 는 SelectionMode — 0 이어도 block 이 있을 수 있다는 것이 이 버그의 핵심.
    """

    def __init__(self, block=None, mode=0):
        self._block = block
        self.SelectionMode = mode
        self.copied = 0
        self.XHwpDocuments = mock.Mock(Count=1)

        engine = self

        class _Action:
            @staticmethod
            def Run(name):
                if name == "Copy":
                    engine.copied += 1
        self.HAction = _Action()

    def GetTextFile(self, fmt, arg):
        if arg == "saveblock":
            return self._block
        return ""


class SelectionReadTest(unittest.TestCase):

    def tearDown(self):
        hwp_engine.hwp = None

    def _use(self, fake):
        hwp_engine.hwp = fake

    def test_선택_내용은_클립보드를_거치지_않고_읽는다(self):
        """핵심 회귀 테스트 — 클립보드가 통째로 막혀 있어도 읽혀야 한다."""
        self._use(FakeHwp(block="다음 중 \\굵게{옳지 않은} 것은?", mode=1))
        with mock.patch.object(clipboard, "get_text",
                               side_effect=AssertionError("클립보드를 읽었다")):
            got = hwp_engine.read_selection_text()
        self.assertEqual(got, "다음 중 \\굵게{옳지 않은} 것은?")
        self.assertEqual(hwp_engine.hwp.copied, 0)      # Copy 도 안 눌렀다

    def test_한글이_남긴_숫자_엔티티는_글자로_되돌린다(self):
        r"""핵심 회귀 (실측 2026-07-26): GetTextFile 은 줄표(—)를 &#8212; 로
        바꿔서 준다. 그대로 두면 — 가 든 공문 문장의 변환이 다 어긋난다."""
        self._use(FakeHwp(block="붙임 &#8212; 계획서 1부 &#8220;안&#8221;",
                          mode=1))
        self.assertEqual(hwp_engine.read_selection_text(),
                         "붙임 — 계획서 1부 “안”")

    def test_엔티티가_없으면_원문_그대로(self):
        self.assertEqual(hwp_engine._unescape_entities("50% <표>&값"),
                         "50% <표>&값")

    def test_SelectionMode가_0이어도_선택_내용이_있으면_읽는다(self):
        self._use(FakeHwp(block="\\원1\\ \\섭씨\\", mode=0))
        self.assertEqual(hwp_engine.read_selection_text(), "\\원1\\ \\섭씨\\")
        self.assertTrue(hwp_engine.has_selection())

    def test_선택이_없으면_클립보드를_읽지_않는다(self):
        """클립보드에 남아 있던 예문이 '선택한 글'로 둔갑하면 안 된다."""
        self._use(FakeHwp(block=None, mode=0))
        with mock.patch.object(clipboard, "get_text",
                               return_value="예전에 복사해 둔 예문"):
            self.assertEqual(hwp_engine.read_selection_text(), "")
        self.assertFalse(hwp_engine.has_selection())
        self.assertEqual(hwp_engine.hwp.copied, 0)

    def test_직접_읽기가_빈손이면_클립보드로_넘어간다(self):
        """표처럼 saveblock 이 빈손인 선택 — 이때만 Copy 를 쓴다."""
        self._use(FakeHwp(block="", mode=1))
        with mock.patch.object(clipboard, "get_text", return_value="1\t2\t3"):
            self.assertEqual(hwp_engine.read_selection_text(), "1\t2\t3")
        self.assertEqual(hwp_engine.hwp.copied, 1)

    def test_두_길이_다_막히면_빈손이되_기록을_남긴다(self):
        self._use(FakeHwp(block="", mode=1))
        with mock.patch.object(clipboard, "get_text", return_value=""), \
                mock.patch("hwp_palette.hwp.hwp_engine.applog.warn") as warned:
            self.assertEqual(hwp_engine.read_selection_text(), "")
        self.assertTrue(warned.called)      # 원인을 찾을 수 있게 남긴다

    def test_한글_조회가_터져도_예외를_흘리지_않는다(self):
        broken = mock.Mock()
        broken.GetTextFile.side_effect = RuntimeError("COM 끊김")
        type(broken).SelectionMode = mock.PropertyMock(
            side_effect=RuntimeError("COM 끊김"))
        self._use(broken)
        # 일부러 터뜨리는 테스트라 app.log 에 오류를 남기지 않는다
        with mock.patch("hwp_palette.hwp.hwp_engine.applog.exc"):
            self.assertEqual(hwp_engine.read_selection_text(), "")
            self.assertFalse(hwp_engine.has_selection())


class ClipboardModuleTest(unittest.TestCase):
    """담는 쪽 — Tk 클립보드는 마지막 수단이어야 한다."""

    def test_윈도우_API가_있으면_Tk를_쓰지_않는다(self):
        win = mock.Mock()
        widget = mock.Mock()
        with mock.patch.object(clipboard, "_win32", return_value=win):
            self.assertTrue(clipboard.set_text("예문", widget=widget))
        win.SetClipboardData.assert_called_once()
        widget.clipboard_append.assert_not_called()

    def test_윈도우_API가_없으면_Tk로_물러난다(self):
        widget = mock.Mock()
        with mock.patch.object(clipboard, "_win32", return_value=None):
            self.assertTrue(clipboard.set_text("예문", widget=widget))
        widget.clipboard_append.assert_called_once_with("예문")

    def test_읽기는_모듈이_없으면_빈손(self):
        with mock.patch.object(clipboard, "_win32", return_value=None):
            self.assertEqual(clipboard.get_text(), "")


if __name__ == "__main__":
    unittest.main()
