# -*- coding: utf-8 -*-
r"""칸 오른쪽 **세로 띠** — 여럿을 담은 칸의 표시 (2026-08-01, 피드백 037).

    "예전에 이런 경우에는 옆에 세로로 MIX라는 띠를 달아준다고 했었는데
     전혀 반영이 안 된 상황입니다."

왜 부품인가: 지금까지 띠는 창고 카드 한 곳에만 손으로 그려져 있어, 같은
물감이 화면마다 다르게 보였다. 부품 하나를 세 화면(메인 팔레트 · 설정 격자 ·
창고 카드)이 같이 써야 또 한 화면만 바뀌는 일이 없다.

무엇이 무엇인가 (안 B — 겹치기와 섞기는 다른 물건이라 표시를 가른다):
  · 겹친 칸(택일)  = 청록 띠에 **개수 숫자** — "몇 개 들었나"가 궁금한 정보다
  · 꾸러미(합체)   = 보라 띠에 **MIX**
판정 자체는 library.block_badge 한 곳이 한다 — 세 화면이 같은 답을 쓴다.

칸 높이·폭은 불변(2026-07-31 결정) — 띠는 칸 안쪽 오른쪽에만 붙는다.
"""

import tkinter as tk

from hwp_palette.design import theme


def colors(kind):
    """띠 색 — kind 는 library.block_badge 가 주는 "stack" / "mix"."""
    if kind == "mix":
        return theme.MIX_BG, theme.MIX_FG
    return theme.STACK_BG, theme.STACK_FG


def attach(tile, kind, text):
    r"""Frame·RoundTile 같은 **그릇 위젯**의 오른쪽에 띠 라벨을 얹는다.

    place() 라 칸 크기에 영향이 없다(높이 불변의 핵심). 캔버스 버튼
    (RoundButton)은 자식 라벨을 못 얹으므로 set_ribbon 을 대신 쓴다.
    """
    bg, fg = colors(kind)
    lab = tk.Label(tile, text="\n".join(str(text)), bg=bg, fg=fg,
                   font=(theme.FONT, max(6, theme.fs(7)), "bold"),
                   padx=1, pady=0)
    lab.place(relx=1.0, rely=0.5, anchor="e", relheight=0.86)
    return lab
