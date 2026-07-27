# -*- coding: utf-8 -*-
r"""변환이 실패했을 때 사용자의 글을 잃지 않는가 (2026-07-26 검진).

변환은 **선택을 먼저 지운 뒤** 계획을 실행한다 — 그 자리가 삽입 지점이라
순서를 바꿀 수 없다. 그런데 계획 실행이 실패하면 지운 글이 돌아오지 않았다.
사용자가 쓴 문장이 조용히 사라지는 유일한 경로였다.

여기서 못박는 것: `restore_text` 는 **줄 구조까지 그대로** 되돌린다.
(한 줄로 뭉치면 표·문단이 어긋나 되돌린 의미가 없다)
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import engine_library        # noqa: E402


class FakeHwp:
    """문서에 들어간 것을 순서대로 기록하는 가짜 한글."""

    def __init__(self, fail_at=None):
        self.written = []
        self._fail_at = fail_at         # 이 번째 삽입에서 터진다 (1부터)
        self._n = 0
        engine = self

        class _Action:
            @staticmethod
            def Run(name):
                if name == "BreakPara":
                    engine.written.append("\n")
        self.HAction = _Action()

    def insert(self, text):
        self._n += 1
        if self._fail_at is not None and self._n >= self._fail_at:
            raise RuntimeError("한글이 응답하지 않습니다")
        self.written.append(text)

    @property
    def text(self):
        return "".join(self.written)


class RestoreTextTest(unittest.TestCase):

    def _run(self, text, fake):
        with mock.patch.object(engine_library, "_h", return_value=fake), \
                mock.patch.object(engine_library, "insert_plain",
                                  side_effect=fake.insert):
            return engine_library.restore_text(text)

    def test_한_줄은_그대로(self):
        fake = FakeHwp()
        self.assertTrue(self._run("다음 중 옳은 것은?", fake))
        self.assertEqual(fake.text, "다음 중 옳은 것은?")

    def test_여러_줄은_문단으로_되살린다(self):
        """핵심 — 통째로 넣으면 한글이 문단을 안 나눠 한 줄로 뭉친다(실측)."""
        fake = FakeHwp()
        self.assertTrue(self._run("첫 줄\n둘째 줄\n셋째 줄", fake))
        self.assertEqual(fake.text, "첫 줄\n둘째 줄\n셋째 줄")

    def test_빈_줄도_살린다(self):
        """빈 줄을 흘리면 문단 사이가 붙어 원문과 달라진다."""
        fake = FakeHwp()
        self.assertTrue(self._run("첫 줄\n\n셋째 줄", fake))
        self.assertEqual(fake.text, "첫 줄\n\n셋째 줄")

    def test_한글이_주는_줄바꿈_모양을_그대로_받는다(self):
        r"""한글은 \r\n 으로 준다 — 그걸 문단 두 개로 세면 빈 줄이 생긴다."""
        fake = FakeHwp()
        self.assertTrue(self._run("첫 줄\r\n둘째 줄", fake))
        self.assertEqual(fake.text, "첫 줄\n둘째 줄")

    def test_역슬래시와_줄표가_그대로(self):
        """되돌린 글이 원문과 한 글자라도 다르면 되돌린 뜻이 없다."""
        fake = FakeHwp()
        src = "붙임 — 계획서 \\원1\\ 1부."
        self.assertTrue(self._run(src, fake))
        self.assertEqual(fake.text, src)

    def test_되돌리기가_실패해도_예외를_흘리지_않는다(self):
        """이미 실패를 수습하는 중이다 — 여기서 또 터지면 안내조차 못 한다."""
        fake = FakeHwp(fail_at=2)
        with mock.patch("engine_library.applog.exc"):
            self.assertFalse(self._run("첫 줄\n둘째 줄", fake))


class ErrorPathTest(unittest.TestCase):
    r"""'문서를 건드리기 전에 실패하는가' 는 되돌리기 방식을 가르는 기준이다.

    engine_library.execute_library_plan 의 error 반환 지점이 **삽입 전** 하나뿐
    이어야, 그 경로에서 문서에 그대로 되돌려도 중복이 안 생긴다.
    나중에 error 반환을 더 만들면 이 테스트가 깨져서 다시 판단하게 된다.
    """

    def test_계획_실행의_error_반환은_한_곳뿐(self):
        src = pathlib.Path(engine_library.__file__).read_text(encoding="utf-8")
        body = src.split("def execute_library_plan")[1]
        body = body.split("\ndef ")[0]
        self.assertEqual(body.count('"error"'), 1,
                         "error 반환 지점이 늘었다 — 되돌리기가 안전한지 "
                         "(삽입 전에 나는지) 다시 확인할 것")


if __name__ == "__main__":
    unittest.main()
