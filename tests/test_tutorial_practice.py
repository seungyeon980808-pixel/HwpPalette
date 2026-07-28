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

from hwp_palette.ui import tutorials            # noqa: E402


class FakeCtx:
    """main.py 의 _TutorialCtx 흉내 — 무엇을 넘겼는지만 받아 둔다."""

    def __init__(self, labels=None):
        self.calls = []
        # 이 사람 라이브러리에 있는 라벨 (None 이면 '뭐든 다 있다')
        self.labels = labels

    def has_label(self, label):
        return True if self.labels is None else label in self.labels

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

    def test_코스끼리_같은_예문을_쓰지_않는다(self):
        r"""'처음 시작하기'와 '마크다운 변환 익히기'가 같은 것을 가르치던 문제
        (사용자 지적 2026-07-26). 처음은 훑어보기, 마크다운 코스는 손에 익히기."""
        seen = {}
        for course in self.courses:
            for code in self._codes(course):
                key = code.strip()
                self.assertNotIn(key, seen,
                                 f"{course['key']} 와 {seen.get(key)} 의 예문이 같다")
                seen[key] = course["key"]

    def test_처음_시작하기는_짧게_끝난다(self):
        """훑어보기 코스이므로 실습이 두 개를 넘지 않는다."""
        start = next(c for c in self.courses if c["key"] == "start")
        self.assertLessEqual(len(self._codes(start)), 2)

    def test_이미_준비가_있는_단계는_덮어쓰지_않는다(self):
        """템플릿 코스 1단계의 '연습용 표 만들기'가 살아 있어야 한다."""
        template = next(c for c in self.courses if c["key"] == "template")
        first = template["steps"][0]
        self.assertIsNotNone(first.get("action"))
        self.assertIsNone(first.get("code"))    # 표를 만드는 단계 그대로


class FreshInstallTest(unittest.TestCase):
    r"""갓 설치한 사람(빈 라이브러리)에게도 튜토리얼이 멀쩡한가.

    v0.1.1 에 실려 나간 흠: '처음 시작하기'의 `\수능양식\` 실습은 만든 사람의
    라이브러리에만 있는 물감이라, 새 사용자는 첫 코스 실습에서 "등록되지 않은
    라벨"을 만났다 (2026-07-26 검진 → 2026-07-27 수정).
    """

    def _start(self, ctx):
        return next(c for c in tutorials.build(ctx) if c["key"] == "start")

    def test_라벨이_없으면_실습이_설명으로_바뀐다(self):
        step = next(s for s in self._start(FreshInstallTest._empty())["steps"]
                    if s.get("needs_label") == "수능양식")
        self.assertIsNone(step.get("code"), "실습이 남아 있으면 변환이 실패한다")
        self.assertIsNone(step.get("task"))
        self.assertIn("양식", step["text"])

    def test_라벨이_있으면_실습_그대로(self):
        ctx = FakeCtx(labels={"수능양식"})
        step = next(s for s in self._start(ctx)["steps"]
                    if s.get("needs_label") == "수능양식")
        self.assertEqual(step.get("code"), "\\수능양식\\")
        self.assertIsNotNone(step.get("task"))

    def test_단계_자체는_사라지지_않는다(self):
        """건너뛰면 양식이라는 것이 있다는 사실조차 모르고 지나간다."""
        full = len(self._start(FakeCtx(labels={"수능양식"}))["steps"])
        empty = len(self._start(FreshInstallTest._empty())["steps"])
        self.assertEqual(full, empty)

    def test_빠진_실습은_연습_문서에도_안_들어간다(self):
        """_fit_to_library 가 _with_example_doc 보다 먼저 돌아야 한다."""
        ctx = FreshInstallTest._empty()
        start = self._start(ctx)
        for step in start["steps"]:
            if step.get("code") and step.get("action"):
                step["action"]()
                break
        _title, examples = ctx.calls[0]
        self.assertNotIn("\\수능양식\\", [code for _t, code in examples])

    def test_판단이_안_되면_원래대로_둔다(self):
        """has_label 이 터져도 튜토리얼이 통째로 무너지면 안 된다."""
        class Broken(FakeCtx):
            def has_label(self, label):
                raise RuntimeError("라이브러리를 읽을 수 없음")
        step = next(s for s in self._start(Broken())["steps"]
                    if s.get("needs_label") == "수능양식")
        self.assertEqual(step.get("code"), "\\수능양식\\")

    @staticmethod
    def _empty():
        return FakeCtx(labels=set())


if __name__ == "__main__":
    unittest.main()
