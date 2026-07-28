# -*- coding: utf-8 -*-
"""전역 단축키의 순수 규칙 (2026-07-25) — 창·윈도우 API 없이 검증.

등록 자체는 윈도우가 필요하지만, 조합을 읽는 부분은 순수 함수라 여기서 덮는다.
"""

import pathlib
import sys
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


if __name__ == "__main__":
    unittest.main()
