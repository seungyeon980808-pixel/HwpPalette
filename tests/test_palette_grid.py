# -*- coding: utf-8 -*-
"""팔레트 격자 좌표 로직 (한글 없이 돌아간다).

블럭은 격자 위의 사각형이다 — (row, col) 에서 span×rows 칸.
예전에는 좌표 없이 목록 순서대로 흘려 배치해서 '세로로 큰 블럭'을 만들 수
없었다. 2026-07-19 좌표 방식으로 바꾸면서 이 규칙들을 고정한다.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import palette        # noqa: E402


def _blk(row, col, span=1, rows=1):
    return {"type": "char", "value": "x", "row": row, "col": col,
            "span": span, "rows": rows}


class ConvertSizeTest(unittest.TestCase):
    """변환 버튼 크기 (2026-07-25) — 창 너비에 직접 영향을 주므로 값이 안전해야 한다."""

    def _with_store(self, saved):
        store = {palette.CONVERT_SIZE_KEY: saved}
        return mock.patch.object(
            palette.settings, "get_config_value",
            side_effect=lambda k, d=None: store.get(k, d)), store

    def test_저장값이_없으면_기본값(self):
        patch, _ = self._with_store(None)
        with patch:
            self.assertEqual(palette.get_convert_size(),
                             (palette.DEFAULT_CONVERT_SIZE["span"],
                              palette.DEFAULT_CONVERT_SIZE["rows"]))

    def test_저장값을_읽는다(self):
        patch, _ = self._with_store({"span": 4, "rows": 3})
        with patch:
            self.assertEqual(palette.get_convert_size(), (4, 3))

    def test_너무_크면_상한으로_자른다(self):
        # 실수로 큰 값을 넣어도 창이 화면을 넘지 않아야 한다
        patch, _ = self._with_store({"span": 999, "rows": 999})
        with patch:
            self.assertEqual(palette.get_convert_size(),
                             (palette.CONVERT_SIZE_MAX,
                              palette.CONVERT_SIZE_MAX))

    def test_0이나_음수는_1로_올린다(self):
        patch, _ = self._with_store({"span": 0, "rows": -5})
        with patch:
            self.assertEqual(palette.get_convert_size(), (1, 1))

    def test_숫자가_아니면_기본값으로_되돌린다(self):
        patch, _ = self._with_store({"span": "넷", "rows": None})
        with patch:
            self.assertEqual(palette.get_convert_size(),
                             (palette.DEFAULT_CONVERT_SIZE["span"],
                              palette.DEFAULT_CONVERT_SIZE["rows"]))


class OccupiedCellsTest(unittest.TestCase):

    def test_한_칸_블럭(self):
        self.assertEqual(palette.occupied_cells([_blk(0, 0)]), {(0, 0)})

    def test_가로로_넓은_블럭(self):
        self.assertEqual(palette.occupied_cells([_blk(1, 2, span=3)]),
                         {(1, 2), (1, 3), (1, 4)})

    def test_세로로_큰_블럭(self):
        self.assertEqual(palette.occupied_cells([_blk(0, 0, rows=3)]),
                         {(0, 0), (1, 0), (2, 0)})

    def test_사각형_블럭(self):
        self.assertEqual(palette.occupied_cells([_blk(0, 0, span=2, rows=2)]),
                         {(0, 0), (0, 1), (1, 0), (1, 1)})

    def test_자기_자신은_뺄_수_있다(self):
        blocks = [_blk(0, 0), _blk(0, 1)]
        self.assertEqual(palette.occupied_cells(blocks, skip_index=0), {(0, 1)})


class AreaIsFreeTest(unittest.TestCase):

    def test_빈_곳은_자유롭다(self):
        self.assertTrue(palette.area_is_free([_blk(0, 0)], 1, 0, 1, 1))

    def test_겹치면_안_된다(self):
        self.assertFalse(palette.area_is_free([_blk(0, 0)], 0, 0, 1, 1))

    def test_세로로_겹치는_것도_잡는다(self):
        blocks = [_blk(1, 0)]
        self.assertFalse(palette.area_is_free(blocks, 0, 0, 1, 2))

    def test_자기_자리로_다시_놓는_건_허용(self):
        blocks = [_blk(0, 0, span=2)]
        self.assertTrue(palette.area_is_free(blocks, 0, 0, 2, 1, skip_index=0))


class FindFreeSpotTest(unittest.TestCase):

    def test_비어_있으면_첫_칸(self):
        self.assertEqual(palette.find_free_spot([], cols=5), (0, 0))

    def test_찬_칸은_건너뛴다(self):
        blocks = [_blk(0, 0), _blk(0, 1)]
        self.assertEqual(palette.find_free_spot(blocks, cols=5), (0, 2))

    def test_줄이_차면_다음_줄로(self):
        blocks = [_blk(0, c) for c in range(3)]
        self.assertEqual(palette.find_free_spot(blocks, cols=3), (1, 0))

    def test_넓은_블럭은_들어갈_만큼_넓은_자리를_찾는다(self):
        # 0행에 0,1 이 차 있고 폭이 4면, 2~3 자리(2칸)가 들어간다
        blocks = [_blk(0, 0), _blk(0, 1)]
        self.assertEqual(palette.find_free_spot(blocks, cols=4, span=2), (0, 2))

    def test_세로로_큰_블럭도_자리를_본다(self):
        blocks = [_blk(1, 0)]          # 아래가 막혀 있으므로 0행 0열엔 2줄이 못 들어감
        self.assertEqual(palette.find_free_spot(blocks, cols=3, rows=2), (0, 1))


class MigrationTest(unittest.TestCase):
    """구 데이터(좌표 없음)를 보던 그대로 좌표로 굳힌다."""

    def test_흐름_배치를_좌표로_바꾼다(self):
        tab = {"cols": 3, "blocks": [
            {"type": "char", "value": "a"},
            {"type": "char", "value": "b"},
            {"type": "char", "value": "c"},
            {"type": "char", "value": "d"},      # 다음 줄로 넘어가야 한다
        ]}
        self.assertTrue(palette._migrate_positions(tab))
        pos = [(b["row"], b["col"]) for b in tab["blocks"]]
        self.assertEqual(pos, [(0, 0), (0, 1), (0, 2), (1, 0)])

    def test_넓은_블럭이_줄을_넘기면_다음_줄로(self):
        tab = {"cols": 3, "blocks": [
            {"type": "char", "value": "a"},
            {"type": "char", "value": "b"},
            {"type": "template", "span": 2},     # 2칸이라 0행엔 못 들어감
        ]}
        palette._migrate_positions(tab)
        self.assertEqual([(b["row"], b["col"]) for b in tab["blocks"]],
                         [(0, 0), (0, 1), (1, 0)])

    def test_이미_좌표가_있으면_건드리지_않는다(self):
        tab = {"cols": 3, "blocks": [_blk(5, 2)]}
        self.assertFalse(palette._migrate_positions(tab))
        self.assertEqual(tab["blocks"][0]["row"], 5)

    def test_rows_기본값이_채워진다(self):
        tab = {"cols": 3, "blocks": [{"type": "char", "value": "a"}]}
        palette._migrate_positions(tab)
        self.assertEqual(tab["blocks"][0]["rows"], 1)


class GridExtentTest(unittest.TestCase):

    def test_빈_격자는_0줄(self):
        self.assertEqual(palette.grid_extent([]), 0)

    def test_세로로_큰_블럭을_반영한다(self):
        self.assertEqual(palette.grid_extent([_blk(0, 0, rows=3)]), 3)

    def test_가장_아래_블럭_기준(self):
        self.assertEqual(palette.grid_extent([_blk(0, 0), _blk(4, 1)]), 5)


if __name__ == "__main__":
    unittest.main()
