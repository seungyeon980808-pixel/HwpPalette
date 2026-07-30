# -*- coding: utf-8 -*-
r"""문항 엑셀 — 양식 만들기와 되읽기 (2026-07-29).

여기서 못 박는 것은 **이미 한 번 물렸던 두 가지**다:

  ① 말머리 떼기가 'ㄱ' 한 글자짜리 선지를 통째로 지웠다.
     예시가 '① ㄱ' 이라 가려져 있었고, 사람이 직접 'ㄱ' 이라고만 쓰면 터졌다.
  ② `}` 이스케이프가 사용자가 직접 쓴 \굵게{…} 의 닫는 괄호까지 먹었다.

한글도 엑셀도 없이 돈다 — openpyxl 만 있으면 된다.
"""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import excel_form      # noqa: E402
from hwp_palette.model import excel_read      # noqa: E402


def _slot_values(lines):
    """채우는 줄이 빈칸 몇 개를 먹는지 — `{ … }` 덩어리는 통째로 한 칸이다.

    (parser 가 세는 방식과 같다. 여기서 어긋나면 뒤의 점수·보기·선지가 통째로
    한 칸씩 밀린다 — 눈으로는 시험지가 다 채워진 것처럼 보이므로 무섭다.)
    """
    count, inside = 0, False
    for line in lines:
        if not inside:
            count += 1
            if line.startswith("{") and not line.rstrip().endswith("}"):
                inside = True
        elif line.rstrip().endswith("}"):
            inside = False
    return count


class 말머리(unittest.TestCase):

    def test_한_글자_선지는_말머리로_보지_않는다(self):
        """합답형 선지는 내용 자체가 'ㄱ' 'ㄱ, ㄴ' 이다."""
        got = excel_read._lines("ㄱ\nㄴ\nㄱ, ㄴ\nㄴ, ㄷ\nㄱ, ㄴ, ㄷ", 5)
        self.assertEqual(got, ["ㄱ", "ㄴ", "ㄱ, ㄴ", "ㄴ, ㄷ", "ㄱ, ㄴ, ㄷ"])

    def test_습관대로_붙여_쓴_말머리는_뗀다(self):
        self.assertEqual(excel_read._lines("① ㄱ\n② ㄴ", 2), ["ㄱ", "ㄴ"])
        self.assertEqual(excel_read._lines("ㄱ. 맨틀\nㄴ. 외핵", 2), ["맨틀", "외핵"])
        self.assertEqual(excel_read._lines("1) 첫째\n2) 둘째", 2), ["첫째", "둘째"])

    def test_모자란_칸은_빈_값으로_채운다(self):
        self.assertEqual(excel_read._lines("가\n나", 5), ["가", "나", "", "", ""])


class 이스케이프(unittest.TestCase):

    def test_직접_쓴_서식은_건드리지_않는다(self):
        t = "이에 대한 설명으로 \\굵게{옳지 않은} 것은?"
        self.assertEqual(excel_read._esc(t), t)

    def test_그냥_닫는_괄호는_글자로_피한다(self):
        self.assertEqual(excel_read._esc("f(x} 꼴"), "f(x\\} 꼴")


class 왕복(unittest.TestCase):
    """양식을 만들고 그대로 되읽으면 예시 5문항이 마크다운으로 나온다."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(pathlib.Path(self.dir.name) / "t.xlsx")

    def tearDown(self):
        self.dir.cleanup()

    def test_만들고_되읽는다(self):
        excel_form.build_workbook(self.path)
        md, report, answers = excel_read.read_workbook(self.path)
        self.assertEqual(len(answers), len(excel_form.SAMPLES))
        self.assertIn("문항 5개 읽음", report[0])
        self.assertIn("\\학교합답1사진5선지\\", md)

    def test_빈칸_개수가_템플릿과_맞는다(self):
        """한 줄이라도 어긋나면 점수·보기·선지가 통째로 한 칸씩 밀린다."""
        excel_form.build_workbook(self.path)
        md, _r, _a = excel_read.read_workbook(self.path)
        for block in md.strip().split("\n\n"):
            lines = block.split("\n")
            label = lines[0].strip("\\")
            if label not in excel_form.TEMPLATES:
                continue                       # 서술형(평문 + 표)
            self.assertEqual(_slot_values(lines[1:]),
                             len(excel_form.TEMPLATES[label]),
                             f"{label} 의 빈칸 수가 안 맞습니다")

    def test_고른_스타일이_파일_안에_남는다(self):
        """엑셀 하나가 자기 스타일을 안고 다녀야 나중에 같은 틀로 나간다."""
        if "수능형 3선지" not in excel_form.styles_for("합답형"):
            self.skipTest("수능형 조각이 등록돼 있지 않다")
        excel_form.build_workbook(self.path, styles={"합답형": "수능형 3선지"})
        md, _r, _a = excel_read.read_workbook(self.path)
        self.assertIn("\\합답형1사진3선지\\", md)


class 스타일(unittest.TestCase):

    def test_등록_안_된_조각은_고를_수_없다(self):
        for qtype in excel_form.QTYPES:
            for name in excel_form.styles_for(qtype):
                mapping = excel_form.mapping_of(qtype, name)
                self.assertTrue(mapping, f"{qtype}/{name} 에 틀 지도가 없습니다")

    def test_모든_템플릿_지도가_이름을_안다(self):
        """slots 이름을 excel_read 가 못 알아보면 그 칸이 조용히 비어 나간다."""
        known = {"번호", "지문", "발문", "배점", "사진1", "사진2",
                 "보기1", "보기2", "보기3",
                 "선1", "선2", "선3", "선4", "선5"}
        for label, slots in excel_form.TEMPLATES.items():
            self.assertLessEqual(set(slots), known, f"{label} 에 모르는 자리")


if __name__ == "__main__":
    unittest.main()
