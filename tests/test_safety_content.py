# -*- coding: utf-8 -*-
r"""내용 정확성 안전망 (2026-07 안전 점검, 묶음 D).

시험지·양식이 **소리 없이 틀린 내용으로 나오던** 사고들의 재발 방지 테스트다.
  · 선지 "ㄱ만 옳다" 가 "ㄱ" 으로 찍히던 것 (자모만 남기고 나머지를 버림)
  · 보기 ㄱ·ㄴ·ㄷ 이 길이순으로 재정렬돼 정답표와 어긋나던 것
  · AI 프롬프트의 빈칸 번호가 채우기 쪽 개수의 두 배로 부풀던 것
  · 속성 붙은 <hp:t xml:space="preserve"> 조각의 빈칸을 못 보던 것
  · 이름이 안 맞는 자리를 지워 버리고 성공으로 보고하던 것
  · "C# 프로그래밍" 이 "C" 로 잘리던 것
  · 저장 실패가 이전 결과물(_완성.hwpx)까지 0바이트로 만들던 것

전부 한글(COM) 없이 돈다 — HWPX 는 zip+XML 이고, 조판 엔진은 가짜 한글을 꽂는다.
"""

import pathlib
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.hwp import exam_engine        # noqa: E402
from hwp_palette.hwp import form_markdown      # noqa: E402
from hwp_palette.hwp import hwp_engine         # noqa: E402
from hwp_palette.model import form_fill        # noqa: E402
from hwp_palette.model import library          # noqa: E402


def make_hwpx(path, runs, raw_body=None):
    r"""글자 조각 목록(또는 body XML 그대로)으로 최소한의 가짜 HWPX 를 만든다."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("version.xml", "<version/>")
        if raw_body is None:
            raw_body = "".join(f"<hp:p><hp:run><hp:t>{t}</hp:t></hp:run></hp:p>"
                               for t in runs)
        zf.writestr("Contents/section0.xml",
                    f'<?xml version="1.0"?><hp:sec>{raw_body}</hp:sec>')


class TmpDirTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def _make(self, runs=None, raw_body=None, name="src.hwpx"):
        p = self.dir / name
        make_hwpx(p, runs or [], raw_body=raw_body)
        return p


# ── 1. 선지 자모 정돈 ─────────────────────────────────
class FmtChoiceTest(unittest.TestCase):

    def test_자모가_섞인_선지는_그대로_둔다(self):
        """"ㄱ만 옳다" 가 시험지에 "ㄱ" 으로 찍히던 사고의 재발 방지."""
        self.assertEqual(exam_engine._fmt_choice("ㄱ만 옳다"), "ㄱ만 옳다")
        self.assertEqual(exam_engine._fmt_choice("ㄱ, ㄴ만 옳다"), "ㄱ, ㄴ만 옳다")
        self.assertEqual(exam_engine._fmt_choice("ㄱ과 ㄷ"), "ㄱ과 ㄷ")

    def test_순수_자모_선지만_쉼표로_고르게_다듬는다(self):
        self.assertEqual(exam_engine._fmt_choice("ㄱ,ㄴ"), "ㄱ, ㄴ")
        self.assertEqual(exam_engine._fmt_choice("ㄱ, ㄷ"), "ㄱ, ㄷ")
        self.assertEqual(exam_engine._fmt_choice("ㄱ·ㄷ"), "ㄱ, ㄷ")
        self.assertEqual(exam_engine._fmt_choice(" ㄴ "), "ㄴ")

    def test_자모가_없는_선지는_그대로_둔다(self):
        self.assertEqual(exam_engine._fmt_choice("옳은 것 없음"), "옳은 것 없음")


# ── 2. 보기 순서 보존 ─────────────────────────────────
class BogiOrderTest(unittest.TestCase):

    def test_보기는_출제자가_쓴_순서_그대로_들어간다(self):
        """길이순 재정렬은 ㄱ·ㄴ·ㄷ 라벨을 바꿔 정답표를 어긋나게 한다."""
        items = ["다니엘 전지처럼 아주 긴 진술이다", "짧다", "중간 길이 진술"]
        data = {"stem": "", "num": "", "question": "",
                "bogi": list(items), "choices": [],
                "material_flag": False, "material_type": "basic"}
        with mock.patch.object(hwp_engine, "hwp", mock.MagicMock()), \
                mock.patch.object(exam_engine, "insert_bogi_box") as rec:
            exam_engine.insert_question(data)
        rec.assert_called_once_with(items)


# ── 3. 빈칸 번호 = 채우기 쪽 개수 ──────────────────────
class SlotNumberParityTest(unittest.TestCase):

    def test_이름표와_쌍_빈칸의_번호가_저장_개수와_같다(self):
        r"""프롬프트가 "빈칸 6개" 라는데 실제로는 3개면, AI 답 줄이 밀려
        둘째 답부터 엉뚱한 칸에 들어간다. 반드시 library.count_slots 와 같아야 한다."""
        md = "성명 \\\\ 학년 \\학년\\ 기타 \\"
        out, n = form_markdown._number_slots(md)
        self.assertEqual(n, library.count_slots(md))
        self.assertEqual(n, 3)
        self.assertIn("【빈칸1】", out)
        self.assertIn("【빈칸2:학년】", out)      # 이름표는 번호 안에 보인다
        self.assertIn("【빈칸3】", out)
        self.assertNotIn("학년【빈칸", out)       # 번호 둘이 이름을 감싸면 안 된다
        self.assertNotIn("\\", out)

    def test_본문_표시는_빈칸으로_세지_않는다(self):
        md = "\\본문\\ 제목 \\\\"
        out, n = form_markdown._number_slots(md)
        self.assertEqual(n, 1)
        self.assertEqual(n, library.count_slots(md))
        self.assertIn("〔여기부터 본문〕", out)

    def test_이름표만_있는_양식도_개수가_같다(self):
        md = "\\학년\\ \\반\\ \\학년\\"
        out, n = form_markdown._number_slots(md)
        self.assertEqual(n, library.count_slots(md))
        self.assertEqual(n, 3)


# ── 4. 속성 붙은 글자 조각 ────────────────────────────
class RunWithAttributesTest(TmpDirTest):

    def test_속성이_붙은_조각도_읽는다(self):
        p = self._make(raw_body=(
            '<hp:p><hp:run>'
            '<hp:t xml:space="preserve">\\학년\\</hp:t>'
            '</hp:run></hp:p>'))
        self.assertEqual(form_fill.read_runs(p), [(0, "\\학년\\")])

    def test_채운_뒤에도_속성이_살아남는다(self):
        src = self._make(raw_body=(
            '<hp:p><hp:run>'
            '<hp:t xml:space="preserve">\\학년\\</hp:t>'
            '</hp:run></hp:p>'))
        dst = self.dir / "out.hwpx"
        report = form_fill.fill_named(src, dst, {"학년": "3"})
        self.assertEqual(report["filled"], 1)
        raw = zipfile.ZipFile(dst).read("Contents/section0.xml").decode("utf-8")
        self.assertIn('<hp:t xml:space="preserve">3</hp:t>', raw)

    # (2026-08-01, 피드백 033-a) 아래 셋은 **뒤집혔다** — 예전에는 "자식 태그가
    # 든 조각은 못 채운다, 대신 hidden 으로 센다"가 규칙이었는데, 그 한계가
    # 수능양식의 "빈칸 2개 중 1개만 보인다"의 정체였다 (실측: 둘째 \\ 앞에
    # <hp:fwSpace/> 가 있었다). 이제 읽고 채우는 것이 규칙이다.
    def test_자식_태그가_든_조각도_읽고_채운다(self):
        src = self._make(raw_body=(
            '<hp:p><hp:run>'
            '<hp:t>머리<hp:lineBreak/>\\학년\\</hp:t>'
            '</hp:run></hp:p>'))
        # 읽기: 자식 태그는 공백으로 눕는다 — 태그 양쪽 홑 \ 가 쌍으로 붙어
        # 보이는 오인을 막는 규칙 (예전 _hidden_token_count 와 같다)
        self.assertEqual(form_fill.read_runs(src), [(0, "머리 \\학년\\")])
        dst = self.dir / "out.hwpx"
        report = form_fill.fill_named(src, dst, {"학년": "3"})
        self.assertEqual(report["filled"], 1)
        self.assertEqual(report["hidden"], 0)

    def test_자식_태그가_든_조각도_fill_이_바꾼다(self):
        src = self._make(raw_body=(
            '<hp:p><hp:run>'
            '<hp:t>머리<hp:lineBreak/>\\</hp:t>'
            '</hp:run></hp:p>'))
        dst = self.dir / "out.hwpx"
        self.assertEqual(form_fill.fill(src, dst, {0: "값"}), 1)
        raw = zipfile.ZipFile(dst).read("Contents/section0.xml").decode("utf-8")
        # 조각 통째로 갈린다 — 사용자가 눕힌 글 전체를 보고 대체 글을 줬다
        self.assertIn("<hp:t>값</hp:t>", raw)

    def test_자식_태그가_든_이름_자리도_목록에_잡힌다(self):
        src = self._make(raw_body=(
            '<hp:p><hp:run>'
            '<hp:t>머리<hp:lineBreak/>\\학년\\</hp:t>'
            '</hp:run></hp:p>'))
        self.assertEqual(form_fill.named_slots(src), [("학년", 1)])
        self.assertEqual(form_fill.hidden_slot_count(src), 0)

    def test_가려진_빈칸이_없으면_세기는_0이다(self):
        src = self._make(runs=["\\학년\\ 성명 \\\\"])
        self.assertEqual(form_fill.hidden_slot_count(src), 0)


# ── 5. 이름이 안 맞는 자리는 지우지 않는다 ─────────────
class FillNamedHonestyTest(TmpDirTest):

    def test_모르는_이름은_그대로_남기고_missing_으로_센다(self):
        """AI 가 이름을 바꿔 오면 예전엔 양식 전체가 빈 채로 나왔다."""
        src = self._make(["\\학년\\", "\\반\\"])
        dst = self.dir / "out.hwpx"
        report = form_fill.fill_named(src, dst, {"학년": "3"})
        self.assertEqual(report["filled"], 1)
        self.assertEqual(report["wiped"], 0)
        self.assertEqual(report["missing"], {"반": 1})
        self.assertEqual([t for _, t in form_fill.read_runs(dst)],
                         ["3", "\\반\\"])      # 반 은 토큰째 살아 있다

    def test_이름이_있는데_값이_비면_토큰만_지운다(self):
        """일부러 비워 둔 칸 — 인쇄물에 \\교시\\ 가 남으면 안 된다."""
        src = self._make(["\\학년\\", "\\반\\"])
        dst = self.dir / "out.hwpx"
        report = form_fill.fill_named(src, dst, {"학년": "3", "반": ""})
        self.assertEqual(report["filled"], 1)
        self.assertEqual(report["wiped"], 1)
        self.assertEqual(report["missing"], {})
        self.assertEqual([t for _, t in form_fill.read_runs(dst)], ["3", ""])

    def test_이름_없는_옛_빈칸도_같은_규칙이다(self):
        src = self._make(["\\"])
        dst = self.dir / "out.hwpx"
        report = form_fill.fill_named(src, dst, {})
        self.assertEqual(report["missing"], {f"{form_fill.UNNAMED_PREFIX}1": 1})
        self.assertEqual([t for _, t in form_fill.read_runs(dst)], ["\\"])


# ── 6. 마크다운 값 해석 ───────────────────────────────
class ParseNamedMarkdownTest(unittest.TestCase):

    def test_값_속의_샵은_살아남는다(self):
        vals, dropped = form_fill.parse_named_markdown("과목: C# 프로그래밍")
        self.assertEqual(vals, {"과목": "C# 프로그래밍"})
        self.assertEqual(dropped, [])

    def test_공백_뒤_샵_꼬리_주석만_지운다(self):
        vals, _ = form_fill.parse_named_markdown("학년: 3   # 2곳에 들어갑니다")
        self.assertEqual(vals, {"학년": "3"})

    def test_형식이_어긋난_줄은_버리되_개수를_알려준다(self):
        vals, dropped = form_fill.parse_named_markdown(
            "# 주석\n\n학년: 3\n그냥 문장 한 줄\n반: 2\n")
        self.assertEqual(vals, {"학년": "3", "반": "2"})
        self.assertEqual(dropped, ["그냥 문장 한 줄"])

    def test_복사한_마크다운이_그대로_왕복된다(self):
        md = form_fill.to_named_markdown([("학년", 2), ("반", 1)],
                                         {"학년": "3", "반": "C# 프로그래밍"})
        vals, dropped = form_fill.parse_named_markdown(md)
        self.assertEqual(vals, {"학년": "3", "반": "C# 프로그래밍"})
        self.assertEqual(dropped, [])


# ── 7. 저장 실패가 이전 결과물을 못 지운다 ─────────────
class AtomicWriteTest(TmpDirTest):

    def _fail_mid_write(self, fn, *args):
        """쓰기 도중 실패를 흉내 낸다 — writestr 가 터지게 한다."""
        with mock.patch.object(zipfile.ZipFile, "writestr",
                               side_effect=RuntimeError("디스크 오류 흉내")):
            with self.assertRaises(RuntimeError):
                fn(*args)

    def test_fill_실패해도_이전_결과물이_그대로다(self):
        src = self._make(["\\"])
        dst = self.dir / "완성.hwpx"
        dst.write_bytes(b"previous good output")
        self._fail_mid_write(form_fill.fill, src, dst, {0: "값"})
        self.assertEqual(dst.read_bytes(), b"previous good output")
        self.assertFalse((self.dir / "완성.hwpx.tmp").exists())

    def test_fill_named_실패해도_이전_결과물이_그대로다(self):
        src = self._make(["\\학년\\"])
        dst = self.dir / "완성.hwpx"
        dst.write_bytes(b"previous good output")
        self._fail_mid_write(form_fill.fill_named, src, dst, {"학년": "3"})
        self.assertEqual(dst.read_bytes(), b"previous good output")
        self.assertFalse((self.dir / "완성.hwpx.tmp").exists())

    def test_성공하면_임시_파일이_안_남는다(self):
        src = self._make(["\\"])
        dst = self.dir / "out.hwpx"
        self.assertEqual(form_fill.fill(src, dst, {0: "값"}), 1)
        self.assertEqual([t for _, t in form_fill.read_runs(dst)], ["값"])
        self.assertFalse((self.dir / "out.hwpx.tmp").exists())


# ── 8. 조각 붙이기에 공백이 안 끼어든다 ────────────────
class CharJoinTest(unittest.TestCase):

    def test_서식으로_쪼개진_글자는_붙여_잇는다(self):
        """"학년" 이 프롬프트에 "학 년" 으로 보이던 사고의 재발 방지."""
        xml = ("<HWPML><BODY><SECTION>"
               "<P><TEXT><CHAR>학</CHAR></TEXT><TEXT><CHAR>년</CHAR></TEXT></P>"
               "</SECTION></BODY></HWPML>")
        self.assertEqual(form_markdown.xml_to_markdown(xml), "학년")

    def test_표_칸_안에서도_붙여_잇고_문단_사이만_띄운다(self):
        xml = ("<HWPML><BODY><SECTION><TABLE><ROW><CELL>"
               "<P><TEXT><CHAR>학</CHAR></TEXT><TEXT><CHAR>년</CHAR></TEXT></P>"
               "<P><TEXT><CHAR>반</CHAR></TEXT></P>"
               "</CELL></ROW></TABLE></SECTION></BODY></HWPML>")
        md = form_markdown.xml_to_markdown(xml)
        self.assertIn("| 학년 반 |", md)


if __name__ == "__main__":
    unittest.main()
