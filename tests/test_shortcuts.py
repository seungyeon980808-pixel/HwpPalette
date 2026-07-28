# -*- coding: utf-8 -*-
"""단축키·창 위치의 순수 규칙 (UI 제안 9·15) — 한글/창 없이 검증.

main.py 는 임포트하면 창을 띄우므로 함수 정의만 떼어 실행한다.
규칙이 바뀌면 여기서 먼저 깨지도록 실제 구현을 읽어온다.
"""

import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import settings      # noqa: E402

from tests.srcpath import src        # noqa: E402

MAIN = src("app")


def _extract(name):
    src = MAIN.read_text(encoding="utf-8")
    m = re.search(rf"def {name}\(.*?\n(?=\n\n)", src, re.S)
    if not m:
        raise AssertionError(f"main.py 에서 {name} 을 못 찾았습니다")
    ns = {}
    exec(m.group(0), ns)
    return ns[name]


reading_order = _extract("_reading_order")


class ReadingOrderTest(unittest.TestCase):
    """Ctrl+1~9 번호의 기준 — 눈으로 읽는 순서(위→아래, 왼→오)."""

    def _v(self, blocks):
        return [b["v"] for b in reading_order(blocks)]

    def test_같은_줄은_왼쪽부터(self):
        blocks = [{"row": 0, "col": 2, "v": "C"},
                  {"row": 0, "col": 0, "v": "A"},
                  {"row": 0, "col": 1, "v": "B"}]
        self.assertEqual(self._v(blocks), ["A", "B", "C"])

    def test_윗줄이_먼저(self):
        blocks = [{"row": 2, "col": 0, "v": "C"},
                  {"row": 0, "col": 9, "v": "A"},
                  {"row": 1, "col": 0, "v": "B"}]
        self.assertEqual(self._v(blocks), ["A", "B", "C"])

    def test_좌표가_없으면_0으로_본다(self):
        blocks = [{"v": "A"}, {"row": 1, "col": 0, "v": "B"}]
        self.assertEqual(self._v(blocks), ["A", "B"])

    def test_원본_목록을_바꾸지_않는다(self):
        blocks = [{"row": 1, "col": 0, "v": "B"}, {"row": 0, "col": 0, "v": "A"}]
        reading_order(blocks)
        self.assertEqual([b["v"] for b in blocks], ["B", "A"])


class WindowPosTest(unittest.TestCase):
    """창 위치 저장 — 값이 깨져 있어도 프로그램이 죽으면 안 된다."""

    def setUp(self):
        self.store = {}
        import unittest.mock as mock
        for name, fn in (("get_config_value",
                          lambda k, d=None: self.store.get(k, d)),
                         ("set_config_value",
                          lambda k, v: self.store.__setitem__(k, v))):
            p = mock.patch.object(settings, name, side_effect=fn)
            p.start()
            self.addCleanup(p.stop)

    def test_저장한_적_없으면_None(self):
        self.assertIsNone(settings.get_window_pos())

    def test_저장하고_읽는다(self):
        settings.set_window_pos(120, 340)
        self.assertEqual(settings.get_window_pos(), (120, 340))

    def test_깨진_값은_None(self):
        for bad in ("이상한값", [1], [1, 2, 3], None, {"x": 1}, ["a", "b"]):
            self.store["window_pos"] = bad
            self.assertIsNone(settings.get_window_pos(), f"{bad!r} 처리 실패")

    def test_실수도_정수로_받는다(self):
        self.store["window_pos"] = [10.7, 20.2]
        self.assertEqual(settings.get_window_pos(), (10, 20))


class UiScaleTest(unittest.TestCase):
    """화면 모드는 두 단계뿐 — 중간값이 들어와도 하나로 정리된다."""

    def setUp(self):
        self.store = {}
        import unittest.mock as mock
        for name, fn in (("get_config_value",
                          lambda k, d=None: self.store.get(k, d)),
                         ("set_config_value",
                          lambda k, v: self.store.__setitem__(k, v))):
            p = mock.patch.object(settings, name, side_effect=fn)
            p.start()
            self.addCleanup(p.stop)

    def test_기본은_작게(self):
        self.assertEqual(settings.get_ui_scale(), 1.0)

    def test_크게_저장하고_읽는다(self):
        settings.set_ui_scale(1.3)
        self.assertEqual(settings.get_ui_scale(), 1.3)

    def test_중간값은_가까운_쪽으로(self):
        self.store["ui_scale"] = 1.2
        self.assertEqual(settings.get_ui_scale(), 1.3)
        self.store["ui_scale"] = 1.1
        self.assertEqual(settings.get_ui_scale(), 1.0)

    def test_깨진_값은_작게(self):
        self.store["ui_scale"] = "이상한값"
        self.assertEqual(settings.get_ui_scale(), 1.0)


if __name__ == "__main__":
    unittest.main()
