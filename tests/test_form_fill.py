# -*- coding: utf-8 -*-
r"""양식 채우기 테스트 — 한글 없이 돌아간다 (HWPX 는 zip + XML 이므로)."""

import pathlib
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import form_fill        # noqa: E402


def make_hwpx(path, runs, sections=1):
    """글자 조각 목록으로 최소한의 가짜 HWPX 를 만든다."""
    per = (len(runs) + sections - 1) // sections
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("version.xml", "<version/>")
        for s in range(sections):
            chunk = runs[s * per:(s + 1) * per]
            body = "".join(f"<hp:p><hp:run><hp:t>{t}</hp:t></hp:run></hp:p>"
                           for t in chunk)
            zf.writestr(f"Contents/section{s}.xml",
                        f'<?xml version="1.0"?><hp:sec>{body}</hp:sec>')


class FormFillTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def _make(self, runs, sections=1, name="src.hwpx"):
        p = self.dir / name
        make_hwpx(p, runs, sections)
        return p

    # ── 읽기 ──
    def test_조각을_순서대로_읽는다(self):
        p = self._make(["가", "나", "다"])
        self.assertEqual(form_fill.read_runs(p), [(0, "가"), (1, "나"), (2, "다")])

    def test_구역이_여러_개여도_이어서_센다(self):
        p = self._make(["가", "나", "다", "라"], sections=2)
        self.assertEqual([i for i, _ in form_fill.read_runs(p)], [0, 1, 2, 3])

    def test_빈칸이_든_조각만_고른다(self):
        p = self._make(["제목", "\\", "본문", "\\. \\."])
        self.assertEqual(form_fill.slots(p), [(1, "\\"), (3, "\\. \\.")])

    def test_빈칸이_없으면_글자_있는_조각_전부(self):
        """빈칸을 안 심어둔 양식도 쓸 수 있어야 한다."""
        p = self._make(["제목", "  ", "본문"])
        self.assertEqual(form_fill.slots(p), [(0, "제목"), (2, "본문")])

    # ── 주고받기 문서 ──
    def test_주고받기_문서에_번호와_내용이_담긴다(self):
        p = self._make(["〈보 기〉", "ㄱ. \\", "ㄴ. \\"])
        sheet = form_fill.to_worksheet(p, title="보기박스")
        self.assertIn("# 양식: 보기박스", sheet)
        self.assertIn("[1] ㄱ. \\", sheet)
        self.assertIn("[2] ㄴ. \\", sheet)
        self.assertIn("〈보 기〉", sheet)          # 미리보기에 문맥이 들어간다

    def test_돌려받은_문서를_해석한다(self):
        got = form_fill.parse_worksheet(
            "# 주석은 무시\n\n[1] 첫째 줄\n[2] 둘째 줄\n")
        self.assertEqual(got, {1: "첫째 줄", 2: "둘째 줄"})

    def test_줄_순서가_바뀌거나_빠져도_된다(self):
        got = form_fill.parse_worksheet("[5] 다섯\n[1] 하나\n")
        self.assertEqual(got, {5: "다섯", 1: "하나"})

    def test_형식에_안_맞는_줄은_무시한다(self):
        got = form_fill.parse_worksheet("아무 말\n[1] 값\n[번호] 값\n")
        self.assertEqual(got, {1: "값"})

    def test_내용이_빈_줄도_받는다(self):
        """'그 칸은 비워라'를 표현할 수 있어야 한다."""
        self.assertEqual(form_fill.parse_worksheet("[2] "), {2: ""})

    # ── 채우기 ──
    def test_지정한_조각만_바뀐다(self):
        src = self._make(["제목", "\\", "꼬리말"])
        dst = self.dir / "out.hwpx"
        n = form_fill.fill(src, dst, {1: "채운 내용"})
        self.assertEqual(n, 1)
        self.assertEqual(form_fill.read_runs(dst),
                         [(0, "제목"), (1, "채운 내용"), (2, "꼬리말")])

    def test_구역이_여러_개여도_번호가_맞는다(self):
        src = self._make(["가", "나", "다", "라"], sections=2)
        dst = self.dir / "out.hwpx"
        form_fill.fill(src, dst, {2: "바뀜"})
        self.assertEqual(form_fill.read_runs(dst),
                         [(0, "가"), (1, "나"), (2, "바뀜"), (3, "라")])

    def test_XML_특수문자를_안전하게_넣는다(self):
        """<, &, > 를 그대로 쓰면 XML 이 깨져 한글이 파일을 못 연다."""
        src = self._make(["\\"])
        dst = self.dir / "out.hwpx"
        form_fill.fill(src, dst, {0: "a < b & c > d"})
        self.assertEqual(form_fill.read_runs(dst), [(0, "a < b & c > d")])
        raw = zipfile.ZipFile(dst).read("Contents/section0.xml").decode("utf-8")
        self.assertIn("&lt;", raw)
        self.assertIn("&amp;", raw)

    def test_바꾸지_않는_파일은_그대로_보존된다(self):
        """표·글꼴·이미지가 살아남는 근거 — 나머지 바이트를 안 건드린다."""
        src = self._make(["\\"])
        dst = self.dir / "out.hwpx"
        form_fill.fill(src, dst, {0: "값"})
        a, b = zipfile.ZipFile(src), zipfile.ZipFile(dst)
        self.assertEqual(a.namelist(), b.namelist())
        self.assertEqual(a.read("mimetype"), b.read("mimetype"))
        self.assertEqual(a.read("version.xml"), b.read("version.xml"))

    def test_없는_번호를_주면_세지_않는다(self):
        src = self._make(["가"])
        dst = self.dir / "out.hwpx"
        self.assertEqual(form_fill.fill(src, dst, {99: "값"}), 0)

    def test_남은_빈칸을_알려준다(self):
        src = self._make(["\\", "\\", "보통 글"])
        dst = self.dir / "out.hwpx"
        form_fill.fill(src, dst, {0: "채움"})
        self.assertEqual(form_fill.unfilled_marks(dst), [(1, "\\")])

    # ── 왕복 ──
    def test_뽑아서_채우고_다시_넣는_왕복(self):
        src = self._make(["〈보 기〉", "ㄱ. \\", "ㄴ. \\", "ㄷ. \\"])
        sheet = form_fill.to_worksheet(src, "보기박스")
        # 사람이 채운 것처럼 [n] 뒤를 바꿔 돌려준다
        filled = "\n".join(
            line if not line.startswith("[") else
            f"{line.split(']')[0]}] 채운내용{line.split(']')[0][1:]}"
            for line in sheet.splitlines())
        dst = self.dir / "out.hwpx"
        n = form_fill.fill(src, dst, form_fill.parse_worksheet(filled))
        self.assertEqual(n, 3)
        self.assertEqual([t for _, t in form_fill.read_runs(dst)],
                         ["〈보 기〉", "채운내용1", "채운내용2", "채운내용3"])


if __name__ == "__main__":
    unittest.main()
