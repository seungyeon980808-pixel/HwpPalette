# -*- coding: utf-8 -*-
r"""튜토리얼 연습 문서 회귀 테스트 (사용자 요청 2026-07-26).

"실습형 예제가 나오는 경우에는 예제가 들어가 있는 한글 창을 띄워 달라 —
한글창에 예제가 가득하면 어떻게 변하는지 직관적으로 알 수 있다."

지켜야 할 것:
  · 실습(code)이 있는 코스는 **첫 실습 단계에서 한 번** 연습 문서를 연다
  · 그 코스의 예문을 **빠짐없이** 넘긴다 (예문을 두 곳에 적어 두지 않는다)
  · 예문마다 **단계 제목을 함께** 넘긴다 ("예문 4가 뭐냐"가 되지 않게)
  · 이미 준비(action)가 있는 단계는 덮어쓰지 않는다 (템플릿 코스의 연습용 표)
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import tutorials            # noqa: E402


class FakeCtx:
    """main.py 의 _TutorialCtx 흉내 — 무엇을 넘겼는지만 받아 둔다."""

    def __init__(self):
        self.calls = []

    def make_example_doc(self, examples, title=""):
        self.calls.append((title, list(examples)))
        return True

    def __getattr__(self, name):
        return lambda *a, **k: None


class ExampleDocWiringTest(unittest.TestCase):

    def setUp(self):
        self.ctx = FakeCtx()
        self.courses = tutorials.build(self.ctx)

    def _codes(self, course):
        return [s["code"] for s in course["steps"] if s.get("code")]

    def _titles(self, course):
        return [s.get("title", "") for s in course["steps"] if s.get("code")]

    def test_실습이_있는_코스는_연습_문서를_한_번만_연다(self):
        for course in self.courses:
            with_code = [s for s in course["steps"] if s.get("code")]
            openers = [s for s in course["steps"]
                       if s.get("code") and s.get("action")]
            if with_code:
                self.assertEqual(len(openers), 1, course["key"])
            else:
                self.assertEqual(openers, [], course["key"])

    def test_연습_문서는_그_코스의_예문을_다_받는다(self):
        for course in self.courses:
            codes = self._codes(course)
            if not codes:
                continue
            self.ctx.calls.clear()
            for step in course["steps"]:
                if step.get("code") and step.get("action"):
                    step["action"]()
                    break
            self.assertEqual(len(self.ctx.calls), 1, course["key"])
            title, passed = self.ctx.calls[0]
            self.assertEqual([c for _, c in passed], codes, course["key"])
            self.assertEqual([t for t, _ in passed], self._titles(course),
                             course["key"])
            self.assertEqual(title, course["title"])

    def test_예문마다_단계_제목이_붙는다(self):
        """문서에 '[실습 4] 시험문제는 전용 문법으로' 처럼 적히게."""
        for course in self.courses:
            if not self._codes(course):
                continue
            self.ctx.calls.clear()
            for step in course["steps"]:
                if step.get("code") and step.get("action"):
                    step["action"]()
                    break
            for step_title, _code in self.ctx.calls[0][1]:
                self.assertTrue(step_title, course["key"])

    def test_첫_실습_단계에_걸린다(self):
        """뒤쪽 실습에 걸리면 앞 단계에서 붙여넣을 곳이 없다."""
        for course in self.courses:
            steps = course["steps"]
            code_at = [i for i, s in enumerate(steps) if s.get("code")]
            if not code_at:
                continue
            opener = [i for i, s in enumerate(steps)
                      if s.get("code") and s.get("action")]
            self.assertEqual(opener[0], code_at[0], course["key"])

    def test_이미_준비가_있는_단계는_덮어쓰지_않는다(self):
        """템플릿 코스 1단계의 '연습용 표 만들기'가 살아 있어야 한다."""
        template = next(c for c in self.courses if c["key"] == "template")
        first = template["steps"][0]
        self.assertIsNotNone(first.get("action"))
        self.assertIsNone(first.get("code"))    # 표를 만드는 단계 그대로


if __name__ == "__main__":
    unittest.main()
