# -*- coding: utf-8 -*-
r"""034 검증 — 고친 `fit_line_spacing` 이 **표 셀 안에서 실제로 도는가**.

새 빈 문서에 표를 만들고, 셀 안 문단을 선택한 상태에서 실제 진입점을 부른다.
본문에서도 한 번 해서 **회귀가 없는지** 함께 본다. 저장하지 않는다.
"""

import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.hwp import engine_library
from hwp_palette.hwp import hwp_engine

OUT = pathlib.Path(__file__).with_suffix(".log")
_lines = []


def say(*a):
    msg = " ".join(str(x) for x in a)
    _lines.append(msg)


def _type(hwp, text):
    ps = hwp.HParameterSet
    hwp.HAction.GetDefault("InsertText", ps.HInsertText.HSet)
    ps.HInsertText.Text = text
    hwp.HAction.Execute("InsertText", ps.HInsertText.HSet)


def main():
    if not hwp_engine.connect():
        say("한글에 연결하지 못했습니다.")
        return
    hwp = hwp_engine.hwp
    hwp_engine.ensure_visible()
    hwp.HAction.Run("FileNew")
    say("새 문서 (FileNew)")

    # ── 본문 회귀 확인 ──
    _type(hwp, "본문에서도 그대로 되어야 한다 " * 8)
    lid, para, _ = hwp.GetPos()
    hwp.SetPos(lid, para, 0)
    hwp.HAction.Run("MoveSelDocEnd")
    say("본문 선택:", hwp.GetSelectedPos())
    say("본문 범위 판정:", engine_library._selected_para_range())
    r = engine_library.fit_line_spacing()
    say("본문 결과:", r, " ← paras 가 0 이면 회귀")

    # ── 표 셀 ──
    hwp.HAction.Run("MoveDocEnd")
    hwp.HAction.Run("BreakPara")
    act, ps = hwp.HAction, hwp.HParameterSet
    act.GetDefault("TableCreate", ps.HTableCreation.HSet)
    ps.HTableCreation.Rows = 1
    ps.HTableCreation.Cols = 2
    ps.HTableCreation.WidthType = 2
    ps.HTableCreation.HeightType = 0
    ps.HTableCreation.CreateItemArray("ColWidth", 2)
    ps.HTableCreation.ColWidth.SetItem(0, 4000)
    ps.HTableCreation.ColWidth.SetItem(1, 4000)
    act.Execute("TableCreate", ps.HTableCreation.HSet)
    _type(hwp, "표 안에서도 자간맞춤이 되어야 한다는 요구사항입니다 " * 3)
    lid, para, _ = hwp.GetPos()
    say("\n셀 좌표:", (lid, para))

    hwp.SetPos(lid, para, 0)
    hwp.HAction.Run("MoveSelParaEnd")
    say("셀 선택:", hwp.GetSelectedPos())
    say("셀 범위 판정:", engine_library._selected_para_range(),
        " ← None 이면 표가 여전히 막혀 있다")

    hwp.SetPos(lid, para, 0)
    hwp.HAction.Run("MoveSelParaEnd")
    r2 = engine_library.fit_line_spacing()
    say("셀 결과:", r2, " ← paras>=1 이면 034 해결")

    # 자간이 실제로 걸렸는지 (선택 없이 조용히 실패하던 길의 확인)
    hwp.SetPos(lid, para, 1)
    act.GetDefault("CharShape", ps.HCharShape.HSet)
    say("셀 첫 줄 자간:", ps.HCharShape.SpacingHangul)

    # ── _apply_spacing 이 셀에서 실제로 먹는가 ──
    # fit_line_spacing 의 tightened 가 0 인 것이 '당길 것이 없어서'인지
    # '자간이 안 걸려서'인지 가른다. 후자면 _select_run 고침이 헛것이다.
    hwp.SetPos(lid, para, 0)
    say("\n_select_run(0,10):", engine_library._select_run(lid, para, 0, 10))
    hwp.HAction.Run("Cancel")
    engine_library._apply_spacing(lid, para, 0, 10, -7)
    say("구간 자간 (-7 이어야):", engine_library._read_spacing(lid, para, 1))
    say("구간 밖 자간 (0 이어야):", engine_library._read_spacing(lid, para, 30))

    say("\n※ 검사 문서는 저장하지 않았습니다 — 한글에서 그냥 닫으십시오.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        say("예외:", type(e).__name__, e)
    finally:
        io.open(OUT, "w", encoding="utf-8").write("\n".join(_lines))
        print(f"[log] {OUT}")
