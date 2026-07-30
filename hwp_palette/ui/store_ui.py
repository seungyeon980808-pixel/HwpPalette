# -*- coding: utf-8 -*-
r"""물감 창고 — 팔레트 설정 창 왼쪽에 붙는 서랍 (2026-07-27).

왜 만들었나:
    물감 설정과 팔레트 설정이 따로 떠 있어서 "물감을 만들고 → 어디 둘지 정한다"
    한 흐름이 창 두 개로 갈려 있었다. 게다가 물감 설정의 목록은 글자 표라
    팔레트의 타일과 **같은 물건으로 안 보였다**. 창고는 물감을 팔레트 블럭과
    같은 생김새의 타일로 보여주고, 그 자리에서 팔레트에 놓게 한다.

색이 말하는 것 (사용자 결정 2026-07-28에 뒤집음):
    흰색  — **안 씀**. 어느 팔레트에도 안 놓인 물감.
    파랑  — **쓰는 중**. 다른 팔레트에 놓여 있다.
    코랄  — **이 팔레트**. 지금 보고 있는 탭에 놓여 있다.
    초록  — **고른 것**.
    "어느 탭에 있는지"를 글자로 적지 않는 이유: 탭을 옮겨 다니면 색이 알려준다.

    왜 뒤집었나: 안 쓰는 물감은 목록 맨 위에 오는데 그것들이 파랗게 칠해져
    있으니 창고를 열 때마다 **파란 덩어리가 먼저 보였다** — 색의 세기는
    '중요하다'가 아니라 '이미 쓰고 있다'를 말해야 한다는 판단 (사용자 지적:
    "안 씀이 파란색이면 느낌이 이상하다"). 흰색은 빈 자리처럼 읽혀서
    '아직 아무 데도 안 갔다'와 정확히 맞물린다.

분류를 탭이 아니라 칩 한 줄로 둔 이유:
    창고의 핵심은 "안 놓인 물감이 여기 있다"인데, 분류로 탭을 갈라 놓으면
    그것들이 네 탭에 흩어져 **어느 탭에서도 다 보이지 않는다.**

놓기가 되는 것:
    템플릿·양식·특수기호. 서식 물감은 팔레트 블럭 종류가 따로 없어(문서에서
    \이름\ 으로 부르는 물건이라) 놓기 대신 안내를 띄운다.
"""

import tkinter as tk
from tkinter import ttk
from hwp_palette.design import dialogs as messagebox   # 윈도우 기본 대화상자 대신 프로그램과 같은 얼굴 (2026-07-27)

from hwp_palette.core import applog
from hwp_palette.model import library
from hwp_palette.model import palette
from hwp_palette.hwp import preview
from hwp_palette.design import theme
from hwp_palette.design.roundbtn import RoundButton, RoundTile

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

# 흰색 = 안 씀 / 초록 = 다른 팔레트에서 쓰는 중 / 코랄 = 이 팔레트 / 파랑 = 고른 것.
# 파랑·코랄·초록은 색상환에서 멀리 떨어져 있어 나란히 놓여도 구별된다.
#
# 2026-07-31: '쓰는 중'과 '고른 것'의 색을 맞바꿨다(사용자 지적) — 강조색
# 계열인 파랑은 **지금 고른 것**(가장 눈에 띄어야 하는 상태)에 주고,
# '쓰는 중'(그냥 정보성 표시)은 초록으로 내렸다. 이름(USED_*/SEL_*)은
# 그대로 두고 **값만** 바꿨다 — 이 값들을 쓰는 다른 코드(선택 강조·
# share_btn 등)를 전부 고칠 필요가 없다.
FREE_BG, FREE_LINE, FREE_FG = CARD, BORDER, TEXT
USED_BG, USED_LINE, USED_FG = "#e6f6ea", "#2da44e", "#116329"
HERE_BG, HERE_LINE, HERE_FG = "#ffefe9", "#f0997b", "#8a3418"
SEL_BG, SEL_LINE, SEL_FG = ACCENT_SOFT, "#54aeff", "#0550ae"

# 고른 해시태그는 **회색**이다 (사용자 지적 2026-07-28) — 예전엔 옅은 파랑이라
# 바로 아래 '안 씀' 견본과 색이 겹쳐, 태그를 고른 것인지 물감 상태인지가
# 한눈에 안 갈렸다. 거르개는 물감의 상태를 말하는 물건이 아니므로 색 규칙
# 바깥의 무채색을 쓴다.
CHIP_ON_BG, CHIP_ON_LINE, CHIP_ON_FG = "#e6e6ea", "#9a9aa0", "#3c3c40"

SHARE_GLYPH = theme.SHARE_GLYPH

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
                 on_drop=None,
                 width=326, height=430):  # 20% 더 넓게 (사용자 결정 2026-07-27)
        super().__init__(master, bg=CARD, width=width, height=height)
        self.pack_propagate(False)
        self.on_place = on_place            # 블럭 dict → 팔레트에 놓기
        self.on_select = on_select          # (분류, 항목) → 오른쪽 미리보기 판
        self.on_drop = on_drop              # (블럭, x_root, y_root) → 격자에 놓기
        self.tab_name_fn = tab_name_fn      # 지금 보고 있는 탭 이름
        self._drag = None                   # 끌기 상태 (타일 → 팔레트 격자)
        self.filter = None                  # None = 전체
        self.sel_key = None                 # 고른 물감 (분류, id)
        # Ctrl 을 누른 채 고르면 여러 개가 쌓인다 (사용자 결정 2026-07-28) —
        # 동료에게 물감 몇 개만 골라 보내는 일에 쓴다. 미리보기 판은 여전히
        # **마지막에 누른 하나**를 보여준다: 여러 개를 한 판에 겹쳐 보여줄
        # 방법이 없고, 고르는 동안 오른쪽이 텅 비면 무엇을 담았는지 모른다.
        self.multi = set()                  # {(분류, id)} — 내보내기 대상
        self._free_hint = ""                # 담은 게 없을 때 머리말에 쓸 말
        self._tiles = {}
        self._photo = None                  # ⚠ 참조를 붙들어야 그림이 안 사라진다

        head = tk.Frame(self, bg=CARD)
        head.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(head, text="물감 창고", font=(FONT, theme.fs(FS["head"]), "bold"),
                 bg=CARD, fg=TEXT).pack(side="left")
        # 나누기 — 팔레트 설정 쪽과 **같은 기호**를 쓴다 (사용자 결정 2026-07-28).
        # 한쪽은 팔레트를, 한쪽은 물감을 주고받지만 하는 일은 같으므로 기호가
        # 같아야 "여기서도 주고받는구나"가 배움 없이 읽힌다.
        self.share_btn = RoundButton(
            head, text=SHARE_GLYPH, command=self._share_menu,
            bg=CARD, fg=MUTED, radius=theme.RADIUS["ctl"],
            font=(FONT, theme.fs(FS["body"])), outline="", zone_bg=CARD)
        self.share_btn.config(width=theme.fs(22), height=theme.fs(20))
        self.share_btn.pack(side="right")
        self.hint = tk.Label(head, text="", font=(FONT, theme.fs(FS["caption"])),
                             bg=CARD, fg=MUTED)
        self.hint.pack(side="left", padx=(6, 0))

        self.chip_box = tk.Frame(self, bg=CARD)
        self.chip_box.pack(fill="x", padx=6, pady=(2, 4))


        # 색이 무슨 뜻인지 화면이 말해 준다 (사용자 지적 2026-07-27) —
        # 안내가 없으면 파랑·코랄을 반대로 읽는다.
        # 견본은 **타일과 같은 생김새**(그 색 판 위에 그 색 글자)로, 세 칸을
        # 같은 폭으로 고르게 편다 — 점 따로 글자 따로 왼쪽에 몰려 있던 옛
        # 안내는 색과 뜻을 잇느라 눈이 한 번 더 오가야 했고 한쪽으로 쏠려
        # 보였다 (사용자 지적 2026-07-27).
        legend = tk.Frame(self, bg=CARD)
        legend.pack(fill="x", padx=8, pady=(0, 6))
        # '안 씀'은 뺐다 (사용자 지적 2026-07-31: "안씀의 경우에는 알려주는
        # 표시가 없어야 합니다") — 안 쓰는 물감은 원래도 흰 카드 그대로라
        # 색이 없다. 색 없는 상태를 위해 색 견본을 그리는 것 자체가 모순이라,
        # 실제로 색이 있는 세 상태만 안내한다.
        states = (("쓰는 중", USED_BG, USED_LINE, USED_FG),
                  ("이 팔레트", HERE_BG, HERE_LINE, HERE_FG),
                  ("고른 것", SEL_BG, SEL_LINE, SEL_FG))
        for i, (text, bg, line, fg) in enumerate(states):
            legend.columnconfigure(i, weight=1, uniform="legend")
            tk.Label(legend, text=text, font=(FONT, theme.fs(FS["caption"])),
                     bg=bg, fg=fg, pady=2,
                     highlightbackground=line, highlightthickness=1
                     ).grid(row=0, column=i, sticky="ew",
                            padx=(0, 3) if i < len(states) - 1 else 0)

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
        self._free_hint = (f"안 쓰는 물감 {free_n}개" if free_n
                           else "모두 팔레트에 놓여 있습니다")
        self._sync_share()

        # 판 폭을 **내용으로 계산한다** (2026-07-31, 사용자 지적: "물감창고와
        # 물감 미리보기가 잘려있다"). 고정 326px 은 카드 이름이 길어지면
        # 두 열의 최소 폭이 그걸 넘어, 오른쪽 열이 미리보기와의 경계선에서
        # 잘렸다. 가장 긴 이름(잘림 처리 후)을 실측해 두 열이 온전히 들어갈
        # 폭으로 판을 늘린다 — 창은 _fit_window 가 따라 커진다.
        try:
            import tkinter.font as tkfont
            f = tkfont.Font(family=FONT, size=theme.fs(FS["sub"]),
                            weight="bold")
            def shown(name):
                return name if len(name) <= 12 else name[:12] + "…"
            widest = max((f.measure(shown(it.get("name", "")))
                          for _c, it in items), default=120)
            # 카드 안쪽 여백(6*2) + 카드 사이(3*2*2) + 스크롤바(≈16) + 판 여백
            need = 2 * (widest + 12 + 6) + 16 + 12
            self.config(width=max(326, min(560, need)))
        except Exception:
            pass

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
                            bg=CHIP_ON_BG if on else CARD,
                            fg=CHIP_ON_FG if on else MUTED,
                            padx=5, pady=2, cursor="hand2",
                            highlightbackground=CHIP_ON_LINE if on else BORDER,
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
        if state == "here":
            return HERE_BG, HERE_LINE, HERE_FG
        if state == "away":
            return USED_BG, USED_LINE, USED_FG
        return FREE_BG, FREE_LINE, FREE_FG      # free · plain — 안 씀(흰색)

    def _tile(self, parent, cat, item, state):
        # 곡률은 메인 창 블럭과 같다 (RoundTile 머리말 참고)
        tile = RoundTile(parent, bg=CARD, radius=theme.RADIUS["ctl"],
                         zone_bg=CARD, cursor="hand2")
        # 가운데 정렬로 통일 (사용자 지적 2026-07-30) — 팔레트 설정 미리보기의
        # 블럭 이름과 같은 규칙이다.
        name = item.get("name", "?")
        nm = tk.Label(tile, text=name if len(name) <= 12 else name[:12] + "…",
                      font=(FONT, theme.fs(FS["sub"]), "bold"),
                      anchor="center", justify="center")
        nm.pack(fill="x", padx=6, pady=(5, 0))
        slots = int(item.get("slot_count") or 0)
        sub = tk.Label(tile, text=(f"빈칸 {slots}" if slots else " "),
                       font=(FONT, theme.fs(FS["caption"])),
                       anchor="center", justify="center")
        sub.pack(fill="x", padx=6, pady=(0, 5))
        tile._parts = (nm, sub)
        tile._state = state
        # 누르면 고르고, 그대로 끌면 팔레트 격자로 가져간다 (사용자 결정
        # 2026-07-28 — '팔레트에 놓기' 버튼 대신 끌어다 놓기)
        for w in (tile, nm, sub):
            w.bind("<ButtonPress-1>",
                   lambda e, c=cat, i=item: self._tile_press(e, c, i))
            w.bind("<B1-Motion>", self._tile_motion)
            w.bind("<ButtonRelease-1>", self._tile_release)
        self._paint_tile(tile, state, selected=False)
        return tile

    # ── 타일 끌어서 팔레트에 놓기 ─────────────────────
    def _tile_press(self, e, cat, item):
        # Ctrl 누른 채 = 여러 개 담기 (0x0004 는 윈도우 Tk 의 Control 비트).
        # 끌기는 시작하지 않는다 — 여러 개를 담는 중에 손이 조금 흔들렸다고
        # 팔레트로 물감이 날아가면 안 된다.
        if e.state & 0x0004:
            self._toggle_multi(cat, item)
            self._drag = None
            return
        self._select(cat, item)             # 누르는 것 자체는 '고르기'
        block = self.block_of(cat, item)
        if self.on_drop is None or block is None:
            self._drag = None               # 놓을 수 없는 분류 (서식)
            return
        self._drag = {"block": block, "name": item.get("name", ""),
                      "x": e.x_root, "y": e.y_root, "ghost": None}

    def _tile_motion(self, e):
        d = self._drag
        if d is None:
            return
        if d["ghost"] is None:
            # 4px 넘게 움직인 뒤에야 든다 — 그냥 클릭과 구분 (팔레트 격자의
            # 타일 끌기와 같은 규칙)
            if abs(e.x_root - d["x"]) <= 4 and abs(e.y_root - d["y"]) <= 4:
                return
            try:
                ghost = tk.Toplevel(self.winfo_toplevel())
                ghost.wm_overrideredirect(True)
                ghost.attributes("-topmost", True)
                try:
                    ghost.attributes("-alpha", 0.85)
                except Exception:
                    pass
                tk.Label(ghost, text=d["name"], bg=SEL_BG, fg=SEL_FG,
                         font=(FONT, theme.fs(FS["sub"]), "bold"),
                         padx=10, pady=6,
                         highlightbackground=SEL_LINE,
                         highlightthickness=1).pack()
                d["ghost"] = ghost
            except Exception as ex:
                applog.exc("끌기 유령 만들기 실패 — 끌기 취소", ex)
                self._drag = None
                return
        try:
            d["ghost"].geometry(f"+{e.x_root + 8}+{e.y_root + 8}")
        except Exception:
            pass

    def _tile_release(self, e):
        d, self._drag = self._drag, None
        if d is None or d["ghost"] is None:
            return                          # 끌지 않았다 — 그냥 클릭
        try:
            d["ghost"].destroy()
        except Exception:
            pass
        if self.on_drop:
            self.on_drop(dict(d["block"]), e.x_root, e.y_root)

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
            self._paint_tile(tile, tile._state,
                             selected=(key == self.sel_key or key in self.multi))

    # ── 여러 개 담기 · 주고받기 ────────────────────────
    def _toggle_multi(self, cat, item):
        key = (cat, item.get("id"))
        if key in self.multi:
            self.multi.discard(key)
        else:
            self.multi.add(key)
            if self.on_select:
                self.on_select(cat, item)   # 방금 담은 것을 오른쪽에 보여준다
        self.sel_key = None                 # 하나 고르기와 섞이지 않게
        self._paint_selection()
        self._sync_share()

    def clear_multi(self):
        if not self.multi:
            return
        self.multi.clear()
        self._paint_selection()
        self._sync_share()

    def _sync_share(self):
        """담은 개수를 화살표 버튼의 색으로 말한다 — 숫자를 따로 안 적는다."""
        n = len(self.multi)
        try:
            self.share_btn.retint(bg=SEL_BG if n else CARD,
                                  fg=SEL_FG if n else MUTED)
        except Exception:
            pass
        try:
            self.hint.config(text=(f"{n}개 담음 — ↗ 로 내보냅니다" if n
                                   else self._free_hint))
        except Exception:
            pass

    def _multi_pairs(self):
        """담은 것 → [(분류, 항목)] — 그새 지워진 물감은 빠진다."""
        pairs = []
        for cat, iid in sorted(self.multi):
            it = library.find_by_id(cat, iid)
            if it is not None:
                pairs.append((cat, it))
        return pairs

    def _share_menu(self):
        r"""↗ — 주고받기. **누르자마자 파일창이 뜨지 않는다** (사용자 결정
        2026-07-28): 내보내기와 불러오기 중 어느 쪽인지 먼저 고르게 한다.
        담은 물감이 없으면 내보낼 것이 없으므로 불러오기만 남는다.
        """
        from hwp_palette.ui import library_ui                   # 순환 참조 회피
        from hwp_palette.design.popover import Popover
        pairs = self._multi_pairs()
        pop = Popover(self.winfo_toplevel(), self.share_btn)
        # 말줄임표를 안 쓴다 (사용자 지적 2026-07-31, palette_ui._share_menu 와
        # 같은 이유·같은 자리).
        if pairs:
            pop.add(f"고른 물감 {len(pairs)}개 내보내기",
                    lambda: library_ui.export_items_flow(
                        self.winfo_toplevel(), pairs, on_done=self.clear_multi))
        else:
            pop.add("내보낼 물감을 Ctrl+클릭으로 고르세요", lambda: None)
        pop.separator()
        pop.add("불러오기",
                lambda: library_ui.import_flow(self.winfo_toplevel(),
                                               on_saved=self.refresh))
        pop.show()

    def refresh_states(self):
        r"""배치 색(안 씀/이 팔레트에 있음)만 다시 칠한다 — 위젯 재생성 없음.

        블럭 하나를 옮길 때마다 창고를 통째로 파괴·재생성하던 것이 버벅임의
        큰 몫이었다 (2026-07-28, 버벅임 1단계). 물감 **목록** 자체가 바뀔 때만
        refresh(전체)를 쓰고, 배치만 바뀌면 이걸로 충분하다.

        '안 쓰는 물감이 위' 정렬은 다음 전체 refresh 때 맞춰진다 — 누른
        타일이 눈앞에서 자리를 옮겨 다니면 안 된다는 규칙(_select 머리말)과
        같은 이유로, 여기서는 일부러 재정렬하지 않는다.
        """
        where = self._placement()
        here = self.tab_name_fn()
        free_n = 0
        for cat, item in getattr(self, "_order", []):
            state = self._state(cat, item, where, here)
            if state == "free":
                free_n += 1
            key = (cat, item.get("id"))
            tile = self._tiles.get(key)
            if tile is None:
                continue
            tile._state = state
            self._paint_tile(tile, state,
                             selected=(key == self.sel_key or key in self.multi))
        self._free_hint = (f"안 쓰는 물감 {free_n}개" if free_n
                           else "모두 팔레트에 놓여 있습니다")
        self._sync_share()

    def _select(self, cat, item):
        r"""물감 고르기 — **화면을 다시 그리지 않는다.**

        예전에는 고를 때마다 창고를 통째로 다시 그리고(펼침 카드 때문에)
        창 크기·위치까지 바꿔서, 누를 때마다 깜빡이고 타일이 다른 자리로
        옮겨 갔다(사용자 지적 2026-07-27). 지금은 타일 색만 바꾸고,
        내용은 오른쪽 미리보기 판이 받는다.
        """
        self.sel_key = (cat, item.get("id"))
        # 그냥 클릭은 담아 둔 것을 푼다 — 파일 탐색기와 같은 규칙이라
        # 따로 배우지 않아도 손이 안다.
        if self.multi:
            self.multi.clear()
            self._sync_share()
        self._paint_selection()
        if self.on_select:
            self.on_select(cat, item)

    def clear_selection(self):
        """바깥(팔레트 설정 격자)에서 블럭을 고르면 이쪽 선택을 지운다.

        예전에는 두 선택이 서로 몰라서 **동시에 파랗게** 보일 수 있었다
        (사용자 지적 2026-07-31: "팔레트에 있는 물감과 물감 창고에 있는
        물감이 동시에 선택이 가능한 버그"). 한 번에 하나만 선택된다.
        """
        if self.sel_key is None:
            return
        self.sel_key = None
        self._paint_selection()

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
        from hwp_palette.ui import library_ui            # 순환 참조 회피 (library_ui → … → store_ui)
        library_ui.edit_item_dialog(self.winfo_toplevel(), cat, item,
                                    on_saved=self.refresh)


def _cat_label(key):
    for label, k in CATS:
        if k == key:
            return label
    return key
