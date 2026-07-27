# -*- coding: utf-8 -*-
r"""편집 화면이 다음 쪽으로 넘어가지 않게 하는 두 장치 (2026-07-27).

사용자 결정: ① 템플릿 편집 탭은 여백을 10mm 로 좁힌다 (빈 새 탭이라
저장물에 안 샌다) ② 양식은 여백이 곧 내용이라 건드리지 않는 대신,
문서 맨 위 안내문을 1줄로 줄인다 (6~7줄 안내가 문서를 밀어내던 주범).
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import engine_library        # noqa: E402
import library_ui            # noqa: E402
from tests.test_edit_session import FakeHwp, _install   # noqa: E402


class NarrowPageWiringTest(unittest.TestCase):

    def setUp(self):
        self.src = pathlib.Path(__file__).with_name("_np_test.hwp")
        self.src.write_bytes(b"fake")
        self.work = pathlib.Path(__file__).with_name("_np_work")
        mock.patch.object(engine_library.paths, "data_dir",
                          lambda: self.work).start()

    def tearDown(self):
        mock.patch.stopall()
        self.src.unlink(missing_ok=True)
        if self.work.exists():
            for p in sorted(self.work.rglob("*"), reverse=True):
                if p.is_file():
                    p.unlink(missing_ok=True)

    def _fake(self):
        fake = FakeHwp()
        fake.body = "표 내용"
        fake.ctrls = ["secd", "cold", "tbl"]
        fake.insert_file = lambda *a, **kw: True
        _install(fake)
        return fake

    def test_템플릿_편집_탭은_여백을_좁힌다(self):
        self._fake()
        spy = mock.patch.object(engine_library, "apply_narrow_page",
                                return_value=True).start()
        engine_library.open_template_copy(self.src, None)
        spy.assert_called_once()

    def test_양식_사본은_여백을_건드리지_않는다(self):
        r"""양식은 여백까지가 내용 — 좁히면 저장할 때 양식 자체가 바뀐다."""
        self._fake()
        spy = mock.patch.object(engine_library, "apply_narrow_page",
                                return_value=True).start()
        engine_library.open_form_copy(self.src, None)
        spy.assert_not_called()

    def test_여백_좁히기_실패는_편집을_막지_않는다(self):
        class Boom:
            def __getattr__(self, name):
                raise RuntimeError("COM 죽음")
        with mock.patch.object(engine_library, "_h", lambda: Boom()):
            self.assertFalse(engine_library.apply_narrow_page())


class EditNoteLengthTest(unittest.TestCase):
    r"""안내문은 **1줄** — 다시 자라면 편집 화면이 또 다음 쪽으로 넘어간다."""

    def test_템플릿_안내문은_한_줄(self):
        self.assertEqual(len(library_ui.LibraryManager._EDIT_NOTE), 1,
                         "안내문이 다시 자랐다 — 자세한 설명은 '고치는 중' "
                         "판·코치 창으로 보낼 것")

    def test_양식_안내문은_한_줄(self):
        self.assertEqual(len(library_ui._FORM_EDIT_NOTE), 1)

    def test_안내문에_덮어쓰기_안내는_남아_있다(self):
        # 줄이더라도 "무엇을 눌러야 저장되는지"는 문서에서 안 사라져야 한다
        self.assertIn("덮어쓰기", library_ui.LibraryManager._EDIT_NOTE[0])
        self.assertIn("덮어쓰기", library_ui._FORM_EDIT_NOTE[0])


if __name__ == "__main__":
    unittest.main()
