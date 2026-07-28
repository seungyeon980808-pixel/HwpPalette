# -*- coding: utf-8 -*-
"""변환 미리보기 요약 (UI 제안 5) — 한글 없이 검증.

main.py 는 임포트하면 창을 띄우므로, 요약 함수만 떼어 같은 규칙으로 검증한다.
(규칙이 바뀌면 여기서 먼저 깨지도록 실제 구현을 읽어와 비교한다)
"""

import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from tests.srcpath import src        # noqa: E402

MAIN = src("app")


def _load_plan_summary():
    """main.py 에서 _plan_summary 정의만 떼어 실행한다 (창을 안 띄우려고)."""
    src = MAIN.read_text(encoding="utf-8")
    m = re.search(r"def _plan_summary\(ops, warns\):.*?\n(?=\n\ndef )", src, re.S)
    if not m:
        raise AssertionError("main.py 에서 _plan_summary 를 못 찾았습니다")
    ns = {}
    exec(m.group(0), ns)
    return ns["_plan_summary"]


plan_summary = _load_plan_summary()


class PlanSummaryTest(unittest.TestCase):

    def test_빈_계획(self):
        self.assertEqual(plan_summary([], []), "바꿀 내용 없음")

    def test_글자_줄만(self):
        self.assertEqual(plan_summary([("line", "가"), ("line", "나")], []),
                         "글자 줄 2개")

    def test_템플릿의_빈칸을_센다(self):
        ops = [("template", {"name": "결재란"}, ["담당", "부장"])]
        self.assertEqual(plan_summary(ops, []), "템플릿 1개 · 빈칸 2개 채움")

    def test_양식도_빈칸을_센다(self):
        ops = [("form", {"name": "표지"}, ["제목"])]
        self.assertEqual(plan_summary(ops, []), "양식 1개 · 빈칸 1개 채움")

    def test_서식_적용_줄(self):
        self.assertEqual(plan_summary([("rich_line", [{}])], []),
                         "서식 적용 줄 1개")

    def test_주의_건수가_붙는다(self):
        out = plan_summary([("line", "가")], ["없는 라벨", "또 없음"])
        self.assertIn("주의 2건", out)

    def test_여러_종류가_섞인_계획(self):
        ops = [("line", "가"),
               ("template", {"name": "t"}, ["a", "b"]),
               ("rich_line", [{}])]
        out = plan_summary(ops, [])
        for expect in ("글자 줄 1개", "템플릿 1개", "서식 적용 줄 1개",
                       "빈칸 2개 채움"):
            self.assertIn(expect, out)


def _load_form_plan_conflict():
    """main.py 에서 _form_plan_conflict 정의만 떼어 실행한다 (창을 안 띄우려고)."""
    src = MAIN.read_text(encoding="utf-8")
    m = re.search(r"def _form_plan_conflict\(ops\):.*?\n(?=\n\ndef )", src, re.S)
    if not m:
        raise AssertionError("main.py 에서 _form_plan_conflict 를 못 찾았습니다")
    ns = {}
    exec(m.group(0), ns)
    return ns["_form_plan_conflict"]


form_conflict = _load_form_plan_conflict()


class FormPlanConflictTest(unittest.TestCase):
    r"""양식은 문서 전체를 여는 것이라 **맨 앞**에만 올 수 있다 (2026-07-24).

    예전에는 '양식과 다른 내용이 섞이면 무조건 거부'였다. 그 규칙 때문에
    시험지처럼 "양식 + 문제들"을 한 번에 변환할 수가 없었다. 지금은 양식 뒤에
    오는 내용은 양식 문서의 본문 자리에 이어 들어가므로 허용한다.
    """

    FORM = ("form", {"name": "수능양식"}, [])

    def test_양식만_있으면_통과(self):
        self.assertIsNone(form_conflict([self.FORM]))

    def test_양식_뒤에_내용이_와도_통과(self):
        # 이게 이번 변경의 핵심 — 예전에는 여기서 거부했다.
        ops = [self.FORM,
               ("template", {"name": "문제1"}, ["1", "어쩌구"]),
               ("line", "이에 대한 설명으로 옳은 것은?")]
        self.assertIsNone(form_conflict(ops))

    def test_양식_앞에_내용이_있으면_거부(self):
        # 양식이 문서를 새로 열어버리므로 앞 내용은 갈 곳이 없다.
        ops = [("line", "머리말"), self.FORM]
        msg = form_conflict(ops)
        self.assertIsNotNone(msg)
        self.assertIn("맨 위", msg)

    def test_양식_앞의_빈_줄은_괜찮다(self):
        ops = [("line", "   "), ("line", ""), self.FORM, ("line", "본문")]
        self.assertIsNone(form_conflict(ops))

    def test_양식이_여러_개면_거부(self):
        ops = [self.FORM, ("form", {"name": "가정통신문"}, [])]
        msg = form_conflict(ops)
        self.assertIsNotNone(msg)
        self.assertIn("여러 개", msg)

    def test_양식이_없으면_통과(self):
        self.assertIsNone(form_conflict([("line", "가"), ("line", "나")]))


if __name__ == "__main__":
    unittest.main()
