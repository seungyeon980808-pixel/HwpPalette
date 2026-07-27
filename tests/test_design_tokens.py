# -*- coding: utf-8 -*-
"""디자인 토큰과 대화상자 규칙 (2026-07-27 개편)."""
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import theme
import dialogs

ROOT = pathlib.Path(__file__).resolve().parent.parent
UI_FILES = ["main.py", "palette_ui.py", "library_ui.py", "store_ui.py",
            "form_table_ui.py", "form_fill_ui.py", "settings_ui.py",
            "bogi_visual_ui.py"]


class TokenTest(unittest.TestCase):
    def test_간격은_4의_배수(self):
        for name, v in theme.SP.items():
            self.assertEqual(v % 4, 0, f"{name}={v}")

    def test_글자_위계는_내림차순(self):
        order = ["title", "head", "body", "sub", "caption"]
        sizes = [theme.FS[k] for k in order]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_파스텔은_12색이고_밝기가_고르다(self):
        self.assertEqual(len(theme.PASTELS), 12)
        self.assertEqual(len(theme.PASTELS_DARK), 12)
        for _name, hexv in theme.PASTELS:
            # 전부 밝아야 검은 글자가 읽힌다 (text_on 이 검정을 준다)
            self.assertEqual(theme.text_on(hexv), "#1d1d1f", hexv)

    def test_파스텔_이름이_두_모드에서_같다(self):
        self.assertEqual([n for n, _ in theme.PASTELS],
                         [n for n, _ in theme.PASTELS_DARK])


class NearestPastelTest(unittest.TestCase):
    def _name(self, hexv):
        table = {v.lower(): n for n, v in theme.PASTELS}
        return table.get((theme.nearest_pastel(hexv) or "").lower())

    def test_원색은_같은_색상의_파스텔로(self):
        self.assertEqual(self._name("#00e050"), "초록")
        self.assertEqual(self._name("#ffe066"), "노랑")
        self.assertEqual(self._name("#0000ff"), "보라")

    def test_무채색은_회색으로(self):
        for c in ("#808080", "#000000", "#ffffff"):
            self.assertEqual(self._name(c), "회색", c)

    def test_이미_파스텔이면_그대로(self):
        for _n, hexv in theme.PASTELS:
            self.assertEqual(theme.nearest_pastel(hexv).lower(), hexv.lower())

    def test_색이_아니면_None(self):
        self.assertIsNone(theme.nearest_pastel("빨강"))
        self.assertIsNone(theme.nearest_pastel(""))


class DialogApiTest(unittest.TestCase):
    """messagebox 를 갈아끼운 자리가 같은 이름·같은 인자를 받는가."""

    def test_messagebox_이름을_모두_갖췄다(self):
        for fn in ("showinfo", "showwarning", "showerror", "askyesno",
                   "askyesnocancel", "askokcancel"):
            self.assertTrue(callable(getattr(dialogs, fn)), fn)

    def test_윈도우_기본_대화상자를_안_쓴다(self):
        """UI 파일이 tkinter.messagebox 를 직접 임포트하면 얼굴이 깨진다."""
        for fn in UI_FILES:
            src = (ROOT / fn).read_text(encoding="utf-8")
            self.assertNotRegex(
                src, r"from tkinter import[^\n]*\bmessagebox\b",
                f"{fn}: dialogs 를 써야 한다")

    def test_자유_색_고르개는_블럭에_안_쓴다(self):
        """블럭 색은 12색 파스텔로만 고른다 (문서 글자색은 예외)."""
        src = (ROOT / "palette_ui.py").read_text(encoding="utf-8")
        for m in re.finditer(r"colorchooser\.askcolor", src):
            head = src[max(0, m.start() - 300):m.start()]
            self.assertIn("문서 글자색", head,
                          "블럭 색 고르기는 _PastelDialog 를 써야 한다")


if __name__ == "__main__":
    unittest.main()
