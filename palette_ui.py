# -*- coding: utf-8 -*-
"""환경설정 창 — 커스텀 팔레트(탭 + 블럭)와 기본 서식을 관리한다.

왼쪽: 탭 목록(추가/이름변경/삭제/순서). 오른쪽: 선택 탭의 블럭 목록
(문자/템플릿/서식 조합 추가, 순서 이동, 칸수(span) 변경, 삭제) + 기본 서식 설정.

블럭 추가:
  문자   한글에서 복사한 문자/문구를 붙여넣거나 직접 입력 (1칸)
  템플릿 라이브러리에 저장된 템플릿 선택 (기본 2칸)
  서식 조합  목록에서 여러 개 체크 → 한 블럭이 병렬 실행 (굵게+자간+글씨체…)
             (라이브러리의 "서식"은 문서에서 캡처한 것, 이쪽은 직접 고르는 것)
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, colorchooser

import applog
import palette
import library
import func_catalog
import builtin_actions              # 프로그램 기능 블럭('도구') 카탈로그
import hwp_engine
import library_ui                  # commit_ime · capture_template_dialog 공용

import appinfo
import screens                     # 창 자리 규칙 (메인 창 옆)
import theme                       # 색은 theme.py 한 곳에서 (밝게/어둡게)
import ui_fx                       # 호버 보간 (애플 A안)
from roundbtn import RoundButton   # 둥근 모서리 버튼

_C = theme.colors()
BG = _C["bg"]
CARD = _C["card"]
ACCENT = _C["accent"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
ROWBG = _C["subbg"]
FONT = theme.FONT

TYPE_LABEL = {"char": "특수기호", "template": "템플릿", "function": "서식 조합",
              "form": "양식"}

# 글자 수 상한 (개선안 23 — 흩어져 있던 매직넘버에 이름을 붙임)
TILE_LABEL_MAX = 12      # 격자 미리보기 타일에 넣을 수 있는 글자 수
AUTO_NAME_MAX = 16       # 이름을 안 지었을 때 기능 이름들을 이어 붙이는 길이

# 격자 한 칸 — 정사각형이고, **칸 수에 맞춰 크기가 변한다**(_cell_px).
# 칸을 늘리면 칸이 작아져 격자 전체 폭은 그대로 유지된다 → 오른쪽에 빈 공간이 안 생김.
GRID_WIDTH_PX = 420      # 격자가 쓸 가로 폭
CELL_MAX_PX = 34
CELL_MIN_PX = 16
CELL_GAP = 2
HEADER_ROWS = 1          # 격자 맨 위 열 머리글 한 줄 (좌표 계산 시 빼야 한다)
HEADER_COLS = 1          # 격자 맨 왼쪽 줄 머리글 한 칸 (칸 번호와 짝을 맞춘다)
# 머리글 크기를 px 상수로 두지 않는다 (2026-07-25 버그 수정). 예전 HEADER_PX=12 는
# 글씨 25% 확대 이후의 실제 머리글 높이(≈18px)와 달랐고, 왼쪽 줄 번호 칸의
# **폭(≈21px)은 아예 계산에서 빠져 있어** 클릭한 칸보다 오른쪽 칸이 칠해졌다.
# 지금은 _xy_to_cell 이 첫 칸의 실제 자리(grid_bbox)를 재서 쓴다 — 글씨 크기를
# 다시 바꿔도 어긋나지 않는다.
EMPTY_BG = "#fbfbfd"     # 빈칸 배경
RANGE_BG = "#d8e9ff"     # 끌어서 지정 중인 범위


def _rgb_int(r, g, b):
    return r + (g << 8) + (b << 16)


def _dialog_btn(parent, text, command, primary=False, zone_bg=None):
    """대화상자 공용 버튼 — 저장/확인은 파랑, 취소는 흰 바탕 (애플 A안)."""
    bg = ACCENT if primary else CARD
    b = RoundButton(parent, text=text, command=command, bg=bg,
                    fg="white" if primary else TEXT, radius=7,
                    font=(FONT, theme.fs(9)), outline="" if primary else BORDER,
                    zone_bg=zone_bg or parent.cget("bg"))
    return b.fit(pad_x=14, pad_y=5)


# ───────────────────────── 기능 블럭 편집 대화상자 ─────────────────────────
class FunctionDialog(tk.Toplevel):
    """조작 목록에서 여러 개를 체크해 '서식 조합' 블럭을 만든다.

    저장 형식의 type 은 "function" 그대로다 — 표기만 바꾸고 개인 config.json 을
    건드리지 않기 위함 (개선안 10).
    """

    def __init__(self, master, block=None):
        super().__init__(master)
        self.result = None
        self.title("서식 조합 블럭")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        existing = {a["func"]: a.get("value") for a in (block or {}).get("actions", [])}
        name0 = (block or {}).get("name", "")

        tk.Label(self, text="서식 조합 블럭 만들기", font=(FONT, theme.fs(11), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(self, text="체크한 것들이 이 블럭 하나에 병렬로 담깁니다. 글자를 선택하고 누르세요.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w", padx=16, pady=(0, 8))

        namef = tk.Frame(self, bg=BG, padx=16)
        namef.pack(fill="x")
        tk.Label(namef, text="블럭 이름", font=(FONT, theme.fs(9)), bg=BG, fg=TEXT).pack(side="left")
        self.name_var = tk.StringVar(value=name0)
        tk.Entry(namef, textvariable=self.name_var, width=20, font=(FONT, theme.fs(10)),
                 relief="solid", bd=1).pack(side="left", padx=(8, 0))

        body = tk.Frame(self, bg=BG, padx=16, pady=8)
        body.pack(fill="x")
        self.rows = {}
        for f in func_catalog.FUNCTIONS:
            key = f["key"]
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=1)
            chk = tk.BooleanVar(value=key in existing)
            tk.Checkbutton(row, variable=chk, bg=BG, activebackground=BG,
                           selectcolor=CARD).pack(side="left")
            tk.Label(row, text=key, font=(FONT, theme.fs(10)), bg=BG, fg=TEXT,
                     width=8, anchor="w").pack(side="left")
            val_widget, val_var = self._value_widget(row, f, existing.get(key))
            tk.Label(row, text=f.get("hint", ""), font=(FONT, theme.fs(7)), bg=BG,
                     fg=MUTED).pack(side="left", padx=(6, 0))
            self.rows[key] = (chk, f, val_var, val_widget)

        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "저장", self._ok, primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+40}+{master.winfo_rooty()+30}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _value_widget(self, parent, f, cur):
        kind = f["kind"]
        if kind in ("toggle", "para"):
            return None, None
        if kind == "font":
            var = tk.StringVar(value=cur or func_catalog.COMMON_FONTS[0])
            w = ttk.Combobox(parent, textvariable=var, width=12,
                             values=func_catalog.COMMON_FONTS, font=(FONT, theme.fs(9)))
            w.pack(side="left")
            return w, var
        if kind == "number":
            var = tk.StringVar(value="" if cur is None else str(cur))
            w = tk.Entry(parent, textvariable=var, width=6, font=(FONT, theme.fs(9)),
                         relief="solid", bd=1)
            w.pack(side="left")
            tk.Label(parent, text=f.get("unit", ""), font=(FONT, theme.fs(8)),
                     bg=BG, fg=MUTED).pack(side="left")
            return w, var
        if kind == "color":
            var = tk.StringVar(value="" if cur is None else str(cur))
            # 저장된 색(HWP는 R + G<<8 + B<<16)을 견본에 복원
            cur_hex = "#000000"
            if cur is not None:
                try:
                    v = int(cur)
                    cur_hex = "#%02x%02x%02x" % (v & 0xFF, (v >> 8) & 0xFF,
                                                 (v >> 16) & 0xFF)
                except (TypeError, ValueError):
                    pass
            swatch = tk.Label(parent, text="  ", bg=cur_hex, relief="solid", bd=1)
            swatch.pack(side="left")

            def pick():
                rgb, _hex = colorchooser.askcolor(parent=self)
                if rgb:
                    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
                    var.set(str(_rgb_int(r, g, b)))
                    swatch.config(bg=_hex)
            # 줄 높이에 맞춘 납작한 둥근 버튼 — 공용 helper 는 여기엔 크다
            RoundButton(parent, text="색 선택", command=pick, bg=CARD, fg=TEXT,
                        radius=7, font=(FONT, theme.fs(8)), outline=BORDER,
                        zone_bg=BG).fit(pad_x=8, pad_y=2).pack(side="left",
                                                               padx=(4, 0))
            return swatch, var
        return None, None

    def _ok(self):
        # 한글 IME 로 조합 중인 마지막 글자를 확정시킨다 (library_ui.commit_ime 설명 참고)
        library_ui.commit_ime(self)
        name = self.name_var.get().strip()
        actions = []
        for key, (chk, f, var, _w) in self.rows.items():
            if not chk.get():
                continue
            kind = f["kind"]
            if kind in ("toggle", "para"):
                actions.append({"func": key})
            elif kind == "number":
                raw = (var.get() or "").strip()
                if raw == "":
                    messagebox.showwarning("값 없음", f"'{key}' 값을 입력해주세요.", parent=self)
                    return
                try:
                    val = (float(raw) if key in func_catalog.FLOAT_KEYS
                           else int(float(raw)))
                except ValueError:
                    messagebox.showwarning("값 오류", f"'{key}' 값이 숫자가 아닙니다.", parent=self)
                    return
                actions.append({"func": key, "value": val})
            elif kind == "font":
                actions.append({"func": key, "value": var.get().strip()})
            elif kind == "color":
                if not var.get():
                    messagebox.showwarning("색 없음", "글자색을 선택해주세요.", parent=self)
                    return
                actions.append({"func": key, "value": int(var.get())})
        if not actions:
            messagebox.showwarning("선택 없음", "하나 이상 체크해주세요.", parent=self)
            return
        if not name:
            name = " + ".join(a["func"] for a in actions)[:AUTO_NAME_MAX]
        self.result = {"type": "function", "name": name, "actions": actions, "span": 1}
        self.destroy()


# ───────────────────────── 환경설정 메인 창 ─────────────────────────
def _mini_btn(parent, text, cmd):
    """작은 정사각 둥근 버튼 (＋／－ 같은 기호 하나짜리).

    무엇을 늘리는지는 **놓인 자리**가 말해 준다(칸 번호 옆 = 칸, 줄 번호 밑 = 줄).
    """
    b = RoundButton(parent, text=text, command=cmd, bg=CARD, fg=TEXT,
                    radius=7, font=(FONT, theme.fs(9)), outline=BORDER,
                    zone_bg=parent.cget("bg"))
    b.config(width=theme.fs(26), height=theme.fs(20))
    return b


def _tip(widget, text):
    """작은 말풍선 — 기호만 남긴 버튼이 무엇인지 알려준다."""
    state = {"win": None, "job": None}

    def _build():
        state["job"] = None
        try:
            if not widget.winfo_exists() or state["win"]:
                return
            win = tk.Toplevel(widget)
            win.wm_overrideredirect(True)
            win.attributes("-topmost", True)
            win.wm_geometry(f"+{widget.winfo_rootx()}"
                            f"+{widget.winfo_rooty() + widget.winfo_height() + 4}")
            tk.Label(win, text=text, font=(FONT, theme.fs(8)), fg=TEXT,
                     bg="#ffffe0", bd=1, relief="solid", padx=6, pady=3).pack()
            state["win"] = win
        except Exception:
            pass

    def show(_e=None):
        if state["job"] is None and state["win"] is None:
            state["job"] = widget.after(450, _build)

    def hide(_e=None):
        if state["job"] is not None:
            try:
                widget.after_cancel(state["job"])
            except Exception:
                pass
            state["job"] = None
        if state["win"] is not None:
            state["win"].destroy()
            state["win"] = None

    widget.bind("<Enter>", show, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<ButtonPress-1>", hide, add="+")


class SettingsWindow(tk.Toplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.on_saved = on_saved
        self._base_title = appinfo.WINDOW_TITLE
        self.title(self._base_title)
        self.configure(bg=BG)
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.sel_tab = 0
        self.sel_block = None
        self._drag_from = None
        self._drop_hint = None
        self._tile_map = {}
        self._empty_map = {}
        self._used_cells = set()
        self._new_from = None      # 빈칸을 끌어 새 블럭 자리를 잡는 중
        self._new_to = None
        self._lifted = None        # 끌면서 들어 올린 타일의 유령 창
        self._lift_failed = False  # 이번 끌기에서 유령 생성 실패 — 재시도 금지
        self._grab_xy = None
        self._extra_rows = 0       # ＋줄 추가로 늘린 빈 줄 수
        self._grid_origin = None   # 격자 첫 칸의 실측 위치 (_xy_to_cell)
        self._blocks_now = []      # 지금 그려진 블럭 스냅샷 (드래그 중 참조)
        self._size_tip = None      # 크기 조절 중 커서 옆에 뜨는 안내

        tk.Label(self, text="팔레트 설정", font=(FONT, theme.fs(12), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(self,
                 text="원하는 물감을 짜서, 나만의 팔레트를 구성합니다.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(
            anchor="w", padx=16, pady=(0, 10))

        # 왼쪽 목록과 오른쪽 격자를 **하나의 흰 판** 안에 나란히 둔다 (2026-07-25).
        # 고른 팔레트(왼쪽)와 그 내용(오른쪽)이 같은 판 위에 있어야
        # "이 팔레트의 내용이 저것"임이 눈으로 이어진다 — 따로 떠 있으면
        # 둘이 무슨 사이인지 알 수 없다. macOS 설정 창의 사이드바와 같은 짜임이다.
        main = tk.Frame(self, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        main.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # 왼쪽: 팔레트 목록 ('팔레트' 라벨은 뺐다 — 위 제목이 이미 말해 준다)
        # 오른쪽 여백을 0 으로 — 고른 항목이 경계선까지 닿아야 이어져 보인다
        left = tk.Frame(main, bg=CARD, padx=0, pady=6)
        left.pack(side="left", fill="y")
        left.configure(padx=0)
        # 목록 — Listbox 가 아니라 **둥근 버튼을 세로로 쌓는다** (2026-07-25).
        #
        # Listbox 는 모서리를 못 깎고 항목마다 우클릭 메뉴를 달기도 어렵다.
        # 버튼으로 만들면 나머지 화면(둥근 블럭)과 모양이 맞고, 엑셀처럼
        # 목록 끝의 작은 ＋ 로 더할 수 있다.
        # 테두리로 감싸 **하나의 목록**으로 보이게 한다 — 버튼이 따로 떠 있으면
        # 무엇이 한 묶음인지 눈에 안 들어온다.
        self.tab_box = tk.Frame(left, bg=CARD)
        self.tab_box.pack(anchor="n", fill="x", padx=(6, 0))
        self._tab_btns = []
        # 조작법 안내는 지웠다 — 끌기·더블클릭·우클릭은 다른 곳과 같은 규칙이라
        # 한 번 익히면 되고, 늘 떠 있으면 화면만 어지럽다 (2026-07-25).

        # 목록과 격자 사이 세로 실선 — 사이드바와 본문의 경계
        tk.Frame(main, bg=BORDER, width=1).pack(side="left", fill="y")

        # 오른쪽: 팔레트 격자. 위쪽 여백을 왼쪽과 같게 줘 **시작 높이가 맞는다**
        right = tk.Frame(main, bg=CARD, padx=8, pady=6)
        right.pack(side="left", fill="both", expand=True)
        # 격자 위 머리말(블럭 수·조작 안내)은 지웠다 — 위 설명이 이미 무엇을
        # 하는 곳인지 말해 준다. 끄는 중 크기 안내는 **창 제목**으로 보여준다.

        self.block_area = tk.Frame(right, bg=CARD)
        self.block_area.pack(fill="both", expand=True)

        # 실행 취소 / 다시 실행 (UI 제안 1) — 잘못 지운 블럭을 되살린다
        self.bind_all("<Control-z>", lambda e: self._undo())
        self.bind_all("<Control-Z>", lambda e: self._undo())
        self.bind_all("<Control-y>", lambda e: self._redo())
        self.bind_all("<Control-Y>", lambda e: self._redo())
        # 아래 버튼 줄을 통째로 없앴다 (2026-07-25):
        #   닫기        — 제목표시줄의 ✕ 가 이미 한다. 창을 닫는 방법이 둘일 이유가 없다
        #   되돌리기    — Ctrl+Z 로 충분 (위 bind_all)
        #   기본 서식   — 다른 곳에서 다루기로 함
        #   변환 버튼 크기 — 이제 도구 블럭이라 끌어서 바꾼다
        # 버튼 줄이 사라지면서 아래 여백과 구분선도 함께 없앴다.
        self.protocol("WM_DELETE_WINDOW", self._close)   # ✕ 로 닫아도 저장 알림
        # Esc 로도 닫는다 (사용자 결정 2026-07-26) — 설정 창은 '잠깐 들렀다
        # 나오는 곳'이라 손이 마우스로 갈 필요가 없어야 한다.
        # bind_all 이 아니라 이 창에만 건다 — 대화상자가 떠 있으면 그쪽이 먼저 받는다.
        self.bind("<Escape>", lambda e: self._close())

        self._reload_tabs()
        self.update_idletasks()
        # 최소 크기를 600×380 으로 못박아 두었더니, 안을 정리해 내용이 작아져도
        # 창만 그대로 커서 오른쪽에 빈 여백이 남았다 (2026-07-25).
        # **내용이 최소 크기**다 — 팔레트 격자가 넓어지면 창도 따라 넓어진다.
        self.minsize(self.winfo_reqwidth(), self.winfo_reqheight())
        # 크기는 지정하지 않는다 — _fit_window 가 내용에 맞춰 잡는다(줄이 늘면 커짐)
        screens.place_beside(self, master)

    # ── 탭 목록 ──
    def _say(self, msg=None):
        """끌면서 잡은 칸 수 안내 — 지금은 **아무 데도 쓰지 않는다**.

        한때 창 제목에 붙였는데, 제목이 계속 바뀌어 오히려 어수선했다
        (사용자 지적 2026-07-25). 잡은 범위는 격자에 파랗게 칠해져 이미 보이므로
        글로 또 말할 필요가 없다. 호출부를 남겨 둔 것은 나중에 다른 자리에
        붙이고 싶을 때를 위해서다.
        """
        return

    _TAB_W = 150            # 팔레트 버튼 폭(px) — 목록이 들쭉날쭉하지 않게 고정
    _SEL_BLEED = 6          # 고른 것이 오른쪽 경계선까지 넘어가는 만큼

    def _reload_tabs(self):
        """탭 목록을 다시 그린다 — 둥근 버튼 세로 목록 + 끝에 작은 ＋."""
        for w in self.tab_box.winfo_children():
            w.destroy()
        self._tab_btns = []
        tabs = palette.load_tabs()
        if tabs:
            self.sel_tab = min(self.sel_tab, len(tabs) - 1)
        for i, t in enumerate(tabs):
            active = (i == self.sel_tab)
            bg = ACCENT if active else CARD
            # 사방 테두리 — '누를 수 있는 것'임이 드러난다. 고른 것은 진한
            # 파랑이라 테두리가 없어도 충분하고, 있으면 오히려 지저분하다.
            btn = RoundButton(self.tab_box, text=t["name"],
                              command=lambda idx=i: self._pick_tab(idx),
                              bg=bg, fg="white" if active else TEXT,
                              radius=8, font=(FONT, theme.fs(9)),
                              outline="" if active else BORDER, zone_bg=CARD)
            btn.fit(pad_x=10, pad_y=5, min_w=self._TAB_W)
            # 고른 것만 **오른쪽 경계선까지 늘려** 붙인다 (2026-07-25).
            # 왼쪽에서 고른 것이 오른쪽 격자의 내용이라는 관계를, 두 영역이
            # 맞닿는 모습으로 보여준다 — 색만 다르면 그냥 '선택됨'에 그친다.
            btn.config(width=self._TAB_W + (self._SEL_BLEED if active else 0))
            # 항목마다 **사방 테두리** — 위아래 선만 있으면 목록이라기보다
            # 글자 더미로 보인다. 테두리를 두르면 '누를 수 있는 것'이 드러난다
            # (사용자 지적 2026-07-25).
            btn.pack(anchor="w", pady=2)
            # 순서는 끌어서, 이름은 더블클릭, 삭제는 우클릭 메뉴
            btn.bind("<B1-Motion>", lambda e, idx=i: self._on_tab_drag(e, idx))
            btn.bind("<Double-Button-1>",
                     lambda e, idx=i: self._rename_tab(idx))
            btn.bind("<Button-3>", lambda e, idx=i: self._tab_menu(e, idx))
            self._tab_btns.append(btn)
        # 엑셀처럼 목록 끝의 작은 ＋ — 큰 '+ 탭' 버튼을 대신한다
        add = RoundButton(self.tab_box, text="＋", command=self._add_tab,
                          bg=CARD, fg=MUTED, radius=8,
                          font=(FONT, theme.fs(9)), outline=BORDER, zone_bg=CARD)
        add.fit(pad_x=10, pad_y=4, min_w=self._TAB_W)
        add.config(width=self._TAB_W)
        add.pack(anchor="w", pady=(2, 0))
        _tip(add, "팔레트 추가")
        self._render_blocks()

    def _pick_tab(self, idx):
        if idx == self.sel_tab:
            return
        self.sel_tab = idx
        self._reload_tabs()

    def _tab_menu(self, e, idx):
        """탭 우클릭 — 삭제 버튼을 따로 두지 않는다 (2026-07-25)."""
        self._pick_tab(idx)
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="이름 바꾸기  (더블클릭)",
                      command=lambda: self._rename_tab(idx))
        m.add_separator()
        m.add_command(label="삭제", command=lambda: self._del_tab(idx))
        m.tk_popup(e.x_root, e.y_root)

    def _add_tab(self):
        name = simpledialog.askstring("탭 추가", "새 탭 이름:", parent=self)
        if name:
            palette.add_tab(name)
            self.sel_tab = len(palette.load_tabs()) - 1
            self._reload_tabs()
            self._notify()

    def _rename_tab(self, idx=None):
        tabs = palette.load_tabs()
        if not tabs:
            return
        if idx is not None:
            self.sel_tab = min(idx, len(tabs) - 1)
        if tabs[self.sel_tab].get("name") == palette.MAIN_TAB:
            messagebox.showinfo("이름 고정",
                "'메인' 탭 이름은 메인 창이 찾는 열쇠라 바꿀 수 없습니다.",
                parent=self)
            return
        cur = tabs[self.sel_tab]["name"]
        name = simpledialog.askstring("이름 변경", "새 이름:", initialvalue=cur, parent=self)
        if name:
            try:
                palette.rename_tab(self.sel_tab, name)
            except ValueError as e:
                messagebox.showwarning("이름 충돌", str(e), parent=self)
                return
            self._reload_tabs()
            self._notify()

    def _del_tab(self, idx=None):
        tabs = palette.load_tabs()
        if not tabs:
            return
        if idx is not None:
            self.sel_tab = min(idx, len(tabs) - 1)
        if tabs[self.sel_tab].get("name") == palette.MAIN_TAB:
            messagebox.showinfo(
                "삭제할 수 없음",
                "'메인' 탭은 메인 창의 변환 버튼 옆 버튼칸입니다.\n"
                "탭 자체는 지울 수 없고, 안의 블럭만 비울 수 있습니다.", parent=self)
            return
        if messagebox.askyesno("삭제", f"'{tabs[self.sel_tab]['name']}' 탭을 삭제할까요?",
                               parent=self):
            palette.delete_tab(self.sel_tab)
            self.sel_tab = max(0, self.sel_tab - 1)
            self._reload_tabs()
            self._notify()

    def _on_tab_drag(self, e, idx):
        """탭 버튼을 끌어 순서를 바꾼다 — 커서가 넘어간 칸만큼 한 칸씩."""
        tabs = palette.load_tabs()
        if len(tabs) < 2 or not self._tab_btns:
            return
        if idx != self.sel_tab:
            self._pick_tab(idx)
            return
        try:    # 커서의 화면 y 로 몇 번째 탭 위인지 계산
            top = self._tab_btns[0].winfo_rooty()
            step_px = max(1, self._tab_btns[0].winfo_height() + 2)
            target = int((e.y_root - top) // step_px)
        except Exception:
            return
        if not (0 <= target < len(tabs)) or target == self.sel_tab:
            return
        step = 1 if target > self.sel_tab else -1
        self._move_tab(step)        # 한 칸씩 — 여러 칸을 건너뛰면 어지럽다

    def _move_tab(self, delta):
        palette.move_tab(self.sel_tab, delta)
        self.sel_tab = max(0, min(self.sel_tab + delta, len(palette.load_tabs()) - 1))
        self._reload_tabs()
        self._notify()

    # ── 블럭 그리드 (문자표처럼 격자 + 드래그로 자유 이동) ──
    def _render_blocks(self):
        r"""블럭 격자를 다시 그린다.

        **그리는 동안 화면 갱신을 멈춘다** (2026-07-25). 예전에는 지우기와
        다시 만들기 사이의 중간 상태가 그대로 화면에 나가, 칸·줄을 늘릴 때마다
        격자가 한 번 번쩍였다. 다 만든 뒤 한꺼번에 보여주면 그 깜빡임이 없다.
        """
        try:
            self.block_area.update_idletasks()      # 밀린 그리기를 먼저 비운다
        except Exception:
            pass
        for w in self.block_area.winfo_children():
            w.destroy()
        self._tile_map = {}
        self._tiles = {}
        tabs = palette.load_tabs()
        if not tabs:
            return
        tab = tabs[self.sel_tab]
        blocks = tab.get("blocks", [])
        cols = tab.get("cols", palette.DEFAULT_COLS)

        # 옛 상단 바(칸수 스핀박스·편집·크기·삭제)는 없앴다 (2026-07-19):
        #  - 칸수 스핀박스는 to=10 이라 ＋칸 버튼과 싸우며 칸 수를 되돌렸다(버그)
        #  - 편집은 더블클릭, 나머지는 타일 우클릭 메뉴로 옮김 — 화면이 한 줄 준다

        if not blocks:
            # 빈 격자라도 그린다 — 거기를 끌어 첫 블럭을 만들어야 하므로
            tk.Label(self.block_area,
                     text="빈칸을 누르거나 끌어서 첫 블럭을 만들어보세요.",
                     font=(FONT, theme.fs(9)), bg=BG, fg=MUTED,
                     justify="left").pack(anchor="w", pady=(0, 4))

        # 격자는 스크롤 없이 그대로 편다 — 줄이 늘면 창 자체가 커진다(_fit_window).
        #
        # ＋／－ 는 **평소엔 숨어 있다가 격자에 마우스를 올리면 나타난다**
        # (2026-07-25). 늘 떠 있으면 화면에 보이는 것이 늘어 어지럽다. place 로
        # 격자 위에 얹으므로, 나타나고 사라져도 배치가 흔들리지 않는다.
        outer = tk.Frame(self.block_area, bg=BG)
        outer.pack(anchor="w", pady=(0, 0))
        grid = tk.Frame(outer, bg=CARD, padx=2, pady=2)
        grid.pack(anchor="w")

        # 칸 크기는 칸 수에 맞춰 정한다 (메인 창과 같은 규칙 — 미리보기가 실물과 맞게)
        cell_px = self._cell_px(cols)
        grid.columnconfigure(0, minsize=theme.fs(16), weight=0)   # 줄 번호 칸
        for c in range(cols):
            grid.columnconfigure(c + HEADER_COLS, minsize=cell_px + CELL_GAP,
                                 weight=0, uniform="cell")

        # 열 머리글 (UI 제안 12) — 15칸이 되니 "몇 번째 칸"을 셀 수 있어야 한다
        for cc in range(cols):
            tk.Label(grid, text=str(cc + 1), font=(FONT, theme.fs(7)), bg=CARD,
                     fg=MUTED).grid(row=0, column=cc + HEADER_COLS, pady=(0, 1))

        self._used_cells = palette.occupied_cells(blocks)

        # ① 블럭 타일 — 저장된 좌표(row, col)에 span×rows 크기로
        for i, blk in enumerate(blocks):
            span = max(1, min(int(blk.get("span", 1)), cols))
            rows = max(1, int(blk.get("rows", 1)))
            cell = tk.Frame(grid, bg=CARD,
                            width=cell_px * span + CELL_GAP * (span - 1),
                            height=cell_px * rows + CELL_GAP * (rows - 1))
            cell.pack_propagate(False)
            cell.grid(row=int(blk.get("row", 0)) + HEADER_ROWS,
                      column=int(blk.get("col", 0)) + HEADER_COLS,
                      columnspan=span, rowspan=rows,
                      padx=CELL_GAP // 2, pady=CELL_GAP // 2)
            self._make_tile(cell, i, blk, span).pack(fill="both", expand=True)

        # ② 빈칸 — 여기를 끌면 가로·세로 크기를 함께 정할 수 있다
        self._empty_map = {}
        total_rows = max(palette.grid_extent(blocks), 0) + self._extra_rows
        total_rows = max(total_rows, 1)     # 블럭이 없어도 놓을 자리는 있어야 한다
        for rr in range(total_rows):
            for cc in range(cols):
                if (rr, cc) not in self._used_cells:
                    self._make_empty_cell(grid, rr, cc, cell_px)

        # 줄 머리글 — 칸 번호(위)와 짝. 줄이 몇 개인지 눈에 보여야 한다 (2026-07-25)
        for rr in range(total_rows):
            tk.Label(grid, text=str(rr + 1), font=(FONT, theme.fs(7)), bg=CARD,
                     fg=MUTED).grid(row=rr + HEADER_ROWS, column=0,
                                    padx=(0, 2))

        # ③ 끝쪽 ＋／－ — **번호가 끝나는 자리**에 작게 늘 둔다 (2026-07-25).
        #
        # 숨겼다 보여주는 방식은 '거기 버튼이 있다'는 걸 아무도 모른다는 게
        # 문제였다. 번호 줄(위·왼쪽)의 연장선에 놓으면 무엇을 늘리는지가
        # 자리로 드러나므로, 작고 흐리게 둬도 알아볼 수 있다.
        # 칸 조절은 격자 오른쪽에 **＋ 위, － 아래**로 세로로 쌓는다.
        # 가로로 늘어놓으면 칸 하나만큼 폭을 더 먹는다 (2026-07-25).
        colbar = tk.Frame(grid, bg=CARD)        # 칸 번호가 끝나는 오른쪽
        colbar.grid(row=0, column=cols + HEADER_COLS,
                    rowspan=2, sticky="n", padx=(4, 0))
        for txt, cmd, tip in (("＋", self._add_col, "칸(가로) 늘리기"),
                              ("－", self._remove_col, "칸(가로) 줄이기")):
            b = _mini_btn(colbar, txt, cmd)
            b.pack()
            _tip(b, tip)

        rowbar = tk.Frame(grid, bg=CARD)        # 줄 번호가 끝나는 아래쪽
        rowbar.grid(row=total_rows + HEADER_ROWS, column=0, pady=(3, 0))
        for txt, cmd, tip in (("＋", self._add_row, "줄(세로) 늘리기"),
                              ("－", self._remove_row, "줄(세로) 줄이기")):
            b = _mini_btn(rowbar, txt, cmd)
            b.pack(side="left")
            _tip(b, tip)

        # 드래그 좌표 계산용 (winfo_containing 없이 수학으로 — 부드러운 이유)
        self._grid_widget = grid
        self._grid_cell_px = cell_px
        self._grid_total_rows = total_rows
        self._grid_cols = cols
        self._grid_origin = None        # 첫 칸 자리 — _xy_to_cell 이 실측해 채움
        self._blocks_now = blocks       # 드래그 중 디스크 재읽기 방지 스냅샷
        grid.bind("<B1-Motion>", self._empty_motion)

        self.after_idle(self._fit_window)

    # ── 줄/칸 늘리기·줄이기 + 창 크기 맞추기 ──
    def _cell_px(self, cols):
        """칸 수에 맞춘 한 칸 크기 (정사각형). 칸이 많아지면 작아진다."""
        avail = GRID_WIDTH_PX
        size = (avail - CELL_GAP * cols) // max(1, cols)
        return max(CELL_MIN_PX, min(CELL_MAX_PX, size))

    def _add_row(self):
        self._extra_rows += 1
        self._render_blocks()

    def _remove_row(self):
        if self._extra_rows > 0:
            self._extra_rows -= 1
            self._render_blocks()

    def _add_col(self):
        self._set_cols(self._cur_cols() + 1)

    def _remove_col(self):
        """칸을 줄인다 — 오른쪽 끝에 블럭이 있으면 막는다(잘려 사라지지 않게).

        최소 8칸(palette.MIN_COLS) 밑으로는 못 줄인다 (사용자 결정 2026-07-25) —
        메인 창이 어차피 8칸 폭을 확보해서, 그 밑으로 줄여도 좁아지지 않는다.
        """
        cols = self._cur_cols()
        if cols <= palette.MIN_COLS:
            messagebox.showinfo(
                "칸을 줄일 수 없음",
                f"팔레트는 최소 {palette.MIN_COLS}칸입니다.\n"
                "메인 창이 이 폭을 항상 확보하므로, 더 줄여도 창은 좁아지지 "
                "않습니다.", parent=self)
            return
        blocks = palette.load_tabs()[self.sel_tab]["blocks"]
        edge = [b for b in blocks
                if int(b.get("col", 0)) + int(b.get("span", 1)) > cols - 1]
        if edge:
            messagebox.showinfo(
                "칸을 줄일 수 없음",
                "마지막 칸에 블럭이 있어 줄이면 잘립니다.\n"
                "그 블럭을 먼저 왼쪽으로 옮겨주세요.", parent=self)
            return
        self._set_cols(cols - 1)

    def _cur_cols(self):
        return palette.load_tabs()[self.sel_tab].get("cols", palette.DEFAULT_COLS)

    def _set_cols(self, cols):
        palette.set_tab_cols(self.sel_tab, max(palette.MIN_COLS, min(30, cols)))
        self._render_blocks()
        self._notify()

    def _fit_window(self):
        """내용에 맞춰 창 높이를 다시 잡는다 — 줄이 늘면 창도 커진다.

        주의 (실측 2026-07-19): 격자에 줄을 더한 직후의 winfo_reqheight() 는 한
        박자 늦은 값을 준다(격자는 이미 커졌는데 창의 요청 크기는 그대로). 그래서
        레이아웃이 정리된 뒤에 부르도록 호출부에서 after_idle 로 미루고, 여기서도
        한 번 더 update_idletasks() 한다.

        폭은 사용자가 늘려 둘 수 있으므로 줄이지 않는다.
        """
        self.update_idletasks()
        # 최소 크기도 내용에 맞춰 갱신한다 — 안 하면 한 번 커진 뒤로는 minsize 가
        # 창을 붙들어, 칸을 줄여도 오른쪽에 빈 여백이 남는다 (2026-07-25).
        try:
            self.minsize(self.winfo_reqwidth(), self.winfo_reqheight())
        except Exception:
            pass
        # geometry("") = "내용에 맞춰라". 크기를 직접 계산해 넣으면 그 순간의
        # winfo_reqheight() 가 한 박자 늦어서 첫 '줄 추가'가 반영되지 않았다(실측).
        self.geometry("")
        self.update_idletasks()

    # ── 빈칸: 끌어서 새 블럭 자리 지정 ──
    def _make_empty_cell(self, grid, r, c, cell_px):
        f = tk.Frame(grid, bg=EMPTY_BG, width=cell_px, height=cell_px,
                     highlightbackground=BORDER, highlightthickness=1)
        f.pack_propagate(False)
        f.grid(row=r + HEADER_ROWS, column=c + HEADER_COLS,
               padx=CELL_GAP // 2, pady=CELL_GAP // 2)
        self._empty_map[str(f)] = (r, c)
        f.bind("<ButtonPress-1>", lambda e, rc=(r, c): self._empty_press(rc))
        f.bind("<B1-Motion>", self._empty_motion)
        f.bind("<ButtonRelease-1>", self._empty_release)
        f.config(cursor="plus")
        return f

    def _empty_press(self, rc):
        if self._drag_from is not None:
            return                      # 타일을 옮기는 중 — 새 블럭 만들기가 아니다
        self._new_from = self._new_to = rc
        self._paint_range()

    def _xy_to_cell(self, x_root, y_root):
        """화면 좌표 → 격자 칸 (row, col). 격자 밖이면 None.

        winfo_containing 은 호출마다 창 시스템을 왕복해서, 드래그 중 매 픽셀마다
        부르면 눈에 띄게 버벅였다(실측). 격자 원점과 칸 크기로 나눗셈 한 번이면
        되므로 이렇게 계산한다 — 이것이 드래그가 부드러워진 이유다.
        """
        g = getattr(self, "_grid_widget", None)
        if g is None or not g.winfo_exists():
            return None
        origin = self._grid_origin
        if origin is None:
            # 첫 데이터 칸(머리글 다음)의 실제 자리를 Tk 에게 직접 묻는다.
            # 상수로 빼서 계산하면 머리글 폭이 글꼴 크기에 따라 변할 때마다
            # 어긋난다 — 실측이면 영원히 맞는다. 렌더마다 한 번만 재고 캐시.
            g.update_idletasks()
            bx, by, _bw, _bh = g.grid_bbox(column=HEADER_COLS, row=HEADER_ROWS)
            origin = self._grid_origin = (bx, by)
        px = self._grid_cell_px + CELL_GAP
        c = (x_root - g.winfo_rootx() - origin[0]) // px
        r = (y_root - g.winfo_rooty() - origin[1]) // px
        if 0 <= c < self._grid_cols and 0 <= r < self._grid_total_rows:
            return (int(r), int(c))
        return None

    def _empty_motion(self, e):
        if self._new_from is None:
            return
        rc = self._xy_to_cell(e.x_root, e.y_root)
        if rc and rc != self._new_to:   # 칸이 바뀔 때만 다시 칠한다
            self._new_to = rc
            self._paint_range()

    def _drag_area(self):
        """지금 끌고 있는 사각형 (row, col, span, rows). 빈칸만 포함하도록 줄인다."""
        r0, c0 = self._new_from
        r1, c1 = self._new_to
        r0, r1 = sorted((r0, r1))
        c0, c1 = sorted((c0, c1))
        # 블럭이 끼어 있으면 거기서 끊는다 (가로 먼저, 그 다음 세로)
        span = 1
        while c0 + span <= c1 and all(
                (rr, c0 + span) not in self._used_cells for rr in range(r0, r1 + 1)):
            span += 1
        rows = 1
        while r0 + rows <= r1 and all(
                (r0 + rows, cc) not in self._used_cells
                for cc in range(c0, c0 + span)):
            rows += 1
        return r0, c0, span, rows

    def _empty_release(self, e):
        if self._drag_from is not None:
            return self._on_release(e)  # 타일 옮기기는 기존 처리로
        if self._new_from is None:
            return
        row, col, span, rows = self._drag_area()
        self._new_from = self._new_to = None
        self._render_blocks()           # 범위 표시 지우기
        self._pick_tool(row, col, span, rows)

    def _paint_range(self):
        """지금 끌고 있는 사각형을 칠하고, 크기·자리를 글로도 알려준다."""
        r0, c0, span, rows = self._drag_area()
        # 지금 몇 칸을 잡았는지 **창 제목**으로 (UI 제안 12).
        # 화면에 고정 라벨을 두면 평소에도 자리를 먹는다 — 끄는 동안만 보인다.
        self._say(f"{span}×{rows}칸 · {r0 + 1}번째 줄, {c0 + 1}번째 칸부터")
        for key, (rr, cc) in self._empty_map.items():
            try:
                w = self.nametowidget(key)
            except Exception:
                continue
            inside = (r0 <= rr < r0 + rows and c0 <= cc < c0 + span)
            w.config(bg=RANGE_BG if inside else EMPTY_BG)

    def _pick_tool(self, row, col, span, rows):
        """자리와 크기를 정한 뒤 '무엇을 넣을지' 고른다."""
        dlg = _ToolPickDialog(self, span, rows)
        self.wait_window(dlg)
        self._pending_area = (row, col, span, rows)
        self._pending_color = getattr(dlg, "color", None)
        if dlg.result == "char":
            self._add_char(span, rows)
        elif dlg.result == "template":
            self._add_template(span, rows)
        elif dlg.result == "function":
            self._add_function(span, rows)
        elif dlg.result == "form":
            self._add_form(span, rows)
        elif dlg.result == "builtin":
            self._add_builtin(span, rows)
        self._pending_area = None
        self._pending_color = None

    def _place(self, block):
        """새 블럭을 지금 지정한 자리에 넣는다 (없으면 첫 빈자리)."""
        area = getattr(self, "_pending_area", None)
        color = getattr(self, "_pending_color", None)
        if color:
            block["color"] = color
        if area:
            row, col, span, rows = area
            block["span"], block["rows"] = span, rows
            palette.add_block(self.sel_tab, block, row=row, col=col)
        else:
            palette.add_block(self.sel_tab, block)
        self._render_blocks()
        self._notify()

    def _make_tile(self, parent, i, blk, span=1):
        selected = (self.sel_block == i)
        # 사용자 지정 색이 우선, 없으면 종류별 기본색 (메인 창과 같은 규칙)
        bg = theme.block_color(blk)     # 메인 창과 같은 규칙 (변환은 강조색)
        tile = tk.Frame(parent, bg=bg,
                        highlightbackground=ACCENT if selected else BORDER,
                        highlightthickness=2 if selected else 1)
        tile.pack_propagate(False)
        # 글자색은 배경 밝기에 맞춰 정한다 — 어두운 색을 골라도 읽히게 (제안 18)
        lab = tk.Label(tile, text=self._tile_text(blk, span), bg=bg,
                       fg=theme.text_on(bg),
                       font=(FONT, theme.fs(10 if blk["type"] == "char" else 8)))
        lab.pack(expand=True)
        self._tiles[i] = tile
        for w in (tile, lab):
            self._tile_map[str(w)] = i
            w.bind("<ButtonPress-1>", lambda e, idx=i: self._on_press(idx, e))
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", self._on_release)
            w.bind("<Double-Button-1>", lambda e, idx=i: self._edit_block(idx))
            w.bind("<Button-3>", lambda e, idx=i: self._tile_menu(e, idx))
            w.config(cursor="hand2")
        self._add_grip(tile, i)
        return tile

    # ── 크기 조절 손잡이 (UI 제안 10) ─────────────────────
    # 여태 크기를 바꾸려면 우클릭 → '가로 +1' 을 여러 번 눌러야 했다. 3×2 로
    # 만들려면 다섯 번이다. 오른쪽 아래 모서리를 끌면 한 번에 끝난다.
    # (우클릭 메뉴는 남겨둔다 — 손잡이가 작아 잡기 어려울 때가 있다)
    def _add_grip(self, tile, i):
        # 크기는 글자 배율을 따라간다 — 7px 고정은 고해상도에서 못 잡았다
        s = max(7, theme.fs(6))
        grip = tk.Frame(tile, bg=ACCENT, width=s, height=s,
                        cursor="bottom_right_corner")
        grip.place(relx=1.0, rely=1.0, anchor="se")
        # tile 에 건 바인딩은 자식인 grip 에는 오지 않는다(Tk 는 위젯별 바인딩을
        # 부모로 전파하지 않는다). 그래서 끌기가 '옮기기'와 섞이지 않는다.
        grip.bind("<ButtonPress-1>", lambda e, idx=i: self._grip_press(idx))
        grip.bind("<B1-Motion>", self._grip_motion)
        grip.bind("<ButtonRelease-1>", self._grip_release)
        _tip(grip, "끌어서 크기 조절")

    def _grip_press(self, idx):
        self._set_selection(idx)
        b = self._blocks_now[idx]
        self._grip = {"idx": idx,
                      "row": int(b.get("row", 0)), "col": int(b.get("col", 0)),
                      "span": int(b.get("span", 1)), "rows": int(b.get("rows", 1)),
                      "span0": int(b.get("span", 1)), "rows0": int(b.get("rows", 1))}

    def _grip_paint(self, g):
        """조절 중인 새 크기를 빈칸 위에 미리 칠한다 — 놓기 전에 결과가 보인다."""
        r0, c0 = g["row"], g["col"]
        for key, (rr, cc) in self._empty_map.items():
            try:
                w = self.nametowidget(key)
            except Exception:
                continue
            inside = (r0 <= rr < r0 + g["rows"] and c0 <= cc < c0 + g["span"])
            w.config(bg=RANGE_BG if inside else EMPTY_BG)

    def _show_size_tip(self, x_root, y_root, text):
        """커서 오른쪽 아래에 붙어 다니는 크기 안내 (툴팁과 같은 기법)."""
        tip = self._size_tip
        if tip is None:
            tip = self._size_tip = tk.Toplevel(self)
            tip.wm_overrideredirect(True)
            tip.attributes("-topmost", True)
            tk.Label(tip, text=text, font=(FONT, theme.fs(8)), bg="#333333",
                     fg="#ffffff", padx=6, pady=2).pack()
        else:
            tip.winfo_children()[0].config(text=text)
        tip.geometry(f"+{x_root + 14}+{y_root + 14}")

    def _hide_size_tip(self):
        if self._size_tip is not None:
            try:
                self._size_tip.destroy()
            except Exception:
                pass
            self._size_tip = None

    def _grip_motion(self, e):
        g = getattr(self, "_grip", None)
        if not g:
            return
        rc = self._xy_to_cell(e.x_root, e.y_root)
        if not rc:
            return
        r, c = rc
        span = max(1, c - g["col"] + 1)
        rows = max(1, r - g["row"] + 1)
        self._show_size_tip(e.x_root, e.y_root, f"{span}×{rows}칸")
        if (span, rows) == (g["span"], g["rows"]):
            return
        if not palette.area_is_free(self._blocks_now, g["row"], g["col"],
                                    span, rows, skip_index=g["idx"]):
            return                      # 다른 블럭 위로는 넘어가지 않는다
        g["span"], g["rows"] = span, rows
        self._grip_paint(g)             # 커지는 만큼 빈칸이 미리 칠해진다

    def _grip_release(self, e):
        g = getattr(self, "_grip", None)
        self._grip = None
        self._hide_size_tip()
        if not g:
            return
        if (g["span"], g["rows"]) == (g["span0"], g["rows0"]):
            self._grip_paint({**g, "span": 0, "rows": 0})   # 칠만 지운다
            return                      # 크기 그대로 — 다시 그릴 필요 없다
        palette.set_block_area(self.sel_tab, g["idx"], g["row"], g["col"],
                               g["span"], g["rows"])
        self._render_blocks()
        self._notify()

    def _tile_menu(self, e, idx):
        """타일 우클릭 메뉴 — 옛 상단 바(편집·크기·삭제)를 여기로 옮겼다."""
        self._set_selection(idx)
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="편집  (더블클릭)", command=lambda: self._edit_block(idx))
        m.add_command(label="이름 바꾸기 (줄바꿈 가능)",
                      command=lambda: self._rename_block(idx))
        m.add_command(label="복제", command=lambda: self._duplicate(idx))
        m.add_command(label="색 바꾸기", command=lambda: self._recolor(idx))
        m.add_command(label="기본색으로", command=lambda: self._recolor(idx, reset=True))
        m.add_separator()
        m.add_command(label="가로 +1", command=lambda: self._resize_selected(1, 0))
        m.add_command(label="가로 -1", command=lambda: self._resize_selected(-1, 0))
        m.add_command(label="세로 +1", command=lambda: self._resize_selected(0, 1))
        m.add_command(label="세로 -1", command=lambda: self._resize_selected(0, -1))
        m.add_separator()
        m.add_command(label="삭제", command=self._del_selected)
        m.tk_popup(e.x_root, e.y_root)

    def _rename_block(self, idx):
        r"""블럭에 보일 이름을 정한다. **줄바꿈(Enter)이 그대로 들어간다.**

        왜 필요한가 (2026-07-25): 긴 이름을 넣으려면 칸을 옆으로 늘리는 수밖에
        없었고, 칸이 넓어지면 창이 그만큼 좌우로 길어졌다. '양식 채우기' 를
        '양식 / 채우기' 두 줄로 쓰면 **좁은 칸(2×2)에 그대로** 들어간다.

        비우면 원래 이름으로 돌아간다(도구는 카탈로그 이름, 템플릿은 라이브러리 이름).
        """
        blocks = palette.load_tabs()[self.sel_tab]["blocks"]
        if not (0 <= idx < len(blocks)):
            return
        blk = dict(blocks[idx])
        dlg = _CaptionDialog(self, self._block_label(blk),
                             blk.get("caption", ""))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        if dlg.result.strip():
            blk["caption"] = dlg.result
        else:
            blk.pop("caption", None)        # 비웠다 = 원래 이름으로
        palette.update_block(self.sel_tab, idx, blk)
        self._render_blocks()
        self._notify()

    def _duplicate(self, idx):
        """블럭 복제 (UI 제안 13) — 비슷한 서식 조합을 처음부터 다시 안 만들게."""
        blocks = palette.load_tabs()[self.sel_tab]["blocks"]
        copy_blk = dict(blocks[idx])
        for k in ("row", "col"):
            copy_blk.pop(k, None)       # 자리는 첫 빈자리로 다시 잡는다
        palette.add_block(self.sel_tab, copy_blk)
        self._render_blocks()
        self._notify()

    def _recolor(self, idx, reset=False):
        """블럭 배경색을 바꾸거나(색 선택) 종류 기본색으로 되돌린다."""
        blocks = palette.load_tabs()[self.sel_tab]["blocks"]
        blk = dict(blocks[idx])
        if reset:
            blk.pop("color", None)
        else:
            _, hexv = colorchooser.askcolor(
                parent=self, initialcolor=blk.get("color") or "#ffffff")
            if not hexv:
                return
            blk["color"] = hexv
        palette.update_block(self.sel_tab, idx, blk)
        self._render_blocks()
        self._notify()

    def _tile_text(self, blk, span=1):
        r"""칸 수에 맞춰 자른다 — 메인 창(main._fit_label)과 **같은 규칙**.

        자동 아이콘(▦ ƒ 📄)은 넣지 않는다 — 사용자가 정한 이름 그대로 (2026-07-19).
        줄바꿈은 살려서 줄마다 따로 자른다 — '양식\n채우기' 처럼 좁은 칸에
        두 줄로 넣을 수 있게 (2026-07-25).
        """
        limit = max(2, span * 2)
        lines = (self._block_label(blk) or "").split("\n")
        return "\n".join(ln if len(ln) <= limit else ln[:limit] + "…"
                         for ln in lines)

    def _block_label(self, blk):
        # 사용자가 지은 표시 이름이 있으면 그것이 우선 (줄바꿈 포함 가능)
        if blk.get("caption"):
            return blk["caption"]
        if blk["type"] == "builtin":
            # 이름은 카탈로그에서 읽는다 — 표기를 고쳐도 기존 블럭이 따라온다
            return builtin_actions.name_of(blk.get("key"))
        if blk["type"] == "char":
            v = blk.get("value", "")
            return v if len(v) <= 20 else v[:20] + "…"
        if blk["type"] in ("template", "form"):
            # 라이브러리의 '현재' 이름을 보여준다 (이름을 바꿔도 따라가게)
            cat = "양식" if blk["type"] == "form" else "템플릿"
            key = "form" if blk["type"] == "form" else "template"
            it = library.get_item(cat, item_id=blk.get("ref"),
                                  name=blk.get(key))
            if it:
                return it["name"]
            return f"{blk.get(key, '?')} (삭제됨)"
        return blk.get("name", " + ".join(a["func"] for a in blk.get("actions", [])))

    # ── 드래그 이동 + 선택 ──
    def _set_selection(self, idx):
        """선택 표시를 '재렌더 없이' 그 자리에서 갱신.

        release마다 _render_blocks()로 다시 그리면 타일 위젯이 파괴돼,
        뒤이어 와야 할 <Double-Button-1>(수정)이 도달하지 못한다(실측 버그).
        그래서 선택은 위젯 config만 바꾼다.
        """
        self.sel_block = idx
        for i, tile in getattr(self, "_tiles", {}).items():
            sel = (i == idx)
            try:
                tile.config(highlightbackground=ACCENT if sel else BORDER,
                            highlightthickness=2 if sel else 1)
            except Exception:
                pass

    def _on_press(self, idx, event=None):
        self._drag_from = idx
        self._set_selection(idx)
        # 끌기 준비 — 실제로 '들어 올리는' 것은 손이 조금 움직인 뒤다.
        # 바로 들면 그냥 클릭한 것도 타일이 튀어 보인다.
        self._lifted = None
        self._lift_failed = False
        self._grab_xy = (event.x_root, event.y_root) if event else None

    def _lift_tile(self, idx, x_root, y_root):
        r"""끌고 있는 타일의 **유령**을 만들어 커서를 따라오게 한다.

        예전에는 타일 위젯 자체를 place 로 떼어 옮기려 했는데, Tk 의 부모-자식
        규칙 위반(place 의 in_ 은 부모의 조상이면 안 된다)으로 **항상 실패**했다
        (2026-07-25 실측: app.log 에 같은 TclError 890건). 실패 결과 타일이
        끄는 내내 사라지고, 모션마다 재시도→오류 로그 기록이 반복돼 그것이
        버벅임의 최대 원인이었다.
        지금은 툴팁(_tip)과 같은 기법 — 테두리 없는 작은 창을 커서에 붙인다.
        원본 타일은 제자리에 흐리게 남아 '어디서 들었는지'를 보여준다.
        """
        tile = getattr(self, "_tiles", {}).get(idx)
        if tile is None:
            return False
        try:
            w, h = tile.winfo_width(), tile.winfo_height()
            off = (x_root - tile.winfo_rootx(), y_root - tile.winfo_rooty())
            blk = self._blocks_now[idx] if idx < len(self._blocks_now) else {}
            bg = theme.block_color(blk)
            ghost = tk.Toplevel(self)
            ghost.wm_overrideredirect(True)
            ghost.attributes("-topmost", True)
            try:
                ghost.attributes("-alpha", 0.85)    # 반투명 — '들려 있는' 느낌
            except Exception:
                pass
            tk.Label(ghost, text=self._tile_text(blk, int(blk.get("span", 1))),
                     bg=bg, fg=theme.text_on(bg),
                     font=(FONT, theme.fs(10 if blk.get("type") == "char"
                                          else 8))).pack(fill="both", expand=True)
            ghost.geometry(f"{w}x{h}+{x_root - off[0]}+{y_root - off[1]}")
            # 원본은 빈칸처럼 흐리게 — 들어 올린 자리가 비어 보인다
            dimmed = []
            for wdg in (tile, *tile.winfo_children()):
                try:
                    dimmed.append((wdg, wdg.cget("bg")))
                    wdg.config(bg=EMPTY_BG)
                    if isinstance(wdg, tk.Label):
                        wdg.config(fg=MUTED)
                except Exception:
                    pass
            self._lifted = {"ghost": ghost, "off": off, "dimmed": dimmed}
            return True
        except Exception as e:
            applog.exc("타일 유령 만들기 실패 — 강조 표시로만 끕니다", e)
            self._lifted = None
            return False

    def _drop_tile(self):
        """유령을 없애고 원본 타일 색을 되살린다."""
        lifted = self._lifted
        self._lifted = None
        if not lifted:
            return
        try:
            lifted["ghost"].destroy()
        except Exception:
            pass
        for wdg, bg in lifted.get("dimmed", []):
            try:
                wdg.config(bg=bg)
            except Exception:
                pass                # 곧 _render_blocks 가 다시 그린다

    def _cell_owner(self, rc):
        """그 칸을 차지한 블럭 index. 빈칸이면 None.

        드래그 중 매 이벤트마다 불리므로 디스크(config.json)를 다시 읽지 않고
        _render_blocks 가 떠 둔 스냅샷(_blocks_now)을 쓴다 (2026-07-25).
        """
        if rc is None:
            return None
        blocks = getattr(self, "_blocks_now", [])
        r, c = rc
        for i, b in enumerate(blocks):
            r0, c0 = int(b.get("row", 0)), int(b.get("col", 0))
            if (r0 <= r < r0 + max(1, int(b.get("rows", 1)))
                    and c0 <= c < c0 + max(1, int(b.get("span", 1)))):
                return i
        return None

    def _on_drag(self, e):
        """드래그 중 — 타일이 커서를 따라오고, 놓일 자리를 미리 칠한다."""
        if self._drag_from is None:
            return
        # 손이 4px 넘게 움직인 뒤에야 들어 올린다 — 그냥 클릭한 것과 구분.
        # 실패했으면 **다시 시도하지 않는다** — 예전에는 모션마다 재시도하며
        # 오류 로그를 디스크에 써서 그 자체가 버벅임이 됐다 (2026-07-25).
        if self._lifted is None and not self._lift_failed and self._grab_xy:
            if (abs(e.x_root - self._grab_xy[0]) > 4
                    or abs(e.y_root - self._grab_xy[1]) > 4):
                if not self._lift_tile(self._drag_from, *self._grab_xy):
                    self._lift_failed = True
        if self._lifted:
            try:
                self._lifted["ghost"].geometry(
                    f"+{e.x_root - self._lifted['off'][0]}"
                    f"+{e.y_root - self._lifted['off'][1]}")
            except Exception:
                pass
        rc = self._xy_to_cell(e.x_root, e.y_root)
        target = self._cell_owner(rc)
        hint = target if target is not None else rc
        if hint == self._drop_hint:
            return                       # 같은 칸이면 다시 그리지 않는다 (버벅임 방지)
        self._drop_hint = hint
        # 타일 강조
        for i, tile in getattr(self, "_tiles", {}).items():
            try:
                if i == target and i != self._drag_from:
                    tile.config(highlightbackground="#34c759", highlightthickness=3)
                elif i == self.sel_block:
                    tile.config(highlightbackground=ACCENT, highlightthickness=2)
                else:
                    tile.config(highlightbackground=BORDER, highlightthickness=1)
            except Exception:
                pass
        # 빈칸 강조 — 놓일 자리를 칠해 보여준다
        for key, cell_rc in self._empty_map.items():
            try:
                w = self.nametowidget(key)
                w.config(bg=RANGE_BG if (target is None and cell_rc == rc)
                         else EMPTY_BG)
            except Exception:
                pass

    def _on_release(self, e):
        src = self._drag_from
        self._drag_from = None
        self._drop_hint = None
        self._grab_xy = None
        self._drop_tile()               # 들어 올렸던 타일을 제자리로 (곧 다시 그린다)
        if src is None:
            return
        rc = self._xy_to_cell(e.x_root, e.y_root)
        target = self._cell_owner(rc)
        if target is None and rc is not None:
            # 빈칸에 놓으면 그 자리로 옮긴다
            blocks = palette.load_tabs()[self.sel_tab]["blocks"]
            b = blocks[src]
            if palette.set_block_area(self.sel_tab, src, rc[0], rc[1],
                                      int(b.get("span", 1)),
                                      int(b.get("rows", 1))):
                self._render_blocks()
                self._notify()
            else:
                self._render_blocks()    # 겹쳐서 실패 — 강조만 지운다
            return
        if target is not None and target != src:
            palette.move_block_to(self.sel_tab, src, target)
            self.sel_block = target
            self._render_blocks()
            self._notify()
        else:
            self._render_blocks()        # 제자리 — 강조 원복

    # ── 선택 블럭 동작 ──
    def _need_sel(self):
        if self.sel_block is None:
            messagebox.showinfo("선택 없음", "먼저 블럭을 눌러 선택하세요.", parent=self)
            return False
        blocks = palette.load_tabs()[self.sel_tab]["blocks"]
        if not (0 <= self.sel_block < len(blocks)):
            self.sel_block = None
            return False
        return True

    def _resize_selected(self, dspan=0, drows=0):
        """선택 블럭의 가로·세로 크기를 한 칸씩 늘리거나 줄인다."""
        if not self._need_sel():
            return
        b = palette.load_tabs()[self.sel_tab]["blocks"][self.sel_block]
        span = max(1, int(b.get("span", 1)) + dspan)
        rows = max(1, int(b.get("rows", 1)) + drows)
        ok = palette.set_block_area(self.sel_tab, self.sel_block,
                                    int(b.get("row", 0)), int(b.get("col", 0)),
                                    span, rows)
        if not ok:
            messagebox.showinfo("자리 없음",
                                "그 방향에 다른 블럭이 있어 늘릴 수 없습니다.\n"
                                "블럭을 먼저 옮겨주세요.", parent=self)
            return
        self._render_blocks()
        self._notify()

    def _del_selected(self):
        if not self._need_sel():
            return
        blocks = palette.load_tabs()[self.sel_tab].get("blocks", [])
        if not (0 <= self.sel_block < len(blocks)):
            return
        # 마지막 남은 '변환' 블럭은 못 지운다 (2026-07-25) — 옮기고 크기를
        # 바꾸는 건 자유지만, 다 지워 버리면 화면에서 되살릴 길이 없다.
        key = palette.protected_key_of(blocks[self.sel_block])
        if key and palette.count_protected(blocks, key) <= 1:
            messagebox.showinfo(
                "지울 수 없음",
                f"'{builtin_actions.name_of(key)}'는 이 프로그램의 본체라\n"
                "마지막 하나는 지울 수 없습니다.\n\n"
                "자리·크기·이름은 다른 블럭과 똑같이 바꿀 수 있습니다.",
                parent=self)
            return
        palette.delete_block(self.sel_tab, self.sel_block)
        self.sel_block = None
        self._render_blocks()
        self._notify()

    def _edit_selected(self):
        if not self._need_sel():
            return
        self._edit_block(self.sel_block)

    def _edit_block(self, idx):
        self.sel_block = idx
        blocks = palette.load_tabs()[self.sel_tab]["blocks"]
        if not (0 <= idx < len(blocks)):
            return
        blk = dict(blocks[idx])
        if blk["type"] == "char":
            val = simpledialog.askstring("특수기호/문구 편집", "내용:",
                                         initialvalue=blk.get("value", ""), parent=self)
            if val is not None and val != "":
                blk["value"] = val
                palette.update_block(self.sel_tab, idx, blk)
        elif blk["type"] == "template":
            items = library.list_items("템플릿")
            if not items:
                return
            pick = _ChoiceDialog(self, "템플릿 변경", [it["name"] for it in items])
            self.wait_window(pick)
            if pick.result:
                it = next(x for x in items if x["name"] == pick.result)
                blk["ref"] = it["id"]
                blk["template"] = it["name"]
                palette.update_block(self.sel_tab, idx, blk)
        else:  # function
            dlg = FunctionDialog(self, block=blk)
            self.wait_window(dlg)
            if dlg.result:
                dlg.result["span"] = blk.get("span", 1)
                palette.update_block(self.sel_tab, idx, dlg.result)
        self._render_blocks()
        self._notify()

    # ── 블럭 추가 ──
    def _need_tab(self):
        if not palette.load_tabs():
            messagebox.showwarning("탭 없음", "먼저 탭을 만들어주세요.", parent=self)
            return False
        return True

    # 새 블럭의 기본 폭은 **모든 종류 두 칸** (사용자 결정 2026-07-25) —
    # 종류마다 폭이 다르면(문자 1칸, 템플릿 2칸) 격자가 들쭉날쭉해 보였다.
    # 한 칸이면 충분한 블럭은 놓은 뒤 손잡이로 줄이면 된다.
    def _add_char(self, span=2, rows=1):
        if not self._need_tab():
            return
        prefill = ""
        try:
            hwp_engine.connect()
            if hwp_engine.has_selection():
                prefill = hwp_engine.read_selection_text(retries=6)
        except Exception:
            pass
        val = simpledialog.askstring(
            "특수기호/문구 블럭", "삽입할 기호나 문구 (한글에서 선택했다면 자동으로 채워집니다):",
            initialvalue=prefill, parent=self)
        if val:
            self._place({"type": "char", "value": val,
                         "span": span, "rows": rows})

    def _add_template(self, span=2, rows=1):
        """템플릿 블럭 추가 — 지금 한글에서 바로 캡처하거나, 등록된 것에서 고른다."""
        if not self._need_tab():
            return
        items = library.list_items("템플릿")
        choice = _SourceDialog(self, has_registered=bool(items))
        self.wait_window(choice)
        if choice.result == "capture":
            self._capture_template_here(span, rows)
        elif choice.result == "registered":
            pick = _ChoiceDialog(self, "템플릿 선택", [it["name"] for it in items])
            self.wait_window(pick)
            if pick.result:
                it = next(x for x in items if x["name"] == pick.result)
                self._add_template_block(it, span, rows)

    def _capture_template_here(self, span=2, rows=1):
        """한글의 현재 선택(또는 커서가 든 표)을 그 자리에서 템플릿으로 등록 + 배치.

        등록 절차 자체는 **라이브러리 창과 같은 코드**를 쓴다 (2026-07-25).
        예전에는 여기에 복사본이 있었고, 그 복사본이 MetaDialog 를 임포트하지
        않아 NameError 로 죽었다 — 환경설정에서는 템플릿 추가가 안 되고
        라이브러리 창에서만 되던 원인. 한 벌로 합쳐 그 어긋남을 없앴다.
        """
        item_id = library_ui.capture_template_dialog(self)
        if item_id is None:
            return
        self._add_template_block(library.find_by_id("템플릿", item_id), span, rows)

    def _add_template_block(self, item, span=2, rows=1):
        if not item:
            return
        self._place({"type": "template", "ref": item["id"],
                     "template": item["name"], "span": span, "rows": rows})

    def _add_function(self, span=2, rows=1):
        if not self._need_tab():
            return
        dlg = FunctionDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            dlg.result["span"], dlg.result["rows"] = span, rows
            self._place(dlg.result)

    def _add_builtin(self, span=2, rows=1):
        """프로그램 기능 블럭 추가 (사진·특수문자·양식 채우기 …).

        고를 수 있는 목록은 builtin_actions 가 정한다 — 사용자가 만드는 것이
        아니라 프로그램이 가진 기능이라, 라이브러리 등록 없이 바로 놓는다.
        """
        if not self._need_tab():
            return
        names = [f"{a['name']} — {a['hint']}"
                 for a in builtin_actions.BUILTIN_ACTIONS]
        pick = _ChoiceDialog(self, "도구 선택", names)
        self.wait_window(pick)
        if not pick.result:
            return
        idx = names.index(pick.result)
        action = builtin_actions.BUILTIN_ACTIONS[idx]
        self._place({"type": "builtin", "key": action["key"],
                     "name": action["name"], "span": span, "rows": rows})

    def _add_form(self, span=2, rows=1):
        """양식 블럭 추가 — 라이브러리에 등록된 양식에서 고른다."""
        if not self._need_tab():
            return
        items = library.list_items("양식")
        if not items:
            messagebox.showinfo(
                "양식 없음",
                "먼저 📚 라이브러리 → 양식 탭에서 hwp 파일을 등록해주세요.\n\n"
                "양식은 '새 문서로 열기'용입니다 (표지·통신문처럼\n"
                "용지·여백·머리말까지 그대로 시작할 때).", parent=self)
            return
        pick = _ChoiceDialog(self, "양식 선택", [it["name"] for it in items])
        self.wait_window(pick)
        if pick.result:
            it = next(x for x in items if x["name"] == pick.result)
            self._place({"type": "form", "ref": it["id"],
                         "form": it["name"], "span": span, "rows": rows})

    # ── 기본 서식 ──
    # ── 실행 취소 / 다시 실행 ──
    def _undo(self):
        if not palette.undo():
            messagebox.showinfo("되돌릴 것 없음",
                                "이 창을 연 뒤 되돌릴 편집이 없습니다.\n"
                                "(프로그램을 켠 동안의 편집만 되돌립니다)",
                                parent=self)
            return
        self.sel_block = None
        self._reload_tabs()
        self._notify()

    def _redo(self):
        if palette.redo():
            self.sel_block = None
            self._reload_tabs()
            self._notify()

    def _edit_default_format(self):
        dlg = _DefaultFormatDialog(self)
        self.wait_window(dlg)
        self._notify()

    def _close(self):
        self._notify()
        self.destroy()

    def _notify(self):
        if self.on_saved:
            self.on_saved()


class _SourceDialog(tk.Toplevel):
    """템플릿 블럭을 어디서 가져올지 — 지금 캡처 vs 이미 등록된 것."""

    def __init__(self, master, has_registered=True):
        super().__init__(master)
        self.result = None
        self.title("템플릿 추가")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        tk.Label(self, text="템플릿을 어디서 가져올까요?", font=(FONT, theme.fs(11), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(14, 8))

        body = tk.Frame(self, bg=BG, padx=16)
        body.pack(fill="x")
        # min_w 로 폭 하한을 두고 fill="x" 로 늘린다 — 아래 버튼과 폭이 맞는다
        RoundButton(body, text="📸  지금 한글에서 캡처해서 추가",
                    command=lambda: self._pick("capture"), bg=ACCENT,
                    fg="white", radius=7, font=(FONT, theme.fs(10), "bold"),
                    zone_bg=BG).fit(pad_x=14, pad_y=10,
                                    min_w=260).pack(fill="x")
        tk.Label(body, text="한글에서 표·영역을 선택해두고 누르세요. 등록과 배치가 한 번에.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w", pady=(3, 10))

        # RoundButton 은 state=disabled 가 없어 이 버튼만 tk.Button 을 유지한다
        state = "normal" if has_registered else "disabled"
        tk.Button(body, text="📚  이미 등록된 템플릿에서 고르기",
                  command=lambda: self._pick("registered"),
                  font=(FONT, theme.fs(10)), bg=CARD, fg=TEXT, bd=1, pady=8,
                  cursor="hand2", state=state).pack(fill="x")
        if not has_registered:
            tk.Label(body, text="(아직 등록된 템플릿이 없습니다)",
                     font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w", pady=(3, 0))

        _dialog_btn(self, "취소", self.destroy).pack(pady=10)

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+50}+{master.winfo_rooty()+50}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _pick(self, what):
        self.result = what
        self.destroy()


class _ChoiceDialog(tk.Toplevel):
    def __init__(self, master, title, options):
        super().__init__(master)
        self.result = None
        self.title(title)
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        tk.Label(self, text=title, font=(FONT, theme.fs(10), "bold"), bg=BG, fg=TEXT).pack(
            anchor="w", padx=16, pady=(12, 6))
        self.var = tk.StringVar(value=options[0])
        ttk.Combobox(self, textvariable=self.var, values=options, width=24,
                     state="readonly", font=(FONT, theme.fs(10))).pack(padx=16)
        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "확인", self._ok, primary=True).pack(side="right")
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+60}+{master.winfo_rooty()+60}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _ok(self):
        self.result = self.var.get()
        self.destroy()


class _DefaultFormatDialog(tk.Toplevel):
    """‘기본 서식으로 변환’이 적용할 기본 서식."""

    def __init__(self, master):
        super().__init__(master)
        self.title("기본 서식 설정")
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        fmt = palette.get_default_format()

        tk.Label(self, text="기본 서식으로 변환 시 적용할 서식",
                 font=(FONT, theme.fs(10), "bold"), bg=BG, fg=TEXT).pack(
                 anchor="w", padx=16, pady=(12, 8))
        body = tk.Frame(self, bg=BG, padx=16)
        body.pack(fill="x")

        self.font_var = tk.StringVar(value=fmt["font"])
        self.size_var = tk.StringVar(value=str(fmt["size_pt"]))
        self.ls_var = tk.StringVar(value=str(fmt["line_spacing"]))
        self.sp_var = tk.StringVar(value=str(fmt["spacing"]))

        rows = [("글꼴", ttk.Combobox(body, textvariable=self.font_var, width=16,
                                     values=func_catalog.COMMON_FONTS, font=(FONT, theme.fs(9)))),
                ("크기(pt)", tk.Entry(body, textvariable=self.size_var, width=8,
                                     font=(FONT, theme.fs(9)), relief="solid", bd=1)),
                ("줄간격(%)", tk.Entry(body, textvariable=self.ls_var, width=8,
                                     font=(FONT, theme.fs(9)), relief="solid", bd=1)),
                ("자간", tk.Entry(body, textvariable=self.sp_var, width=8,
                                font=(FONT, theme.fs(9)), relief="solid", bd=1))]
        for i, (lbl, w) in enumerate(rows):
            tk.Label(body, text=lbl, font=(FONT, theme.fs(9)), bg=BG, fg=TEXT).grid(
                row=i, column=0, sticky="w", pady=3)
            w.grid(row=i, column=1, sticky="w", padx=(8, 0), pady=3)

        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "저장", self._ok, primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+50}+{master.winfo_rooty()+50}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _ok(self):
        try:
            fmt = {
                "font": self.font_var.get().strip() or "함초롬바탕",
                "size_pt": float(self.size_var.get()),
                "line_spacing": int(float(self.ls_var.get())),
                "spacing": int(float(self.sp_var.get())),
                "align": palette.get_default_format().get("align", 0),
            }
        except ValueError:
            messagebox.showwarning("값 오류", "크기·줄간격·자간은 숫자여야 합니다.", parent=self)
            return
        palette.save_default_format(fmt)
        self.destroy()


class _CaptionDialog(tk.Toplevel):
    r"""블럭에 보일 이름 — **Enter 로 줄을 나눌 수 있다**.

    Entry 가 아니라 Text 를 쓰는 이유: Entry 는 Enter 를 '확인'으로 삼켜 줄바꿈을
    넣을 수가 없다. 저장은 아래 버튼(또는 Ctrl+Enter)으로 한다.
    """

    def __init__(self, master, current, caption=""):
        super().__init__(master)
        self.result = None
        self.title("블럭 이름")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        tk.Label(self, text="버튼에 보일 이름", font=(FONT, theme.fs(11), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(self,
                 text="Enter 로 줄을 나눌 수 있습니다 — 좁은 칸에 두 줄로 넣을 때 씁니다.\n"
                      "비우고 저장하면 원래 이름으로 돌아갑니다.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED, justify="left").pack(
            anchor="w", padx=16, pady=(0, 8))

        self.box = tk.Text(self, width=24, height=3, font=(FONT, theme.fs(11)),
                           relief="solid", bd=1, wrap="none")
        self.box.pack(padx=16)
        self.box.insert("1.0", caption or "")
        self.box.focus_set()
        self.box.bind("<Control-Return>", lambda e: self._ok())

        tk.Label(self, text=f"지금 이름: {current!r}", font=(FONT, theme.fs(8)),
                 bg=BG, fg=MUTED).pack(anchor="w", padx=16, pady=(6, 0))

        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "저장  (Ctrl+Enter)", self._ok,
                    primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+60}+{master.winfo_rooty()+80}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _ok(self):
        library_ui.commit_ime(self)     # 한글 조합 중인 마지막 글자 확정
        self.result = self.box.get("1.0", "end").rstrip("\n")
        self.destroy()


class _ToolPickDialog(tk.Toplevel):
    """빈칸을 끌어 칸 수를 정한 뒤 '무엇을 넣을지' 고르는 창."""

    _TOOLS = [
        ("char", "특수기호", "특수기호·자주 쓰는 문구를 커서 자리에 삽입"),
        ("template", "템플릿", "표·결재란 등 문서 일부를 커서 자리에 꽂기"),
        ("function", "서식 조합", "선택한 글자에 굵게·크기·자간 등을 한 번에"),
        ("form", "양식", "hwp 파일 전체를 새 문서로 열기"),
        ("builtin", "도구", "이 프로그램의 기능 (사진·특수기호·양식 채우기 …)"),
    ]

    def __init__(self, master, span, rows=1):
        super().__init__(master)
        self.result = None
        self.title("어떤 도구를 넣을까요?")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        size = f"{span}칸" if rows <= 1 else f"{span}×{rows}칸"
        tk.Label(self, text=f"{size} 자리에 넣을 도구",
                 font=(FONT, theme.fs(11), "bold"), bg=BG, fg=TEXT).pack(
            anchor="w", padx=16, pady=(12, 2))
        tk.Label(self, text="고르면 그 도구를 만드는 창이 이어서 열립니다.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w", padx=16,
                                                       pady=(0, 8))

        body = tk.Frame(self, bg=BG, padx=16)
        body.pack(fill="x")
        for key, name, desc in self._TOOLS:
            # min_w 를 같이 주어 다섯 줄의 폭을 통일한다
            row = RoundButton(body, text=f"{name}\n{desc}",
                              command=lambda k=key: self._pick(k),
                              bg=CARD, fg=TEXT, radius=7,
                              font=(FONT, theme.fs(9)), outline=BORDER,
                              zone_bg=BG, justify="left")
            row.fit(pad_x=12, min_w=340).pack(fill="x", pady=2)

        # 버튼 색 — 기본(종류별 색) 또는 직접 지정
        self.color = None
        crow = tk.Frame(self, bg=BG, padx=16)
        crow.pack(fill="x", pady=(6, 0))
        tk.Label(crow, text="버튼 색", font=(FONT, theme.fs(8)), bg=BG,
                 fg=MUTED).pack(side="left", padx=(0, 6))
        self._color_lbl = tk.Label(crow, text="기본", font=(FONT, theme.fs(8)),
                                   bg=CARD, fg=TEXT, relief="solid", bd=1,
                                   padx=8, pady=2)
        self._color_lbl.pack(side="left")
        for hexv in ("#ffffff", "#eef4ff", "#fff4e6", "#eafaf1",
                     "#fdecec", "#f3ecfd", "#fdf7dc"):
            sw = tk.Label(crow, text="  ", bg=hexv, relief="solid", bd=1)
            sw.pack(side="left", padx=2)
            sw.bind("<Button-1>", lambda e, v=hexv: self._set_color(v))
            sw.config(cursor="hand2")
        # 색 견본 줄 높이에 맞춘 납작한 둥근 버튼
        RoundButton(crow, text="직접", command=self._custom_color, bg=CARD,
                    fg=TEXT, radius=7, font=(FONT, theme.fs(8)),
                    outline=BORDER, zone_bg=BG).fit(pad_x=8, pad_y=2).pack(
            side="left", padx=(4, 0))

        _dialog_btn(self, "취소", self.destroy).pack(anchor="e",
                                                   padx=16, pady=12)

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+60}+{master.winfo_rooty()+80}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _set_color(self, hexv):
        self.color = hexv
        self._color_lbl.config(text=hexv or "기본",
                               bg=hexv or CARD)

    def _custom_color(self):
        _, hexv = colorchooser.askcolor(parent=self)
        if hexv:
            self._set_color(hexv)

    def _pick(self, key):
        self.result = key
        self.destroy()


def open_settings(master, on_saved=None):
    win = SettingsWindow(master, on_saved=on_saved)
    ui_fx.attach_all(win)               # 창 안 모든 버튼에 호버 보간
    return win
