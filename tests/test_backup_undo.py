# -*- coding: utf-8 -*-
"""안전망 테스트 — 롤링 백업(제안 2)과 팔레트 실행취소(제안 1).

둘 다 '실수로 잃는 것'을 막는 장치라, 동작보다 **경계 조건**이 중요하다.
"""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import backup        # noqa: E402
from hwp_palette.model import palette       # noqa: E402


class RotateTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.f = pathlib.Path(self.tmp.name) / "config.json"

    def _bak(self, n):
        return self.f.with_suffix(self.f.suffix + f".bak{n}")

    def test_첫_저장은_백업하지_않는다(self):
        backup.rotate(self.f)                    # 파일이 아직 없다
        self.assertFalse(self._bak(1).exists())

    def test_직전_상태가_bak1_로_들어간다(self):
        self.f.write_text("A", encoding="utf-8")
        backup.rotate(self.f)
        self.assertEqual(self._bak(1).read_text(encoding="utf-8"), "A")

    def test_세_단계까지_밀린다(self):
        for text in "ABCD":
            self.f.write_text(text, encoding="utf-8")
            backup.rotate(self.f)
        # 마지막 rotate 직전 파일이 D → bak1=D, bak2=C, bak3=B (A 는 버려짐)
        self.assertEqual(self._bak(1).read_text(encoding="utf-8"), "D")
        self.assertEqual(self._bak(2).read_text(encoding="utf-8"), "C")
        self.assertEqual(self._bak(3).read_text(encoding="utf-8"), "B")
        self.assertFalse(self._bak(4).exists())

    def test_내용이_같으면_밀지_않는다(self):
        """같은 값 저장이 반복돼도 멀쩡한 과거가 밀려나면 안 된다."""
        self.f.write_text("A", encoding="utf-8")
        backup.rotate(self.f)
        self.f.write_text("B", encoding="utf-8")
        backup.rotate(self.f)                    # bak1=B, bak2=A
        for _ in range(5):
            backup.rotate(self.f)                # 내용 그대로 → 무시돼야 한다
        self.assertEqual(self._bak(1).read_text(encoding="utf-8"), "B")
        self.assertEqual(self._bak(2).read_text(encoding="utf-8"), "A")

    def test_복원하면_그_내용으로_돌아간다(self):
        self.f.write_text("옛날", encoding="utf-8")
        backup.rotate(self.f)
        self.f.write_text("망가짐", encoding="utf-8")
        self.assertTrue(backup.restore(self.f, 1))
        self.assertEqual(self.f.read_text(encoding="utf-8"), "옛날")

    def test_복원_전_상태도_백업된다(self):
        """되돌리기를 잘못했을 때 다시 되돌릴 수 있어야 한다."""
        self.f.write_text("옛날", encoding="utf-8")
        backup.rotate(self.f)
        self.f.write_text("지금", encoding="utf-8")
        backup.restore(self.f, 1)
        self.assertEqual(self._bak(1).read_text(encoding="utf-8"), "지금")

    def test_없는_백업은_복원_실패(self):
        self.f.write_text("A", encoding="utf-8")
        self.assertFalse(backup.restore(self.f, 3))

    def test_목록은_최신순(self):
        for text in "AB":
            self.f.write_text(text, encoding="utf-8")
            backup.rotate(self.f)
        nums = [n for n, _p, _s in backup.list_backups(self.f)]
        self.assertEqual(nums, [1, 2])


class UndoTest(unittest.TestCase):
    """팔레트 편집 되돌리기 — config.json 을 건드리지 않고 메모리로 검증."""

    def setUp(self):
        self.store = {}
        patches = [
            mock.patch.object(palette.settings, "get_config_value",
                              side_effect=lambda k, d=None: self.store.get(k, d)),
            mock.patch.object(palette.settings, "set_config_value",
                              side_effect=lambda k, v: self.store.__setitem__(k, v)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        palette._undo_stack.clear()
        palette._redo_stack.clear()
        self.addCleanup(palette._undo_stack.clear)
        self.addCleanup(palette._redo_stack.clear)

    def _tabs(self, *names):
        return [{"name": n, "cols": 5, "blocks": []} for n in names]

    def test_처음엔_되돌릴_것이_없다(self):
        self.assertFalse(palette.can_undo())
        self.assertFalse(palette.undo())

    def test_한_번_되돌린다(self):
        palette.save_tabs(self._tabs("가"))
        palette.save_tabs(self._tabs("가", "나"))
        self.assertTrue(palette.undo())
        self.assertEqual([t["name"] for t in self.store["palette_tabs"]], ["가"])

    def test_여러_단계_되돌린다(self):
        for names in (("가",), ("가", "나"), ("가", "나", "다")):
            palette.save_tabs(self._tabs(*names))
        palette.undo()
        palette.undo()
        self.assertEqual([t["name"] for t in self.store["palette_tabs"]], ["가"])

    def test_다시_실행(self):
        palette.save_tabs(self._tabs("가"))
        palette.save_tabs(self._tabs("가", "나"))
        palette.undo()
        self.assertTrue(palette.redo())
        self.assertEqual([t["name"] for t in self.store["palette_tabs"]],
                         ["가", "나"])

    def test_새_편집이_생기면_다시실행은_무효(self):
        palette.save_tabs(self._tabs("가"))
        palette.save_tabs(self._tabs("가", "나"))
        palette.undo()
        palette.save_tabs(self._tabs("가", "다"))   # 다른 방향으로 편집
        self.assertFalse(palette.can_redo())

    def test_같은_내용_저장은_쌓이지_않는다(self):
        palette.save_tabs(self._tabs("가"))
        for _ in range(3):
            palette.save_tabs(self._tabs("가"))
        self.assertFalse(palette.can_undo())

    def test_기록하지_않는_저장은_쌓이지_않는다(self):
        """하위호환 이전은 사용자의 편집이 아니므로 되돌림 대상이 아니다."""
        palette.save_tabs(self._tabs("가"))
        palette.save_tabs(self._tabs("가", "나"), _record=False)
        self.assertFalse(palette.can_undo())

    def test_한도를_넘으면_오래된_것부터_버린다(self):
        for i in range(palette._UNDO_LIMIT + 10):
            palette.save_tabs(self._tabs(f"탭{i}"))
        self.assertLessEqual(len(palette._undo_stack), palette._UNDO_LIMIT)


if __name__ == "__main__":
    unittest.main()
