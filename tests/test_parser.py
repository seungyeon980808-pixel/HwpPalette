# -*- coding: utf-8 -*-
r"""parser.py 순수 함수 테스트 (개선안 22).

여기 있는 것들은 한글(pyhwpx)이 없어도 돌아가는 함수만 다룬다. 한글을 띄워야
하는 엔진 쪽은 자동 테스트가 불가능하므로, '한글 없이 검증 가능한 경계'인
파싱 계층부터 덮는다.

실행:  python -m unittest discover -s tests
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import parser as md_parser        # noqa: E402


class ParseExamTest(unittest.TestCase):
    """시험문제 문법 파싱."""

    def test_기본_문항을_항목별로_나눈다(self):
        data = md_parser.parse(
            "발문: 다음 중 옳은 것은?\n"
            "질문: 이유를 쓰시오.\n"
            "선지5:\n①가\n②나\n③다\n④라\n⑤마\n"
        )
        self.assertEqual(data["stem"], "다음 중 옳은 것은?")
        self.assertEqual(data["question"], "이유를 쓰시오.")
        self.assertEqual(data["choices"], ["가", "나", "다", "라", "마"])
        self.assertEqual(data["choices_type"], "5")

    def test_선지_앞의_원문자는_떼어낸다(self):
        data = md_parser.parse("선지:\n①첫째\n둘째")
        self.assertEqual(data["choices"], ["첫째", "둘째"])

    def test_선지1과_선지3은_종류가_다르다(self):
        self.assertEqual(md_parser.parse("선지1:\n가")["choices_type"], "1")
        self.assertEqual(md_parser.parse("선지3:\n가")["choices_type"], "3")

    def test_여러_줄_발문은_한_줄로_이어붙인다(self):
        data = md_parser.parse("발문: 첫 줄\n이어지는 줄")
        self.assertEqual(data["stem"], "첫 줄 이어지는 줄")

    def test_자료는_줄바꿈을_유지한다(self):
        data = md_parser.parse("자료: 첫 줄\n둘째 줄")
        self.assertEqual(data["material"], "첫 줄\n둘째 줄")

    def test_보기의_ㄱ_접두어를_떼어낸다(self):
        data = md_parser.parse("보기:\nㄱ:첫째\nㄴ:둘째")
        self.assertEqual(data["bogi"], ["첫째", "둘째"])

    def test_사진자료와_실험자료는_종류로_구분된다(self):
        self.assertEqual(md_parser.parse("사진자료:")["material_type"], "photo")
        self.assertEqual(md_parser.parse("실험자료:")["material_type"], "experiment")

    def test_띄어쓴_키워드도_인식한다(self):
        # '발 문:' '자 료:' 처럼 사용자가 띄어 쓰는 습관을 지원한다
        self.assertEqual(md_parser.parse("발 문: 문제")["stem"], "문제")
        self.assertEqual(md_parser.parse("자 료: 내용")["material"], "내용")


class RecognizedContentTest(unittest.TestCase):
    """시험문제로 볼지 라이브러리 변환으로 볼지 가르는 분기."""

    def test_아무것도_없으면_인식_실패(self):
        self.assertFalse(md_parser.has_recognized_content(md_parser.parse("그냥 문장")))

    def test_발문만_있어도_부분_변환으로_인정(self):
        self.assertTrue(md_parser.has_recognized_content(md_parser.parse("발문: 문제")))

    def test_자료_키워드만_있어도_인정(self):
        # material_flag — 내용이 비어도 '자료:'를 썼으면 자료박스를 만든다
        self.assertTrue(md_parser.has_recognized_content(md_parser.parse("자료:")))


class StripCircledMarkersTest(unittest.TestCase):
    """기본 서식 되돌리기 시 원문자 제거."""

    def test_원문자와_뒤_공백_한_칸을_지운다(self):
        self.assertEqual(md_parser.strip_circled_markers("① 가나다"), "가나다")

    def test_여러_종류의_원문자를_모두_지운다(self):
        self.assertEqual(
            md_parser.strip_circled_markers("①가 ㉠나 ⓐ다"), "가 나 다")

    def test_원문자가_없으면_그대로_둔다(self):
        self.assertEqual(md_parser.strip_circled_markers("평범한 문장"), "평범한 문장")


class LibraryTokenTest(unittest.TestCase):
    r"""\라벨\ 문법 감지."""

    def test_라벨이_있으면_참(self):
        self.assertTrue(md_parser.has_library_tokens(r"앞 \인사말\ 뒤"))

    def test_라벨이_없으면_거짓(self):
        self.assertFalse(md_parser.has_library_tokens("그냥 문장"))

    def test_빈_입력도_안전하게_처리한다(self):
        self.assertFalse(md_parser.has_library_tokens(""))
        self.assertFalse(md_parser.has_library_tokens(None))


def _lookup(**kinds):
    """{라벨: (분류, 항목)} 형태의 가짜 라이브러리를 만든다."""
    out = {}
    for label, (cat, extra) in kinds.items():
        item = {"name": label, "label": label}
        item.update(extra)
        out[label] = (cat, item)
    return out


class BuildLibraryPlanTest(unittest.TestCase):
    r"""\라벨\ → 실행 계획. 이 프로젝트에서 가장 로직이 복잡한 순수 함수."""

    def test_문자_라벨은_줄_안에서_치환된다(self):
        lookup = _lookup(인사말=("문자", {"text": "안녕하세요"}))
        ops, warns = md_parser.build_library_plan(r"앞 \인사말\ 뒤", lookup)
        self.assertEqual(ops, [("line", "앞 안녕하세요 뒤")])
        self.assertEqual(warns, [])

    def test_등록되지_않은_라벨은_원문을_남기고_경고한다(self):
        # raw 문자열은 백슬래시로 끝날 수 없어 여기서는 이스케이프로 쓴다
        ops, warns = md_parser.build_library_plan("\\없는거\\", {})
        self.assertEqual(ops, [("line", "\\없는거\\")])
        self.assertEqual(len(warns), 1)
        self.assertIn("등록되지 않은", warns[0])

    def test_템플릿은_아랫줄들을_빈칸_수만큼_가져간다(self):
        lookup = _lookup(결재란=("템플릿", {"slot_count": 2, "file": "a.hwp"}))
        ops, _ = md_parser.build_library_plan(
            "\\결재란\\\n담당\n부장\n그 다음 줄", lookup)
        kind, item, fills = ops[0]
        self.assertEqual(kind, "template")
        self.assertEqual(item["name"], "결재란")
        self.assertEqual(fills, ["담당", "부장"])
        # 빈칸 수를 넘는 줄은 템플릿 몫이 아니라 일반 줄로 남는다
        self.assertEqual(ops[1], ("line", "그 다음 줄"))

    def test_하이픈_한_줄은_그_빈칸을_비운다(self):
        lookup = _lookup(결재란=("템플릿", {"slot_count": 2, "file": "a.hwp"}))
        ops, _ = md_parser.build_library_plan("\\결재란\\\n-\n부장", lookup)
        self.assertEqual(ops[0][2], [None, "부장"])

    def test_다음_라벨을_만나면_거기서_끊는다(self):
        lookup = _lookup(
            결재란=("템플릿", {"slot_count": 5, "file": "a.hwp"}),
            도장=("템플릿", {"slot_count": 1, "file": "b.hwp"}))
        ops, _ = md_parser.build_library_plan(
            "\\결재란\\\n담당\n\\도장\\\n인", lookup)
        self.assertEqual(ops[0][2], ["담당"])       # 5칸이지만 1줄에서 끊김
        self.assertEqual(ops[1][2], ["인"])

    def test_양식은_템플릿과_다른_종류로_계획된다(self):
        lookup = _lookup(표지=("양식", {"slot_count": 1, "file": "c.hwp"}))
        ops, _ = md_parser.build_library_plan("\\표지\\\n제목", lookup)
        self.assertEqual(ops[0][0], "form")
        self.assertEqual(ops[0][2], ["제목"])

    def test_빈칸_채울_줄_안의_문자_라벨도_치환된다(self):
        lookup = _lookup(
            결재란=("템플릿", {"slot_count": 1, "file": "a.hwp"}),
            학교=("문자", {"text": "대왕중학교"}))
        ops, _ = md_parser.build_library_plan("\\결재란\\\n\\학교\\ 교장", lookup)
        self.assertEqual(ops[0][2], ["대왕중학교 교장"])

    # ── { } 한 칸에 여러 줄 (2026-07-25) ─────────────────────────

    def test_중괄호로_묶으면_한_빈칸에_여러_줄(self):
        lookup = _lookup(문항=("템플릿", {"slot_count": 2, "file": "a.hwp"}))
        ops, warns = md_parser.build_library_plan(
            "\\문항\\\n{(가) 준비한다.\n(나) 측정한다.\n(다) 기록한다.}\n다음 칸",
            lookup)
        fills = ops[0][2]
        self.assertEqual(len(fills), 2)                 # 덩어리가 한 칸을 먹는다
        self.assertEqual(fills[0],
                         md_parser.MultiLine(("(가) 준비한다.", "(나) 측정한다.",
                                              "(다) 기록한다.")))
        self.assertEqual(fills[1], "다음 칸")
        self.assertEqual(warns, [])

    def test_중괄호를_따로_한_줄에_둬도_된다(self):
        lookup = _lookup(문항=("템플릿", {"slot_count": 1, "file": "a.hwp"}))
        ops, _ = md_parser.build_library_plan(
            "\\문항\\\n{\n가\n나\n}", lookup)
        self.assertEqual(ops[0][2][0], md_parser.MultiLine(("가", "나")))

    def test_한_줄짜리_덩어리도_된다(self):
        lookup = _lookup(문항=("템플릿", {"slot_count": 1, "file": "a.hwp"}))
        ops, _ = md_parser.build_library_plan("\\문항\\\n{한 줄}", lookup)
        self.assertEqual(ops[0][2][0], md_parser.MultiLine(("한 줄",)))

    def test_덩어리_안에서도_라벨과_서식이_된다(self):
        lookup = _lookup(문항=("템플릿", {"slot_count": 1, "file": "a.hwp"}),
                         학교=("문자", {"text": "대왕중"}))
        ops, _ = md_parser.build_library_plan(
            "\\문항\\\n{\\학교\\ 과학실\n\\굵게{주의}}", lookup)
        block = ops[0][2][0]
        self.assertEqual(block.lines[0], "대왕중 과학실")
        self.assertIsInstance(block.lines[1], list)      # 서식은 조각 목록

    def test_덩어리_안에서도_표가_만들어진다(self):
        # 실제 사용 형태: [실험 결과] 아래 표가 같은 빈칸에 들어간다.
        # 예전에는 덩어리 안의 \표3*3\ 을 '등록 안 된 라벨'로 보고 경고만 냈다.
        lookup = _lookup(문항=("템플릿", {"slot_count": 1, "file": "a.hwp"}))
        ops, warns = md_parser.build_library_plan(
            "\\문항\\\n{[실험 결과]\n\\표3*3\\\n1&2&3\n4&5&6\n7&8&9\n}", lookup)
        block = ops[0][2][0]
        self.assertEqual(block.lines[0], "[실험 결과]")
        table = block.lines[1]
        self.assertIsInstance(table, md_parser.Table)
        self.assertEqual((table.rows, table.cols), (3, 3))
        self.assertEqual(table.grid,
                         [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]])
        self.assertEqual(warns, [])

    def test_덩어리_안_표가_닫는_중괄호를_행으로_먹지_않는다(self):
        # 행이 모자랄 때 } 까지 표의 행으로 삼키면 덩어리가 안 닫힌다
        lookup = _lookup(문항=("템플릿", {"slot_count": 2, "file": "a.hwp"}))
        ops, warns = md_parser.build_library_plan(
            "\\문항\\\n{\\표3*2\\\n1&2\n}\n다음 칸", lookup)
        block = ops[0][2][0]
        self.assertEqual(block.lines[0].grid, [["1", "2"]])
        self.assertEqual(ops[0][2][1], "다음 칸")     # 덩어리가 제대로 닫혔다
        self.assertEqual(warns, [])

    def test_덩어리를_안_닫으면_경고한다(self):
        lookup = _lookup(문항=("템플릿", {"slot_count": 1, "file": "a.hwp"}))
        _, warns = md_parser.build_library_plan("\\문항\\\n{가\n나", lookup)
        self.assertTrue(any("닫는 }" in w for w in warns))

    # ── \표3*3\ (2026-07-25) ─────────────────────────────────────

    def test_표는_아랫줄들을_행으로_읽는다(self):
        ops, _ = md_parser.build_library_plan(
            "\\표3*3\\\n1&2&3\n4&5&6\n7&8&9", {})
        self.assertEqual(ops[0][0], "table")
        self.assertEqual(ops[0][1], 3)          # 행
        self.assertEqual(ops[0][2], 3)          # 열
        self.assertEqual(ops[0][3],
                         [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]])

    def test_표_행이_모자라도_만든다(self):
        ops, _ = md_parser.build_library_plan("\\표3*2\\\n1&2", {})
        self.assertEqual(ops[0][0], "table")
        self.assertEqual(ops[0][3], [["1", "2"]])   # 나머지 행은 빈 칸으로 남음

    def test_표_빈_칸은_하이픈(self):
        ops, _ = md_parser.build_library_plan("\\표1*3\\\n1&-&3", {})
        self.assertEqual(ops[0][3], [["1", None, "3"]])

    def test_표_셀_안에_라벨과_서식을_쓸_수_있다(self):
        lookup = _lookup(학교=("문자", {"text": "대왕중"}))
        ops, _ = md_parser.build_library_plan(
            "\\표1*2\\\n\\학교\\&\\굵게{중요}", lookup)
        row = ops[0][3][0]
        self.assertEqual(row[0], "대왕중")          # 문자 라벨은 치환
        self.assertIsInstance(row[1], list)         # 서식은 조각 목록으로

    def test_표_셀에_앰퍼샌드를_글자로_쓰려면_두_번(self):
        ops, _ = md_parser.build_library_plan("\\표1*2\\\nA&&B&C", {})
        self.assertEqual(ops[0][3], [["A&B", "C"]])

    def test_라벨_바로_뒤의_앰퍼샌드도_칸을_나눈다(self):
        # 라벨을 닫는 \ 때문에 \& 로 오해하면 안 된다 (이 문법을 고른 이유)
        lookup = _lookup(학교=("문자", {"text": "대왕중"}))
        ops, _ = md_parser.build_library_plan("\\표1*2\\\n\\학교\\&뒤", lookup)
        self.assertEqual(ops[0][3], [["대왕중", "뒤"]])

    def test_표_다음_표가_오면_거기서_끊는다(self):
        ops, _ = md_parser.build_library_plan(
            "\\표1*2\\\n1&2\n\\표1*2\\\n3&4", {})
        self.assertEqual(len(ops), 2)
        self.assertEqual(ops[0][3], [["1", "2"]])
        self.assertEqual(ops[1][3], [["3", "4"]])

    def test_표_크기가_터무니없으면_거부하고_원문을_남긴다(self):
        ops, warns = md_parser.build_library_plan("\\표999*999\\", {})
        self.assertEqual(ops[0][0], "line")
        self.assertTrue(any("표 크기" in w for w in warns))

    def test_등록한_라벨이_표보다_우선한다(self):
        # 라벨에 * 가 들어가 키워드 인자로 못 쓰므로 사전을 직접 만든다
        lookup = {"표2*2": ("문자", {"name": "표2*2", "label": "표2*2",
                                     "text": "내가 정한 것"})}
        ops, _ = md_parser.build_library_plan("\\표2*2\\", lookup)
        self.assertEqual(ops, [("line", "내가 정한 것")])

    def test_x_와_곱셈기호도_받아준다(self):
        # 기본은 * (한글 IME 에서 영문 전환 없이 쳐진다) 지만 x·× 도 같은 뜻
        for label in ("표1x2", "표1×2"):
            ops, _ = md_parser.build_library_plan(f"\\{label}\\\n가&나", {})
            self.assertEqual(ops[0][0], "table", label)
            self.assertEqual(ops[0][3], [["가", "나"]], label)

    # ── 양식 빈칸 ↔ 본문 경계 (시험지 한 장 통째 변환) ──────────────
    # 양식에도 빈칸이 있고 그 뒤에 본문이 이어지는 실제 사용 형태.
    # 어디까지가 양식 빈칸 몫이고 어디부터가 본문인지가 헷갈리기 쉬워 못박아 둔다.

    def test_양식_빈칸을_채우고_그_뒤는_본문이_된다(self):
        lookup = _lookup(
            수능양식=("양식", {"slot_count": 2, "file": "c.hwp"}),
            문제1=("템플릿", {"slot_count": 1, "file": "a.hwp"}))
        ops, _ = md_parser.build_library_plan(
            "\\수능양식\\\n물리학Ⅰ\n제4교시\n\\문제1\\\n1번 문제\n남는 줄", lookup)
        # 양식 바로 뒷줄 2개(=빈칸 수)만 양식 몫
        self.assertEqual(ops[0][0], "form")
        self.assertEqual(ops[0][2], ["물리학Ⅰ", "제4교시"])
        # 그다음부터는 본문 — 템플릿과 일반 줄로 이어진다
        self.assertEqual(ops[1][0], "template")
        self.assertEqual(ops[1][2], ["1번 문제"])
        self.assertEqual(ops[2], ("line", "남는 줄"))

    def test_양식_바로_뒤가_템플릿이면_양식_빈칸은_안_채워진다(self):
        # 사용자가 빈칸 채울 줄을 안 쓰고 바로 본문을 시작한 경우.
        # 템플릿 라벨은 '새 삽입 시작'이라 양식 빈칸 채우기를 여기서 끊는다.
        lookup = _lookup(
            수능양식=("양식", {"slot_count": 2, "file": "c.hwp"}),
            문제1=("템플릿", {"slot_count": 1, "file": "a.hwp"}))
        ops, _ = md_parser.build_library_plan(
            "\\수능양식\\\n\\문제1\\\n1번 문제", lookup)
        self.assertEqual(ops[0][0], "form")
        self.assertEqual(ops[0][2], [])          # 양식 빈칸은 비워둔 채로
        self.assertEqual(ops[1][0], "template")
        self.assertEqual(ops[1][2], ["1번 문제"])

    def test_양식_빈칸을_건너뛰고_싶으면_하이픈(self):
        lookup = _lookup(
            수능양식=("양식", {"slot_count": 2, "file": "c.hwp"}),
            문제1=("템플릿", {"slot_count": 1, "file": "a.hwp"}))
        ops, _ = md_parser.build_library_plan(
            "\\수능양식\\\n-\n제4교시\n\\문제1\\\n1번 문제", lookup)
        self.assertEqual(ops[0][2], [None, "제4교시"])
        self.assertEqual(ops[1][0], "template")

    def test_템플릿_라벨이_줄_중간에_있으면_경고한다(self):
        lookup = _lookup(결재란=("템플릿", {"slot_count": 1, "file": "a.hwp"}))
        ops, warns = md_parser.build_library_plan(r"앞 \결재란\ 뒤", lookup)
        self.assertEqual(ops[0][0], "line")          # 템플릿으로 처리되지 않음
        self.assertIn("단독으로", warns[0])

    def test_양식_라벨이_줄_중간에_있으면_양식이라고_경고한다(self):
        # 등록은 돼 있는데 '등록되지 않은 라벨'이라고 알려주던 버그
        lookup = _lookup(표지=("양식", {"slot_count": 1, "file": "c.hwp"}))
        _, warns = md_parser.build_library_plan(r"앞 \표지\ 뒤", lookup)
        self.assertIn("양식", warns[0])
        self.assertNotIn("등록되지 않은", warns[0])

    def test_빈_줄은_빈칸_채우기에서_건너뛴다(self):
        lookup = _lookup(결재란=("템플릿", {"slot_count": 2, "file": "a.hwp"}))
        ops, _ = md_parser.build_library_plan(
            "\\결재란\\\n담당\n\n부장", lookup)
        self.assertEqual(ops[0][2], ["담당", "부장"])

    def test_줄바꿈_형식이_달라도_같게_처리한다(self):
        lookup = _lookup(결재란=("템플릿", {"slot_count": 1, "file": "a.hwp"}))
        for newline in ("\n", "\r\n", "\r"):
            ops, _ = md_parser.build_library_plan(
                f"\\결재란\\{newline}담당", lookup)
            self.assertEqual(ops[0][2], ["담당"], f"{newline!r} 처리 실패")


class StyleTokenTest(unittest.TestCase):
    r"""서식 명령 하나를 해석하는 규칙 (\굵게, \15, \크기15, \색빨강, \함초롬바탕)."""

    def setUp(self):
        self.lookup = _lookup(내강조=("서식", {"fields": {"굵게": True,
                                                        "글자색": 255}}))
        self.warns = []

    def r(self, tok):
        return md_parser.resolve_style_token(tok, self.lookup, self.warns)

    def test_토글(self):
        self.assertEqual(self.r("굵게"), {"굵게": True})
        self.assertEqual(self.r("기울임"), {"기울임": True})
        self.assertEqual(self.r("밑줄"), {"밑줄": True})

    def test_맨_숫자는_크기로_본다(self):
        self.assertEqual(self.r("15"), {"크기": 15.0})
        self.assertEqual(self.r("10.5"), {"크기": 10.5})

    def test_이름_붙인_값(self):
        self.assertEqual(self.r("크기15"), {"크기": 15.0})
        self.assertEqual(self.r("자간-5"), {"자간": -5})

    def test_색_이름과_코드(self):
        self.assertEqual(self.r("색빨강"), {"글자색": 255})          # R=255
        self.assertEqual(self.r("색#0000FF"), {"글자색": 255 << 16})  # B=255

    def test_아는_글꼴은_그대로(self):
        self.assertEqual(self.r("함초롬바탕"), {"글꼴": "함초롬바탕"})

    def test_목록에_없는_글꼴은_이름을_붙여_쓴다(self):
        self.assertEqual(self.r("글꼴나눔고딕"), {"글꼴": "나눔고딕"})

    def test_글꼴_오타는_조용히_통과시키지_않는다(self):
        # '함초롱'은 실제 글꼴명이 아니다 (함초롬바탕/함초롬돋움)
        self.assertIsNone(self.r("함초롱"))
        self.assertIn("모르는 서식", self.warns[0])

    def test_등록한_서식_라벨도_명령으로_쓴다(self):
        self.assertEqual(self.r("내강조"), {"굵게": True, "글자색": 255})

    def test_문단_서식은_거부하고_이유를_알려준다(self):
        self.assertIsNone(self.r("가운데정렬"))
        self.assertIn("문단 전체", self.warns[0])


class StyleSpanTest(unittest.TestCase):
    r"""서식 적용 문법 \굵게{내용} — LaTeX 구조 차용."""

    def setUp(self):
        self.lookup = _lookup(
            내강조=("서식", {"fields": {"굵게": True}}),
            인사말=("문자", {"text": "안녕하세요"}),
            결재란=("템플릿", {"slot_count": 1, "file": "a.hwp"}),
        )

    def _rich(self, text):
        return md_parser.build_library_plan(text, self.lookup)

    def test_감싼_구간에만_서식이_붙는다(self):
        ops, _ = self._rich("다음 중 \\굵게{옳지 않은} 것은?")
        self.assertEqual(ops[0][0], "rich_line")
        segs = ops[0][1]
        self.assertEqual([s["text"] for s in segs],
                         ["다음 중 ", "옳지 않은", " 것은?"])
        self.assertEqual([s["style"] for s in segs],
                         [None, {"굵게": True}, None])

    def test_명령을_여러_개_쌓는다(self):
        """원래 원했던 것 — 굵게+기울임+15pt 를 한 번에."""
        ops, _ = self._rich("\\굵게\\기울임\\크기15{나는 이제 할 수 있는게 없다.}")
        segs = ops[0][1]
        self.assertEqual(segs[0]["text"], "나는 이제 할 수 있는게 없다.")
        self.assertEqual(segs[0]["style"],
                         {"굵게": True, "기울임": True, "크기": 15.0})

    def test_쌓는_순서는_결과에_영향_없다(self):
        a, _ = self._rich("\\굵게\\크기15{x}")
        b, _ = self._rich("\\크기15\\굵게{x}")
        self.assertEqual(a[0][1][0]["style"], b[0][1][0]["style"])

    def test_내용_안에_라벨을_넣을_수_있다(self):
        """예전 \\...\\ 문법으로는 불가능했던 것."""
        ops, _ = self._rich("\\굵게{안녕 \\인사말\\ 님}")
        segs = ops[0][1]
        self.assertEqual(segs[0]["text"], "안녕 안녕하세요 님")
        self.assertEqual(segs[0]["style"], {"굵게": True})

    def test_내용_안에_빈칸_표시를_넣을_수_있다(self):
        """이것도 예전엔 불가능했다."""
        ops, _ = self._rich("\\굵게{준비물은 \\ 입니다}")
        segs = ops[0][1]
        self.assertEqual(segs[0]["text"], "준비물은 \\ 입니다")

    def test_중첩하면_바깥_서식_위에_덧씌운다(self):
        ops, _ = self._rich("\\굵게{가 \\기울임{나} 다}")
        segs = ops[0][1]
        self.assertEqual([s["text"] for s in segs], ["가 ", "나", " 다"])
        self.assertEqual(segs[0]["style"], {"굵게": True})
        self.assertEqual(segs[1]["style"], {"굵게": True, "기울임": True})
        self.assertEqual(segs[2]["style"], {"굵게": True})

    def test_안쪽이_바깥쪽을_덮어쓴다(self):
        ops, _ = self._rich("\\크기10{가 \\크기20{나}}")
        segs = ops[0][1]
        self.assertEqual(segs[1]["style"]["크기"], 20.0)

    def test_등록한_서식에_즉석_지정을_덧붙인다(self):
        ops, _ = self._rich("\\내강조\\크기15{내용}")
        self.assertEqual(ops[0][1][0]["style"], {"굵게": True, "크기": 15.0})

    def test_역슬래시_두_개는_글자_역슬래시(self):
        ops, _ = self._rich("경로는 C:\\\\폴더 입니다")
        self.assertEqual(ops[0], ("line", "경로는 C:\\폴더 입니다"))

    def test_모르는_명령이면_서식으로_보지_않는다(self):
        """안전장치 — 우연한 일치가 서식으로 오해받으면 안 된다."""
        ops, warns = self._rich("\\없는것{내용}")
        self.assertEqual(ops[0][0], "line")
        self.assertIn("모르는 서식", warns[0])

    def test_닫는_중괄호가_없으면_알려준다(self):
        _, warns = self._rich("\\굵게{안 닫음")
        self.assertTrue(any("닫는 }" in w for w in warns))

    def test_서식이_없으면_기존대로_line(self):
        ops, _ = self._rich("그냥 문장")
        self.assertEqual(ops[0], ("line", "그냥 문장"))

    def test_템플릿_줄은_서식보다_우선한다(self):
        ops, _ = self._rich("\\결재란\\\n담당")
        self.assertEqual(ops[0][0], "template")

    def test_서식_라벨을_내용_없이_쓰면_안내한다(self):
        _, warns = self._rich("\\내강조\\")
        self.assertIn("적용할 내용이 필요", warns[0])

    def test_has_library_tokens가_새_문법도_인식한다(self):
        # 이게 안 되면 변환 자체가 라이브러리 경로로 안 간다
        self.assertTrue(md_parser.has_library_tokens("\\굵게{내용}"))
        self.assertTrue(md_parser.has_library_tokens("\\인사말\\"))
        self.assertFalse(md_parser.has_library_tokens("그냥 문장"))


class PhotoLabelTest(unittest.TestCase):
    r"""\사진이름\ — 사진 폴더 파일을 라벨로 부르기."""

    def setUp(self):
        self.lookup = _lookup(
            인사말=("문자", {"text": "안녕하세요"}),
            굵게=("서식", {"fields": {"굵게": True}}),
        )
        self.lookup["실험사진1"] = ("사진", {"name": "실험사진1",
                                            "path": r"C:\photos\실험사진1.png"})

    def _plan(self, text):
        return md_parser.build_library_plan(text, self.lookup)

    def test_사진_라벨은_image_조각이_된다(self):
        ops, warns = self._plan("앞 \\실험사진1\\ 뒤")
        self.assertEqual(warns, [])
        self.assertEqual(ops[0][0], "rich_line")
        segs = ops[0][1]
        self.assertEqual(segs[0]["text"], "앞 ")
        self.assertEqual(segs[1].get("image"), r"C:\photos\실험사진1.png")
        self.assertEqual(segs[2]["text"], " 뒤")

    def test_사진만_한_줄이어도_된다(self):
        ops, _ = self._plan("\\실험사진1\\")
        self.assertEqual(ops[0][0], "rich_line")
        self.assertEqual(ops[0][1][0].get("image"), r"C:\photos\실험사진1.png")

    def test_문자와_사진을_한_줄에_섞는다(self):
        ops, _ = self._plan("\\인사말\\ \\실험사진1\\")
        segs = ops[0][1]
        self.assertEqual(segs[0]["text"], "안녕하세요 ")
        self.assertTrue(segs[1].get("image"))

    def test_서식_안의_사진도_넣을_수_있다(self):
        # \굵게{...} 안의 사진 — 사진엔 서식이 안 먹지만 글자엔 먹어야 한다
        ops, _ = self._plan("\\굵게{제목 \\실험사진1\\}")
        segs = ops[0][1]
        self.assertEqual(segs[0]["style"], {"굵게": True})
        self.assertTrue(segs[1].get("image"))

    def test_사진_단독_줄은_빈칸에_들어간다(self):
        # 사진은 '내용' 라벨이므로 빈칸을 채운다.
        # (예전에는 여기서 채우기가 끊겨 사진이 템플릿 뒤로 밀려났다 —
        #  \합답1사진3선지\ 처럼 사진 자리를 가진 템플릿을 쓸 수 없던 원인)
        lookup = dict(self.lookup)
        lookup["결재란"] = ("템플릿", {"name": "결재란", "slot_count": 2,
                                       "file": "a.hwp"})
        ops, _ = md_parser.build_library_plan(
            "\\결재란\\\n담당\n\\실험사진1\\", lookup)
        self.assertEqual(len(ops), 1)                # 뒤로 새는 줄이 없다
        self.assertEqual(ops[0][0], "template")
        fills = ops[0][2]
        self.assertEqual(fills[0], "담당")
        self.assertIsInstance(fills[1], list)        # 조각 목록 = 사진이 든 빈칸
        self.assertTrue(fills[1][0].get("image"))

    def test_템플릿_라벨은_여전히_빈칸_채우기를_끊는다(self):
        # 사진과 달리 템플릿·양식은 '다음 삽입 시작'이므로 여기서 끊겨야 한다
        lookup = dict(self.lookup)
        lookup["결재란"] = ("템플릿", {"name": "결재란", "slot_count": 3,
                                       "file": "a.hwp"})
        lookup["도장"] = ("템플릿", {"name": "도장", "slot_count": 1, "file": "b.hwp"})
        ops, _ = md_parser.build_library_plan(
            "\\결재란\\\n담당\n\\도장\\\n인", lookup)
        self.assertEqual(ops[0][2], ["담당"])
        self.assertEqual(ops[1][0], "template")

    def test_미등록_라벨은_여전히_빈칸_채우기를_끊는다(self):
        # 무엇인지 모르는 것을 빈칸에 밀어 넣지 않는다 (예전 동작 유지)
        lookup = dict(self.lookup)
        lookup["결재란"] = ("템플릿", {"name": "결재란", "slot_count": 3,
                                       "file": "a.hwp"})
        ops, _ = md_parser.build_library_plan(
            "\\결재란\\\n담당\n\\없는것\\", lookup)
        self.assertEqual(ops[0][2], ["담당"])

    def test_빈칸_채우기_줄에_글자와_섞인_사진도_들어간다(self):
        lookup = dict(self.lookup)
        lookup["결재란"] = ("템플릿", {"name": "결재란", "slot_count": 1,
                                       "file": "a.hwp"})
        ops, warns = md_parser.build_library_plan(
            "\\결재란\\\n이름 \\실험사진1\\ 옆", lookup)
        self.assertFalse(any("사진을 넣을 수 없어" in w for w in warns))
        segs = ops[0][2][0]
        self.assertIsInstance(segs, list)
        self.assertTrue(any(s.get("image") for s in segs))
        self.assertEqual("".join(s["text"] for s in segs), "이름  옆")

    def test_어디에도_없는_라벨_경고에_사진_폴더가_언급된다(self):
        _, warns = self._plan("\\없는것\\")
        self.assertIn("사진 폴더", warns[0])


class SplitSelectionUnitsTest(unittest.TestCase):
    r"""표에서 여러 셀을 선택했을 때의 조각 나누기.

    한글은 셀 블록을 복사하면 열을 탭, 행을 줄바꿈으로 이어 붙여 준다.
    탭을 경계로 안 보면 두 셀이 한 줄로 묶여, 변환 결과가 한 셀에 몰린다.
    """

    def test_탭은_셀_경계다(self):
        units = md_parser.split_selection_units("\\문제2-1\\\t\\문제2-2\\")
        self.assertEqual(units, ["\\문제2-1\\", "\\문제2-2\\"])

    def test_행과_열을_읽는_순서대로_편다(self):
        units = md_parser.split_selection_units("가\t나\r\n다\t라")
        self.assertEqual(units, ["가", "나", "다", "라"])

    def test_빈_셀은_빠진다(self):
        units = md_parser.split_selection_units("가\t\t나\n\n다")
        self.assertEqual(units, ["가", "나", "다"])

    def test_표가_아닌_여러_줄도_줄마다_쪼갠다(self):
        units = md_parser.split_selection_units("첫 줄\n둘째 줄")
        self.assertEqual(units, ["첫 줄", "둘째 줄"])

    def test_빈_입력은_빈_목록(self):
        self.assertEqual(md_parser.split_selection_units(""), [])
        self.assertEqual(md_parser.split_selection_units(None), [])


if __name__ == "__main__":
    unittest.main()
