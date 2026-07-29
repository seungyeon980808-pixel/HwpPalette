# -*- coding: utf-8 -*-
r"""도킹 띠 — 한글 옆구리에 붙었을 때의 우리 화면 (2026-07-29).

평소 화면(격자 + 창고 + 미리보기)을 세로 한 줄로 접은 것이다. 시안 B
(`docs/mockups/dock-strip.html`): 블럭 이름이 안 잘리는 대신 편집 폭을 조금
먹는다. 사용자 결정 2026-07-29.

여기 없는 것: 미리보기 판·물감 창고·설정. 띠는 **누르는 곳**이지 만드는 곳이
아니다. 만들려면 '떼기'로 평소 창을 부른다.

바깥(app.py)과의 약속은 콜백 한 묶음뿐이다 — 이 모듈은 팔레트 자료구조도
한글도 모른다. 블럭 하나를 어떻게 실행하고 어떤 이름으로 부를지는 전부
넘겨받는다 (app.py 의 run_palette_block · _block_label 을 그대로 쓴다).
"""

import tkinter as tk

from hwp_palette.design import theme
from hwp_palette.design.roundbtn import RoundButton
from hwp_palette.model import palette

_C = theme.colors()
BG, CARD, BORDER = _C["bg"], _C["card"], _C["border"]
TEXT, MUTED, FAINT = _C["text"], _C["muted"], _C["faint"]
ACCENT, SUBBG = _C["accent"], _C["subbg"]
FONT = theme.FONT

# 띠 폭 — 이름이 잘리지 않는 최소치(실측: '합답형2사진3선지' 8글자가 들어간다).
# 배율을 곱해 쓰므로 여기 값은 100% 기준이다.
STRIP_W_BASE = 150
CHIP_H_BASE = 28


def strip_width(scale):
    return int(round(STRIP_W_BASE * scale))


class DockStrip(tk.Frame):
    """한글 왼쪽에 세워지는 세로 띠."""

    def __init__(self, master, *, scale, font_fn, run_block, label_fn,
                 block_color_fn, tabs_fn, tab_index_fn, on_pick_tab,
                 on_undock, on_minimize, on_maximize):
        super().__init__(master, bg=CARD)
        self._scale = scale
        self._font = font_fn
        self._run = run_block
        self._label = label_fn
        self._color = block_color_fn
        self._tabs = tabs_fn
        self._tab_index = tab_index_fn
        self._pick_tab = on_pick_tab
        self._chip_h = int(round(CHIP_H_BASE * scale))

        # ── 머리 ──
        head = tk.Frame(self, bg=CARD)
        head.pack(fill="x", padx=6, pady=(6, 4))
        tk.Frame(head, bg=ACCENT, width=12, height=12).pack(side="left",
                                                            pady=2)
        tk.Label(head, text="물감판", font=font_fn(7), fg=MUTED,
                 bg=CARD).pack(side="left", padx=(5, 0))
        # 창 단추는 오른쪽 끝에서부터 ◱(떼기) ▢ ─ 순으로 — 윈도우 관습과 같은
        # 자리에 같은 순서로 둔다. 다만 ✕ 는 두지 않는다: 이 자리의 ✕ 는
        # '한글을 닫는다'로 읽히기 쉬운데, 원고를 닫는 일을 도구 띠가 대신
        # 해서는 안 된다 (사용자 결정 2026-07-29).
        for sym, cmd, tip in (("◱", on_undock, "도킹 떼기"),
                              ("▢", on_maximize, "최대화"),
                              ("─", on_minimize, "최소화")):
            b = tk.Label(head, text=sym, font=font_fn(7), fg=MUTED, bg=CARD,
                         cursor="hand2", padx=3)
            b.pack(side="right")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(fg=TEXT))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=MUTED))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── 팔레트 고르개 ──
        self._pick = RoundButton(self, text="", command=self._menu,
                                 bg=CARD, fg=TEXT, radius=theme.RADIUS["ctl"],
                                 font=font_fn(7), outline=BORDER,
                                 focus_color=ACCENT, zone_bg=CARD,
                                 align="left", trailing="▾")
        self._pick.pack(fill="x", padx=6, pady=(6, 2))

        # ── 블럭 목록 (스크롤) ──
        wrap = tk.Frame(self, bg=CARD)
        wrap.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0, bd=0)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._inner = tk.Frame(self._canvas, bg=CARD)
        self._win = self._canvas.create_window((0, 0), window=self._inner,
                                               anchor="nw")
        self._inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfigure(
            self._win, width=e.width))
        # 휠은 띠 어디에 올려도 먹어야 한다 — 칩 위에서만 안 먹으면 답답하다
        for w in (self._canvas, self._inner):
            w.bind("<MouseWheel>", self._wheel)

        self.render()

    # ── 그리기 ──────────────────────────────────────
    def render(self):
        for w in self._inner.winfo_children():
            w.destroy()
        tabs = self._tabs()
        self._pick.set_text(self._pick_text(tabs), pad_x=8, pad_y=3)

        main = next((t for t in tabs if t.get("name") == palette.MAIN_TAB), None)
        if main and main.get("blocks"):
            self._section("공통")
            for blk in self._sorted(main["blocks"]):
                self._chip(blk)

        others = [t for t in tabs if t.get("name") != palette.MAIN_TAB]
        idx = min(self._tab_index(), max(len(others) - 1, 0))
        if others:
            cur = others[idx]
            if cur.get("blocks"):
                self._section(cur.get("name", ""))
                for blk in self._sorted(cur["blocks"]):
                    self._chip(blk)

    def _sorted(self, blocks):
        """읽는 차례대로 — 격자에서 위에서 아래, 왼쪽에서 오른쪽."""
        return sorted(blocks, key=lambda b: (int(b.get("row", 0)),
                                             int(b.get("col", 0))))

    def _section(self, name):
        tk.Label(self._inner, text=name, font=self._font(7), fg=FAINT,
                 bg=CARD, anchor="w").pack(fill="x", padx=8, pady=(8, 2))

    def _chip(self, blk):
        bg = self._color(blk)
        text = self._label(blk).replace("\n", " ")
        if len(text) > 9:
            text = text[:8] + "…"
        b = RoundButton(self._inner, text=text,
                        command=lambda x=blk: self._run(x),
                        bg=bg, fg=theme.text_on(bg),
                        radius=theme.RADIUS["ctl"], font=self._font(8),
                        outline=BORDER, focus_color=ACCENT, zone_bg=CARD,
                        align="left", pad_in=8)
        b.config(height=self._chip_h)
        b.pack(fill="x", padx=6, pady=2)
        b.bind("<MouseWheel>", self._wheel)

    def _wheel(self, e):
        self._canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        return "break"

    # ── 팔레트 고르기 ────────────────────────────────
    def _pick_text(self, tabs=None):
        others = [t for t in (tabs or self._tabs())
                  if t.get("name") != palette.MAIN_TAB]
        if not others:
            return "팔레트 없음"
        name = others[min(self._tab_index(), len(others) - 1)].get("name", "")
        return name if len(name) <= 8 else name[:7] + "…"

    def _menu(self):
        """띠에서는 팝오버 대신 **다음 팔레트로 넘기기**로 둔다.

        폭 150px 짜리 띠 위에 메뉴를 띄우면 메뉴가 띠보다 넓어져 한글을
        덮는다. 팔레트가 보통 두셋이라 한 번 눌러 넘기는 편이 빠르다.
        """
        others = [t for t in self._tabs() if t.get("name") != palette.MAIN_TAB]
        if len(others) <= 1:
            return
        self._pick_tab((self._tab_index() + 1) % len(others))
        self.render()
