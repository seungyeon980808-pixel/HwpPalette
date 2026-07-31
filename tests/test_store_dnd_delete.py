# -*- coding: utf-8 -*-
r"""창고의 우클릭과 끌어놓기 (2026-08-01, 피드백 038-a·c·d).

세 가지가 한 자리에서 바뀌었다.

  038-a  우클릭에 **삭제**가 없었다 — 물감을 지우려면 다른 창으로 가야 했다.
  038-c  '옮기기' 목록이 **지금 있는 분류까지** 늘어놓아서, 눌러도 아무 일이
         안 일어나는 항목이 늘 하나 섞여 있었다.
  038-d  사용자 결정: *"옮기기 기능은 끌어놓기로 하겠습니다"* — 위쪽 하위
         분류 탭에 끌어다 놓으면 그 분류로 간다.

그래서 우클릭은 **삭제 전용**이 되어 단순해졌다. 038-c 는 목록 자체가
없어지면서 함께 풀렸다.
"""

import pathlib
import sys
import tkinter as tk
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import srcpath                                     # noqa: E402

from hwp_palette.model import library              # noqa: E402
from hwp_palette.ui import store_ui                # noqa: E402


def _read(module):
    return srcpath.src(module).read_text(encoding="utf-8")


class _Ev:
    def __init__(self, x, y):
        self.x_root, self.y_root = x, y


def _panel(root, on_drop):
    p = store_ui.StorePanel(root, on_place=lambda b: None,
                            tab_name_fn=lambda: "메인", on_drop=on_drop)
    p.pack()
    root.update()
    root.update_idletasks()
    return p


class RightClickIsDeleteOnly(unittest.TestCase):
    r"""우클릭 메뉴는 삭제만 남는다 — 옮기기는 끌어놓기로 갔다."""

    def test_옛_옮기기_메뉴가_없다(self):
        code = _read("store_ui")
        self.assertNotIn("def _move_menu", code)
        self.assertNotIn("로 옮기기", code,
                         "옮기기 목록이 남아 있으면 038-c 의 '눌러도 아무 일 없는 "
                         "항목'도 함께 돌아온다")

    def test_삭제_메뉴가_있다(self):
        code = _read("store_ui")
        self.assertIn("def _tile_menu", code)
        body = code.split("def _tile_menu")[1].split("\n    def ")[0]
        self.assertIn("_delete_items", body)

    def test_함께_사라지는_것을_미리_센다(self):
        r"""팔레트 자리는 물감을 지우면 같이 걷힌다(_purge_palette_refs).

        모르고 지우면 시험지 팔레트에 구멍이 난다 — 지우기 전에 말해야 한다.
        """
        body = _read("store_ui").split("def _delete_items")[1] \
                                .split("\n    def ")[0]
        self.assertIn("count_palette_refs", body)
        self.assertIn("askyesno", body)
        self.assertIn("되돌릴 수 없", body)

    def test_꾸러미가_쓰는_물감은_막는다(self):
        """지우면 그 꾸러미의 빈칸 수가 조용히 줄어 시험지가 어긋난다."""
        body = _read("store_ui").split("def _delete_items")[1] \
                                .split("\n    def ")[0]
        self.assertIn("MixInUse", body)


class DropOnSubTab(unittest.TestCase):
    r"""끌어서 하위 분류 탭에 놓으면 그 분류로 옮긴다 (038-d)."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("400x600+50+50")
        self.dropped = []
        self.panel = _panel(self.root, lambda b, x, y: self.dropped.append((x, y)))
        self.panel.filter = "템플릿"
        self.panel._show_sub_row()
        self.root.update()
        self.root.update_idletasks()
        self.addCleanup(self.root.destroy)

    def _cell_xy(self, sub):
        cell = self.panel._sub_frames["템플릿"]._cells[sub][0]
        return cell.winfo_rootx() + 3, cell.winfo_rooty() + 3

    def test_탭_안이면_그_분류를_돌려준다(self):
        x, y = self._cell_xy("")
        # 미분류는 빈 문자열이라 **못 찾은 None 과 반드시 구분**돼야 한다
        self.assertEqual(self.panel._sub_at(x, y), "")

    def test_탭_밖이면_None(self):
        x, y = self._cell_xy("")
        self.assertIsNone(self.panel._sub_at(x, y + 5000))

    def test_탭에_놓으면_팔레트로_안_간다(self):
        x, y = self._cell_xy("")
        self.panel.refresh = lambda: None
        self.panel._drag = {"ghost": object(), "cat": "템플릿",
                            "item": {"id": "t1"}, "block": {"type": "template"},
                            "over": None}
        self.panel._tile_release(_Ev(x, y))
        self.assertEqual(self.dropped, [], "분류로 옮기려던 것이 팔레트에 꽂혔다")

    def test_탭_밖에_놓으면_팔레트로_간다(self):
        """기존 길(팔레트에 끌어다 놓기)이 그대로 살아 있어야 한다."""
        x, y = self._cell_xy("")
        self.panel._drag = {"ghost": object(), "cat": "템플릿",
                            "item": {"id": "t1"}, "block": {"type": "template"},
                            "over": None}
        self.panel._tile_release(_Ev(x, y + 5000))
        self.assertEqual(len(self.dropped), 1)

    def test_다른_분류에_놓으면_옮긴다(self):
        made = library.add_subcat("템플릿", "검사용분류")
        self.addCleanup(lambda: library.delete_subcat("템플릿", made))
        self.panel.refresh = lambda: None
        self.panel._subcats.setdefault("템플릿", [])
        if made not in self.panel._subcats["템플릿"]:
            self.panel._subcats["템플릿"].append(made)
        self.panel._sub_frames.pop("템플릿", None)
        self.panel._sub_shown = None
        self.panel._show_sub_row()
        self.root.update()
        self.root.update_idletasks()
        x, y = self._cell_xy(made)
        moved = []
        with mock.patch.object(library, "set_subcat",
                               lambda c, i, s: moved.append((c, i, s))):
            self.panel._drag = {"ghost": object(), "cat": "템플릿",
                                "item": {"id": "t1"}, "block": None,
                                "over": None}
            self.panel._tile_release(_Ev(x, y))
        self.assertEqual(moved, [("템플릿", "t1", made)])

    def test_제자리에_놓으면_아무_일도_안_한다(self):
        moved = []
        with mock.patch.object(library, "set_subcat",
                               lambda c, i, s: moved.append(s)):
            self.panel.refresh = lambda: None
            self.panel._move_to_sub("템플릿", {"id": "t1"}, "")
        self.assertEqual(moved, [])

    def test_끌고_지나가는_탭을_강조한다(self):
        """어디에 떨어지는지 안 보이면 끌어놓기는 못 쓴다."""
        cell = self.panel._sub_frames["템플릿"]._cells[""][0]
        d = {"over": None}
        self.panel._hover_sub(d, "")
        self.assertEqual(int(cell.cget("highlightthickness")), 2)
        self.panel._hover_sub(d, None)
        self.assertEqual(int(cell.cget("highlightthickness")), 1)

    def test_담아_둔_것이_있으면_전부_옮긴다(self):
        """Ctrl 로 담아 두고 그중 하나를 끌면 담은 것 전부가 간다."""
        self.panel.multi = {("템플릿", "a"), ("템플릿", "b"), ("양식", "z")}
        got = self.panel._targets_of("템플릿", {"id": "a"})
        self.assertEqual(sorted(got), ["a", "b"], "다른 분류까지 딸려가면 안 된다")

    def test_담은_것_밖을_집으면_그_하나만(self):
        self.panel.multi = {("템플릿", "a")}
        self.assertEqual(self.panel._targets_of("템플릿", {"id": "c"}), ["c"])


if __name__ == "__main__":
    unittest.main()
