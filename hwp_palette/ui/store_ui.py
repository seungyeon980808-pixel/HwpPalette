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

분류를 해시태그에서 **탭**으로 (사용자 결정 2026-07-31):
    예전에는 `#전체 #서식 #특수기호 #템플릿 #양식` 칩 한 줄이었고, 그 옆에
    '쓰는 중·이 팔레트·고른 것' 색 안내가 나란히 붙어 있었다. 성격이 다른
    두 가지가 한 줄에 섞여 위계가 안 보였다 — 앞은 **분류**(무엇인가)이고
    뒤는 **상태**(지금 어떤가)다.

        분류  → 탭 한 줄. 물감은 반드시 다섯 중 하나에 속하므로 한 번에 하나.
        상태  → 창고 **제목 옆**으로 옮긴다. 자리를 따로 먹지 않는다.

    '전체'는 없앴다 (사용자: "섞여있을 필요가 없습니다"). 특수기호와 양식을
    같은 목록에서 볼 일이 없고, 개수는 탭마다 적혀 있다.

    '도구'를 정식 분류로 올렸다. 예전엔 팔레트 빈칸 대화상자에만 있고 창고엔
    없어서, 만드는 입구가 화면마다 달랐다. 다만 도구는 프로그램이 가진
    기능이라 **읽기 전용**이다 — ＋ 가 없다(무인 진행 규약 2026-07-31).

만드는 입구(＋)는 분류 바로 아래 (사용자 결정 2026-07-31, 시안 안 3):
    고정 줄이라 목록을 굴려도 늘 보이고, 분류 바로 밑이라 목록과도 가깝다.
    글씨는 켜 놓은 분류를 따라 바뀐다 — 누르기 전에 무엇이 만들어질지 안다.
    **팔레트 빈칸을 끌어 만드는 기존 길은 그대로 둔다** — 여기는 길을 하나
    더 내는 것이지 옮기는 것이 아니다.

폭을 고정한 이유 (사용자 지적 2026-07-31):
    내용에 따라 판 폭을 계산하던 것을 그만뒀다. 물감이 있고 없고에 따라
    좌우 폭이 출렁여서 "변형되어서는 안 된다"는 지적을 받았다. 이제 가득 찬
    상태를 기준으로 못박고, 스크롤바 자리도 늘 비워 둔다.

놓기가 되는 것:
    템플릿·양식·특수기호. 서식 물감은 팔레트 블럭 종류가 따로 없어(문서에서
    \이름\ 으로 부르는 물건이라) 놓기 대신 안내를 띄운다.
"""

import tkinter as tk
from tkinter import ttk
from hwp_palette.design import dialogs as messagebox   # 윈도우 기본 대화상자 대신 프로그램과 같은 얼굴 (2026-07-27)

from hwp_palette.core import applog
from hwp_palette.model import builtin_actions          # '도구' 분류의 목록
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
SUBBG = _C["subbg"]
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

# 꾸러미(섞은 물감) 리본 — 상태 색(파랑·초록·코랄) 어느 것과도 안 겹치는
# 보라 계열이다. 이건 '상태'가 아니라 '무엇인가'를 말하는 표시라서다.
MIX_BG, MIX_FG = "#f3eefc", "#6639ba"

SHARE_GLYPH = theme.SHARE_GLYPH

# 분류 다섯 — 이 차례가 화면의 탭 차례다. '전체'는 없다(위 머리말 참고).
# 라벨은 짧게: '서식 조합' 은 탭에서 줄이 바뀌어 '서식' 으로 줄였다
# (사용자 결정 2026-07-31).
CATS = (("특수기호", "문자"), ("템플릿", "템플릿"), ("서식", "서식"),
        ("양식", "양식"), ("도구", "도구"))
DEFAULT_CAT = "템플릿"        # 창고를 열면 여기부터 (가장 많이 쓰는 분류)
READONLY_CATS = {"도구"}      # 사용자가 만들 수 없는 분류 — ＋ 를 숨긴다
PLACEABLE = {"템플릿", "양식", "문자"}
PREVIEW_W, PREVIEW_H = 260, 150
COLS = 2                      # 타일 열 수

# 판 폭 고정 (사용자 결정 2026-07-31) — 내용에 따라 재계산하지 않는다.
# 가득 찬 상태에서 두 열이 온전히 들어가는 폭이다.
# 300 → 344 (사용자 지적 2026-07-31: "대칭이 안 맞게 지 맘대로 잘라버리면
# 어떻게 하냐"). 300 은 두 열 카드의 오른쪽 열이 판 가장자리에서 **비대칭으로**
# 잘리고, 제목 옆 색 안내('고른 것')까지 물렸다. 카드 두 열 + 스크롤바가
# 온전히 들어가는 실측 폭으로 되돌린다. 창이 세로 모니터 폭(1080)을 넘는 것은
# 감수하기로 했다 — 미리보기(400)는 줄이지 않는다.
STORE_W = 344


class StorePanel(tk.Frame):
    # 높이를 못박는 이유: 창 크기는 '내용이 최소'로 잡히는데(palette_ui.minsize),
    # 창고는 스크롤이라 내용 높이가 0에 가깝다. 그대로 두면 창고가 두 줄만
    # 보이게 창이 납작해진다.
    def __init__(self, master, on_place, tab_name_fn, on_select=None,
                 on_drop=None, on_new=None,
                 width=STORE_W, height=430):
        super().__init__(master, bg=CARD, width=width, height=height)
        self.pack_propagate(False)
        self.on_place = on_place            # 블럭 dict → 팔레트에 놓기
        self.on_select = on_select          # (분류, 항목) → 오른쪽 미리보기 판
        self.on_drop = on_drop              # (블럭, x_root, y_root) → 격자에 놓기
        self.on_new = on_new                # 분류 key → 그 분류의 물감 새로 만들기
        self.tab_name_fn = tab_name_fn      # 지금 보고 있는 탭 이름
        self._drag = None                   # 끌기 상태 (타일 → 팔레트 격자)
        # 분류는 늘 하나가 켜져 있다 — '전체'가 없어졌으므로 None 이 될 수 없다
        self.filter = DEFAULT_CAT
        self.sel_key = None                 # 고른 물감 (분류, id)
        # Ctrl 을 누른 채 고르면 여러 개가 쌓인다 (사용자 결정 2026-07-28) —
        # 동료에게 물감 몇 개만 골라 보내는 일에 쓴다. 미리보기 판은 여전히
        # **마지막에 누른 하나**를 보여준다: 여러 개를 한 판에 겹쳐 보여줄
        # 방법이 없고, 고르는 동안 오른쪽이 텅 비면 무엇을 담았는지 모른다.
        self.multi = set()                  # {(분류, id)} — 내보내기 대상
        self._free_hint = ""                # 담은 게 없을 때 머리말에 쓸 말
        self._tiles = {}
        self._order = []
        # 분류마다 만들어 둔 판 — 탭을 갈아탈 때 다시 만들지 않는다 (2026-07-31)
        self._cat_cache = {}
        self._cat_shown = None
        self._where_memo = None             # (배치, 지금 탭 이름) — 판 지을 때 공유
        self._states_dirty = False          # 배치가 바뀌어 다시 칠해야 하는가
        self._counts = {}                   # 분류별 개수 — 탭에 적는 숫자
        self._chip_w = {}                   # 분류 탭 위젯 — 한 번 만들고 색만 바꾼다
        self._photo = None                  # ⚠ 참조를 붙들어야 그림이 안 사라진다
        self._name_font = None              # 카드 이름 재기용 Font — 만들기가 비싸 재사용
        self._states_job = None             # refresh_states 모아치기 예약 (after id)

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
        # 색 안내를 **제목 줄 오른쪽**으로 옮겼다 (사용자 결정 2026-07-31:
        # "이 부분은 물감창고 이름 옆으로 옮기는 걸로 하겠습니다. 굳이 저
        # 위치에 있을 필요가 없습니다"). 제목줄은 원래 오른쪽이 비어 있던
        # 자리라 세로 길이가 늘지 않고, 분류 탭 아래 한 줄이 통째로 사라져
        # 그만큼 목록이 더 보인다.
        #
        # '안 씀'은 넣지 않는다 (사용자 지적 2026-07-31: "안씀의 경우에는
        # 알려주는 표시가 없어야 합니다") — 안 쓰는 물감은 흰 카드 그대로라
        # 색이 없다. 색 없는 상태를 위해 색 견본을 그리는 것이 모순이다.
        states = (("쓰는 중", USED_BG, USED_LINE, USED_FG),
                  ("이 팔레트", HERE_BG, HERE_LINE, HERE_FG),
                  ("고른 것", SEL_BG, SEL_LINE, SEL_FG))
        legend = tk.Frame(head, bg=CARD)
        legend.pack(side="right", padx=(6, 4))
        for text, bg, line, fg in states:
            tk.Label(legend, text=text, font=(FONT, theme.fs(FS["caption"])),
                     bg=bg, fg=fg, padx=4,
                     highlightbackground=line, highlightthickness=1
                     ).pack(side="left", padx=(0, 3))

        self.hint = tk.Label(head, text="", font=(FONT, theme.fs(FS["caption"])),
                             bg=CARD, fg=MUTED)
        self.hint.pack(side="left", padx=(6, 0))

        # 분류 탭 — 한 번에 하나만 켜진다 (물감은 다섯 중 하나에 속하므로)
        self.chip_box = tk.Frame(self, bg=SUBBG, highlightbackground=BORDER,
                                 highlightthickness=1)
        self.chip_box.pack(fill="x", padx=8, pady=(4, 0))

        # ＋ 줄 — 분류 **바로 아래** 고정 (사용자 결정 2026-07-31, 시안 안 3)
        self.new_btn = tk.Label(self, text="", cursor="hand2",
                                font=(FONT, theme.fs(FS["sub"]), "bold"),
                                bg=CARD, fg=ACCENT, pady=5,
                                highlightbackground=SEL_LINE, highlightthickness=1)
        self.new_btn.bind("<Button-1>", lambda e: self._new_here())
        self.new_btn.pack(fill="x", padx=8, pady=(5, 5))

        # 물감이 스무 개를 넘으면 스크롤이 필요하다.
        # 스크롤바는 **늘 자리를 차지한다** — 목록 길이에 따라 생겼다 없어지면
        # 그만큼 카드 폭이 출렁인다 (폭 고정 규칙, 위 머리말).
        wrap = tk.Frame(self, bg=CARD)
        self._list_wrap = wrap
        wrap.pack(fill="both", expand=True, padx=(6, 0), pady=(0, 6))
        self.canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0)
        messagebox.style_scrollbars(self)
        bar = ttk.Scrollbar(wrap, orient="vertical",
                            style="App.Vertical.TScrollbar",
                            command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg=CARD)
        self.body.grid_columnconfigure(0, weight=1)
        # 스크롤 범위는 _sync_scroll 이 **보이는 판**의 높이로 잡는다
        # (판을 겹쳐 두므로 bbox("all") 은 가장 큰 판을 가리킨다)
        self.body.bind("<Configure>", lambda e: self._sync_scroll())
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

    def _sync_scroll(self, frame=None):
        """스크롤 범위를 **지금 보이는 판**의 높이에 맞춘다."""
        if frame is None:
            got = self._cat_cache.get(self._cat_shown)
            frame = got["frame"] if got else None
        if frame is None:
            return
        try:
            h = max(frame.winfo_reqheight(), 1)
            self.canvas.configure(
                scrollregion=(0, 0, max(self.canvas.winfo_width(), 1), h))
        except Exception:
            pass

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
    def _items(self, lib=None, key=None):
        r"""[(분류, 항목)] — **key 분류**의 물감들. key 를 안 주면 지금 켠 분류.

        key 를 받는 이유 (2026-07-31): 분류 판을 미리 지어 둘 때는 화면에 켜진
        분류와 **다른** 분류를 짓는다. self.filter 를 보면 미리 지은 판이 전부
        지금 분류의 목록으로 채워진다 (실측: 다섯 판 모두 템플릿 24개가 들어갔다).

        lib 는 refresh 가 한 번 읽어 건네주는 library.load() 결과다 —
        분류마다 list_items 를 부르면 그때마다 창고 전체를 다시 읽는다(깊은
        복사 포함). 안 주면 여기서 읽는다 (단독 호출 대비).
        """
        if lib is None:
            lib = library.load()
        if key is None:
            key = self.filter
        if key == "도구":
            # 도구는 라이브러리에 없다 — 프로그램이 가진 기능 목록이다.
            # 항목 모양(id·name)만 맞춰 주면 아래 그리기가 그대로 돈다.
            return [("도구", {"id": f"builtin:{a['key']}", "name": a["name"],
                              "hint": a.get("hint", ""), "key": a["key"]})
                    for a in builtin_actions.BUILTIN_ACTIONS]
        return [(key, it) for it in lib.get(key, [])]

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
        # 창고 데이터는 **한 번만** 읽는다 (2026-07-31, 성능): 칩 개수와
        # 목록이 제각기 list_items 를 부르면(내부는 매번 전체 깊은 복사)
        # 한 번 그리는 데 여덟아홉 번을 읽었다. 여기서 읽어 둘이 나눠 쓴다.
        lib = library.load()
        self._draw_chips(lib)
        # 만들어 둔 분류 판을 통째로 버린다 — 물감이 늘거나 줄었으므로
        for got in self._cat_cache.values():
            try:
                got["frame"].destroy()
            except Exception:
                pass
        self._cat_cache = {}
        self._cat_shown = None
        self._where_memo = None
        for w in self.body.winfo_children():
            w.destroy()
        self._show_cat(lib)
        # 나머지 분류는 **한가할 때 미리 지어 둔다** — 그래야 첫 전환도
        # 기다림 없이 넘어간다. 한 번에 하나씩 지어 화면이 멎지 않게 한다.
        self._prebuild_rest(lib)

    def _prebuild_rest(self, lib=None):
        rest = [k for _l, k in CATS if k not in self._cat_cache]
        if not rest:
            return
        def step(keys, lib_):
            if not keys or not self.winfo_exists():
                return
            k = keys[0]
            if k not in self._cat_cache:
                try:
                    got = self._build_cat(k, lib_)   # 지어만 두고 안 보인다
                    self._cat_cache[k] = got
                except Exception as e:
                    applog.exc(f"창고: '{k}' 미리 짓기 실패", e)
            self.after(30, lambda: step(keys[1:], lib_))
        try:
            self.after(120, lambda: step(rest, lib or library.load()))
        except Exception:
            pass

    def _build_cat(self, key, lib=None):
        """분류 하나의 판을 만든다 — 여기서만 타일을 새로 만든다."""
        if lib is None:
            lib = library.load()
        frame = tk.Frame(self.body, bg=CARD)
        # 모든 분류 판이 **같은 칸**을 쓴다. 보이는 것 하나만 grid() 로 두고
        # 나머지는 grid_remove() — 자리 정보(row/column)는 남아 있어 되돌릴 때
        # 다시 계산하지 않는다. pack/pack_forget 보다 이쪽이 가볍다.
        frame.grid(row=0, column=0, sticky="new")
        frame.grid_remove()
        tiles = {}
        # 배치 정보는 **한 번만** 읽는다 — 분류 다섯 판을 지으면서 팔레트
        # 전체를 다섯 번 다시 읽을 이유가 없다. refresh() 가 이 기억을 비운다.
        if self._where_memo is None:
            self._where_memo = (self._placement(), self.tab_name_fn())
        where, here = self._where_memo
        items = self._items(lib, key)
        # 안 쓰는 물감이 늘 위에 온다 (사용자 결정) — 정렬은 여기서만 한다.
        # 고를 때마다 다시 정렬하면 눌렀던 것이 눈앞에서 도망간다.
        rank = {"free": 0, "here": 1, "away": 2, "plain": 3}
        items.sort(key=lambda ci: rank[self._state(ci[0], ci[1], where, here)])

        free_n = sum(1 for c, i in items
                     if self._state(c, i, where, here) == "free")
        free_hint = (f"안 쓰는 물감 {free_n}개" if free_n
                     else "모두 팔레트에 놓여 있습니다")

        # 폭은 **다시 계산하지 않는다** (사용자 결정 2026-07-31). 예전에는 가장
        # 긴 이름을 재서 판을 늘렸는데, 그 바람에 물감이 있고 없고·분류를
        # 바꿀 때마다 좌우 폭이 출렁였다 ("변형되어서는 안 됩니다"). 이름이
        # 길면 카드 안에서 말줄임으로 처리하고, 판은 STORE_W 로 고정한다.

        grid = tk.Frame(frame, bg=CARD)
        grid.pack(fill="x")
        for c in range(COLS):
            grid.columnconfigure(c, weight=1, uniform="tile")
        for n, (cat, item) in enumerate(items):
            key = (cat, item.get("id"))
            tile = self._tile(grid, cat, item,
                              self._state(cat, item, where, here))
            tile.grid(row=n // COLS, column=n % COLS, sticky="ew",
                      padx=3, pady=3)
            tiles[key] = tile
        if not items:
            # 비었다고 판이 좁아지지는 않는다(폭 고정) — 대신 여기서 무엇을
            # 하면 되는지 말해 준다. 읽기 전용 분류에는 ＋ 가 없으므로 안내도 다르다.
            msg = ("이 분류에 물감이 없습니다."
                   if key in READONLY_CATS
                   else f"아직 {_cat_label(key)}이(가) 없습니다.\n"
                        "위의 ＋ 로 하나 만들어 보세요.")
            tk.Label(frame, text=msg, justify="center",
                     font=(FONT, theme.fs(FS["sub"])), bg=CARD, fg=MUTED).pack(pady=SP["xl"])
        return {"frame": frame, "tiles": tiles, "order": items,
                "free_hint": free_hint}

    def _draw_chips(self, lib=None):
        r"""분류 탭 한 줄 — 이름 위, 개수 아래. 켜진 하나만 흰 칸으로 뜬다.

        위젯은 **한 번만 만들고 색만 바꾼다** (2026-07-31). 탭을 누를 때마다
        다섯 칸을 부수고 다시 만들면 그때마다 판 전체 배치가 다시 계산돼,
        전환이 눈에 띄게 무거워졌다(실측: update() 한 번에 100ms 넘게).
        """
        if lib is not None:                 # 창고를 방금 읽었다 — 개수를 새로 센다
            counts = {key: len(lib.get(key, [])) for _l, key in CATS}
            counts["도구"] = len(builtin_actions.BUILTIN_ACTIONS)
            self._counts = counts
        counts = self._counts
        if not self._chip_w:
            for i, (label, key) in enumerate(CATS):
                cell = tk.Frame(self.chip_box, bg=SUBBG, cursor="hand2",
                                highlightthickness=1, highlightbackground=SUBBG)
                cell.grid(row=0, column=i, sticky="nsew", padx=1, pady=1)
                nm = tk.Label(cell, text=label,
                              font=(FONT, theme.fs(FS["caption"])),
                              bg=SUBBG, fg=MUTED, pady=0)
                nm.pack(fill="x", pady=(3, 0))
                ct = tk.Label(cell, text="", font=(FONT, theme.fs(FS["caption"])),
                              bg=SUBBG, fg=BORDER, pady=0)
                ct.pack(fill="x", pady=(0, 3))
                for w in (cell, nm, ct):
                    w.bind("<Button-1>", lambda e, k=key: self._pick_chip(k))
                self._chip_w[key] = (cell, nm, ct)
            for c in range(len(CATS)):
                self.chip_box.columnconfigure(c, weight=1, uniform="cat")
        for label, key in CATS:
            cell, nm, ct = self._chip_w[key]
            on = (self.filter == key)
            bg = CARD if on else SUBBG
            try:
                cell.config(bg=bg, highlightbackground=BORDER if on else SUBBG)
                nm.config(bg=bg, fg=TEXT if on else MUTED,
                          font=(FONT, theme.fs(FS["caption"]),
                                "bold" if on else "normal"))
                ct.config(bg=bg, fg=MUTED if on else BORDER,
                          text=str(counts.get(key, 0)))
            except tk.TclError:
                pass
        self._sync_new_btn()

    def _sync_new_btn(self):
        r"""＋ 줄 — 글씨는 켜 놓은 분류를 따라가고, 읽기 전용 분류에선 안내로 바뀐다.

        **배치에서 빼지 않는다** (2026-07-31). 예전에는 '도구' 탭에서
        pack_forget 으로 감췄는데, 줄 하나가 사라졌다 나타날 때마다 판과 창이
        통째로 다시 배치돼 전환이 100ms 씩 걸렸다(실측). 자리는 그대로 두고
        생김새만 바꾼다 — 덤으로 "왜 도구에만 ＋ 가 없지"에 답까지 된다.
        """
        try:
            if self.filter in READONLY_CATS or self.on_new is None:
                self.new_btn.config(
                    text="도구는 프로그램이 가진 기능입니다",
                    fg=MUTED, bg=CARD, cursor="",
                    highlightbackground=BORDER)
            else:
                self.new_btn.config(
                    text=f"＋ 새 {_cat_label(self.filter)} 만들기",
                    fg=ACCENT, bg=CARD, cursor="hand2",
                    highlightbackground=SEL_LINE)
        except Exception as e:
            applog.exc("창고: ＋ 줄 갱신 실패", e)

    def _new_here(self):
        """＋ — 지금 켜 놓은 분류의 물감을 새로 만든다."""
        if self.on_new is None or self.filter in READONLY_CATS:
            return
        try:
            self.on_new(self.filter)
        except Exception as e:
            applog.exc("창고: 새 물감 만들기 실패", e)

    def _pick_chip(self, key):
        r"""분류 탭 누르기 — **다시 만들지 않고 갈아 끼운다** (2026-07-31).

        예전에는 탭을 누를 때마다 refresh() 로 타일을 전부 부수고 다시 만들었다.
        템플릿 24개면 RoundTile 24개(각각 Canvas 폴리곤)를 새로 그리는 일이라
        전환 한 번에 190~330ms 가 걸렸다 — 사용자 지적 "물감 창고에서 영역을
        이동할때 버벅거리는 느낌이 강합니다" 의 정체다.

        이제 분류마다 만들어 둔 판을 pack/pack_forget 으로 바꿔 끼운다. 두
        번째부터는 새로 만드는 일이 없다. 물감 목록 자체가 바뀌면(등록·삭제)
        refresh() 가 이 저장분을 통째로 버린다.
        """
        if key == self.filter and key in self._cat_cache:
            return
        self.filter = key
        # 이미 지어 둔 분류면 **창고를 다시 읽지 않는다** — library.load() 는
        # 전체 깊은 복사라, 탭을 누를 때마다 부르면 캐시로 아낀 시간을 도로
        # 쓴다. 탭에 적힌 개수는 refresh() 가 세어 둔 것을 그대로 쓴다.
        cached = key in self._cat_cache
        lib = None if cached else library.load()
        self._draw_chips(lib)
        self._show_cat(lib)
        # 스크롤을 맨 위로 되돌린다 — 안 그러면 항목이 줄어든 만큼 위쪽이
        # 텅 빈 채로 남는다 (실측 2026-07-27: #양식 3개를 골랐는데 화면
        # 아래쪽에 붙어 보였다)
        self.canvas.yview_moveto(0)

    def _show_cat(self, lib=None):
        r"""지금 분류의 판을 앞으로 — 없으면 그때 한 번 만든다.

        판을 같은 칸에 겹쳐 두고 tkraise 로 올리는 방법을 시도했다가 물렀다
        (2026-07-31): 더 빠르긴 했지만 **도구 탭에 템플릿 카드가 그대로
        보이는** 어긋남이 났다. 짧은 판을 올려도 뒤에 있는 긴 판의 아랫부분이
        비어져 나온다. 30ms 아끼자고 틀린 목록을 보여줄 수는 없다.

        속도는 다른 데서 벌었다 — 타일을 분류마다 한 번만 만들고(_cat_cache),
        탭 위젯을 다시 만들지 않고, 창고를 매번 읽지 않고, ＋ 줄을 배치에서
        빼지 않는다. 그것만으로 330ms → 70ms 가 됐다.
        """
        cur = self._cat_shown
        if cur is not None and cur in self._cat_cache:
            try:
                self._cat_cache[cur]["frame"].grid_remove()
            except Exception:
                pass
        key = self.filter
        got = self._cat_cache.get(key)
        if got is None:
            got = self._build_cat(key, lib)
            self._cat_cache[key] = got
        got["frame"].grid()
        self._cat_shown = key
        self._sync_scroll(got["frame"])
        self._tiles = got["tiles"]
        self._order = got["order"]
        self._free_hint = got["free_hint"]
        self._sync_share()
        # 색 다시 칠하기는 **배치가 실제로 바뀌었을 때만** 한다. 전환할 때마다
        # 칠하면 타일 24개를 다시 그리고 팔레트도 디스크에서 다시 읽어, 캐시로
        # 아낀 시간을 그대로 도로 쓴다 (실측 2026-07-31: 54ms → 134ms 로 악화).
        if self._states_dirty:
            self._paint_states_now()
        else:
            self._paint_selection()

    def _colors(self, state):
        if state == "here":
            return HERE_BG, HERE_LINE, HERE_FG
        if state == "away":
            return USED_BG, USED_LINE, USED_FG
        return FREE_BG, FREE_LINE, FREE_FG      # free · plain — 안 씀(흰색)

    def _sub_text(self, cat, item):
        """카드 둘째 줄 — 분류마다 **그 분류에서 뜻이 있는 것**을 보인다.

        '빈칸 N' 은 템플릿·양식에서만 뜻이 있다. 예전에는 분류를 가리지 않고
        그것만 적어, 특수기호·서식 카드는 늘 빈 줄이었다 (무인 진행 규약
        2026-07-31 에서 분류별 표기를 정함).
        """
        if cat == "도구":
            # 카드 폭(2열)에 들어가는 길이는 열한 자쯤이다 — 그보다 길면
            # 가운데 정렬 라벨이 양옆으로 삐져나가 앞뒤가 함께 잘린다(실측).
            hint = item.get("hint", "")
            return hint if len(hint) <= 11 else hint[:11] + "…"
        if cat == "문자":
            txt = (item.get("text") or "").replace("\n", " ").strip()
            return (txt if len(txt) <= 14 else txt[:14] + "…") or " "
        if cat == "서식":
            return self._func_summary(item)
        slots = int(item.get("slot_count") or 0)
        if item.get("mix"):
            return f"빈칸 {slots} · {len(item['mix'])}개"
        return f"빈칸 {slots}" if slots else " "

    @staticmethod
    def _func_summary(item):
        """서식 물감 — 켜져 있는 것 두어 개를 수치와 함께 짧게."""
        fx = item.get("funcs") or item.get("value") or {}
        if not isinstance(fx, dict):
            return " "
        parts = []
        for key, unit in (("size", "pt"), ("spacing", ""), ("line", "%")):
            v = fx.get(key)
            if v not in (None, ""):
                parts.append(f"{v}{unit}")
        if not parts:
            n = sum(1 for v in fx.values() if v not in (None, "", False))
            return f"{n}가지" if n else " "
        return " · ".join(parts[:3])

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
        sub = tk.Label(tile, text=self._sub_text(cat, item),
                       font=(FONT, theme.fs(FS["caption"])),
                       anchor="center", justify="center")
        sub.pack(fill="x", padx=6, pady=(0, 5))
        # 꾸러미(섞은 물감)는 오른쪽 끝에 세로 MIX 리본을 단다 (사용자 결정
        # 2026-07-31: "섞음 배지를 아래에 달아서 칸의 높이가 늘어나지 않게
        # 하십시오. 옆에 세로로 MIX라고 표현해주어야 합니다"). 아랫줄에 배지를
        # 더하면 카드가 낱개보다 높아져 목록이 들쭉날쭉해진다.
        if item.get("mix"):
            rib = tk.Label(tile, text="\n".join("MIX"), bg=MIX_BG, fg=MIX_FG,
                           font=(FONT, max(6, theme.fs(FS["caption"]) - 2), "bold"),
                           padx=1, pady=0)
            rib.place(relx=1.0, rely=0.5, anchor="e", relheight=0.86)
            tile._rib = rib
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

    def _mix_selected(self):
        """Ctrl+클릭으로 담은 템플릿들을 섞는다 — 입구 ①."""
        pairs = [(c, i) for c, i in self._multi_pairs() if c == "템플릿"]
        self.open_mix([i["id"] for i in (p[1] for p in pairs)])

    def open_mix(self, member_ids=None, edit_id=None):
        r"""섞기 창 — 요소를 골라 차례를 정하고 이름을 붙인다.

        입구가 둘이다 (사용자 결정 2026-07-31): 창고에서 Ctrl+클릭으로 고른 뒤
        [섞기], 또는 그냥 [섞기]를 눌러 빈 창에서 **[＋ 물감 추가]** 로 하나씩
        골라 배열. 어느 쪽으로 들어와도 창 안에서 추가·빼기·차례 바꾸기가 된다.
        """
        from hwp_palette.ui import mix_ui               # 순환 참조 회피
        mix_ui.open_mix_dialog(self.winfo_toplevel(), member_ids=member_ids,
                               edit_id=edit_id, on_saved=self._after_mix)

    def _after_mix(self):
        self.clear_multi()
        self.filter = "템플릿"
        self.refresh()

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
        # 물감 섞기 (2026-07-31) — 담아 둔 템플릿이 있으면 그것들을 안고
        # 열리고, 없으면 빈 창에서 [＋ 물감 추가]로 고른다. 입구 둘이 여기서
        # 하나로 만난다.
        picked = len([p for p in pairs if p[0] == "템플릿"])
        pop.add(f"물감 섞기 ({picked}개 담음)" if picked else "물감 섞기",
                self._mix_selected)
        pop.separator()
        pop.add("불러오기",
                lambda: library_ui.import_flow(self.winfo_toplevel(),
                                               on_saved=self.refresh))
        pop.show()

    def refresh_states(self):
        r"""배치 색 다시 칠하기 — **잦은 호출을 모아친다** (2026-07-31, 성능).

        설정을 편집할 때마다 이게 동기로 불리는데, 스핀·드래그처럼 값이
        연달아 바뀌는 동안 매번 타일 전부를 다시 칠하면 끌기가 버벅인다.
        180ms 안에 또 오면 앞 예약을 물리고 다시 재므로 손을 멈춘 뒤 한 번만
        칠한다 — 마지막 예약은 취소되지 않으니 최종 상태는 반드시 반영된다.
        """
        self._states_dirty = True        # 배치가 바뀌었다 — 다음 전환 때 칠한다
        if self._states_job is not None:
            try:
                self.after_cancel(self._states_job)
            except Exception:
                pass
            self._states_job = None
        try:
            self._states_job = self.after(180, self._paint_states_now)
        except Exception:
            self._paint_states_now()        # after 를 못 거는 상황 — 즉시 칠한다

    def _paint_states_now(self):
        r"""배치 색(안 씀/이 팔레트에 있음)만 다시 칠한다 — 위젯 재생성 없음.

        블럭 하나를 옮길 때마다 창고를 통째로 파괴·재생성하던 것이 버벅임의
        큰 몫이었다 (2026-07-28, 버벅임 1단계). 물감 **목록** 자체가 바뀔 때만
        refresh(전체)를 쓰고, 배치만 바뀌면 이걸로 충분하다.

        '안 쓰는 물감이 위' 정렬은 다음 전체 refresh 때 맞춰진다 — 누른
        타일이 눈앞에서 자리를 옮겨 다니면 안 된다는 규칙(_select 머리말)과
        같은 이유로, 여기서는 일부러 재정렬하지 않는다.
        """
        self._states_job = None
        try:
            if not self.winfo_exists():     # 예약이 창 파괴보다 늦게 왔다
                return
        except Exception:
            return
        where = self._placement()
        here = self.tab_name_fn()
        # 새로 읽은 배치를 판 짓기 쪽과도 나눠 쓴다 (아직 안 지은 분류가 있다)
        self._where_memo = (where, here)
        self._states_dirty = False
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
        # '도구'는 라이브러리 항목이 아니다 — 미리보기 판이 id 로 찾아보면
        # 없는 물감이라 빈손으로 돌아온다. 고르기 표시(파란 테두리)만 하고
        # 오른쪽 판은 건드리지 않는다.
        if self.on_select and cat != "도구":
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
        if cat == "도구":
            return {"type": "builtin", "key": item["key"],
                    "name": item["name"], "span": 2, "rows": 1}
        return None

    def edit_item(self, cat, item):
        # 꾸러미는 파일이 아니라 '요소 목록'이라 고치는 창이 다르다
        if item.get("mix"):
            self.open_mix(edit_id=item.get("id"))
            return
        from hwp_palette.ui import library_ui            # 순환 참조 회피 (library_ui → … → store_ui)
        library_ui.edit_item_dialog(self.winfo_toplevel(), cat, item,
                                    on_saved=self.refresh)


def _cat_label(key):
    for label, k in CATS:
        if k == key:
            return label
    return key
