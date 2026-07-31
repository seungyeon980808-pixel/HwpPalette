# -*- coding: utf-8 -*-
r"""물감 섞기 — 부품을 순서대로 펼치고 빈칸을 이어 채운다 (2026-07-29).

여기서 못 박는 것:
    ① 섞기는 **새 op 종류를 만들지 않는다** — 부품 수만큼의 template op 로
       펼쳐진다. 그래야 엔진이 섞기를 몰라도 그대로 돈다.
    ② 빈칸은 부품 순서대로 이어진다. 한 칸이라도 어긋나면 뒤가 통째로 밀리는데
       화면에는 아무 표시가 안 난다.
    ③ 부품이 없어지면 **조용히 넘어가지 않는다.**

한글 없이 순수 함수만 검사한다.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import parser       # noqa: E402


def lab(name):
    r"""이름 → `\이름\`.

    raw 문자열은 백슬래시로 끝날 수 없어서(`r"\발문\"` 는 문법 오류)
    이 작은 함수로 만든다 — 백슬래시를 겹쳐 쓴 리터럴보다 읽기 쉽다.
    """
    return "\\" + name + "\\"


def md(*lines):
    return "\n".join(lines)


LOOKUP = {
    "발문":  ("템플릿", {"name": "발문", "slot_count": 2}),
    "3보기": ("템플릿", {"name": "3보기", "slot_count": 3}),
    "5선지": ("템플릿", {"name": "5선지", "slot_count": 5}),
    "수능양식": ("양식", {"name": "수능양식", "slot_count": 2}),
    "기본문항": ("섞기", {"name": "기본문항",
                          "parts": ["발문", "3보기", "5선지"]}),
    "깨진문항": ("섞기", {"name": "깨진문항",
                          "parts": ["발문", "없는물감", "5선지"]}),
    "양식섞기": ("섞기", {"name": "양식섞기",
                          "parts": ["발문", "수능양식"]}),
}

FILLED = md(
    lab("기본문항"),
    "1", "3",                                     # 발문 2칸
    "맨틀은 크다", "외핵은 액체", "내핵은 차갑다",    # 3보기 3칸
    "ㄱ", "ㄴ", "ㄱ, ㄴ", "ㄴ, ㄷ", "ㄱ, ㄴ, ㄷ",    # 5선지 5칸
)


class 펼치기(unittest.TestCase):

    def test_부품_수만큼_template_op_로_펼쳐진다(self):
        ops, warns = parser.build_library_plan(FILLED, LOOKUP)
        self.assertEqual([o[0] for o in ops], ["template"] * 3)
        self.assertEqual([o[1]["name"] for o in ops], ["발문", "3보기", "5선지"])
        self.assertEqual(warns, [])

    def test_빈칸이_부품_순서대로_갈린다(self):
        ops, _w = parser.build_library_plan(FILLED, LOOKUP)
        self.assertEqual(ops[0][2], ["1", "3"])
        self.assertEqual(ops[1][2], ["맨틀은 크다", "외핵은 액체", "내핵은 차갑다"])
        self.assertEqual(ops[2][2], ["ㄱ", "ㄴ", "ㄱ, ㄴ", "ㄴ, ㄷ", "ㄱ, ㄴ, ㄷ"])

    def test_건너뛰기와_여러줄_덩어리도_그대로_먹는다(self):
        ops, _w = parser.build_library_plan(
            md(lab("기본문항"), "1", "-",
               "{첫 줄", "둘째 줄}", "ㄴ내용", "ㄷ내용",
               "ㄱ", "ㄴ", "ㄷ", "ㄱ, ㄴ", "ㄱ, ㄷ"), LOOKUP)
        self.assertEqual(ops[0][2][0], "1")
        self.assertIsNone(ops[0][2][1])          # `-` 는 그 빈칸을 비운다
        self.assertEqual(len(ops[1][2]), 3)      # { } 덩어리는 한 칸
        self.assertEqual(len(ops[2][2]), 5)

    def test_다음_삽입을_만나면_거기서_끊는다(self):
        ops, _w = parser.build_library_plan(
            md(lab("기본문항"), "1", "3", lab("발문"), "뒤", "칸"), LOOKUP)
        self.assertEqual(ops[0][2], ["1", "3"])       # 발문 몫만 채워졌다
        self.assertEqual(ops[-1][1]["name"], "발문")  # 그 뒤는 새 삽입


class 부품이_없을_때(unittest.TestCase):

    def test_없어진_부품은_경고를_남긴다(self):
        ops, warns = parser.build_library_plan(
            md(lab("깨진문항"), "1", "2"), LOOKUP)
        self.assertEqual([o[1]["name"] for o in ops], ["발문", "5선지"])
        self.assertTrue(any("없는물감" in w for w in warns), warns)

    def test_섞을_수_없는_분류는_건너뛰고_알린다(self):
        _ops, warns = parser.build_library_plan(
            md(lab("양식섞기"), "1", "2"), LOOKUP)
        self.assertTrue(any("수능양식" in w for w in warns), warns)


class 라벨_취급(unittest.TestCase):

    def test_섞기도_새_삽입의_시작이다(self):
        """앞 템플릿의 빈칸 채우기가 섞기 라벨에서 끊겨야 한다."""
        ops, _w = parser.build_library_plan(
            md(lab("5선지"), "가", lab("기본문항"), "1", "3"), LOOKUP)
        self.assertEqual(ops[0][1]["name"], "5선지")
        self.assertEqual(ops[0][2], ["가"])       # 한 칸만 먹고 끊겼다
        self.assertEqual(ops[1][1]["name"], "발문")


if __name__ == "__main__":
    unittest.main()
