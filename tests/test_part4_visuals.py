# -*- coding: utf-8 -*-
r"""파트 4 — 보이는 것 (027·029·030·037, 2026-08-01).

넷 다 화면 부품·판의 규칙이라, 되돌리면 화면이 옛날로 돌아가는 모양을 못박는다.
"""

import pathlib
import sys
import tkinter as tk
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import srcpath                                     # noqa: E402

from hwp_palette.design import ribbon              # noqa: E402
from hwp_palette.design import theme               # noqa: E402
from hwp_palette.design.roundbtn import RoundButton  # noqa: E402
from hwp_palette.model import builtin_actions      # noqa: E402
from hwp_palette.model import library              # noqa: E402


def _read(module):
    return srcpath.src(module).read_text(encoding="utf-8")


class RibbonRules(unittest.TestCase):
    r"""037 — 여럿을 담은 칸의 세로 띠 (안 B: 겹침=개수 · 섞기=MIX)."""

    def test_판정은_한_곳이다(self):
        """겹친 칸은 개수, 꾸러미는 MIX — 세 화면이 같은 답을 쓴다."""
        self.assertEqual(library.block_badge(
            {"type": "stack", "items": [{}, {}, {}]}), ("stack", "3"))
        self.assertIsNone(library.block_badge({"type": "char"}))
        self.assertIsNone(library.block_badge({"type": "stack", "items": []}))

    def test_겹침과_섞기는_색을_가른다(self):
        """택일과 합체는 다른 물건 — 같은 표시면 서로를 가린다."""
        self.assertNotEqual(ribbon.colors("stack"), ribbon.colors("mix"))
        self.assertEqual(ribbon.colors("mix"), (theme.MIX_BG, theme.MIX_FG))

    def test_세_화면이_같은_부품을_쓴다(self):
        self.assertIn("btn.set_ribbon", _read("app"))            # 메인 팔레트
        self.assertIn("ribbon.attach", _read("palette_ui"))      # 설정 격자
        self.assertIn("ribbon.attach", _read("store_ui"))        # 창고 카드
        for m in ("app", "palette_ui"):
            self.assertIn("block_badge", _read(m))

    def test_버튼_띠는_그려지고_떼진다(self):
        root = tk.Tk()
        root.geometry("200x120+40+40")     # withdraw 하면 크기가 안 잡혀 못 그린다
        try:
            b = RoundButton(root, text="답안", bg="#ffffff",
                            font=(theme.FONT, 10))
            b.fit(pad_x=20, pad_y=14)
            b.pack()
            root.update()
            b.set_ribbon("6", *ribbon.colors("stack"))
            self.assertTrue(b.find_withtag("ribbon"))
            self.assertEqual(b.itemcget("ribbontxt", "text"), "6")
            b.set_ribbon(None, "", "")
            self.assertFalse(b.find_withtag("ribbon"))
        finally:
            root.destroy()


class UsageRules(unittest.TestCase):
    r"""027 — 도구 판의 빈자리는 사용법. **글의 출처는 builtin_actions 한 곳.**"""

    def test_보이는_도구는_전부_사용법이_있다(self):
        for a in builtin_actions.visible_actions():
            self.assertTrue(builtin_actions.usage_of(a["key"]),
                            f"{a['key']} 의 사용법이 없다 — 판이 도로 빈다")

    def test_판이_그_출처를_쓴다(self):
        body = _read("palette_ui").split("def _show_tool_detail")[1] \
                                  .split("\n    def ")[0]
        self.assertIn("usage_of", body)


class PhotoPanelRules(unittest.TestCase):
    r"""029 (안 1) — 사진 폴더 관리는 **판 안에서**. [설정] 단추는 없앴다."""

    def test_다섯_탭_창을_여는_단추가_없다(self):
        body = _read("palette_ui").split("def _show_tool_detail")[1] \
                                  .split("\n    def _show_edit_form")[0]
        self.assertNotIn("open_manager", body,
                         "판 안 관리로 바꿨는데 설정 창 입구가 돌아왔다")
        self.assertIn("_render_photo_dirs", body)

    def test_순서_바꾸기가_있다(self):
        r"""폴더 순서 = 이름 충돌 우선순위 — 여태 바꿀 길이 없었다."""
        from hwp_palette.core import settings
        self.assertTrue(callable(settings.move_photo_dir))
        body = _read("palette_ui").split("def _render_photo_dirs")[1] \
                                  .split("\n    def ")[0]
        self.assertIn("move_photo_dir", body)

    def test_순서_바꾸기_동작(self):
        from unittest import mock
        from hwp_palette.core import settings
        store = {"photo_dirs": ["C:/a", "C:/b", "C:/c"]}
        with mock.patch.object(settings, "get_config_value",
                               lambda k, d=None: store.get(k, d)), \
             mock.patch.object(settings, "set_config_value",
                               lambda k, v: store.__setitem__(k, v)):
            self.assertTrue(settings.move_photo_dir("C:/c", -1))
            self.assertEqual([p.lower().replace("\\", "/")
                              for p in store["photo_dirs"]],
                             ["c:/a", "c:/c", "c:/b"])
            self.assertFalse(settings.move_photo_dir("C:/a", -1))  # 맨 위


class FormatDialogRules(unittest.TestCase):
    r"""030 (범위 ②) — 서식 만들기 창이 앱과 같은 얼굴이 된다."""

    def test_윈도우_기본_체크와_스핀이_없다(self):
        body = _read("palette_ui").split("class FunctionDialog")[1] \
                                  .split("\nclass ")[0]
        code = [ln for ln in body.splitlines()
                if not ln.strip().startswith("#")]     # 내력 주석은 남는다
        joined = "\n".join(code)
        self.assertNotIn("tk.Checkbutton", joined)
        self.assertNotIn("ttk.Spinbox", joined)
        self.assertIn("fields.Check", joined)
        self.assertIn("fields.Spin", joined)

    def test_세_카드로_묶인다(self):
        body = _read("palette_ui").split("class FunctionDialog")[1] \
                                  .split("\nclass ")[0]
        for title in ("글자", "문단", "여백"):
            self.assertIn(f'"{title}"', body)

    def test_카탈로그의_모든_항목이_창에_나온다(self):
        r"""카드 목록에 빠진 키가 있어도 **맨 아래에라도** 나와야 한다 —
        카탈로그에 항목을 더했는데 창에서 조용히 사라지면 안 된다."""
        root = tk.Tk()
        root.withdraw()
        try:
            from hwp_palette.model import func_catalog
            from hwp_palette.ui import palette_ui
            d = palette_ui.FunctionDialog(root)
            root.update()
            self.assertEqual(set(d.rows),
                             {f["key"] for f in func_catalog.FUNCTIONS})
            d.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
