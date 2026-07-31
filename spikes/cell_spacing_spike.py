# -*- coding: utf-8 -*-
r"""034 실측 — 자간 맞춤 배관이 **표 셀 안에서도** 도는가 (2026-08-01).

무엇을 재는가 (기획서 034 의 '실측 3건'):
  ① 셀 안에서 MoveLineBegin / MoveSelLineEnd / MoveRight 이동이 본문과
     같게 노는가
  ② SelectText 가 셀 좌표에서 동작하는가 (안 되면 MoveSelRight 대체 경로)
  ③ 어절 단위(ParagraphShape.BreakNonLatinWord)와 자간(CharShape) 적용이
     셀 문단에도 같은 액션으로 먹는가

왜 실측이 먼저인가: 지금 배관은 전부 `SetPos(0, …)` 로 **본문(list 0)을
박아** 쓴다. list_id 를 꿰기만 하면 되는지, 아니면 셀에서는 이동 액션 자체가
다르게 노는지에 따라 구현이 갈린다.

원본은 건드리지 않는다 — **새 빈 문서**를 만들어 거기에만 쓰고, 끝나면
저장하지 않고 닫는다.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.hwp import hwp_engine

OUT = pathlib.Path(__file__).with_suffix(".log")
_lines = []


def say(*a):
    msg = " ".join(str(x) for x in a)
    print(msg)
    _lines.append(msg)


def main():
    if not hwp_engine.connect():
        say("한글에 연결하지 못했습니다.")
        return
    hwp = hwp_engine.hwp
    hwp_engine.ensure_visible()

    # ── 검사용 새 문서 (사용자 문서는 건드리지 않는다) ──
    # XHwpDocuments 는 쓰지 않는다 — pywin32 의 gen_py 캐시가 깨져 있으면
    # 그 속성 접근에서 터진다. 앱과 같은 길(FileNew)로 연다.
    hwp.HAction.Run("FileNew")
    say("새 문서 생성 (FileNew)")

    # 본문 문단 하나
    hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet)
    hwp.HParameterSet.HInsertText.Text = (
        "본문 기준 문단입니다 " * 6)
    hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet)
    hwp.HAction.Run("BreakPara")

    body_pos = hwp.GetPos()
    say("본문 GetPos =", body_pos)

    # ── 표 1×1 을 넣고 그 셀 안으로 들어간다 ──
    act, ps = hwp.HAction, hwp.HParameterSet
    act.GetDefault("TableCreate", ps.HTableCreation.HSet)
    ps.HTableCreation.Rows = 1
    ps.HTableCreation.Cols = 1
    ps.HTableCreation.WidthType = 2
    ps.HTableCreation.HeightType = 0
    ps.HTableCreation.CreateItemArray("ColWidth", 1)
    ps.HTableCreation.ColWidth.SetItem(0, 8000)
    act.Execute("TableCreate", ps.HTableCreation.HSet)
    say("표 1x1 생성")

    # 표를 만들면 커서가 첫 셀 안에 있다
    cell_pos = hwp.GetPos()
    say("셀 GetPos =", cell_pos, "  ← list 번호가 본문(0)과 다른가:",
        cell_pos[0] != body_pos[0])

    hwp.HAction.GetDefault("InsertText", ps.HInsertText.HSet)
    ps.HInsertText.Text = ("표 안에 넣은 긴 문장이며 줄이 넘어가야 한다 " * 4)
    hwp.HAction.Execute("InsertText", ps.HInsertText.HSet)

    lid, para, _p = hwp.GetPos()
    say(f"\n=== 셀 좌표 (list={lid}, para={para}) 에서 실측 ===")

    # ① 이동 액션
    hwp.SetPos(lid, para, 0)
    ok_home = hwp.HAction.Run("MoveLineBegin")
    say("① MoveLineBegin ->", ok_home, "GetPos", hwp.GetPos())
    ok_sel = hwp.HAction.Run("MoveSelLineEnd")
    say("① MoveSelLineEnd ->", ok_sel, "GetSelectedPos", hwp.GetSelectedPos())
    hwp.HAction.Run("Cancel")
    hwp.SetPos(lid, para, 0)
    ok_right = hwp.HAction.Run("MoveRight")
    say("① MoveRight ->", ok_right, "GetPos", hwp.GetPos())

    # 줄 끝에서 MoveRight 가 다음 셀/문단으로 튀는지 (경계 방어 근거)
    hwp.SetPos(lid, para, 0)
    hwp.HAction.Run("MoveLineEnd")
    before = hwp.GetPos()
    hwp.HAction.Run("MoveRight")
    after = hwp.GetPos()
    say("① 줄 끝에서 MoveRight:", before, "->", after,
        " list 가 바뀌나:", before[0] != after[0])

    # ② SelectText
    hwp.SetPos(lid, para, 0)
    try:
        got = hwp.SelectText(para, 0, para, 5)
        say("② SelectText(셀 좌표) ->", got, "GetSelectedPos",
            hwp.GetSelectedPos())
    except Exception as e:
        say("② SelectText 예외:", type(e).__name__, e)
    hwp.HAction.Run("Cancel")

    # ③ 문단모양·글자모양이 셀 문단에도 먹는가
    hwp.SetPos(lid, para, 0)
    act.GetDefault("ParagraphShape", ps.HParaShape.HSet)
    was = ps.HParaShape.BreakNonLatinWord
    ps.HParaShape.BreakNonLatinWord = 0
    r1 = act.Execute("ParagraphShape", ps.HParaShape.HSet)
    act.GetDefault("ParagraphShape", ps.HParaShape.HSet)
    now = ps.HParaShape.BreakNonLatinWord
    say(f"③ ParagraphShape 어절단위: {was} -> 실행 {r1} -> 읽으니 {now}",
        " 먹었나:", str(now) == "0")

    hwp.SetPos(lid, para, 0)
    hwp.HAction.Run("MoveLineBegin")
    hwp.HAction.Run("MoveSelLineEnd")
    act.GetDefault("CharShape", ps.HCharShape.HSet)
    ps.HCharShape.SpacingHangul = -5
    r2 = act.Execute("CharShape", ps.HCharShape.HSet)
    hwp.HAction.Run("Cancel")
    hwp.SetPos(lid, para, 1)
    act.GetDefault("CharShape", ps.HCharShape.HSet)
    say(f"③ CharShape 자간 -5 실행 {r2} -> 읽으니",
        ps.HCharShape.SpacingHangul)

    say("\n=== 끝 — 저장하지 않고 닫습니다 ===")
    say("※ 검사 문서는 저장하지 않았습니다 — 한글에서 그냥 닫으십시오.")


if __name__ == "__main__":
    try:
        main()
    finally:
        OUT.write_text("\n".join(_lines), encoding="utf-8")
        print(f"\n[로그] {OUT}")
