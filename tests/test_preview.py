# -*- coding: utf-8 -*-
"""조각 미리보기 (UI 제안 7).

.hwp 는 이진 파일이라 나중에 읽을 수 없다. 그래서 **저장하는 순간** 본문
글자를 뽑아 몇 줄로 줄여 저장해 둔다. 여기서 검증하는 건 그 '줄이는 규칙'.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import library   # noqa: E402

W = library.PREVIEW_WIDTH
N = library.PREVIEW_LINES


class MakePreviewTest(unittest.TestCase):

    def test_빈_입력(self):
        for empty in ("", None):
            self.assertEqual(library.make_preview(empty), "")

    def test_한_줄_그대로(self):
        self.assertEqual(library.make_preview("결재란"), "결재란")

    def test_빈_줄은_버린다(self):
        # 표를 캡처하면 빈 셀이 빈 줄로 잔뜩 나온다 — 그대로 두면 미리보기가
        # 공백만 네 줄이 되어 아무 정보도 못 준다.
        out = library.make_preview("\n\n담당\n\n\n부장\n")
        self.assertEqual(out, "담당\n부장")

    def test_연속_공백은_한_칸으로(self):
        self.assertEqual(library.make_preview("담당    \t 부장"), "담당 부장")

    def test_긴_줄은_자르고_말줄임(self):
        out = library.make_preview("가" * (W + 10))
        self.assertEqual(out, "가" * W + "…")

    def test_딱_맞는_길이는_안_자른다(self):
        out = library.make_preview("나" * W)
        self.assertEqual(out, "나" * W)
        self.assertNotIn("…", out)

    def test_줄이_많으면_말줄임_줄을_붙인다(self):
        out = library.make_preview("\n".join(f"줄{i}" for i in range(N + 3)))
        lines = out.splitlines()
        self.assertEqual(len(lines), N + 1)
        self.assertEqual(lines[-1], "…")

    def test_줄_수가_딱_맞으면_말줄임을_안_붙인다(self):
        out = library.make_preview("\n".join(f"줄{i}" for i in range(N)))
        self.assertEqual(len(out.splitlines()), N)
        self.assertNotIn("…", out)

    def test_빈_줄을_뺀_뒤로_센다(self):
        # 빈 줄이 섞여 실제 내용은 N줄뿐이면 '더 있다' 표시가 뜨면 안 된다.
        raw = "\n\n".join(f"줄{i}" for i in range(N))
        self.assertNotIn("…", library.make_preview(raw))

    def test_문자열이_아니어도_죽지_않는다(self):
        self.assertEqual(library.make_preview(12345), "12345")


class GetPreviewTest(unittest.TestCase):
    """예전에 등록한 항목에는 preview 키가 아예 없다 — 그때도 조용해야 한다."""

    def test_없으면_빈_문자열(self):
        for item in ({}, {"name": "결재란"}, {"preview": None},
                     {"preview": ""}, None):
            self.assertEqual(library.get_preview(item), "")

    def test_있으면_그대로(self):
        self.assertEqual(library.get_preview({"preview": "담당\n부장"}),
                         "담당\n부장")


class CaptureContractTest(unittest.TestCase):
    """add_template_from_capture 의 두 번째 인자는 '함수'다.

    palette_ui 가 여기에 Path 를 넘기고 있어서 환경설정에서 템플릿 블럭을
    만들 때마다 터졌다. 계약을 테스트로 못박아 다시 어긋나지 않게 한다.
    """

    def test_함수를_받아_그_자리에_저장한다(self):
        import tempfile
        import shutil
        tmpdir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmpdir, True)
        seen = {}

        def fake_save(dest):
            seen["dest"] = dest
            dest.write_bytes(b"HWP")
            return "담당\n부장\n\n교장"      # capture_fragment 의 반환값 흉내

        orig_dir, orig_path = library.FRAGMENTS_DIR, library.LIBRARY_PATH
        library.FRAGMENTS_DIR = tmpdir / "fragments"
        library.LIBRARY_PATH = tmpdir / "library.json"
        try:
            item_id = library.add_template_from_capture("결재란", fake_save)
            item = library.find_by_id("템플릿", item_id)
        finally:
            library.FRAGMENTS_DIR, library.LIBRARY_PATH = orig_dir, orig_path

        self.assertTrue(seen["dest"].exists(), "함수가 받은 경로에 저장돼야 한다")
        self.assertEqual(item["preview"], "담당\n부장\n교장")

    def test_Path_를_넘기면_바로_터진다(self):
        # 이 오류가 '조용히 넘어가지' 않는다는 것 자체가 안전장치다.
        with self.assertRaises(TypeError):
            library.add_template_from_capture("x", pathlib.Path("아무거나.hwp"))


if __name__ == "__main__":
    unittest.main()
