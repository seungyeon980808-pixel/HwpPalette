# -*- coding: utf-8 -*-
r"""하위 분류(subcat) 모델 테스트 (2026-07-31, 시안 docs/mockups/store-subcats.html).

규칙 (시안 K-3):
  · 기본은 미분류 ("" 로 저장) — 분류는 의무가 아니라 선택
  · 하위 분류는 분류마다 따로 (템플릿의 '내신'과 양식의 '내신'은 남남)
  · 분류를 지우면 안의 물감은 **미분류로** 돌아간다 — 물감이 지워지는 일은 없다
  · 내보내기에는 빠진다 (태그와 같은 이유 — 내 정리 습관)
"""

import json
import pathlib
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import library        # noqa: E402


class _TempLibrary(unittest.TestCase):
    """진짜 library.json 대신 임시 폴더를 쓰는 공통 바닥."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.frag = root / "fragments"
        self.frag.mkdir()
        for p in (mock.patch.object(library, "LIBRARY_PATH",
                                    root / "library.json"),
                  mock.patch.object(library, "FRAGMENTS_DIR", self.frag)):
            p.start()
            self.addCleanup(p.stop)
        # 앞 테스트의 읽기 캐시가 새 임시 파일로 새어 들지 않게 비운다
        library._load_cache["tok"] = None
        library._load_cache["data"] = None
        self.addCleanup(lambda: library._load_cache.update(
            {"tok": None, "data": None}))


class SubcatNormalizeTest(unittest.TestCase):

    def test_미분류는_빈_값과_같다(self):
        self.assertEqual(library.normalize_subcat("미분류"), "")
        self.assertEqual(library.normalize_subcat(None), "")
        self.assertEqual(library.normalize_subcat("  "), "")

    def test_앞뒤_공백을_벗긴다(self):
        self.assertEqual(library.normalize_subcat(" 내신 "), "내신")


class SubcatListTest(_TempLibrary):

    def test_만들고_목록에_나온다(self):
        self.assertEqual(library.add_subcat("템플릿", "내신"), "내신")
        self.assertEqual(library.list_subcats("템플릿"), ["내신"])

    def test_분류마다_따로다(self):
        library.add_subcat("템플릿", "내신")
        self.assertEqual(library.list_subcats("양식"), [])

    def test_미분류라는_이름은_만들_수_없다(self):
        self.assertIsNone(library.add_subcat("템플릿", "미분류"))
        self.assertIsNone(library.add_subcat("템플릿", ""))
        self.assertEqual(library.list_subcats("템플릿"), [])

    def test_같은_이름을_두_번_만들어도_하나다(self):
        library.add_subcat("템플릿", "내신")
        library.add_subcat("템플릿", "내신")
        self.assertEqual(library.list_subcats("템플릿"), ["내신"])

    def test_빈_하위분류도_저장에서_살아남는다(self):
        # 물감이 하나도 없어도 만든 분류는 다시 읽어도 남아 있어야 한다
        library.add_subcat("템플릿", "수능")
        library._load_cache["tok"] = None       # 캐시 말고 파일에서 다시
        self.assertEqual(library.list_subcats("템플릿"), ["수능"])


class SubcatItemTest(_TempLibrary):

    def test_저장할_때_지정한_분류가_기록되고_목록에도_등록된다(self):
        library.add_char("인사말", "안녕하세요", subcat="자주씀")
        item = library.list_items("문자")[0]
        self.assertEqual(library.subcat_of(item), "자주씀")
        self.assertEqual(library.list_subcats("문자"), ["자주씀"])

    def test_안_고르면_미분류다(self):
        library.add_char("인사말", "안녕하세요")
        item = library.list_items("문자")[0]
        self.assertEqual(library.subcat_of(item), "")

    def test_set_subcat_으로_옮긴다(self):
        item_id = library.add_char("인사말", "안녕하세요")
        self.assertTrue(library.set_subcat("문자", item_id, "내신"))
        self.assertEqual(
            library.subcat_of(library.find_by_id("문자", item_id)), "내신")

    def test_update_item_에서_None_은_안_건드리고_빈_값은_미분류다(self):
        item_id = library.add_char("인사말", "안녕", subcat="내신")
        library.update_item("문자", item_id, name="인사말2")     # subcat=None
        self.assertEqual(
            library.subcat_of(library.find_by_id("문자", item_id)), "내신")
        library.update_item("문자", item_id, subcat="")
        self.assertEqual(
            library.subcat_of(library.find_by_id("문자", item_id)), "")

    def test_템플릿_캡처에도_기록된다(self):
        library.add_template_from_capture(
            "표", lambda dest: dest.write_bytes(b"FRAG"), subcat="수능")
        item = library.list_items("템플릿")[0]
        self.assertEqual(library.subcat_of(item), "수능")
        self.assertEqual(library.list_subcats("템플릿"), ["수능"])

    def test_꾸러미도_하위_분류를_가진다(self):
        a = library.add_template_from_capture(
            "요소1", lambda dest: dest.write_bytes(b"A"))
        b = library.add_template_from_capture(
            "요소2", lambda dest: dest.write_bytes(b"B"))
        mix_id = library.add_mix("가", [a, b], subcat="유형")
        self.assertEqual(
            library.subcat_of(library.find_by_id("템플릿", mix_id)), "유형")
        library.update_mix(mix_id, subcat="")
        self.assertEqual(
            library.subcat_of(library.find_by_id("템플릿", mix_id)), "")


class SubcatDeleteRenameTest(_TempLibrary):

    def test_지우면_물감은_미분류로_돌아간다(self):
        item_id = library.add_char("인사말", "안녕", subcat="내신")
        moved = library.delete_subcat("문자", "내신")
        self.assertEqual(moved, 1)
        self.assertEqual(library.list_subcats("문자"), [])
        # 물감은 지워지지 않는다 — 미분류로 이동만
        item = library.find_by_id("문자", item_id)
        self.assertIsNotNone(item)
        self.assertEqual(library.subcat_of(item), "")

    def test_없는_분류_지우기는_실패로_알린다(self):
        self.assertEqual(library.delete_subcat("문자", "없음"), -1)

    def test_이름을_바꾸면_물감도_따라간다(self):
        item_id = library.add_char("인사말", "안녕", subcat="내신")
        self.assertTrue(library.rename_subcat("문자", "내신", "수행"))
        self.assertEqual(library.list_subcats("문자"), ["수행"])
        self.assertEqual(
            library.subcat_of(library.find_by_id("문자", item_id)), "수행")

    def test_이미_있는_이름으로는_못_바꾼다(self):
        library.add_subcat("문자", "내신")
        library.add_subcat("문자", "수능")
        self.assertFalse(library.rename_subcat("문자", "내신", "수능"))
        self.assertEqual(library.list_subcats("문자"), ["내신", "수능"])


class SubcatExportTest(_TempLibrary):

    def test_내보내기에는_하위_분류가_빠진다(self):
        # 태그와 같은 이유 — 받는 쪽 서랍에 남의 정리 습관이 생기면 안 된다
        library.add_char("인사말", "안녕", subcat="내신")
        item = library.list_items("문자")[0]
        dest = pathlib.Path(self.tmp.name) / "out.zip"
        library.export_items([("문자", item)], dest)
        with zipfile.ZipFile(dest) as zf:
            manifest = json.loads(zf.read("library.json").decode("utf-8"))
        self.assertNotIn("subcat", manifest["items"][0])

    def test_받은_물감은_미분류로_시작한다(self):
        library.add_char("인사말", "안녕", subcat="내신")
        item = library.list_items("문자")[0]
        dest = pathlib.Path(self.tmp.name) / "out.zip"
        library.export_items([("문자", item)], dest)
        r = library.import_archive(dest)
        self.assertEqual(r["added"], 1)
        got = [it for it in library.list_items("문자")
               if it.get("origin_id")][0]
        self.assertEqual(library.subcat_of(got), "")


if __name__ == "__main__":
    unittest.main()
