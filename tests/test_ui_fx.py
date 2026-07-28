# -*- coding: utf-8 -*-
"""호버 색 보간의 순수 계산 (애플 A안, 2026-07-25) — 창 없이 검증.

색이 틀리면 '부드러운 전환'이 아니라 '이상한 색 번쩍임'이 된다.
블럭 색은 사용자가 아무 색이나 고를 수 있으므로 극단값도 안전해야 한다.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.design import ui_fx        # noqa: E402


class HexTest(unittest.TestCase):

    def test_기본_변환(self):
        self.assertEqual(ui_fx.hex_to_rgb("#ffffff"), (255, 255, 255))
        self.assertEqual(ui_fx.hex_to_rgb("#000000"), (0, 0, 0))
        self.assertEqual(ui_fx.rgb_to_hex((255, 0, 128)), "#ff0080")

    def test_축약형도_받는다(self):
        self.assertEqual(ui_fx.hex_to_rgb("#abc"), (0xaa, 0xbb, 0xcc))

    def test_색이_아니면_거부(self):
        for bad in ("", None, "#12", "파랑"):
            with self.assertRaises(ValueError):
                ui_fx.hex_to_rgb(bad)

    def test_범위를_벗어난_값은_잘라낸다(self):
        self.assertEqual(ui_fx.rgb_to_hex((300, -5, 128.7)), "#ff0080")


class LerpTest(unittest.TestCase):

    def test_양끝은_원래_색(self):
        self.assertEqual(ui_fx.lerp("#000000", "#ffffff", 0), "#000000")
        self.assertEqual(ui_fx.lerp("#000000", "#ffffff", 1), "#ffffff")

    def test_중간은_중간_색(self):
        self.assertEqual(ui_fx.lerp("#000000", "#ffffff", 0.5), "#7f7f7f")


class EaseOutTest(unittest.TestCase):
    """감속 곡선 — 선형 보간은 끝에서 뚝 멈춰 기계적으로 느껴진다."""

    def test_양끝은_0과_1(self):
        self.assertEqual(ui_fx.ease_out(0), 0)
        self.assertEqual(ui_fx.ease_out(1), 1)

    def test_초반이_더_빠르다(self):
        # ease-out: 앞에서 많이 가고 뒤에서 천천히 — 그래야 부드럽게 멈춘다
        self.assertGreater(ui_fx.ease_out(0.5), 0.5)

    def test_계속_증가한다(self):
        # 어느 구간에서도 뒤로 가면 안 된다 (색이 튀어 보인다)
        prev = -1
        for i in range(ui_fx.STEPS + 1):
            v = ui_fx.ease_out(i / ui_fx.STEPS)
            self.assertGreater(v, prev)
            prev = v

    def test_범위_밖도_안전하다(self):
        self.assertEqual(ui_fx.ease_out(-1), 0)
        self.assertEqual(ui_fx.ease_out(9), 1)


class DarkenTest(unittest.TestCase):

    def test_흰색이_회색이_된다(self):
        self.assertEqual(ui_fx.darken("#ffffff", 0.9), "#e5e5e5")

    def test_검정은_그대로(self):
        # 사용자가 검정 블럭을 골라도 죽지 않아야 한다
        self.assertEqual(ui_fx.darken("#000000"), "#000000")

    def test_누름이_호버보다_진하다(self):
        base = "#0071e3"
        hover = ui_fx.darken(base, ui_fx.HOVER_FACTOR)
        press = ui_fx.darken(base, ui_fx.PRESS_FACTOR)
        self.assertGreater(sum(ui_fx.hex_to_rgb(hover)),
                           sum(ui_fx.hex_to_rgb(press)))


class FontPickTest(unittest.TestCase):

    def test_글꼴은_아는_것_중_하나다(self):
        # Pretendard(Medium 우선)가 있으면 그것, 없으면 맑은 고딕
        from hwp_palette.design import theme
        self.assertIn(theme.FONT,
                      ("Pretendard Medium", "Pretendard", "맑은 고딕"))

    def test_프리텐다드면_크기를_1pt_올린다(self):
        # 같은 pt 에서 맑은 고딕보다 작게 보여 보정한다 (시인성 실측 2026-07-25)
        from hwp_palette.design import theme
        expect = 1 if theme.FONT.startswith("Pretendard") else 0
        self.assertEqual(theme.FONT_BOOST, expect)


if __name__ == "__main__":
    unittest.main()
