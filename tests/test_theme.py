# -*- coding: utf-8 -*-
"""색·대비 규칙 (UI 제안 17·18).

여기서 지키려는 것은 "예쁘다"가 아니라 **읽힌다**이다. 배경이 어떻든 글자가
보여야 하고, 두 모드가 같은 이름의 색을 모두 갖고 있어야 한 창만 하얗게
뜨는 일이 없다.
"""

import pathlib
import sys
import unittest
import unittest.mock as mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import settings   # noqa: E402
from hwp_palette.design import theme      # noqa: E402

WCAG_BODY = 4.5     # 본문 글자 최소 대비
WCAG_LARGE = 3.0    # 큰 글자·보조 표기 최소 대비


class PaletteShapeTest(unittest.TestCase):
    """두 모드가 같은 이름을 갖춰야 한다 — 하나라도 빠지면 KeyError 로 창이 안 뜬다."""

    def test_같은_키를_갖는다(self):
        self.assertEqual(set(theme.LIGHT), set(theme.DARK))

    def test_블럭색도_같은_키(self):
        self.assertEqual(set(theme.BLOCK_LIGHT), set(theme.BLOCK_DARK))

    def test_알림색도_같은_키(self):
        self.assertEqual(set(theme.NOTICE_LIGHT), set(theme.NOTICE_DARK))

    def test_블럭_종류가_다_있다(self):
        # main._BLOCK_COLOR 가 이 목록으로 만들어진다. 빠지면 그 종류만 흰 칸.
        for t in ("char", "template", "function", "form"):
            self.assertIn(t, theme.BLOCK_LIGHT)

    def test_전부_여섯자리_색(self):
        for name, table in (("LIGHT", theme.LIGHT), ("DARK", theme.DARK),
                            ("BLOCK_LIGHT", theme.BLOCK_LIGHT),
                            ("BLOCK_DARK", theme.BLOCK_DARK)):
            for k, v in table.items():
                self.assertRegex(v, r"^#[0-9a-fA-F]{6}$", f"{name}[{k}]")


class ContrastTest(unittest.TestCase):
    """실제로 읽히는지 — 숫자로 재서 확인한다."""

    def test_본문_대비(self):
        for table in (theme.LIGHT, theme.DARK):
            r = theme.contrast_ratio(table["text"], table["bg"])
            self.assertGreaterEqual(r, WCAG_BODY, f"본문 대비 {r:.1f}")

    def test_보조글자_대비(self):
        # 버전·저작자 표기에 쓰는 색. 예전 #86868b 는 3.3 이라 여기서 걸렸다.
        for table in (theme.LIGHT, theme.DARK):
            for bg in (table["bg"], table["card"]):
                r = theme.contrast_ratio(table["muted"], bg)
                self.assertGreaterEqual(r, WCAG_BODY, f"보조 대비 {r:.1f}")

    def test_알림_대비(self):
        for table in (theme.NOTICE_LIGHT, theme.NOTICE_DARK):
            for kind, (fg, bg) in table.items():
                r = theme.contrast_ratio(fg, bg)
                self.assertGreaterEqual(r, WCAG_BODY, f"{kind} 대비 {r:.1f}")

    def test_블럭_기본색_위의_글자(self):
        for table in (theme.BLOCK_LIGHT, theme.BLOCK_DARK):
            for t, bg in table.items():
                r = theme.contrast_ratio(theme.text_on(bg), bg)
                self.assertGreaterEqual(r, WCAG_BODY, f"{t} 대비 {r:.1f}")

    def test_사용자가_어떤_색을_골라도_글자가_보인다(self):
        # 색 고르기는 자유다(colorchooser). 극단값에서도 대비가 나와야 한다.
        for bg in ("#000000", "#ffffff", "#ff0000", "#00ff00", "#0000ff",
                   "#808080", "#7f7f7f", "#123456", "#fedcba"):
            r = theme.contrast_ratio(theme.text_on(bg), bg)
            self.assertGreaterEqual(r, WCAG_LARGE, f"{bg} 대비 {r:.1f}")

    def test_회색_경계에서_흰검이_갈린다(self):
        self.assertEqual(theme.text_on("#ffffff"), "#1d1d1f")
        self.assertEqual(theme.text_on("#000000"), "#ffffff")

    def test_깨진_색은_검은_글자(self):
        # 설정 파일이 손상돼도 흰 배경 가정이 안전하다(대개 밝은 배경).
        for bad in ("", None, "빨강", "#12", "#zzzzzz"):
            self.assertEqual(theme.text_on(bad), "#1d1d1f")

    def test_세자리_색도_읽는다(self):
        self.assertEqual(theme.text_on("#fff"), theme.text_on("#ffffff"))

    def test_대비는_순서를_안_탄다(self):
        a = theme.contrast_ratio("#000000", "#ffffff")
        b = theme.contrast_ratio("#ffffff", "#000000")
        self.assertAlmostEqual(a, b)
        self.assertAlmostEqual(a, 21.0, places=1)


class ModeTest(unittest.TestCase):

    def setUp(self):
        self.store = {}
        # settings 를 목으로 갈아끼우는 동안 theme 의 모드 캐시가 진짜
        # config.json 의 세대 표식을 물고 있으면 목이 안 보인다 — 시작할 때
        # 비우고, 끝날 때도 비워 목으로 캐시된 값이 뒤 테스트로 새지 않게 한다.
        theme._drop_mode_cache()
        self.addCleanup(theme._drop_mode_cache)
        for name, fn in (("get_config_value",
                          lambda k, d=None: self.store.get(k, d)),
                         ("set_config_value",
                          lambda k, v: self.store.__setitem__(k, v))):
            p = mock.patch.object(settings, name, side_effect=fn)
            p.start()
            self.addCleanup(p.stop)

    def test_기본은_밝게(self):
        self.assertEqual(theme.get_mode(), "light")
        self.assertFalse(theme.is_dark())

    def test_어둡게_저장하고_읽는다(self):
        theme.set_mode("dark")
        self.assertTrue(theme.is_dark())
        self.assertEqual(theme.colors()["bg"], theme.DARK["bg"])

    def test_모르는_값은_밝게(self):
        for bad in ("", None, "어둡게", 1, "DARK"):
            self.store[theme.MODE_KEY] = bad
            self.assertEqual(theme.get_mode(), "light", f"{bad!r}")

    def test_colors_는_복사본이라_원본이_안_바뀐다(self):
        c = theme.colors()
        c["bg"] = "#ff0000"
        self.assertNotEqual(theme.LIGHT["bg"], "#ff0000")


if __name__ == "__main__":
    unittest.main()
