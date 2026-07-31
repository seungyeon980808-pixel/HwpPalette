# -*- coding: utf-8 -*-
r"""2026-07-31 2차 피드백 반영분의 순수 로직 테스트.

무엇을 지키는가:
  · '기본 서식' 도구 폐지 — 카탈로그에서 빠지고, 이미 놓인 블럭도 걷힌다
  · 서식 물감을 팔레트 블럭(function)으로 놓을 수 있다 — 창고와 팔레트가
    같은 형식(actions)을 쓴다
  · 옛 캡처 형식(fields)도 계속 읽힌다 (style_actions / style_fields)
  · 수치 칸의 위아래 버튼 범위(func_catalog.SPIN)가 모든 수치 항목에 있다
  · 자간 맞춤 도구가 카탈로그와 실행표에 이어져 있다
"""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import builtin_actions        # noqa: E402
from hwp_palette.model import func_catalog           # noqa: E402
from hwp_palette.model import library                # noqa: E402
from hwp_palette.model import palette                # noqa: E402


class RetiredToolTest(unittest.TestCase):
    """'기본 서식'은 사용자 결정으로 없앤 도구다 (2026-07-31)."""

    def test_카탈로그에_없다(self):
        self.assertNotIn("reset_format", builtin_actions.ACTION_BY_KEY)
        self.assertNotIn("reset_format", builtin_actions.DEFAULT_MAIN_KEYS)

    def test_폐지_목록에_있다(self):
        self.assertIn("reset_format", builtin_actions.RETIRED_KEYS)

    def test_이미_놓인_블럭을_걷어낸다(self):
        tabs = [{"name": "메인", "cols": 8, "blocks": [
            {"type": "builtin", "key": "convert"},
            {"type": "builtin", "key": "reset_format"},
            {"type": "char", "value": "★"},
        ]}]
        self.assertTrue(palette._drop_retired_tools(tabs))
        keys = [b.get("key") for b in tabs[0]["blocks"]]
        self.assertNotIn("reset_format", keys)
        self.assertIn("convert", keys)          # 남은 것은 그대로
        self.assertEqual(len(tabs[0]["blocks"]), 2)

    def test_걷을_것이_없으면_안_건드린다(self):
        tabs = [{"name": "메인", "blocks": [{"type": "builtin",
                                             "key": "convert"}]}]
        self.assertFalse(palette._drop_retired_tools(tabs))


class SpacingFitToolTest(unittest.TestCase):
    """자간 맞춤 — 사용자가 '어떻게 쓰는지 알 수 없다'고 한 그 기능."""

    def test_카탈로그에_있다(self):
        self.assertIn("spacing_fit", builtin_actions.ACTION_BY_KEY)
        self.assertIn(builtin_actions.ACTION_BY_KEY["spacing_fit"],
                      builtin_actions.visible_actions())

    def test_이름과_설명이_있다(self):
        self.assertEqual(builtin_actions.name_of("spacing_fit"), "자간 맞춤")
        self.assertTrue(builtin_actions.hint_of("spacing_fit"))

    def test_엔진에_구현이_있다(self):
        from hwp_palette.hwp import engine_library
        self.assertTrue(callable(engine_library.fit_line_spacing))
        # 좁히기만 한다 — 넓히면 앞 줄이 다시 흔들린다 (스파이크 판정)
        self.assertLess(engine_library.FIT_MIN_PCT, 0)


class ToolConfigTest(unittest.TestCase):
    """설정이 필요한 도구는 그 사실을 데이터로 말한다 (창고가 [설정] 을 붙인다)."""

    def test_사진은_설정을_갖는다(self):
        self.assertEqual(builtin_actions.config_of("photo"), "photo_dirs")

    def test_설정이_없는_도구는_None(self):
        self.assertIsNone(builtin_actions.config_of("convert"))
        self.assertIsNone(builtin_actions.config_of("모르는키"))


class SpinRangeTest(unittest.TestCase):
    """수치 칸에는 전부 위아래 버튼이 붙어야 한다 (사용자 요청 2026-07-31)."""

    def test_모든_수치_항목에_범위가_있다(self):
        for f in func_catalog.FUNCTIONS:
            if f["kind"] != "number":
                continue
            with self.subTest(key=f["key"]):
                self.assertIn(f["key"], func_catalog.SPIN)
                lo, hi, step = func_catalog.SPIN[f["key"]]
                self.assertLess(lo, hi)
                self.assertGreater(step, 0)

    def test_기본값이_범위_안에_있다(self):
        for key, val in func_catalog.DEFAULTS.items():
            lo, hi, _step = func_catalog.SPIN[key]
            with self.subTest(key=key):
                self.assertGreaterEqual(val, lo)
                self.assertLessEqual(val, hi)


class StyleActionsTest(unittest.TestCase):
    """창고의 서식 물감 = 팔레트의 서식 조합 (같은 actions 형식)."""

    def test_새_형식은_그대로_돌려준다(self):
        acts = [{"func": "굵게"}, {"func": "글씨크기", "value": 12}]
        got = library.style_actions({"actions": acts})
        self.assertEqual(got, acts)

    def test_옛_캡처_형식도_읽힌다(self):
        old = {"fields": {"굵게": True, "크기": 12, "글꼴": "맑은 고딕",
                          "자간": -5}}
        got = {a["func"]: a.get("value") for a in library.style_actions(old)}
        self.assertIn("굵게", got)
        self.assertEqual(got["글씨크기"], 12)
        self.assertEqual(got["글씨체"], "맑은 고딕")
        self.assertEqual(got["자간"], -5)

    def test_옛_형식의_꺼진_토글은_안_담긴다(self):
        got = library.style_actions({"fields": {"굵게": False, "크기": 11}})
        self.assertNotIn("굵게", [a["func"] for a in got])

    def test_줄_일부에_걸_수_있는_것만_델타로(self):
        # 문단 조작(줄간격·정렬)은 한 줄 안의 몇 글자에 걸 수 없다
        item = {"actions": [{"func": "굵게"},
                            {"func": "줄간격", "value": 160},
                            {"func": "가운데정렬"},
                            {"func": "글씨크기", "value": 12}]}
        fields = library.style_fields(item)
        self.assertEqual(fields, {"굵게": True, "크기": 12})

    def test_옛_형식은_델타를_그대로_준다(self):
        self.assertEqual(library.style_fields({"fields": {"자간": -3}}),
                         {"자간": -3})


class StylePlacementTest(unittest.TestCase):
    """서식 물감은 팔레트에 놓을 수 있어야 한다 (예전에는 거절당했다)."""

    def test_놓을_수_있는_분류에_서식이_있다(self):
        from hwp_palette.ui import store_ui
        self.assertIn("서식", store_ui.PLACEABLE)

    def test_삭제_시_정리할_블럭_타입이_function(self):
        # 서식 물감을 지우면 그것을 가리키던 function 블럭이 함께 정리된다
        self.assertEqual(library._BLOCK_TYPE["서식"], "function")


class StyleStorageTest(unittest.TestCase):
    """서식 물감 저장·수정 (임시 창고)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        (root / "fragments").mkdir()
        for p in (mock.patch.object(library, "LIBRARY_PATH",
                                    root / "library.json"),
                  mock.patch.object(library, "FRAGMENTS_DIR",
                                    root / "fragments")):
            p.start()
            self.addCleanup(p.stop)
        library._load_cache.update({"tok": None, "data": None})
        self.addCleanup(lambda: library._load_cache.update(
            {"tok": None, "data": None}))

    def test_actions_로_저장하고_읽는다(self):
        acts = [{"func": "굵게"}, {"func": "줄간격", "value": 180}]
        iid = library.add_style("발문체", actions=acts, subcat="내신")
        it = library.find_by_id("서식", iid)
        self.assertEqual(library.style_actions(it), acts)
        self.assertEqual(library.subcat_of(it), "내신")

    def test_고치면_id_가_유지된다(self):
        iid = library.add_style("발문체", actions=[{"func": "굵게"}])
        self.assertTrue(library.update_style_actions(
            iid, name="발문체2", actions=[{"func": "기울임"}]))
        it = library.find_by_id("서식", iid)
        self.assertEqual(it["name"], "발문체2")
        self.assertEqual(library.style_actions(it), [{"func": "기울임"}])

    def test_새_형식으로_갈아타면_옛_형식은_지운다(self):
        iid = library.add_style("옛것", fields={"굵게": True})
        library.update_style_actions(iid, actions=[{"func": "밑줄"}])
        it = library.find_by_id("서식", iid)
        self.assertNotIn("fields", it)


if __name__ == "__main__":
    unittest.main()
