# -*- coding: utf-8 -*-
r"""물감 섞기(꾸러미) — 값이 요소마다 **차례대로** 나뉘어 들어가는가.

사용자 기획 (2026-07-31):
    물감 1·2·3 이 빈칸 2개씩이고 셋을 섞어 \숫자\ 로 이름 지었다면,

        \숫자\
        1 2 3 4 5 6   (여섯 줄)

    은 1↦(1,2) · 2↦(3,4) · 3↦(5,6) 으로 나뉘어, 셋을 이어 붙인 결과가 된다.

이 규칙이 깨지면 시험지가 조용히 어긋나므로(값이 한 칸씩 밀린다) 여기서
먼저 깨지게 둔다. 한글 없이 도는 순수 계획 검증이다.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import library, parser      # noqa: E402


def _tpl(iid, name, slots):
    return {"id": iid, "name": name, "label": name, "slot_count": slots}


class MixPlanTest(unittest.TestCase):
    def setUp(self):
        self.a = _tpl("a", "물감1", 2)
        self.b = _tpl("b", "물감2", 2)
        self.c = _tpl("c", "물감3", 2)
        self.mix = {"id": "m", "name": "숫자", "label": "숫자",
                    "mix": ["a", "b", "c"], "slot_count": 6,
                    "_mix_items": [self.a, self.b, self.c]}
        self.lookup = {"숫자": ("템플릿", self.mix)}

    def test_값이_요소마다_차례대로_나뉜다(self):
        ops, warn = parser.build_library_plan(
            "\\숫자\\\n1\n2\n3\n4\n5\n6", self.lookup)
        self.assertEqual([], warn)
        self.assertEqual(
            [("template", "물감1", ["1", "2"]),
             ("template", "물감2", ["3", "4"]),
             ("template", "물감3", ["5", "6"])],
            [(k, it["name"], f) for k, it, f in ops])

    def test_줄이_모자라면_뒤쪽_요소는_빈_채로_간다(self):
        """모자란다고 앞쪽으로 당겨오지 않는다 — 당기면 어긋남이 번진다."""
        ops, _ = parser.build_library_plan("\\숫자\\\n1\n2\n3", self.lookup)
        self.assertEqual([["1", "2"], ["3"], []],
                         [f for _k, _it, f in ops])

    def test_요소가_풀리지_않았으면_통째로_남는다(self):
        """_mix_items 가 없으면(요소를 못 찾음) 예전처럼 하나로 다룬다."""
        mix = dict(self.mix)
        mix.pop("_mix_items")
        ops, _ = parser.build_library_plan(
            "\\숫자\\\n1\n2", {"숫자": ("템플릿", mix)})
        self.assertEqual(1, len(ops))
        self.assertEqual("숫자", ops[0][1]["name"])


class MixReferenceTest(unittest.TestCase):
    """꾸러미는 요소를 **가리킨다** — 복사해 두지 않는다."""

    def setUp(self):
        self.a = _tpl("a", "선지 5택", 5)
        self.mix = {"id": "m", "name": "가", "mix": ["a"], "slot_count": 5}
        self.data = {"템플릿": [self.a, self.mix]}

    def test_요소를_고치면_꾸러미가_따라온다(self):
        self.a["slot_count"] = 3
        library._resolve_mixes(self.data)
        self.assertEqual(3, self.mix["slot_count"])

    def test_쓰이는_요소는_지울_수_없다(self):
        self.assertEqual(["가"], library.mix_users("a", self.data))

    def test_지워진_요소는_조용히_빠진다(self):
        self.assertEqual([], library.mix_members(
            {"mix": ["없는id"]}, {"템플릿": []}))


if __name__ == "__main__":
    unittest.main()
