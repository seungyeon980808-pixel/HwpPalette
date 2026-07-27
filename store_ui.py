# -*- coding: utf-8 -*-
r"""물감 창고 — 팔레트 설정 창 왼쪽에 붙는 서랍 (2026-07-27).

왜 만들었나:
    물감 설정과 팔레트 설정이 따로 떠 있어서 "물감을 만들고 → 어디 둘지 정한다"
    한 흐름이 창 두 개로 갈려 있었다. 게다가 물감 설정의 목록은 글자 표라
    팔레트의 타일과 **같은 물건으로 안 보였다**. 창고는 물감을 팔레트 블럭과
    같은 생김새의 타일로 보여주고, 그 자리에서 팔레트에 놓게 한다.

색이 말하는 것 (사용자 결정):
    파랑  — 어느 팔레트에도 안 놓인 물감. 눈에 띄어야 할 쪽은 이쪽이다.
    코랄  — **지금 보고 있는 탭**에 이미 놓인 물감. 탭을 바꾸면 따라 바뀐다.
    흰색  — 다른 탭에만 놓인 물감.
    "어느 탭에 있는지"를 글자로 적지 않는 이유: 탭을 옮겨 다니면 색이 알려준다.

분류를 탭이 아니라 칩 한 줄로 둔 이유:
    창고의 핵심은 "안 놓인 물감이 여기 있다"인데, 분류로 탭을 갈라 놓으면
    그것들이 네 탭에 흩어져 **어느 탭에서도 다 보이지 않는다.**

놓기가 되는 것:
    템플릿·양식·특수기호. 서식 물감은 팔레트 블럭 종류가 따로 없어(문서에서
    \이름\ 으로 부르는 물건이라) 놓기 대신 안내를 띄운다.
"""

import tkinter as tk
from tkinter import ttk
import dialogs as messagebox   # 윈도우 기본 대화상자 대신 프로그램과 같은 얼굴 (2026-07-27)

import applog
import library
import palette
import preview
import theme
from roundbtn import RoundButton

_C = theme.colors()
BG = _C["bg"]
CARD = _C["card"]
ACCENT = _C["accent"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
SOFT = _C["yellow"]
ACCENT_SOFT = _C["accent_soft"]
FONT = theme.FONT
SP = theme.SP
FS = theme.FS

# 파랑 = 안 놓임 / 코랄 = 이 탭에 있음 / 초록 = 지금 고른 것.
# 셋 다 색상환에서 멀리 떨어져 있어 나란히 놓여도 구별된다.
FREE_BG, FREE_LINE, FREE_FG = ACCENT_SOFT, "#54aeff", "#0550ae"
HERE_BG, HERE_LINE, HERE_FG = "#ffefe9", "#f0997b", "#8a3418"
SEL_BG, SEL_LINE, SEL_FG = "#e6f6ea", "#2da44e", "#116329"

CATS = (("전체", None), ("서식", "서식"), ("특수기호", "문자"),
        ("템플릿", "템플릿"), ("양식", "양식"))
PLACEABLE = {"템플릿", "양식", "문자"}
PREVIEW_W, PREVIEW_H = 260, 150
COLS = 2                      # 타일 열 수


class StorePanel(tk.Frame):
    # 높이를 못박는 이유: 창 크기는 '내용이 최소'로 잡히는데(palette_ui.minsize),
    # 창고는 스크롤이라 내용 높이가 0에 가깝다. 그대로 두면 창고가 두 줄만
    # 보이게 창이 납작해진다.
    def __init__(self, master, on_place, tab_name_fn, on_select=None,
                 width=326, height=430):  # 20% 더 넓게 (사용자 결정 2026-07-27)
        super().__init__(master, bg=CARD, width=width, height=height)
        self.pack_propagate(False)
        self.on_place = on_place            # 블럭 dict → 팔레트에 놓기
        self.on_select = on_select          # (분류, 항목) → 오른쪽 미리보기 판
        self.tab_name_fn = tab_name_fn      # 지금 보고 있는 탭 이름
        self.filter = None                  # None = 전체
        self.sel_key = None                 # 고른 물감 (분류, id)
        self._tiles = {}
        self._photo = None                  # ⚠ 참조를 붙들어야 그림이 안 사라진다

        head = tk.Frame(self, bg=CARD)
        head.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(head, text="물감 창고", font=(FONT, theme.fs(FS["head"]), "bold"),
                 bg=CARD, fg=TEXT).pack(side="left")
        self.hint = tk.Label(head, text="", font=(FONT, theme.fs(FS["caption"])),
                             bg=CARD, fg=MUTED)
        self.hint.pack(side="left", padx=(6, 0))

        self.chip_box = tk.Frame(self, bg=CARD)
        self.chip_box.pack(fill="x", padx=6, pady=(2, 4))


        # 색이 무슨 뜻인지 화면이 말해 준다 (사용자 지적 2026-07-27) —
        # 안내가 없으면 파랑·코랄을 반대로 읽는다
        legend = tk.Frame(self, bg=CARD)
        legend.pack(fill="x", padx=8, pady=(0, 4))
        for text, col in (("안 씀", FREE_BG), ("이 팔레트에 있음", HERE_BG),
                          ("고른 것", SEL_BG)):
            dot = tk.Label(legend, text="  ", bg=col, font=(FONT, theme.fs(6)),
                           highlightbackground=BORDER, highlightthickness=1)
            dot.pack(side="left")
            tk.Label(legend, text=text, font=(FONT, theme.fs(FS["caption"])), bg=CARD,
                     fg=MUTED).pack(side="left", padx=(3, 8))

        # 물감이 스무 개를 넘으면 스크롤이 필요하다
        wrap = tk.Frame(self, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=(6, 0), pady=(0, 6))
        self.canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0)
        messagebox.style_scrollbars(self)
        bar = ttk.Scrollbar(wrap, orient="vertical",
                            style="App.Vertical.TScrollbar",
                            command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg=CARD)
        self.body.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.body,
                                              anchor="nw")
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        # 마우스 휠은 여기서 bind_all 하지 않는다 (2026-07-27) — bind_all 은
        # Tk 의 "all" 태그 하나를 **덮어쓴다.** 옆의 미리보기 판도 같은 식으로
        # bind_all 하면 나중 것만 남고 먼저 것은 조용히 죽는다. 창고와 미리보기
        # 판을 함께 담은 SettingsWindow 가 한 곳(_route_wheel)에서 모아 이
        # 메서드를 불러 준다.

        self.refresh()

    def on_wheel(self, e):
        """마우스 휠 — 커서가 창고 위일 때만 굴린다. 부모가 한 곳에서 불러 준다."""
        try:
            x, y = e.x_root, e.y_root
            if not (self.winfo_rootx() <= x <= self.winfo_rootx() + self.winfo_width()
                    and self.winfo_rooty() <= y <= self.winfo_rooty() + self.winfo_height()):
                return
            self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        except Exception:
            pass

    # ── 데이터 ────────────────────────────────────
    def _items(self):
        """[(분류, 항목)] — 지금 고른 칩에 맞는 것만, 분류 순서대로."""
        out = []
        for _label, key in CATS[1:]:
            if self.filter and key != self.filter:
                continue
            for it in library.list_items(key):
                out.append((key, it))
        return out

    def _placement(self):
        """{항목 id: set(탭 이름)} — 어느 팔레트에 놓여 있는지.

        ref 를 갖는 템플릿·양식만 정확히 알 수 있다. 특수기호 블럭은 값을
        복사해 넣는 것이라 원본과의 연결이 없다.
        """
        where = {}
        try:
            for tab in palette.load_tabs():
                for b in tab.get("blocks", []):
                    ref = b.get("ref")
                    if ref:
                        where.setdefault(ref, set()).add(tab.get("name"))
        except Exception as e:
            applog.exc("창고: 팔레트 배치 읽기 실패", e)
        return where

    def _state(self, cat, item, where, here):
        """타일 색을 정하는 상태 — free / here / away / plain."""
        if cat not in ("템플릿", "양식"):
            return "plain"          # 놓임을 추적할 수 없는 분류
        tabs = where.get(item.get("id"))
        if not tabs:
            return "free"
        return "here" if here in tabs else "away"

    # ── 그리기 ────────────────────────────────────
    def refresh(self):
        r"""창고를 다시 그린다 — **물감 목록이나 배치가 바뀔 때만** 부른다.

        물감을 고르는 것만으로 여기를 부르면 안 된다 (사용자 지적 2026-07-27:
        "누를 때마다 깜빡거리면서 위치가 이동한다"). 고르기는 _select 가
        타일 색만 바꾸므로 화면이 흔들리지 않는다.
        """
        self._draw_chips()
        for w in self.body.winfo_children():
            w.destroy()
        self._tiles = {}
        where = self._placement()
        here = self.tab_name_fn()
        items = self._items()
        # 안 쓰는 물감이 늘 위에 온다 (사용자 결정) — 정렬은 여기서만 한다.
        # 고를 때마다 다시 정렬하면 눌렀던 것이 눈앞에서 도망간다.
        rank = {"free": 0, "here": 1, "away": 2, "plain": 3}
        items.sort(key=lambda ci: rank[self._state(ci[0], ci[1], where, here)])
        self._order = items

        free_n = sum(1 for c, i in items
                     if self._state(c, i, where, here) == "free")
        self.hint.config(text=(f"안 쓰는 물감 {free_n}개"
                               if free_n else "모두 팔레트에 놓여 있습니다"))

        grid = tk.Frame(self.body, bg=CARD)
        grid.pack(fill="x")
        for c in range(COLS):
            grid.columnconfigure(c, weight=1, uniform="tile")
        for n, (cat, item) in enumerate(items):
            key = (cat, item.get("id"))
            tile = self._tile(grid, cat, item,
                              self._state(cat, item, where, here))
            tile.grid(row=n // COLS, column=n % COLS, sticky="ew",
                      padx=3, pady=3)
            self._tiles[key] = tile
        if not items:
            tk.Label(self.body, text="이 분류에 물감이 없습니다.",
                     font=(FONT, theme.fs(FS["sub"])), bg=CARD, fg=MUTED).pack(pady=SP["xl"])
        self._paint_selection()

    def _draw_chips(self):
        for w in self.chip_box.winfo_children():
            w.destroy()
        counts = {key: len(library.list_items(key))
                  for _l, key in CATS[1:]}
        counts[None] = sum(counts.values())
        # 칩은 세 개씩 줄바꿈한다 — 한 줄로 늘어놓으면 창고 폭을 넘어
        # 마지막 칩(#양식)이 잘려 안 보였다 (실측 2026-07-27).
        for i, (label, key) in enumerate(CATS):
            on = (self.filter == key)
            chip = tk.Label(self.chip_box,
                            text=f"#{label} {counts.get(key, 0)}",
                            font=(FONT, theme.fs(FS["caption"])),
                            bg=ACCENT_SOFT if on else CARD,
                            fg=FREE_FG if on else MUTED,
                            padx=5, pady=2, cursor="hand2",
                            highlightbackground=FREE_LINE if on else BORDER,
                            highlightthickness=1)
            chip.grid(row=i // 3, column=i % 3, sticky="ew", padx=2, pady=1)
            chip.bind("<Button-1>", lambda e, k=key: self._pick_chip(k))
        for c in range(3):
            self.chip_box.columnconfigure(c, weight=1)

    def _pick_chip(self, key):
        self.filter = key
        self.refresh()
        # 스크롤을 맨 위로 되돌린다 — 안 그러면 항목이 줄어든 만큼 위쪽이
        # 텅 빈 채로 남는다 (실측 2026-07-27: #양식 3개를 골랐는데 화면
        # 아래쪽에 붙어 보였다)
        self.canvas.yview_moveto(0)

    def _colors(self, state):
        if state == "free":
            return FREE_BG, FREE_LINE, FREE_FG
        if state == "here":
            return HERE_BG, HERE_LINE, HERE_FG
        return CARD, BORDER, TEXT

    def _tile(self, parent, cat, item, state):
        tile = tk.Frame(parent, cursor="hand2", highlightthickness=1)
        name = item.get("name", "?")
        nm = tk.Label(tile, text=name if len(name) <= 12 else name[:12] + "…",
                      font=(FONT, theme.fs(FS["sub"]), "bold"), anchor="w")
        nm.pack(fill="x", padx=6, pady=(5, 0))
        slots = int(item.get("slot_count") or 0)
        sub = tk.Label(tile, text=(f"빈칸 {slots}" if slots else " "),
                       font=(FONT, theme.fs(FS["caption"])), anchor="w")
        sub.pack(fill="x", padx=6, pady=(0, 5))
        tile._parts = (nm, sub)
        tile._state = state
        for w in (tile, nm, sub):
            w.bind("<Button-1>", lambda e, c=cat, i=item: self._select(c, i))
        self._paint_tile(tile, state, selected=False)
        return tile

    def _paint_tile(self, tile, state, selected):
        """타일 하나의 색만 바꾼다 — 위젯을 다시 만들지 않으므로 안 깜빡인다."""
        bg, line, fg = (SEL_BG, SEL_LINE, SEL_FG) if selected             else self._colors(state)
        try:
            tile.config(bg=bg, highlightbackground=line,
                        highlightcolor=line,
                        highlightthickness=2 if selected else 1)
            for w in tile._parts:
                w.config(bg=bg, fg=fg)
        except tk.TclError:
            pass                      # 다시 그리는 중이면 지나간다

    def _paint_selection(self):
        for key, tile in getattr(self, "_tiles", {}).items():
            self._paint_tile(tile, tile._state, selected=(key == self.sel_key))

    def _select(self, cat, item):
        r"""물감 고르기 — **화면을 다시 그리지 않는다.**

        예전에는 고를 때마다 창고를 통째로 다시 그리고(펼침 카드 때문에)
        창 크기·위치까지 바꿔서, 누를 때마다 깜빡이고 타일이 다른 자리로
        옮겨 갔다(사용자 지적 2026-07-27). 지금은 타일 색만 바꾸고,
        내용은 오른쪽 미리보기 판이 받는다.
        """
        self.sel_key = (cat, item.get("id"))
        self._paint_selection()
        if self.on_select:
            self.on_select(cat, item)

    # ── 바깥(미리보기 판)에서 부르는 동작 ─────────────
    def place_item(self, cat, item):
        block = self.block_of(cat, item)
        if block is None:
            messagebox.showinfo("놓을 수 없음",
                                "서식 물감은 팔레트 블럭이 아니라 문서에서 "
                                r"\이름\ 으로 부르는 물감입니다.", parent=self)
            return
        self.on_place(block)

    def block_of(self, cat, item):
        """물감 → 팔레트 블럭. 놓을 수 없는 분류면 None."""
        if cat == "템플릿":
            return {"type": "template", "ref": item["id"],
                    "template": item["name"], "span": 2, "rows": 1}
        if cat == "양식":
            return {"type": "form", "ref": item["id"],
                    "form": item["name"], "span": 2, "rows": 1}
        if cat == "문자":
            return {"type": "char", "value": item.get("text", ""),
                    "caption": item["name"], "span": 2, "rows": 1}
        return None

    def edit_item(self, cat, item):
        import library_ui            # 순환 참조 회피 (library_ui → … → store_ui)
        library_ui.edit_item_dialog(self.winfo_toplevel(), cat, item,
                                    on_saved=self.refresh)


def _cat_label(key):
    for label, k in CATS:
        if k == key:
            return label
    return key
