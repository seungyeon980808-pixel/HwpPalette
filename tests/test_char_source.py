# -*- coding: utf-8 -*-
r"""특수기호 목록은 **두 창이 같은 규칙**을 쓴다 (2026-08-01, 피드백 028).

회귀의 내력: 기호를 고르는 화면이 두 벌이었다. 창고의 '문자' 탭에는 묶음
목록과 내가 등록한 기호가 있었고, 팔레트 빈칸에서 여는 창에는 검색칸뿐이었다.
022("에셋별로 만들기 창은 하나")를 반영하며 **기능이 적은 쪽으로 합쳐**
사용자가 둘 다 잃었다.

    "원래 특수기호가 종류별로 잘 정리가 되어있었는데 왜 구조가 자기 마음대로
     변경된 것인지? 종류별로 분류되어 있어야 합니다.
     내가 추가한 특수기호도 들어가야하는거고요"

여기 검사는 **두 곳이 다시 갈라지는 것**을 막는다 — 갈라진 것이 원인이었다.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import srcpath                                     # noqa: E402

from hwp_palette.model import builtin_chars        # noqa: E402
from hwp_palette.ui import char_source             # noqa: E402


def _read(module):
    return srcpath.src(module).read_text(encoding="utf-8")


_MY = [{"id": "x1", "name": "내가 만든 기호", "label": "내기호", "text": "♣"}]


class Groups(unittest.TestCase):

    def test_전체와_내가_등록이_맨_앞(self):
        g = char_source.groups()
        self.assertEqual(g[:2], [char_source.ALL_GROUP, char_source.MY_GROUP])

    def test_묶음은_기호가_스스로_달고_온다(self):
        """하드코딩하면 기호를 더할 때 묶음이 안 따라온다."""
        g = char_source.groups()
        for _label, _text, grp in builtin_chars.BUILTINS:
            self.assertIn(grp, g)
        self.assertGreater(len(g), 10, "묶음이 열몇 갈래는 돼야 목록이 의미가 있다")
        self.assertEqual(len(g), len(set(g)), "묶음이 중복된다")


class Entries(unittest.TestCase):

    def setUp(self):
        p = mock.patch.object(char_source.library, "list_items",
                              lambda cat: list(_MY) if cat == "문자" else [])
        p.start()
        self.addCleanup(p.stop)

    def test_내가_등록한_것이_먼저_온다(self):
        out = char_source.entries()
        self.assertEqual(out[0]["kind"], "item")
        self.assertEqual(out[0]["group"], char_source.MY_GROUP)

    def test_내가_등록_묶음에는_내_것만(self):
        out = char_source.entries(char_source.MY_GROUP)
        self.assertEqual([e["kind"] for e in out], ["item"])

    def test_묶음을_고르면_그_묶음만(self):
        some = builtin_chars.BUILTINS[0][2]
        out = char_source.entries(some)
        self.assertTrue(out)
        self.assertEqual({e["group"] for e in out}, {some})
        self.assertNotIn("item", [e["kind"] for e in out])

    def test_전체에는_내_것과_내장이_함께(self):
        kinds = {e["kind"] for e in char_source.entries()}
        self.assertEqual(kinds, {"item", "builtin"})

    def test_검색은_내_것에도_걸린다(self):
        """내가 등록한 기호가 검색에서 빠지면 '안 보인다'가 그대로 돌아온다."""
        out = char_source.entries(query="내기호")
        self.assertIn("item", [e["kind"] for e in out])


class BothWindowsShareTheRule(unittest.TestCase):
    r"""두 창이 **각자 만들지 않는다** — 갈라진 것이 회귀의 원인이었다."""

    def test_창고가_공유_규칙을_쓴다(self):
        code = _read("library_ui")
        body = code.split("def _char_entries")[1].split("\n    def ")[0]
        self.assertIn("char_source.entries", body)
        chips = code.split("def _build_chips")[1].split("\n    def ")[0]
        self.assertIn("char_source.groups()", chips)

    def test_팔레트_창도_같은_규칙을_쓴다(self):
        code = _read("palette_ui")
        body = code.split("class _CharDialog")[1].split("\nclass ")[0]
        self.assertIn("char_source.entries", body)
        self.assertIn("char_source.groups()", body)

    def test_팔레트_창에_묶음_목록이_있다(self):
        """사용자가 잃었다고 말한 것 하나."""
        body = _read("palette_ui").split("class _CharDialog")[1].split("\nclass ")[0]
        self.assertIn("def _build_chips", body)

    def test_96개_상한이_없어졌다(self):
        r"""묶음이 생기면 상한이 필요 없다 — 묶음 하나가 그보다 작다.

        상한이 남아 있으면 '내가 등록한 기호'가 96번째 뒤로 밀려 또 안 보인다.
        """
        body = _read("palette_ui").split("class _CharDialog")[1].split("\nclass ")[0]
        self.assertNotIn("_SHOW_MAX", body)

    def test_큰_목록은_나눠_그린다(self):
        """상한을 없앤 대신 창고와 같은 방식으로 버벅임을 막는다."""
        body = _read("palette_ui").split("class _CharDialog")[1].split("\nclass ")[0]
        self.assertIn("_grid_job", body)
        self.assertIn("after_cancel", body)


if __name__ == "__main__":
    unittest.main()
