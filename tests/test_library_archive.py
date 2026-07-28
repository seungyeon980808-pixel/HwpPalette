# -*- coding: utf-8 -*-
"""라이브러리 내보내기/가져오기 왕복 테스트 (개선안 30).

임시 폴더로 LIBRARY_PATH·FRAGMENTS_DIR 를 갈아끼워, 사용자의 실제 라이브러리를
건드리지 않고 검증한다. 조각 .hwp 는 내용이 중요한 게 아니라 '따라오는지'가
중요하므로 더미 바이트로 대신한다.
"""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import library        # noqa: E402


class ArchiveRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.frag = root / "fragments"
        self.frag.mkdir()
        patches = [
            mock.patch.object(library, "LIBRARY_PATH", root / "library.json"),
            mock.patch.object(library, "FRAGMENTS_DIR", self.frag),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _seed_template(self, name="결재란", label=None):
        """조각 파일을 가진 템플릿 하나를 등록한다.

        add_template_from_capture 는 이제 '목적지에 저장하는 함수'를 받는다
        (한글이 파일을 물어 이름 바꾸기가 실패하던 WinError 32 회피).
        테스트에서는 더미 바이트를 그 자리에 써 주는 함수를 넘긴다.
        """
        return library.add_template_from_capture(
            name, lambda dest: dest.write_bytes(b"HWP-FRAGMENT-BYTES"),
            label=label, slot_count=2)

    def _export_all(self):
        dest = pathlib.Path(self.tmp.name) / "out.zip"
        pairs = [(cat, it) for cat in library.CATEGORIES
                 for it in library.list_items(cat)]
        n = library.export_items(pairs, dest)
        return dest, n

    def test_문자_항목을_내보내고_다시_가져온다(self):
        library.add_char("인사말", "안녕하세요", label="인사말")
        dest, n = self._export_all()
        self.assertEqual(n, 1)

        result = library.import_archive(dest)
        self.assertEqual(result["added"], 1)
        names = [it["name"] for it in library.list_items("문자")]
        # 원본 + 가져온 것 = 2개, 이름은 겹치지 않게 번호가 붙는다
        self.assertEqual(sorted(names), ["인사말", "인사말 (2)"])

    def test_템플릿_조각_파일이_함께_따라온다(self):
        self._seed_template()
        dest, _ = self._export_all()
        library.import_archive(dest)

        items = library.list_items("템플릿")
        self.assertEqual(len(items), 2)
        # 파일명은 새로 발급돼야 한다 (원본을 덮어쓰면 안 됨)
        files = {it["file"] for it in items}
        self.assertEqual(len(files), 2)
        for it in items:
            path = library.FRAGMENTS_DIR / it["file"]
            self.assertTrue(path.exists(), f"조각 파일 없음: {it['file']}")
            self.assertEqual(path.read_bytes(), b"HWP-FRAGMENT-BYTES")

    def test_slot_count_가_보존된다(self):
        self._seed_template()
        dest, _ = self._export_all()
        library.import_archive(dest)
        self.assertTrue(all(it["slot_count"] == 2
                            for it in library.list_items("템플릿")))

    def test_id는_새로_발급된다(self):
        """같은 id가 둘이면 팔레트 참조가 엉킨다."""
        original_id = self._seed_template()
        dest, _ = self._export_all()
        library.import_archive(dest)
        ids = [it["id"] for it in library.list_items("템플릿")]
        self.assertEqual(len(set(ids)), 2)
        self.assertIn(original_id, ids)

    def test_라벨이_겹치면_번호를_붙인다(self):
        """라벨을 그대로 두면 가져온 항목이 조용히 호출 불가가 된다."""
        library.add_char("인사말", "안녕", label="인사")
        dest, _ = self._export_all()
        result = library.import_archive(dest)

        labels = [it["label"] for it in library.list_items("문자")]
        self.assertEqual(sorted(labels), ["인사", "인사2"])
        self.assertEqual(result["relabeled"], [("인사", "인사2")])
        # 두 항목 모두 \라벨\ 로 호출 가능해야 한다
        lookup = library.label_lookup()
        self.assertIn("인사", lookup)
        self.assertIn("인사2", lookup)

    def test_가져오기는_덮어쓰지_않는다(self):
        library.add_char("인사말", "원본내용", label="인사")
        dest, _ = self._export_all()
        library.import_archive(dest)
        texts = [it["text"] for it in library.list_items("문자")]
        self.assertIn("원본내용", texts)      # 원본이 살아 있다
        self.assertEqual(len(texts), 2)

    def test_건너뛴_항목이_이름을_선점하지_않는다(self):
        r"""조각 파일이 없어 건너뛴 항목이 이름·라벨을 먼저 차지하면, 뒤따르는
        멀쩡한 항목이 있지도 않은 충돌 때문에 이름이 바뀐다."""
        import json
        import zipfile
        z = pathlib.Path(self.tmp.name) / "partial.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("library.json", json.dumps({
                "version": library.ARCHIVE_VERSION,
                "items": [
                    # 조각이 zip 에 없음 → 건너뛰어야 함
                    {"category": "템플릿", "name": "결재란", "label": "결재란",
                     "file": "missing.hwp", "slot_count": 1},
                    # 같은 이름·라벨이지만 이쪽은 멀쩡한 문자 항목
                    {"category": "문자", "name": "결재란", "label": "결재란",
                     "text": "내용"},
                ]}, ensure_ascii=False))
        r = library.import_archive(z)
        self.assertEqual(r["added"], 1)
        self.assertEqual(r["renamed"], [])         # 충돌이 없어야 한다
        self.assertEqual(r["relabeled"], [])
        self.assertEqual(library.list_items("문자")[0]["label"], "결재란")

    def test_형식_버전이_다르면_거부한다(self):
        import json
        import zipfile
        bad = pathlib.Path(self.tmp.name) / "bad.zip"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("library.json",
                        json.dumps({"version": 999, "items": []}))
        with self.assertRaises(ValueError):
            library.import_archive(bad)

    def test_조각_파일이_빠진_항목은_건너뛴다(self):
        self._seed_template()
        # 조각 파일을 지운 뒤 내보내면 그 항목은 목록에서 빠져야 한다
        for it in library.list_items("템플릿"):
            (library.FRAGMENTS_DIR / it["file"]).unlink()
        _, n = self._export_all()
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
