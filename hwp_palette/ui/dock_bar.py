# -*- coding: utf-8 -*-
r"""도킹 도구줄 — 한글을 감싼 창의 **위쪽 한 줄**에 물감을 늘어놓는다 (2026-07-29).

첫 판(세로 띠, `dock_strip.py`)을 버리고 다시 만들었다. 사용자 지적:

    "엄청 버벅거린다 · 짤리는 느낌이 심하다.
     차라리 감싸고 있어서 버벅거리더라도 따라오는 느낌이 낫겠다."

세로 띠는 우리 창을 한글 옆에 **매 틱 옮겨 붙이는** 방식이라, 창 둘이 각자
움직이며 서로를 쫓는 것이 눈에 그대로 보였다. 지금은 반대다 — 우리 창이
한글을 **감싸고**(hwp_dock.Dock), 한글이 우리 판 자리로 따라 들어온다.
템플릿을 고칠 때 쓰던 방식 그대로다.

그래서 이 파일은 '띠'가 아니라 **도구줄**이다: 창 맨 위 한 줄에 물감 칩을
늘어놓고, 아래 넓은 자리는 통째로 한글에게 준다.

칩은 **줄바꿈한다** (짤림 방지). 폭이 줄면 다음 줄로 넘어가지, 잘리지 않는다.
"""

import tkinter as tk

from hwp_palette.design import theme
from hwp_palette.design.roundbtn import RoundButton
from hwp_palette.model import palette

_C = theme.colors()
CARD, BORDER = _C["card"], _C["border"]
TEXT, MUTED, FAINT = _C["text"], _C["muted"], _C["faint"]
ACCENT, SUBBG = _C["accent"], _C["subbg"]

CHIP_H_BASE = 26
CHIP_GAP = 4


class DockBar(tk.Frame):
    """감싼 창 맨 위의 물감 도구줄."""

    def __init__(self, master, *, scale, font_fn, run_block, label_fn,
                 block_color_fn, tabs_fn, tab_index_fn, on_pick_tab,
                 on_undock, mode_label=None, on_toggle_mode=None):
        super().__init__(master, bg=CARD)
        self._font = font_fn
        self._run = run_block
        self._label = label_fn
        self._color = block_color_fn
        self._tabs = tabs_fn
        self._tab_index = tab_index_fn
        self._pick_tab = on_pick_tab
        self._chip_h = int(round(CHIP_H_BASE * scale))
        self._chips = []
        self._last_w = 0

        head = tk.Frame(self, bg=CARD)
        head.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(head, text="물감", font=font_fn(7), fg=FAINT,
                 bg=CARD).pack(side="left")
        self._pick = RoundButton(head, text="", command=self._next_tab,
                                 bg=CARD, fg=TEXT, radius=theme.RADIUS["ctl"],
                                 font=font_fn(7), outline=BORDER,
                                 focus_color=ACCENT, zone_bg=CARD,
                                 trailing="▾")
        self._pick.pack(side="left", padx=(6, 0))
        # 떼기는 오른쪽 끝 — 도킹을 푸는 단 하나의 문이다. 한글을 닫는 ✕ 는
        # 두지 않는다 (사용자 결정 2026-07-29): 원고를 닫는 일은 한글 몫이다.
        undock = RoundButton(head, text="◱  떼기", command=on_undock,
                             bg=SUBBG, fg=MUTED, radius=theme.RADIUS["ctl"],
                             font=font_fn(7), outline=BORDER,
                             focus_color=ACCENT, zone_bg=CARD)
        undock.fit(pad_x=9, pad_y=3)
        undock.pack(side="right")
        # 감싸는 방식 갈아타기 (2026-07-30) — 임베드와 도킹을 번갈아 써 보고
        # 고르라고 둔 단추다. 누르면 뗐다가 반대 방식으로 다시 문다.
        if on_toggle_mode is not None:
            swap = RoundButton(head, text=f"⇄  {mode_label or '방식'}",
                               command=on_toggle_mode,
                               bg=SUBBG, fg=MUTED, radius=theme.RADIUS["ctl"],
                               font=font_fn(7), outline=BORDER,
                               focus_color=ACCENT, zone_bg=CARD)
            swap.fit(pad_x=9, pad_y=3)
            swap.pack(side="right", padx=(0, 6))

        self._flow = tk.Frame(self, bg=CARD)
        self._flow.pack(fill="x", padx=8, pady=(5, 7))
        # 폭이 바뀌면 다시 흘려 담는다 — 창을 좁히면 칩이 아랫줄로 내려간다
        self._flow.bind("<Configure>", self._on_resize)

        self.render()

    # ── 흘려 담기 ────────────────────────────────────
    def _on_resize(self, e):
        if abs(e.width - self._last_w) < 8:
            return                      # 잔떨림으로 매번 다시 깔지 않는다
        self._last_w = e.width
        self._reflow(e.width)

    def _reflow(self, width):
        if not self._chips:
            return
        x = y = 0
        row_h = self._chip_h + CHIP_GAP
        for chip in self._chips:
            w = chip.winfo_reqwidth()
            if x and x + w > width:     # 이 줄에 안 들어간다 → 다음 줄
                x, y = 0, y + row_h
            chip.place(x=x, y=y, height=self._chip_h)
            x += w + CHIP_GAP
        self._flow.configure(height=y + self._chip_h)

    # ── 그리기 ──────────────────────────────────────
    def render(self):
        for w in self._chips:
            w.destroy()
        self._chips = []
        tabs = self._tabs()
        self._pick.set_text(self._pick_text(tabs), pad_x=8, pad_y=3)

        blocks = []
        main = next((t for t in tabs if t.get("name") == palette.MAIN_TAB), None)
        if main:
            blocks += self._sorted(main.get("blocks", []))
        others = [t for t in tabs if t.get("name") != palette.MAIN_TAB]
        if others:
            cur = others[min(self._tab_index(), len(others) - 1)]
            blocks += self._sorted(cur.get("blocks", []))

        for blk in blocks:
            self._chips.append(self._chip(blk))
        self._last_w = 0
        self.after_idle(lambda: self._reflow(max(self._flow.winfo_width(), 1)))

    def _sorted(self, blocks):
        """읽는 차례 — 격자에서 위에서 아래, 왼쪽에서 오른쪽."""
        return sorted(blocks, key=lambda b: (int(b.get("row", 0)),
                                             int(b.get("col", 0))))

    def _chip(self, blk):
        bg = self._color(blk)
        # 이름을 **자르지 않는다** (사용자 지적 2026-07-29: "짤리는 느낌").
        # 칩 폭은 이름을 따라가고, 줄이 모자라면 아랫줄로 넘긴다.
        b = RoundButton(self._flow, text=self._label(blk).replace("\n", " "),
                        command=lambda x=blk: self._run(x),
                        bg=bg, fg=theme.text_on(bg),
                        radius=theme.RADIUS["ctl"], font=self._font(8),
                        outline=BORDER, focus_color=ACCENT, zone_bg=CARD)
        b.fit(pad_x=10, pad_y=3)
        return b

    # ── 팔레트 넘기기 ────────────────────────────────
    def _pick_text(self, tabs=None):
        others = [t for t in (tabs or self._tabs())
                  if t.get("name") != palette.MAIN_TAB]
        if not others:
            return "팔레트 없음"
        return others[min(self._tab_index(), len(others) - 1)].get("name", "")

    def _next_tab(self):
        others = [t for t in self._tabs() if t.get("name") != palette.MAIN_TAB]
        if len(others) <= 1:
            return
        self._pick_tab((self._tab_index() + 1) % len(others))
        self.render()
