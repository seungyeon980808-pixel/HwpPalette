# -*- coding: utf-8 -*-
r"""사진 폴더 여러 개 연결 (settings.photo_dirs + library._photo_lookup).

config.json 을 건드리면 안 되므로 get/set_config_value 를 가짜 dict 로 갈아끼운다
(tests/test_shortcuts.py 의 창 위치 테스트와 같은 방식).
"""

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import library         # noqa: E402
import settings        # noqa: E402


class _FakeConfig(unittest.TestCase):
    """config.json 대신 메모리 dict 를 쓰는 공통 바탕."""

    def setUp(self):
        self.store = {}
        for name, fn in (("get_config_value",
                          lambda k, d=None: self.store.get(k, d)),
                         ("set_config_value",
                          lambda k, v: self.store.__setitem__(k, v))):
            p = mock.patch.object(settings, name, side_effect=fn)
            p.start()
            self.addCleanup(p.stop)

    def _tmpdir(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        return pathlib.Path(t.name)


class MigrationTest(_FakeConfig):
    """구버전은 폴더가 하나(photo_dir 문자열)뿐이었다 — 그게 사라지면 안 된다."""

    def test_구_단일폴더가_목록으로_보인다(self):
        self.store["photo_dir"] = r"C:\사진"
        self.assertEqual(settings.get_photo_dirs(), [os.path.normpath(r"C:\사진")])

    def test_읽기만_해서는_저장하지_않는다(self):
        self.store["photo_dir"] = r"C:\사진"
        settings.get_photo_dirs()
        self.assertNotIn("photo_dirs", self.store)      # 지연 승격

    def test_추가하는_순간_목록으로_기록된다(self):
        self.store["photo_dir"] = r"C:\사진"
        self.assertTrue(settings.add_photo_dir(r"D:\수업사진"))
        self.assertEqual(self.store["photo_dirs"],
                         [os.path.normpath(r"C:\사진"),
                          os.path.normpath(r"D:\수업사진")])

    def test_구_키도_첫_폴더로_유지된다(self):
        settings.set_photo_dirs([r"C:\가", r"D:\나"])
        self.assertEqual(self.store["photo_dir"], os.path.normpath(r"C:\가"))

    def test_목록이_있으면_구_키는_무시한다(self):
        self.store["photo_dir"] = r"C:\옛날"
        self.store["photo_dirs"] = [r"D:\새것"]
        self.assertEqual(settings.get_photo_dirs(), [os.path.normpath(r"D:\새것")])
        self.assertEqual(settings.get_photo_dir(), os.path.normpath(r"D:\새것"))

    def test_깨진_값은_빈_목록(self):
        for bad in ("문자열", 3, {"a": 1}, [None, "", "   "]):
            self.store["photo_dirs"] = bad
            self.store.pop("photo_dir", None)
            self.assertEqual(settings.get_photo_dirs(), [], f"{bad!r} 처리 실패")


class AddRemoveTest(_FakeConfig):
    """추가·삭제·중복."""

    def test_같은_폴더는_두_번_안_들어간다(self):
        self.assertTrue(settings.add_photo_dir(r"C:\사진"))
        self.assertFalse(settings.add_photo_dir(r"C:\사진"))
        self.assertEqual(len(settings.get_photo_dirs()), 1)

    def test_끝의_역슬래시나_슬래시_방향이_달라도_같은_폴더(self):
        settings.add_photo_dir(r"C:\사진")
        self.assertFalse(settings.add_photo_dir("C:/사진/"))
        self.assertEqual(len(settings.get_photo_dirs()), 1)

    @unittest.skipUnless(os.name == "nt", "윈도우 경로만 대소문자 무시")
    def test_대소문자만_다르면_같은_폴더(self):
        settings.add_photo_dir(r"C:\Photos")
        self.assertFalse(settings.add_photo_dir(r"c:\photos"))

    def test_빈_경로는_추가되지_않는다(self):
        self.assertFalse(settings.add_photo_dir(""))
        self.assertFalse(settings.add_photo_dir(None))

    def test_삭제(self):
        settings.set_photo_dirs([r"C:\가", r"D:\나"])
        self.assertTrue(settings.remove_photo_dir("c:/가/"))
        self.assertEqual(settings.get_photo_dirs(), [os.path.normpath(r"D:\나")])
        self.assertFalse(settings.remove_photo_dir(r"C:\없는곳"))

    def test_전체_교체는_중복을_정리한다(self):
        settings.set_photo_dirs([r"C:\가", "C:/가/", r"D:\나", ""])
        self.assertEqual(settings.get_photo_dirs(),
                         [os.path.normpath(r"C:\가"), os.path.normpath(r"D:\나")])

    def test_구버전_API도_그대로_동작한다(self):
        settings.set_photo_dirs([r"C:\가", r"D:\나"])
        self.assertEqual(settings.get_photo_dir(), os.path.normpath(r"C:\가"))
        settings.set_photo_dir(r"E:\혼자")            # 하나만 남긴다
        self.assertEqual(settings.get_photo_dirs(), [os.path.normpath(r"E:\혼자")])
        settings.set_photo_dir("")                   # 전부 해제
        self.assertEqual(settings.get_photo_dirs(), [])
        self.assertEqual(settings.get_photo_dir(), "")


class MultiFolderLookupTest(_FakeConfig):
    r"""여러 폴더를 훑는 \사진이름\ 조회."""

    def setUp(self):
        super().setUp()
        self.a = self._tmpdir()
        self.b = self._tmpdir()

    @staticmethod
    def _touch(d, name):
        (d / name).write_bytes(b"IMG")

    def test_두_폴더의_사진이_모두_보인다(self):
        self._touch(self.a, "가.png")
        self._touch(self.b, "나.jpg")
        settings.set_photo_dirs([str(self.a), str(self.b)])
        out = library._photo_lookup()
        self.assertEqual(set(out), {"가", "나"})

    def test_이름이_겹치면_먼저_등록한_폴더가_이긴다(self):
        self._touch(self.a, "겹침.png")
        self._touch(self.b, "겹침.png")
        settings.set_photo_dirs([str(self.a), str(self.b)])
        self.assertTrue(library._photo_lookup()["겹침"][1]["path"]
                        .startswith(str(self.a)))
        settings.set_photo_dirs([str(self.b), str(self.a)])   # 순서를 바꾸면 반대
        self.assertTrue(library._photo_lookup()["겹침"][1]["path"]
                        .startswith(str(self.b)))

    def test_없는_폴더는_건너뛰고_나머지는_살아_있다(self):
        self._touch(self.b, "살아있음.png")
        settings.set_photo_dirs([str(self.a / "없는폴더"), str(self.b)])
        out = library._photo_lookup()                 # 예외 없이
        self.assertEqual(set(out), {"살아있음"})

    def test_폴더가_하나도_없으면_빈_결과(self):
        self.assertEqual(library._photo_lookup(), {})

    def test_이미지가_아닌_파일은_제외(self):
        self._touch(self.a, "메모.txt")
        settings.set_photo_dirs([str(self.a)])
        self.assertEqual(library._photo_lookup(), {})


class PhotoFoldersSummaryTest(_FakeConfig):
    """UI 표시용 현황."""

    def setUp(self):
        super().setUp()
        self.a = self._tmpdir()

    def test_개수와_존재_여부를_센다(self):
        (self.a / "1.png").write_bytes(b"IMG")
        (self.a / "2.jpg").write_bytes(b"IMG")
        (self.a / "메모.txt").write_bytes(b"x")       # 이미지가 아니므로 제외
        missing = str(self.a / "없는폴더")
        settings.set_photo_dirs([str(self.a), missing])
        rows = library.photo_folders_summary()
        self.assertEqual([r["exists"] for r in rows], [True, False])
        self.assertEqual([r["count"] for r in rows], [2, 0])
        self.assertEqual(rows[1]["path"], os.path.normpath(missing))

    def test_폴더가_없으면_빈_목록(self):
        self.assertEqual(library.photo_folders_summary(), [])

    def test_설정_조회가_터져도_죽지_않는다(self):
        with mock.patch.object(settings, "get_photo_dirs",
                               side_effect=RuntimeError("boom")):
            self.assertEqual(library.photo_folders_summary(), [])


if __name__ == "__main__":
    unittest.main()
