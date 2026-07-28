# -*- coding: utf-8 -*-
r"""블럭 이름 표시 규칙 (2026-07-25) — 창 없이 검증.

긴 이름을 넣으려면 칸을 옆으로 늘리는 수밖에 없었고, 칸이 넓어지면 창이 그만큼
좌우로 길어졌다. 이름에 **줄바꿈**을 허용해 좁은 칸에 두 줄로 넣을 수 있게 했다.
그 규칙(줄마다 따로 자른다)을 여기서 못박는다.

main.py 는 임포트하면 창을 띄우므로 함수 정의만 떼어 실행한다.
"""

import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from tests.srcpath import src        # noqa: E402

MAIN = src("app")


def _extract(*names):
    """main.py 에서 함수 정의들을 떼어 한 네임스페이스에서 실행한다."""
    src = MAIN.read_text(encoding="utf-8")
    ns = {}
    for name in names:
        m = re.search(rf"def {name}\(.*?\n(?=\n\n)", src, re.S)
        if not m:
            raise AssertionError(f"main.py 에서 {name} 을 못 찾았습니다")
        exec(m.group(0), ns)
    return ns


_ns = _extract("_block_label_max", "_fit_label")
fit_label = _ns["_fit_label"]
label_max = _ns["_block_label_max"]


class FitLabelTest(unittest.TestCase):

    def test_짧으면_그대로(self):
        self.assertEqual(fit_label("사진", span=1), "사진")

    def test_길면_자르고_말줄임(self):
        # 1칸 = 2자
        self.assertEqual(fit_label("양식채우기", span=1), "양식…")

    def test_칸이_넓으면_더_많이_들어간다(self):
        self.assertEqual(fit_label("양식채우기", span=3), "양식채우기")

    def test_줄바꿈은_살린다(self):
        # 이게 핵심 — 좁은 칸에 두 줄로 넣을 수 있어야 한다
        self.assertEqual(fit_label("양식\n채우기", span=2), "양식\n채우기")

    def test_줄마다_따로_자른다(self):
        # 전체를 한 덩어리로 자르면 둘째 줄이 통째로 사라진다 (span 2 = 줄당 4자)
        self.assertEqual(fit_label("가나다라마\n바사아자차", span=2),
                         "가나다라…\n바사아자…")

    def test_한_줄만_길어도_다른_줄은_안_건드린다(self):
        self.assertEqual(fit_label("가\n나다라마바", span=2), "가\n나다라마…")

    def test_줄당_한도라서_두_줄이면_두_배가_들어간다(self):
        # 칸을 넓히지 않고도 긴 이름을 넣는 방법 — 이게 이 기능의 존재 이유다
        self.assertEqual(fit_label("양식\n채우기", span=2), "양식\n채우기")

    def test_빈_값도_안전하다(self):
        self.assertEqual(fit_label("", span=2), "")
        self.assertEqual(fit_label(None, span=2), "")

    def test_한_칸도_최소_두_자는_보인다(self):
        self.assertEqual(label_max(1), 2)
        self.assertEqual(label_max(0), 2)      # 이상값이 와도 0자가 되진 않는다


if __name__ == "__main__":
    unittest.main()
