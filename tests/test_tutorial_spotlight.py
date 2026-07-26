# -*- coding: utf-8 -*-
r"""여러 곳을 함께 짚기 · 코스가 창을 남기지 않기 (사용자 지적 2026-07-26).

  · "기호를 누르면 창 아래에 부르는 법이 나옵니다" — 누르는 곳과 결과가
    보이는 곳이 떨어져 있어, 하나만 짚으면 정작 봐야 할 아래쪽이 흐림에 가렸다.
  · 팔레트 코스의 마지막 단계는 메인 화면을 짚는데, 그 전에 팔레트 설정 창을
    닫지 않아 설정 창이 그 위에 남아 있었다.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import tutorial            # noqa: E402
import tutorials          # noqa: E402


class FakeWidget:
    """winfo_* 만 흉내 낸 위젯 — Tk 없이 좌표 계산을 검사한다."""

    def __init__(self, x, y, w, h, alive=True):
        self._geo = (x, y, w, h)
        self._alive = alive

    def winfo_exists(self):
        return self._alive

    def winfo_rootx(self):
        return self._geo[0]

    def winfo_rooty(self):
        return self._geo[1]

    def winfo_width(self):
        return self._geo[2]

    def winfo_height(self):
        return self._geo[3]

    def winfo_toplevel(self):
        return "창"


class RectTest(unittest.TestCase):

    def test_하나면_그_위젯의_사각형(self):
        self.assertEqual(tutorial._rect_of(FakeWidget(10, 20, 30, 40)),
                         (10, 20, 30, 40))

    def test_여러_개면_전체를_감싼다(self):
        """기호판(위) + 하단 안내줄(아래)을 한 구멍으로."""
        top = FakeWidget(100, 100, 200, 300)        # 기호판
        bottom = FakeWidget(80, 460, 300, 30)       # 창 맨 아래 안내줄
        self.assertEqual(tutorial._rect_of([top, bottom]),
                         (80, 100, 300, 390))

    def test_죽은_위젯은_빠진다(self):
        alive = FakeWidget(10, 10, 10, 10)
        dead = FakeWidget(0, 0, 500, 500, alive=False)
        self.assertEqual(tutorial._rect_of([alive, dead]), (10, 10, 10, 10))

    def test_아무것도_없으면_None(self):
        self.assertIsNone(tutorial._rect_of(None))
        self.assertIsNone(tutorial._rect_of([]))
        self.assertIsNone(tutorial._rect_of([FakeWidget(0, 0, 1, 1,
                                                        alive=False)]))

    def test_대상이_없으면_기준_창은_fallback(self):
        self.assertEqual(tutorial._base_of(None, "root"), "root")
        self.assertEqual(tutorial._base_of(FakeWidget(0, 0, 1, 1), "root"),
                         "창")


class CourseWindowTest(unittest.TestCase):
    """코스가 짚는 대상·닫는 창."""

    def setUp(self):
        self.opened = []

        class Ctx:
            def __getattr__(_self, name):
                return lambda *a, **k: True
        self.courses = tutorials.build(Ctx())

    def _course(self, key):
        return next(c for c in self.courses if c["key"] == key)

    def test_기호_호출법_단계는_두_곳_이상을_짚는다(self):
        step = next(s for s in self._course("symbol")["steps"]
                    if "부르는 법" in s.get("title", ""))
        got = step["widget"]()
        self.assertIsInstance(got, list)
        self.assertGreaterEqual(len(got), 2)

    def test_팔레트_코스는_마지막_전에_설정창을_닫는다(self):
        steps = self._course("palette")["steps"]
        self.assertIsNotNone(steps[-2].get("next_action"),
                             "마지막 단계는 메인 화면을 짚으므로 설정 창을 닫아야 한다")

    def test_설정창을_여는_코스는_닫는_단계도_갖는다(self):
        for course in self.courses:
            opens = any(s.get("next_action") or s.get("restore")
                        for s in course["steps"])
            if not opens:
                continue
            # 창을 여는 코스는 어딘가에서 닫는 일이 걸려 있어야 한다
            self.assertTrue(
                any(s.get("next_action") for s in course["steps"]),
                course["key"])


if __name__ == "__main__":
    unittest.main()
