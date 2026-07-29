# -*- coding: utf-8 -*-
r"""도킹 도구줄 — 한글을 감싼 창의 **위쪽 한 줄**에 물감을 늘어놓는다 (2026-07-29).

첫 판(세로 띠, `dock_strip.py`)을 버리고 다시 만들었다. 사용자 지적:

    "엄청 버벅거린다 · 짤리는 느낌이 심하다.
     차라리 감싸고 있어서 버벅거리더라도 따라오는 느낌이 낫겠다."

세로 띠는 우리 창을 한글 옆에 **매 틱 옮겨 붙이는** 방식이라, 창 둘이 각자
움직이며 서로를 쫓는 것이 눈에 그대로 보였다. 지금은 반대다 — 우리 창이
한글을 **감싸고**, 한글이 우리 판 자리로 들어온다.

그래서 이 파일은 '띠'가 아니라 **도구줄**이다: 창 맨 위 한 줄에 물감 칩을
늘어놓고, 아래 넓은 자리는 통째로 한글에게 준다.

좌우 분할 (2026-07-30, 사용자 지적):

    "공통 팔레트와 개인 팔레트가 위계적으로 전혀 구분이 안 갑니다.
     도구는 성격이 다르기 때문에 구별이 가야 합니다."

여태 둘을 한 줄에 그냥 이어 붙여, `통합 찾기`(공통) 다음에 `수능양식`(개인)이
아무 경계 없이 붙어 있었다. 이제 **가운데를 기준으로 왼쪽은 공통, 오른쪽은
개인**이고 사이에 세로 구분선이 선다. 자리 자체가 성격을 말한다.

빈 자리도 함께 걷어냈다: '물감 [팔레트▾]' 머리줄을 따로 두던 것을 없애고
팔레트 고르기 단추를 **개인 구역의 머리**로 옮겼다 — 그 단추가 고르는 것이
바로 오른쪽 칩들이므로, 옆에 붙어 있어야 뜻이 읽힌다. 한 줄이 통째로 줄었다.

칩은 **줄바꿈한다** (짤림 방지). 폭이 줄면 다음 줄로 넘어가지, 잘리지 않는다.
각 구역은 자기 폭 안에서 따로 흘려 담는다.
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
ZONE_PAD = 8              # 구분선과 칩 사이 숨통


class _Zone(tk.Frame):
    """칩을 흘려 담는 구역 하나 (공통 또는 개인).

    자기 폭만 보고 줄을 나눈다 — 옆 구역이 몇 줄이든 상관하지 않는다.
    """

    def __init__(self, master, chip_h):
        super().__init__(master, bg=CARD)
        self._chip_h = chip_h
        self._chips = []
        self._last_w = 0
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, e):
        if abs(e.width - self._last_w) < 8:
            return                      # 잔떨림으로 매번 다시 깔지 않는다
        self._last_w = e.width
        self.reflow(e.width)

    def set_chips(self, chips):
        for w in self._chips:
            w.destroy()
        self._chips = chips
        self._last_w = 0
        self.after_idle(lambda: self.reflow(max(self.winfo_width(), 1)))

    def reflow(self, width):
        if not self._chips:
            self.configure(height=self._chip_h)
            return
        x = y = 0
        row_h = self._chip_h + CHIP_GAP
        for chip in self._chips:
            w = chip.winfo_reqwidth()
            if x and x + w > width:     # 이 줄에 안 들어간다 → 다음 줄
                x, y = 0, y + row_h
            chip.place(x=x, y=y, height=self._chip_h)
            x += w + CHIP_GAP
        self.configure(height=y + self._chip_h)


class DockBar(tk.Frame):
    """감싼 창 맨 위의 물감 도구줄 — 왼쪽 공통, 오른쪽 개인."""

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

        # 한 줄짜리 격자: [공통 구역] │ [개인 구역] [단추들]
        # 두 구역에 같은 무게를 줘서 **가운데가 경계**가 되게 한다.
        self.grid_columnconfigure(0, weight=1, uniform="zone")
        self.grid_columnconfigure(2, weight=1, uniform="zone")

        left = tk.Frame(self, bg=CARD)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, ZONE_PAD),
                  pady=(6, 7))
        tk.Label(left, text="공통", font=font_fn(7), fg=FAINT,
                 bg=CARD).pack(side="left", anchor="n", padx=(0, 6))
        self._common = _Zone(left, self._chip_h)
        self._common.pack(side="left", fill="both", expand=True)

        # 세로 구분선 — 성격이 다른 도구 사이의 경계
        tk.Frame(self, bg=BORDER, width=1).grid(row=0, column=1, sticky="ns",
                                                pady=6)

        right = tk.Frame(self, bg=CARD)
        right.grid(row=0, column=2, sticky="nsew", padx=(ZONE_PAD, 6),
                   pady=(6, 7))
        # 팔레트 고르기 단추가 곧 이 구역의 이름표다 — 무엇을 고르는 단추인지
        # 옆에 있는 칩들이 바로 말해 준다.
        self._pick = RoundButton(right, text="", command=self._next_tab,
                                 bg=CARD, fg=TEXT, radius=theme.RADIUS["ctl"],
                                 font=font_fn(7), outline=BORDER,
                                 focus_color=ACCENT, zone_bg=CARD,
                                 trailing="▾")
        self._pick.pack(side="left", anchor="n", padx=(0, 6))
        self._personal = _Zone(right, self._chip_h)
        self._personal.pack(side="left", fill="both", expand=True)

        # 단추들은 오른쪽 끝 — 물감이 아니라 창을 다루는 것이라 구역 밖이다.
        ctrl = tk.Frame(self, bg=CARD)
        ctrl.grid(row=0, column=3, sticky="ne", padx=(0, 8), pady=6)
        # 떼기는 도킹을 푸는 단 하나의 문이다. 한글을 닫는 ✕ 는 두지 않는다
        # (사용자 결정 2026-07-29): 원고를 닫는 일은 한글 몫이다.
        undock = RoundButton(ctrl, text="◱  떼기", command=on_undock,
                             bg=SUBBG, fg=MUTED, radius=theme.RADIUS["ctl"],
                             font=font_fn(7), outline=BORDER,
                             focus_color=ACCENT, zone_bg=CARD)
        undock.fit(pad_x=9, pad_y=3)
        undock.pack(side="right")
        # 감싸는 방식 갈아타기 (2026-07-30) — 임베드와 도킹을 번갈아 써 보고
        # 고르라고 둔 단추다. 누르면 뗐다가 반대 방식으로 다시 문다.
        if on_toggle_mode is not None:
            swap = RoundButton(ctrl, text=f"⇄  {mode_label or '방식'}",
                               command=on_toggle_mode,
                               bg=SUBBG, fg=MUTED, radius=theme.RADIUS["ctl"],
                               font=font_fn(7), outline=BORDER,
                               focus_color=ACCENT, zone_bg=CARD)
            swap.fit(pad_x=9, pad_y=3)
            swap.pack(side="right", padx=(0, 6))

        self.render()

    # ── 그리기 ──────────────────────────────────────
    def render(self):
        tabs = self._tabs()
        self._pick.set_text(self._pick_text(tabs), pad_x=8, pad_y=3)

        main = next((t for t in tabs if t.get("name") == palette.MAIN_TAB), None)
        common = self._sorted(main.get("blocks", [])) if main else []

        others = [t for t in tabs if t.get("name") != palette.MAIN_TAB]
        personal = []
        if others:
            cur = others[min(self._tab_index(), len(others) - 1)]
            personal = self._sorted(cur.get("blocks", []))

        self._common.set_chips([self._chip(self._common, b) for b in common])
        self._personal.set_chips([self._chip(self._personal, b)
                                  for b in personal])

    def _sorted(self, blocks):
        """읽는 차례 — 격자에서 위에서 아래, 왼쪽에서 오른쪽."""
        return sorted(blocks, key=lambda b: (int(b.get("row", 0)),
                                             int(b.get("col", 0))))

    def _chip(self, parent, blk):
        bg = self._color(blk)
        # 이름을 **자르지 않는다** (사용자 지적 2026-07-29: "짤리는 느낌").
        # 칩 폭은 이름을 따라가고, 줄이 모자라면 아랫줄로 넘긴다.
        b = RoundButton(parent, text=self._label(blk).replace("\n", " "),
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
