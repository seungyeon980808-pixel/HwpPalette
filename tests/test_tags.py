# -*- coding: utf-8 -*-
r"""태그 — 예전의 '분류'를 대체한 꼬리표 (사용자 결정 2026-07-26).

분류를 버린 이유: **배타적이라 아무도 안 골랐다.** '합답형1사진3선지' 를
수능·시험문제·사진문항 중 하나만 고르라니 고르지 않았고, 실제로 물감 15개가
전부 '기본' 이었다. 게다가 팔레트 탭이 이미 서랍 노릇을 해서 서랍이 두 벌이었다.

여기서 못박는 규칙:
  · 태그는 0개도 여러 개도 된다 ('미분류' 라는 억지 이름이 필요 없다)
  · 내보낼 때 빠진다 — 남의 정리 습관은 나에게 뜻이 없다
  · 검색칸 하나가 태그 필터와 글자 검색을 함께 한다 (#수능)
  · 옛 데이터의 group 은 조용히 이관된다
"""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import library            # noqa: E402


class TempLibrary(unittest.TestCase):
    """실제 라이브러리를 건드리지 않도록 임시 폴더로 갈아끼운다."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self._tmp.name)
        self._patches = [
            mock.patch.object(library, "LIBRARY_PATH", root / "library.json"),
            mock.patch.object(library, "FRAGMENTS_DIR", root / "fragments"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()


class NormalizeTest(unittest.TestCase):

    def test_문자열_하나로_줘도_받는다(self):
        """입력칸에서 '수능 사진문항' 처럼 통째로 넘어온다."""
        self.assertEqual(library.normalize_tags("수능 사진문항"),
                         ["수능", "사진문항"])

    def test_쉼표도_구분자로_본다(self):
        self.assertEqual(library.normalize_tags("수능, 사진문항"),
                         ["수능", "사진문항"])

    def test_샵을_벗긴다(self):
        """화면에는 #수능 으로 보이지만 저장은 알맹이로."""
        self.assertEqual(library.normalize_tags("#수능 #사진"),
                         ["수능", "사진"])

    def test_중복은_한_번만_순서는_유지(self):
        self.assertEqual(library.normalize_tags("수능 사진 수능"),
                         ["수능", "사진"])

    def test_빈_값은_빈_목록(self):
        for v in (None, "", "   ", [], ["", "  "]):
            self.assertEqual(library.normalize_tags(v), [])

    def test_다섯_글자까지만_받는다(self):
        """규칙: 한글 5글자 이내 (사용자 결정 2026-07-26).

        자르지 않고 **버린다** — 자르면 '가나다라마바사' 가 '가나다라마' 로
        조용히 바뀌어, 사용자가 지은 것과 다른 태그가 생긴다.
        """
        self.assertEqual(library.normalize_tags("가나다라마"), ["가나다라마"])
        self.assertEqual(library.normalize_tags("가나다라마바"), [])

    def test_한글이_아니면_버린다(self):
        for bad in ("sooneung", "수능2026", "3학년", "수능!", "수능_문제",
                    "고1수능"):
            self.assertEqual(library.normalize_tags(bad), [], bad)

    def test_한글이면_받는다(self):
        for good in ("수능", "가", "가나다라마", "ㄱ"):
            self.assertEqual(library.normalize_tags(good), [good], good)

    def test_섞여_있으면_맞는_것만_남는다(self):
        """가져오기·옛 데이터처럼 화면을 안 거치는 경로의 마지막 관문."""
        self.assertEqual(library.normalize_tags("수능 abc 사진"),
                         ["수능", "사진"])

    def test_입력_가르기는_검사_전이라_그대로_돌려준다(self):
        """화면이 '무엇이 걸렸는지' 를 말하려면 잘못된 것도 봐야 한다."""
        self.assertEqual(library.split_tag_input("#수능 abc, 사진"),
                         ["수능", "abc", "사진"])


class MigrationTest(TempLibrary):
    """옛 데이터(group)를 열었을 때."""

    def _write(self, items):
        import json
        data = {c: [] for c in library.CATEGORIES}
        data["문자"] = items
        library.LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        library.LIBRARY_PATH.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_기본_분류는_버린다(self):
        """'기본' 은 '아직 정리 안 함' 이라 태그로 옮길 내용이 아니다."""
        self._write([{"id": "x", "name": "가", "label": "가",
                      "group": "기본", "text": "★"}])
        it = library.load()["문자"][0]
        self.assertEqual(it["tags"], [])
        self.assertNotIn("group", it)

    def test_직접_지은_분류는_태그로_살린다(self):
        self._write([{"id": "x", "name": "가", "label": "가",
                      "group": "수능", "text": "★"}])
        self.assertEqual(library.load()["문자"][0]["tags"], ["수능"])

    def test_태그가_없던_예전_항목도_빈_목록을_갖는다(self):
        self._write([{"id": "x", "name": "가", "label": "가", "text": "★"}])
        self.assertEqual(library.load()["문자"][0]["tags"], [])


class ItemTagTest(TempLibrary):

    def test_등록할_때_태그를_단다(self):
        library.add_char("사각박스", "□", tags="수능 도형")
        self.assertEqual(library.list_items("문자")[0]["tags"],
                         ["수능", "도형"])

    def test_태그_없이도_등록된다(self):
        library.add_char("사각박스", "□")
        self.assertEqual(library.list_items("문자")[0]["tags"], [])

    def test_수정으로_태그를_통째로_바꾼다(self):
        cid = library.add_char("가", "★", tags="수능")
        library.update_item("문자", cid, tags="학교 시험")
        self.assertEqual(library.list_items("문자")[0]["tags"],
                         ["학교", "시험"])

    def test_빈_목록으로_바꾸면_태그를_다_뗀다(self):
        """빈 목록도 뜻이 있다 — None 일 때만 안 건드려야 한다."""
        cid = library.add_char("가", "★", tags="수능")
        library.update_item("문자", cid, tags=[])
        self.assertEqual(library.list_items("문자")[0]["tags"], [])

    def test_이름만_고치면_태그는_그대로(self):
        cid = library.add_char("가", "★", tags="수능")
        library.update_item("문자", cid, name="나")
        self.assertEqual(library.list_items("문자")[0]["tags"], ["수능"])

    def test_많이_쓴_태그가_먼저_나온다(self):
        """자동완성 칩은 자주 쓰는 것이 앞에 와야 손이 덜 간다."""
        library.add_char("가", "★", tags="수능")
        library.add_char("나", "☆", tags="수능 도형")
        library.add_char("다", "○", tags="도형")
        library.add_char("라", "●", tags="수능")
        self.assertEqual(library.list_tags()[:2], ["수능", "도형"])


class ExportTest(TempLibrary):
    """내보낼 때 태그가 빠지는가 — 남의 정리 습관은 안 넘어가야 한다."""

    def test_꾸러미에_태그가_안_들어간다(self):
        import json
        import zipfile
        library.add_char("사각박스", "□", tags="수능 내가만든")
        dest = pathlib.Path(self._tmp.name) / "out.zip"
        library.export_items([("문자", library.list_items("문자")[0])], dest)
        with zipfile.ZipFile(dest) as zf:
            manifest = json.loads(zf.read("library.json").decode("utf-8"))
        rec = manifest["items"][0]
        self.assertNotIn("tags", rec)
        self.assertEqual(rec["name"], "사각박스")     # 나머지는 그대로

    def test_받은_물감은_태그_없이_들어온다(self):
        library.add_char("사각박스", "□", tags="수능")
        dest = pathlib.Path(self._tmp.name) / "out.zip"
        library.export_items([("문자", library.list_items("문자")[0])], dest)
        library.import_archive(dest)
        got = [it for it in library.list_items("문자")
               if it["name"] != "사각박스"]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["tags"], [])

    def test_옛_꾸러미의_분류도_안_따라온다(self):
        """version 1 꾸러미에는 group 이 들어 있다 — 그것도 떨군다."""
        import json
        import zipfile
        dest = pathlib.Path(self._tmp.name) / "old.zip"
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("library.json", json.dumps({
                "version": library.ARCHIVE_VERSION,
                "items": [{"category": "문자", "name": "가", "label": "가",
                           "group": "남의분류", "text": "★"}]},
                ensure_ascii=False))
        library.import_archive(dest)
        it = library.list_items("문자")[0]
        self.assertEqual(it["tags"], [])
        self.assertNotIn("group", it)


class SearchQueryTest(unittest.TestCase):
    r"""검색칸 하나가 태그 필터까지 한다 — 화면을 늘리지 않기 위해."""

    def setUp(self):
        # library_ui 는 tkinter 를 부르므로, 순수 함수만 떼어 와 검사한다
        import re
        src = pathlib.Path(__file__).resolve().parent.parent / "library_ui.py"
        text = src.read_text(encoding="utf-8")
        m = re.search(r"    @staticmethod\n    def split_query.*?\n"
                      r"        return tags, \" \"\.join\(words\)\n",
                      text, re.S)
        assert m, "split_query 를 찾지 못했습니다"
        body = "\n".join(line[4:] if line.startswith("    ") else line
                         for line in m.group(0).splitlines())
        ns = {}
        exec(body.replace("@staticmethod\n", ""), ns)
        self.split = ns["split_query"]

    def test_글자만(self):
        self.assertEqual(self.split("사진"), ([], "사진"))

    def test_태그만(self):
        self.assertEqual(self.split("#수능"), (["수능"], ""))

    def test_섞어_쓰기(self):
        self.assertEqual(self.split("#수능 사진"), (["수능"], "사진"))

    def test_태그_여러_개는_모두_만족(self):
        self.assertEqual(self.split("#수능 #사진"), (["수능", "사진"], ""))

    def test_샵만_있으면_글자로_본다(self):
        """'#' 한 글자를 태그 조건으로 보면 아무것도 안 나온다."""
        self.assertEqual(self.split("#"), ([], "#"))

    def test_빈_검색어(self):
        self.assertEqual(self.split(""), ([], ""))


if __name__ == "__main__":
    unittest.main()
