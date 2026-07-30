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

# 실제 화면 값 (2026-07-30): 칸 58px, 이름 body = 12pt → 한글 한 자 16px.
# 이 조합에서 한 칸은 2자, 두 칸은 6자가 들어간다.
CELL = 58
CHAR = 16


def fit(text, span):
    return fit_label(text, span, CELL, CHAR)


class LabelMaxTest(unittest.TestCase):
    r"""자수 상한은 **칸 폭에서 계산한다**.

    예전에는 `span * 2` 로 못박혀 있었다. 그 값은 26px 칸 시절 것이라, 칸이
    58px 로 커진 뒤에도 그대로 남아 '마크다운 변환'(6자)이 두 칸을 쓰고도
    네 자에서 잘렸다 (사용자 지적 2026-07-30). 그 회귀를 여기서 막는다.
    """

    def test_칸이_커지면_자수도_늘어난다(self):
        self.assertGreater(label_max(2, 58, 16), label_max(2, 26, 16))

    def test_글자가_커지면_자수는_줄어든다(self):
        self.assertLess(label_max(2, 58, 20), label_max(2, 58, 16))

    def test_두_칸이면_한_칸의_두_배보다_넉넉하다(self):
        # 칸 사이 틈까지 글자가 쓰므로 단순히 두 배가 아니다
        self.assertGreater(label_max(2, CELL, CHAR), label_max(1, CELL, CHAR) * 2)

    def test_아무리_좁아도_두_자는_보인다(self):
        self.assertEqual(label_max(1, 10, 99), 2)
        self.assertEqual(label_max(0, CELL, CHAR), 2)


class FitLabelTest(unittest.TestCase):

    def test_짧으면_그대로(self):
        self.assertEqual(fit("사진", span=1), "사진")

    def test_길면_자르고_말줄임(self):
        self.assertEqual(fit("양식채우기", span=1), "양식…")

    def test_칸이_넓으면_더_많이_들어간다(self):
        self.assertEqual(fit("양식채우기", span=3), "양식채우기")

    def test_두_칸이면_여섯_자가_들어간다(self):
        # 이게 이번에 고친 것 — 예전에는 네 자에서 잘려 '마크다운…' 이었다
        self.assertEqual(fit("마크다운 변환", span=2), "마크다운 변환")
        self.assertEqual(fit("통합 찾기", span=2), "통합 찾기")

    def test_줄바꿈은_살린다(self):
        # 이게 핵심 — 좁은 칸에 두 줄로 넣을 수 있어야 한다
        self.assertEqual(fit("양식\n채우기", span=2), "양식\n채우기")

    def test_줄마다_따로_자른다(self):
        # 전체를 한 덩어리로 자르면 둘째 줄이 통째로 사라진다
        self.assertEqual(fit("가나다라마바사\n아자차카타파하", span=2),
                         "가나다라마…\n아자차카타…")

    def test_한_줄만_길어도_다른_줄은_안_건드린다(self):
        self.assertEqual(fit("가\n나다라마바사아자", span=2), "가\n나다라마바…")

    def test_빈_값도_안전하다(self):
        self.assertEqual(fit("", span=2), "")
        self.assertEqual(fit(None, span=2), "")


if __name__ == "__main__":
    unittest.main()
