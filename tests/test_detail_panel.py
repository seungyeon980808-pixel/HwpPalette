# -*- coding: utf-8 -*-
r"""미리보기 판이 '지금 고른 것'만 보여주는지 (2026-07-31 피드백).

사용자 지적 두 가지를 이 파일이 지킨다:
  · "내가 미리보기랑 전혀 상관없는 물감을 눌렀는데 미리보기가 나오고 있습니다"
    → 도구를 고르면 앞서 고른 템플릿의 그림이 남아 있으면 안 된다.
  · "미리 볼 내용이 없는 경우에는 미리보기가 떠서는 안됩니다"
    → 고른 것이 없으면(격자 블럭을 고르면) 판이 비어야 한다.
그리고 설정이 필요한 도구(사진)에는 [설정] 단추가 붙어야 한다.

Tk 창을 실제로 만들지만 화면에 띄우지는 않는다 — 위젯의 **글자**만 읽는다.
"""

import json
import pathlib
import sys
import tempfile
import tkinter as tk
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import library                # noqa: E402
from hwp_palette.model import palette                # noqa: E402
from hwp_palette.core import settings                # noqa: E402

TABS = [{"name": "메인", "cols": 8, "blocks": [
    {"type": "builtin", "key": "convert", "row": 0, "col": 0,
     "span": 2, "rows": 1}]}]


def _texts(widget):
    """위젯 하위 전체의 글자를 모은다.

    RoundButton 은 Canvas 라 글자가 `cget("text")` 로 안 잡힌다 — 그쪽은
    `_text` 에 들고 있으므로 둘 다 훑는다.
    """
    out = []
    try:
        out.append(str(widget.cget("text")))
    except Exception:
        pass
    label = getattr(widget, "_text", None)
    if isinstance(label, str):
        out.append(label)
    for child in widget.winfo_children():
        out.extend(_texts(child))
    return out


class _PanelBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            cls._probe = tk.Tk()
            cls._probe.withdraw()
        except tk.TclError as e:              # 화면이 없는 환경
            raise unittest.SkipTest(f"Tk 를 띄울 수 없음: {e}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls._probe.destroy()
        except Exception:
            pass

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        (root / "fragments").mkdir()
        self.photo_a = root / "실험사진"
        self.photo_b = root / "수업사진"
        for d in (self.photo_a, self.photo_b):
            d.mkdir()
            (d / f"{d.name}.png").write_bytes(b"IMG")
        (root / "library.json").write_text(json.dumps({
            "서식": [], "문자": [], "양식": [],
            "템플릿": [{"id": "t1", "name": "합답형1사진3선지",
                        "label": "합답형1사진3선지", "tags": [],
                        "file": "x.hwp", "slot_count": 12,
                        "slot_names": [], "subcat": "",
                        "preview": "발문 미리보기 글자"}],
            "subcats": {},
        }, ensure_ascii=False), encoding="utf-8")
        for p in (mock.patch.object(library, "LIBRARY_PATH",
                                    root / "library.json"),
                  mock.patch.object(library, "FRAGMENTS_DIR",
                                    root / "fragments"),
                  mock.patch.object(palette, "load_tabs", return_value=TABS),
                  mock.patch.object(palette, "save_tabs",
                                    lambda *a, **k: None),
                  mock.patch.object(settings, "get_photo_dirs",
                                    return_value=[str(self.photo_a),
                                                  str(self.photo_b)])):
            p.start()
            self.addCleanup(p.stop)
        library._load_cache.update({"tok": None, "data": None})
        self.addCleanup(lambda: library._load_cache.update(
            {"tok": None, "data": None}))

        from hwp_palette.ui import palette_ui
        self.root = tk.Toplevel(self._probe)
        self.root.withdraw()
        self.win = palette_ui.SettingsWindow(self.root,
                                             on_saved=lambda *a, **k: None)
        self.win.withdraw()
        self.win.update_idletasks()
        self.addCleanup(self._teardown_win)

    def _teardown_win(self):
        for w in (self.win, self.root):
            try:
                w.destroy()
            except Exception:
                pass

    def body_text(self):
        return "\n".join(_texts(self.win._zoom_body))

    def foot_text(self):
        return "\n".join(_texts(self.win._zoom_foot))


class ToolDetailTest(_PanelBase):

    def _photo_item(self):
        return next(it for _c, it in self.win.store._items(key="도구")
                    if it["key"] == "photo")

    def test_도구를_고르면_앞_물감의_미리보기가_남지_않는다(self):
        tmpl = library.list_items("템플릿")[0]
        self.win._show_detail("템플릿", tmpl)
        self.assertIn("합답형1사진3선지", self.win.zoom_hint.cget("text"))
        # 이제 도구를 고른다
        self.win._show_detail("도구", self._photo_item())
        body = self.body_text()
        self.assertNotIn("합답형1사진3선지", body)
        self.assertIn("사진", body)
        self.assertEqual(self.win._zoom_title.cget("text"), "도구")

    # (2026-08-01, 피드백 029 · 안 1) [설정] 단추는 **없앴다** — 다섯 탭짜리
    # 물감 설정 창을 통째로 열던 그 단추다. 폴더 관리는 판 안에서 직접 한다.
    def test_사진_도구는_판_안에서_폴더를_관리한다(self):
        self.win._show_detail("도구", self._photo_item())
        self.assertNotIn("설정", self.foot_text())
        body = self.body_text()
        self.assertIn("＋ 폴더 연결", body)
        self.assertIn("우선", body)             # 순서 = 이름 충돌 우선순위 안내

    def test_설정_창을_여는_단추가_없다(self):
        convert = next(it for _c, it in self.win.store._items(key="도구")
                       if it["key"] == "convert")
        self.win._show_detail("도구", convert)
        self.assertNotIn("설정", self.foot_text())

    def test_도구_판에_사용법이_보인다(self):
        """(2026-08-01, 피드백 027) 빈자리를 사용법으로 — 출처는 builtin_actions."""
        convert = next(it for _c, it in self.win.store._items(key="도구")
                       if it["key"] == "convert")
        self.win._show_detail("도구", convert)
        body = self.body_text()
        self.assertIn("사용법", body)
        self.assertIn("드래그로 선택", body)

    def test_연결된_사진_폴더를_판에_보여준다(self):
        self.win._show_detail("도구", self._photo_item())
        body = self.body_text()
        self.assertIn("실험사진", body)
        self.assertIn("수업사진", body)
        # 폴더가 둘 이상이면 누를 때 어디서 고를지 묻는다는 안내
        self.assertIn("어느 폴더", body)


class EmptyDetailTest(_PanelBase):

    def test_고른_것이_없으면_판이_빈다(self):
        tmpl = library.list_items("템플릿")[0]
        self.win._show_detail("템플릿", tmpl)
        self.win._show_detail(None, None)
        self.assertIsNone(self.win._detail)
        self.assertEqual(self.win.zoom_hint.cget("text"), "")
        body = self.body_text()
        self.assertNotIn("합답형1사진3선지", body)
        self.assertIn("고르면", body)

    def test_창고_선택을_풀면_판도_비운다(self):
        tmpl = library.list_items("템플릿")[0]
        self.win.store._select("템플릿", tmpl)
        self.assertIsNotNone(self.win._detail)
        self.win.store.clear_selection()
        self.assertIsNone(self.win._detail)


if __name__ == "__main__":
    unittest.main()
