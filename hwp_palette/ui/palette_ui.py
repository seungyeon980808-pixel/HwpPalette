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
from tkinter import filedialog, simpledialog, ttk, colorchooser
from hwp_palette.design import dialogs as messagebox   # 윈도우 기본 대화상자 대신 프로그램과 같은 얼굴 (2026-07-27)
import pathlib

from hwp_palette.core import applog
from hwp_palette.model import chip                       # 팔레트를 칩으로 내보내기
from hwp_palette.model import palette
from hwp_palette.model import library
from hwp_palette.model import func_catalog
from hwp_palette.model import builtin_actions              # 프로그램 기능 블럭('도구') 카탈로그
from hwp_palette.hwp import engine_library               # 고치기 세션 마무리 (hide_window_if_ours)
from hwp_palette.hwp import hwp_dock                     # 고치는 동안 한글 창을 미리보기 판에 도킹
from hwp_palette.hwp import hwp_engine
from hwp_palette.design import disclosure                  # 접었다 펴는 안내 (양식 문법)
from hwp_palette.ui import library_ui                  # commit_ime · capture_template_dialog 공용

from hwp_palette.core import appinfo
from hwp_palette.design.popover import Popover        # 팔레트 고르기 드롭다운 (main.py 의 pal_pick 과 같은 얼굴)
from hwp_palette.core import screens                     # 창 자리 규칙 (메인 창 옆)
from hwp_palette.ui import store_ui                    # 왼쪽 물감 창고 패널
from hwp_palette.hwp import preview                     # 물감 미리보기 그림
from hwp_palette.design import theme                       # 색은 theme.py 한 곳에서 (밝게/어둡게)
from hwp_palette.design import ui_fx                       # 호버 보간 (애플 A안)
from hwp_palette.design.roundbtn import RoundButton, RoundTile   # 둥근 모서리 버튼·타일

_C = theme.colors()
BG = _C["bg"]
CARD = _C["card"]
ACCENT = _C["accent"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
ROWBG = _C["subbg"]
SOFT = _C["yellow"]      # 옅은 회색 버튼 바탕 (물감 상세의 '수정')
ACCENT_SOFT = _C["accent_soft"]   # 팔레트 고르개가 열려 있는 동안의 옅은 파랑
FONT = theme.FONT
SP = theme.SP        # 간격 토큰 (4의 배수)
FS = theme.FS        # 글자 위계 (역할 이름)

TYPE_LABEL = {"char": "특수기호", "template": "템플릿", "function": "서식 조합",
              "form": "양식"}

# 글자 수 상한 (개선안 23 — 흩어져 있던 매직넘버에 이름을 붙임)
TILE_LABEL_MAX = 12      # 격자 미리보기 타일에 넣을 수 있는 글자 수
AUTO_NAME_MAX = 16       # 이름을 안 지었을 때 기능 이름들을 이어 붙이는 길이

# 격자 한 칸 — 정사각형이고, **칸 수에 맞춰 크기가 변한다**(_cell_px).
# 칸을 늘리면 칸이 작아져 격자 전체 폭은 그대로 유지된다 → 오른쪽에 빈 공간이 안 생김.
GRID_WIDTH_PX = 420      # 격자가 쓸 가로 폭
# 34 → 44 (사용자 지적 2026-07-30: "팔레트 설정도 버튼 크기를 조정해야겠습니다")
#
# 34px 칸에는 아이콘(15pt ≈ 20px) + 이름(11pt ≈ 15px) = 35px 이 안 들어가서
# **이름 아랫부분이 잘려 점선처럼 보였다.** 딱 1px 모자랐다.
# 9열이면 폭으로 44px 까지 잡을 수 있는데(420 ÷ 9) 이 상한이 34 로 막고 있었다.
# 상한만 풀면 창은 그대로 두고 칸만 커진다 — GRID_WIDTH_PX 가 총 폭을 지킨다.
CELL_MAX_PX = 44
# 최소 24px — 접근성 기준(WCAG 2.5.8)이 정한 클릭 대상 하한이다
# (사용자 결정 2026-07-30). 예전 16px 은 8px 모자랐고, 배치 격자는 끌어서
# 옮기는 곳이라 작으면 옆 칸을 집는다.
#
# 대신 **한 줄에 담기는 칸이 24개에서 16개로 줄어든다** (420px ÷ 26px).
# 이 결정을 하기 전에 실제 config.json 을 재 봤다: 지금 쓰는 팔레트 다섯 개
# 중 가장 넓은 것이 '학교 시험문제' 15열이라 잃는 것이 없다.
# 17열 이상을 쓰게 되면 GRID_WIDTH_PX 를 함께 키워야 한다.
CELL_MIN_PX = 24
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
                    fg="white" if primary else TEXT, radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["body"])), outline="" if primary else BORDER,
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
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED).pack(anchor="w", padx=16, pady=(0, 8))

        namef = tk.Frame(self, bg=BG, padx=16)
        namef.pack(fill="x")
        tk.Label(namef, text="블럭 이름", font=(FONT, theme.fs(FS["body"])), bg=BG, fg=TEXT).pack(side="left")
        self.name_var = tk.StringVar(value=name0)
        tk.Entry(namef, textvariable=self.name_var, width=20, font=(FONT, theme.fs(FS["head"])),
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
            tk.Label(row, text=key, font=(FONT, theme.fs(FS["head"])), bg=BG, fg=TEXT,
                     width=8, anchor="w").pack(side="left")
            val_widget, val_var = self._value_widget(row, f, existing.get(key))
            tk.Label(row, text=f.get("hint", ""), font=(FONT, theme.fs(FS["caption"])), bg=BG,
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
                             values=func_catalog.COMMON_FONTS, font=(FONT, theme.fs(FS["body"])))
            w.pack(side="left")
            return w, var
        if kind == "number":
            var = tk.StringVar(value="" if cur is None else str(cur))
            w = tk.Entry(parent, textvariable=var, width=6, font=(FONT, theme.fs(FS["body"])),
                         relief="solid", bd=1)
            w.pack(side="left")
            tk.Label(parent, text=f.get("unit", ""), font=(FONT, theme.fs(FS["sub"])),
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
                # 문서 글자색 — 여기는 자유 선택을 유지한다. 화면 장식이 아니라
                # 시험지에 실제로 인쇄되는 색이라 12색으로 좁히면 안 된다
                # (블럭 색은 _PastelDialog 로 좁혔다, 2026-07-27).
                rgb, _hex = colorchooser.askcolor(parent=self)
                if rgb:
                    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
                    var.set(str(_rgb_int(r, g, b)))
                    swatch.config(bg=_hex)
            # 줄 높이에 맞춘 납작한 둥근 버튼 — 공용 helper 는 여기엔 크다
            RoundButton(parent, text="색 선택", command=pick, bg=CARD, fg=TEXT,
                        radius=theme.RADIUS["ctl"], font=(FONT, theme.fs(FS["sub"])), outline=BORDER,
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
    # 크기를 25% 줄였다 (사용자 결정 2026-07-27) — 격자 옆의 보조 단추라
    # 눈에 띄기보다 자리만 지키면 되는데, 블럭만 하게 커서 시선을 끌었다.
    b = RoundButton(parent, text=text, command=cmd, bg=CARD, fg=TEXT,
                    radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["caption"])), outline=BORDER,
                    zone_bg=parent.cget("bg"))
    b.config(width=int(theme.fs(26) * 0.75), height=int(theme.fs(20) * 0.75))
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
            tk.Label(win, text=text, font=(FONT, theme.fs(FS["sub"])), fg=TEXT,
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


# 양식 문법 안내 — '양식 수정' 중 판 아래에 접힌 채로 놓인다 (disclosure.py).
#
# 규칙만 나열하던 옛 네 줄을 **"이렇게 쓰면 이렇게 나온다"** 로 다시 썼다
# (사용자 지적 2026-07-28). 문법을 외우게 하는 글이 아니라, 지금 눈앞의
# 한글 문서에 무엇을 치면 채우기 표가 어떻게 생기는지를 보여주는 글이다.
_FORM_SYNTAX_LINES = [
    "빈칸 만들기",
    [("   문서에 ", 0), ("\\", 1), (" 하나를 치면", 0),
     ("   →   ", 1), ("채우기 표에 칸이 하나 생깁니다", 0)],
    [("   빈칸 하나 = 내용 한 줄이 들어갈 자리입니다.", 0)],
    "빈칸에 이름 붙이기",
    [("   ", 0), ("\\학년\\", 1), (" 이라고 치면", 0),
     ("   →   ", 1), ("채우기 표에 ", 0), ("'학년'", 1), (" 이라고 나옵니다", 0)],
    [("   이름이 없으면 ", 0), ("빈칸 1 · 빈칸 2", 1),
     (" 로만 나와, 나중에 어디가 어디인지 알아보기 어렵습니다.", 0)],
    "채워지는 차례",
    [("   ", 0), ("위에서 아래 → 왼쪽에서 오른쪽", 1),
     (" 입니다 (표 안에서도 같습니다).", 0)],
    [("   AI 에게 값을 받아 채울 때도 이 차례를 따릅니다.", 0)],
    "단위 글자는 이름표 밖에",
    [("   ", 0), ("\\월\\월", 1), (" 이라고 치면", 0), ("   →   ", 1),
     ("'3월'", 1), (" 이 됩니다", 0)],
    [("   ", 0), ("\\월월\\", 1), (" 이라고 치면", 0), ("   →   ", 1),
     ("'3'", 1), (" 만 남고 '월' 이 사라집니다", 0)],
    [("   이름표는 값으로 ", 0), ("통째로", 1), (" 바뀌기 때문입니다.", 0)],
]

# 미리보기 판의 폭 — 창고보다 넓어야 '크게 본다'가 성립하지만,
# 셋이 나란히 서므로 창이 화면을 넘지 않는 선에서 잡는다
ZOOM_W = 396          # 20% 더 넓게, 330 → 396 (사용자 결정 2026-07-27)

# 격자 블럭 안쪽 글자 여백 — main._BLOCK_TEXT_PAD 와 같은 값이어야 한다.
# (이 판은 메인 창 블럭의 미리보기다)
TILE_TEXT_PAD = 8


class SettingsWindow(tk.Toplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        # 다 만들 때까지 숨긴다 (사용자 지적 2026-07-28: "이상한 곳에 깜빡
        # 하면서 생겼다가 옮겨온다") — Tk 는 창을 만들면 기본 자리에 먼저
        # 그린 뒤 geometry 로 옮긴다. 숨긴 채 만들고 제자리에서 한 번에 편다.
        self.withdraw()
        self.on_saved = on_saved
        self._base_title = appinfo.WINDOW_TITLE
        self.title(self._base_title)
        self.configure(bg=BG)
        self.resizable(True, True)
        # **메인 창의 자식으로 못박는다** (사용자 지적 2026-07-28: "팔레트 설정을
        # 누르면 메인 페이지 위로 떠야 하는데 그 아래에 깔린다").
        #
        # 원인: 메인 창이 -topmost 라 '항상 위' 무리에 있고, 이 창도 -topmost 지만
        # 같은 무리 안에서는 순서가 보장되지 않는다 — 메인 창이 무슨 이유로든
        # 다시 활성화되면 그 위로 올라온다.
        # transient 는 윈도우에게 **소유 관계**를 알려준다: 소유된 창은 소유자
        # 위에 있는 것이 운영체제 규칙이라, 이 한 줄이 순서를 영구히 고정한다.
        # (메인 위젯이 우리 창들 중 늘 맨 아래여야 한다는 요구와 같은 해법)
        try:
            self.transient(master)
        except Exception:
            pass
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
        self._pending_block = None  # 창고에서 고른 뒤 '자리 고르는 중'인 물감
        self._edit_ctx = None      # '내용 고치는 중' 상태 (세션·창 목록·topmost)
        self._dock = None          # 편집 중 한글 창 도킹
        self._edit_form = None     # 판에 심은 이름·태그 폼 (수정 상태)
        self._notify_job = None    # 메인 창 반영 디바운스 (400ms 모아 한 번)
        self._last_req = None      # _fit_window 가 마지막으로 잡은 요청 크기

        # 창 제목·설명 줄은 없앴다 (사용자 지적 2026-07-27: "윗부분에 남는
        # 공간이 너무 많다"). 판마다 머리말이 이미 있어서 — '팔레트',
        # '물감 창고', '미리보기' — 위에서 같은 말을 또 할 필요가 없었다.
        # 창 제목표시줄이 프로그램 이름을 말하고, 무슨 화면인지는 판이 말한다.

        # 왼쪽 목록과 오른쪽 격자를 **하나의 흰 판** 안에 나란히 둔다 (2026-07-25).
        # 고른 팔레트(왼쪽)와 그 내용(오른쪽)이 같은 판 위에 있어야
        # "이 팔레트의 내용이 저것"임이 눈으로 이어진다 — 따로 떠 있으면
        # 둘이 무슨 사이인지 알 수 없다. macOS 설정 창의 사이드바와 같은 짜임이다.
        # 창고와 팔레트는 **각각 다른 판**이다 (사용자 지적 2026-07-27) —
        # 한 판 위에 붙여 뒀더니 어디까지가 창고이고 어디부터가 팔레트인지
        # 구별되지 않았다. 사이를 띄우고 판을 나눈다.
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=SP["l"], pady=SP["m"])

        # 왼쪽부터 **팔레트 → 물감 창고 → 미리보기** (사용자 결정 2026-07-27).
        # 셋 다 처음부터 자리를 차지한다 — 눌렀을 때 판이 생겼다 없어지면
        # 창 크기와 위치가 바뀌어 화면이 흔들린다.
        main = tk.Frame(outer, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        main.pack(side="left", fill="both", expand=True)
        self._main_card = main     # '고치는 중'엔 접었다 편다 (_enter_dock_layout)

        self._store_grip = tk.Label(outer, text="⟩", bg=BG, fg=MUTED,
                                    font=(FONT, theme.fs(FS["sub"])), cursor="hand2",
                                    padx=4)
        self._store_grip.pack(side="left", fill="y")
        self._store_grip.bind("<Button-1>", lambda e: self._toggle_store())

        # 창고와 미리보기는 **한 판** 안에 둔다 (사용자 지적 2026-07-28:
        # "물감 창고와 물감 미리보기가 한 묶음이라는 느낌이 들어야 한다").
        #
        # 예전에는 셋(팔레트 설정·창고·미리보기)이 각각 테두리를 두르고 같은
        # 간격으로 서 있어서, 화면이 '나란한 세 개'로 읽혔다. 실제 관계는
        # **팔레트 설정 ┃ (창고 + 미리보기)** 다 — 오른쪽 둘은 같은 물감을
        # 고르고 들여다보는 한 벌이고, 왼쪽은 그것을 놓는 판이다.
        # 테두리를 하나로 합치고 사이는 1px 선으로만 가르면, 바깥 테두리가
        # '이 둘은 한 벌'을, 안쪽 선이 '그 안에서 하는 일은 둘'을 말한다.
        self._paint_group = tk.Frame(outer, bg=CARD, highlightbackground=BORDER,
                                     highlightthickness=1)
        self._paint_group.pack(side="left", fill="y", padx=(SP["s"], 0))

        store_card = tk.Frame(self._paint_group, bg=CARD)
        store_card.pack(side="left", fill="y")
        self._store_card = store_card
        self._paint_div = tk.Frame(self._paint_group, bg=BORDER, width=1)
        self._paint_div.pack(side="left", fill="y")
        self.store = store_ui.StorePanel(
            store_card, on_place=self._place_from_store,
            tab_name_fn=self._cur_tab_name, on_select=self._show_detail,
            on_drop=self._drop_from_store)
        self.store.pack(fill="both", expand=True)

        # 맨 오른쪽 판: 고른 물감의 미리보기와 동작. 늘 떠 있고 내용만 바뀐다.
        #
        # 짜임을 둘로 나눴다 (사용자 지적 2026-07-27: "미리보기 크기에 따라
        # 버튼 위치가 변해서 불편하다") —
        #   위: 스크롤되는 내용 칸 (그림이 커도 판 밖으로 안 넘친다)
        #   아래: **항상 같은 자리**에 고정된 버튼 줄
        # 그림이 커지거나 작아져도 버튼은 절대 움직이지 않는다.
        self.zoom_pane = tk.Frame(self._paint_group, bg=CARD, width=ZOOM_W)
        self.zoom_pane.pack_propagate(False)
        self.zoom_pane.pack(side="left", fill="y")
        self._zoom_photo = None
        self._detail = None

        # 판 머리말 — 다른 두 판('팔레트'·'물감 창고')과 같은 자리·같은 크기.
        # 없으면 이 판이 무엇인지 화면이 말해 주지 않는다 (사용자 지적
        # 2026-07-27: "이 창이 템플릿 미리보기라는 것을 알 수 있어야 한다").
        zhead = tk.Frame(self.zoom_pane, bg=CARD)
        zhead.pack(side="top", fill="x", padx=SP["s"], pady=(SP["s"], 2))
        # 제목은 상태 따라 바뀐다: 미리보기 ↔ 양식 수정 (사용자 결정 2026-07-28)
        # '미리보기' → '물감 미리보기' (사용자 결정 2026-07-28) — 옆의
        # '물감 창고'와 이름을 맞춰야 둘이 한 벌로 읽힌다.
        self._zoom_title = tk.Label(zhead, text="물감 미리보기",
                                    font=(FONT, theme.fs(FS["head"]), "bold"),
                                    bg=CARD, fg=TEXT)
        self._zoom_title.pack(side="left")
        self.zoom_hint = tk.Label(zhead, text="물감을 고르면 보입니다",
                                  font=(FONT, theme.fs(FS["caption"])),
                                  bg=CARD, fg=MUTED)
        self.zoom_hint.pack(side="left", padx=(SP["xs"] + 2, 0))
        tk.Frame(self.zoom_pane, bg=BORDER, height=1).pack(side="top", fill="x")

        # 버튼 줄을 **먼저** side="bottom" 으로 붙인다 — 그래야 내용이 아무리
        # 길어도 이 줄은 밀려나지 않고 판 맨 아래에 그대로 남는다.
        self._zoom_foot = tk.Frame(self.zoom_pane, bg=CARD)
        self._zoom_foot.pack(side="bottom", fill="x")
        tk.Frame(self.zoom_pane, bg=BORDER, height=1).pack(side="bottom",
                                                           fill="x")

        zoom_wrap = tk.Frame(self.zoom_pane, bg=CARD)
        zoom_wrap.pack(side="top", fill="both", expand=True)
        self._zoom_canvas = tk.Canvas(zoom_wrap, bg=CARD, highlightthickness=0)
        zoom_bar = ttk.Scrollbar(zoom_wrap, orient="vertical",
                                 style="App.Vertical.TScrollbar",
                                 command=self._zoom_canvas.yview)
        self._zoom_body = tk.Frame(self._zoom_canvas, bg=CARD)
        self._zoom_body.bind("<Configure>", lambda e: self._zoom_canvas.configure(
            scrollregion=self._zoom_canvas.bbox("all")))
        self._zoom_win = self._zoom_canvas.create_window(
            (0, 0), window=self._zoom_body, anchor="nw")
        self._zoom_canvas.bind("<Configure>", lambda e: self._zoom_canvas.itemconfig(
            self._zoom_win, width=e.width))
        self._zoom_canvas.configure(yscrollcommand=zoom_bar.set)
        self._zoom_canvas.pack(side="left", fill="both", expand=True)
        zoom_bar.pack(side="right", fill="y")
        messagebox.style_scrollbars(self)

        # 팔레트 판의 머리말 — 창고에도 같은 자리에 머리말이 있다.
        # 없으면 오른쪽이 무엇을 하는 곳인지 화면이 말해 주지 않는다
        # (사용자 지적 2026-07-27).
        #
        # 탭 목록은 **왼쪽 세로 버튼 더미**였다가 여기(머리말 오른쪽)의
        # 드롭다운으로 옮겼다 (사용자 지적 2026-07-27 — "왼쪽 탭이 공간
        # 낭비가 심하다"). 메인 창의 '개인 팔레트 [수능 ▾]' 와 같은 얼굴이다.
        # 세로 목록이 없어진 만큼 격자가 쓸 폭이 그대로 늘어난다.
        # 머리말과 고르개를 **두 줄로** 나눈다 (사용자 결정 2026-07-27).
        # 한 줄에 다 넣었더니 이름이 긴 팔레트('부천여자중학교 원안지')에서
        # 설명과 드롭다운이 서로를 밀어내 줄이 빡빡했다.
        phead = tk.Frame(main, bg=CARD)
        phead.pack(fill="x", padx=SP["s"], pady=(SP["s"], 2))
        tk.Label(phead, text="팔레트 설정",
                 font=(FONT, theme.fs(FS["head"]), "bold"),
                 bg=CARD, fg=TEXT).pack(side="left")
        self.pal_hint = tk.Label(phead, text=self._pal_hint_text(),
                                 font=(FONT, theme.fs(FS["caption"])),
                                 bg=CARD, fg=MUTED)
        self.pal_hint.pack(side="left", padx=(SP["xs"] + 2, 0))

        # 둘째 줄: 고르기(드롭다운) 하나뿐 — 추가·관리도 이 안에 있다
        # (사용자 결정 2026-07-27: ＋·⋯ 버튼을 없애고 드롭다운으로 모음.
        #  각 팔레트의 오른쪽 ⋯ 로 이름·순서·내보내기·삭제, 맨 아래
        #  '＋ 새 팔레트' 로 추가).
        prow = tk.Frame(main, bg=CARD)
        prow.pack(fill="x", padx=SP["s"], pady=(0, SP["s"]))
        # 이름은 왼쪽 붙임, ▾ 는 오른쪽 끝 고정 (사용자 지적 2026-07-28) —
        # 자세한 이유는 RoundButton 의 trailing 설명.
        self.tab_pick = RoundButton(
            prow, text="", command=self._tab_dropdown, trailing="▾",
            bg=CARD, fg=TEXT, radius=theme.RADIUS["ctl"],
            font=(FONT, theme.fs(FS["body"])), outline=BORDER,
            focus_color=ACCENT, zone_bg=CARD)
        # 폭을 **가장 긴 이름 기준으로 한 번만** 잰다 (사용자 지적 2026-07-27:
        # "드롭다운의 길이가 일정해야 한다") — 고를 때마다 이름 길이 따라
        # 버튼이 늘었다 줄었다 하면 그 줄 전체가 다시 배치되며 창이 덜컹거린다.
        self.tab_pick._text = "가" * self._TAB_NAME_MAX
        self.tab_pick.fit(pad_x=SP["m"] - 3, pad_y=3)
        self.tab_pick.pack(side="left")

        # ↗ — 이 팔레트를 파일로 내보내거나, 받은 파일을 불러온다
        # (사용자 결정 2026-07-28: 설정 메뉴의 '물감 나누기'를 없애고
        #  물감·팔레트를 보고 있는 자리로 옮겼다).
        # 팔레트 고르개 **바로 옆**에 두는 이유: 무엇이 나가는지가 그 옆의
        # 이름으로 정해지므로, 둘이 붙어 있어야 "이것을 보낸다"가 읽힌다.
        self.share_btn = RoundButton(
            prow, text=theme.SHARE_GLYPH, command=self._share_menu,
            bg=CARD, fg=MUTED, radius=theme.RADIUS["ctl"],
            font=(FONT, theme.fs(FS["body"])), outline="", zone_bg=CARD)
        self.share_btn.config(width=theme.fs(24), height=theme.fs(21))
        self.share_btn.pack(side="right")
        _tip(self.share_btn, "이 팔레트 내보내기 · 받은 파일 불러오기")

        tk.Frame(main, bg=BORDER, height=1).pack(fill="x")

        # 오른쪽에 있던 격자가 이제 전체 폭을 쓴다 (왼쪽 탭 목록이 없어졌다)
        right = tk.Frame(main, bg=CARD, padx=8, pady=6)
        right.pack(fill="both", expand=True)
        # 격자 위 머리말(블럭 수·조작 안내)은 지웠다 — 위 설명이 이미 무엇을
        # 하는 곳인지 말해 준다. 끄는 중 크기 안내는 **창 제목**으로 보여준다.

        self.block_area = tk.Frame(right, bg=CARD)
        self.block_area.pack(fill="both", expand=True)

        # 마우스 휠을 한 곳에서 받아 창고·미리보기 중 커서가 있는 쪽으로 돌린다
        # (2026-07-27) — 각자 bind_all 하면 Tk 의 "all" 태그를 서로 덮어써
        # 나중 것만 남는다. store_ui.on_wheel 설명 참고.
        self.bind_all("<MouseWheel>", self._route_wheel)

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
        #
        # 자리는 **메인 창을 완전히 덮는 자리** (사용자 결정 2026-07-28) —
        # 옆에 붙이면 화면 어딘가에서 깜빡 나타났다 옮겨오는 것처럼 보였다.
        # 설정하는 동안 메인 창을 쓸 일도 없다.
        try:
            pos = master.geometry().split("+")
            x, y = int(pos[1]), int(pos[2])
        except Exception:
            x, y = 80, 80
        # 모니터 안으로만 민다 — 이 창은 세로 주모니터(1080)보다 넓어서,
        # 오른쪽 끝 기준으로 밀면 x 가 음수(모니터 사이 빈 구간)로 튄다.
        # 왼쪽 끝을 이기게 두면 적어도 왼쪽 위는 항상 화면 안이다.
        try:
            ml, mt, mw, mh = screens.monitor_bounds(master)
            x = max(ml, min(x, ml + mw - self.winfo_reqwidth()))
            y = max(mt, min(y, mt + mh - self.winfo_reqheight()))
        except Exception:
            pass
        self.geometry(f"+{x}+{y}")
        self.deiconify()                 # 제자리에서 한 번에 나타난다

    # ── 물감 창고 ──
    def _cur_tab_name(self):
        try:
            tabs = palette.load_tabs()
            return tabs[self.sel_tab].get("name") if tabs else ""
        except Exception:
            return ""

    def _place_from_store(self, block):
        r"""창고에서 고른 물감을 놓는다 — **자리를 끌어서 고르게** 한다.

        첫 빈자리에 알아서 넣지 않는 이유 (사용자 결정 2026-07-27):
        어디에 들어갈지 누른 사람이 정해야 하고, 칸 수(가로 폭)도 그 자리에서
        정해지기 때문. 격자의 빈 칸을 끄는 동작은 이미 있으므로
        (_empty_press ~ _empty_release), 그 흐름에 '놓을 물감'만 얹는다.
        """
        if not self._need_tab():
            return
        self._pending_block = block
        name = self._block_label(block) or "물감"
        self.pal_hint.config(
            text=f"'{name}' 을(를) 놓을 자리를 빈 칸에서 끌어 주세요 (Esc 취소)",
            fg=ACCENT)
        self.bind("<Escape>", lambda e: self._cancel_place())

    def _drop_from_store(self, block, x_root, y_root):
        r"""창고 타일을 격자에 떨어뜨렸다 (사용자 결정 2026-07-28 — '팔레트에
        놓기' 버튼 대신 끌어다 놓기). 격자 밖이면 조용히 취소.

        떨어뜨린 칸이 비어 있으면 그 자리에, 차 있으면 첫 빈자리에 넣는다 —
        "놓으려 했는데 아무 일도 없다"보다 어딘가라도 들어가는 쪽이 낫고,
        자리는 끌어서 다시 옮기면 된다.
        """
        if not self._need_tab():
            return False
        rc = self._xy_to_cell(x_root, y_root)
        if rc is None:
            return False                    # 격자 밖 — 끌기 취소
        row, col = rc
        blk = dict(block)
        if (row, col) in self._used_cells:
            palette.add_block(self.sel_tab, blk)            # 첫 빈자리
        else:
            palette.add_block(self.sel_tab, blk, row=row, col=col)
        self._render_blocks()
        self._notify()
        return True

    def _cancel_place(self):
        """놓을 자리 고르기 취소 — Esc 는 원래 창 닫기라 되돌려 준다."""
        if getattr(self, "_pending_block", None) is None:
            self._close()
            return
        self._pending_block = None
        self.pal_hint.config(text=self._pal_hint_text(), fg=MUTED)
        self.bind("<Escape>", lambda e: self._close())

    def _pal_hint_text(self):
        # 한 문장으로 줄였다 (사용자 결정 2026-07-28) — 머리말 옆 설명은
        # '무엇을 하는 곳인가' 한 가지만 말해야 눈에 걸린다.
        return "빈칸을 드래그해서 물감을 짭니다"

    def _share_menu(self):
        r"""↗ — 이 팔레트 주고받기. 누르자마자 파일창이 뜨지 않는다
        (사용자 결정 2026-07-28): 내보내기인지 불러오기인지 먼저 고른다.
        """
        tabs = palette.load_tabs()
        cur = tabs[self.sel_tab] if 0 <= self.sel_tab < len(tabs) else None
        pop = Popover(self, self.share_btn)
        if cur is not None:
            pop.add(f"'{cur['name']}' 팔레트 내보내기…",
                    lambda t=cur: library_ui.export_palette_flow(self, t))
        pop.separator()
        pop.add("불러오기…", self._import_share)
        pop.show()

    def _import_share(self):
        r"""받은 파일 등록 — 물감도 팔레트도 이 한 입구로 들어온다.

        들어온 뒤 창고와 팔레트 목록을 **둘 다** 다시 읽는다: 파일에 팔레트가
        들어 있으면 탭이 늘어나는데, 목록을 안 읽으면 드롭다운에 안 보인다.
        """
        if library_ui.import_flow(self, on_saved=None):
            self._reload_tabs()
            self._refresh_store()
            self._notify(items_changed=True)

    def _toggle_store(self):
        """⟩ — 창고+미리보기 묶음을 통째로 접었다 편다 (둘은 한 벌이다)."""
        if self._paint_group.winfo_manager() == "pack":
            self._paint_group.pack_forget()
            self._store_grip.config(text="⟨")
        else:
            self._paint_group.pack(side="left", fill="y", padx=(SP["s"], 0))
            self._store_grip.config(text="⟩")
        self._fit_window()

    def _show_detail(self, cat, item):
        r"""고른 물감을 보여준다 — 그림(스크롤 영역)과 버튼(고정 영역)을 나눈다.

        **버튼은 self._zoom_foot(맨 아래 고정)에, 그림·설명은
        self._zoom_body(스크롤 영역)에 넣는다** — 판 자체가 아니라 이 둘만
        갈아 끼운다. 예전에는 판 전체를 지우고 위에서부터 다시 쌓아, 그림이
        크면 버튼이 판 밖으로 밀려나거나 자리가 매번 바뀌었다 (사용자 지적
        2026-07-27: "미리보기 크기에 따라 버튼 위치가 변해서 불편하다").
        이제 그림이 창보다 커도 스크롤만 늘어나고 버튼은 항상 같은 자리다.
        """
        if self._edit_ctx is not None:
            return              # 고치는 중 — 판을 다른 내용으로 갈아끼우지 않는다
        self._detail = (cat, item)
        self._edit_form = None
        for w in self._zoom_body.winfo_children():
            w.destroy()
        for w in self._zoom_foot.winfo_children():
            w.destroy()
        self._zoom_canvas.yview_moveto(0)   # 새 물감을 고르면 맨 위부터 보여준다

        self.zoom_hint.config(text=f"{item.get('name', '')} · #{cat}")

        photo = None
        if cat in ("템플릿", "양식"):
            try:
                # 폭은 판에 맞추되, 높이는 크게 열어 둔다 — 어차피 스크롤되므로
                # 그림이 커도 잘리거나 버튼을 밀어내지 않는다.
                photo = preview.tk_photo_for_item(
                    item, library.template_path(item), ZOOM_W - 44, 1400)
            except Exception as e:
                applog.exc(f"미리보기 실패 — {item.get('name')}", e)
        if photo is not None:
            self._zoom_photo = photo        # 참조 유지
            # 그림을 **종이처럼** 흰 바탕 + 테두리로 감싼다 (사용자 지적
            # 2026-07-27: "어디서부터 어디까지가 양식인지 안 보인다").
            # 미리보기 그림은 배경이 흰색이라 판 바탕과 그대로 이어져 보여,
            # 문서의 가장자리가 어디인지 알 수 없었다.
            paper = tk.Frame(self._zoom_body, bg="#ffffff",
                             highlightbackground=BORDER, highlightthickness=1)
            paper.pack(padx=SP["m"], pady=SP["s"])
            lbl = tk.Label(paper, image=photo, bg="#ffffff", bd=0)
            lbl.image = photo
            lbl.pack(padx=SP["xs"], pady=SP["xs"])
        else:
            text = (library.get_preview(item) or "").strip() or "(미리보기 없음)"
            tk.Label(self._zoom_body, text=text[:600], bg=CARD, fg=MUTED,
                     font=(FONT, theme.fs(FS["sub"])), justify="left", anchor="nw",
                     wraplength=ZOOM_W - 32).pack(fill="x", padx=SP["m"] - 2,
                                                  pady=SP["s"])

        self._zoom_title.config(text="물감 미리보기")
        acts = tk.Frame(self._zoom_foot, bg=CARD)
        acts.pack(fill="x", padx=SP["m"] - 2, pady=SP["s"])
        # 버튼은 오른쪽 정렬 (사용자 결정 2026-07-28). '팔레트에 놓기' 버튼은
        # 없앴다 — 창고 타일을 격자로 **끌어다 놓는** 것으로 대신한다.
        if cat in ("템플릿", "양식"):
            # 창(MetaDialog)을 띄우지 않고 이 판을 수정 폼으로 갈아끼운다
            # (사용자 결정 2026-07-27 — "미리보기 창이 템플릿 수정으로 치환")
            RoundButton(acts, text="수정",
                        command=lambda: self._show_edit_form(cat, item),
                        bg=ACCENT, fg="white", radius=theme.RADIUS["ctl"],
                        font=(FONT, theme.fs(FS["body"]), "bold"),
                        outline="", zone_bg=CARD).fit(pad_x=12, pad_y=5).pack(
                        side="right")
        if self.store.block_of(cat, item) is not None:
            tk.Label(acts, text="창고의 카드를 팔레트 빈 칸으로 끌어다 놓으세요",
                     font=(FONT, theme.fs(FS["caption"])), bg=CARD,
                     fg=MUTED).pack(side="left")
        else:
            tk.Label(acts, text=r"문서에서 \%s\ 로 씁니다"
                     % (item.get("label") or item.get("name")),
                     font=(FONT, theme.fs(FS["caption"])), bg=CARD, fg=MUTED).pack(side="left")

    # ── 미리보기 판의 상태 전환: 미리보기 → 수정 → 고치는 중 ──────────
    # 셋 다 **같은 판**의 내용(_zoom_body)과 버튼 줄(_zoom_foot)만 갈아끼운다.
    # 창을 새로 띄우거나 판을 늘리지 않는 것이 규칙이다 (사용자 결정
    # 2026-07-27 — "최대한 위젯 창을 늘리지 않는 로직").

    def _clear_zoom(self):
        for w in self._zoom_body.winfo_children():
            w.destroy()
        for w in self._zoom_foot.winfo_children():
            w.destroy()
        self._zoom_canvas.yview_moveto(0)

    def _show_edit_form(self, cat, item):
        """[수정] — 미리보기 자리에 이름·태그 폼을 심는다 (창 없음)."""
        if self._edit_ctx is not None:
            return
        self._clear_zoom()
        # 판 제목이 **지금 무엇을 하는 중인지**를 말한다 (사용자 지적
        # 2026-07-28: "수정 버튼을 누르면 여전히 미리보기입니다").
        # 미리보기 → 물감 이름 수정 → 양식 수정, 셋이 같은 판을 갈아 쓴다.
        self._zoom_title.config(text="물감 이름 수정")
        self.zoom_hint.config(text=item.get("name", ""))
        form = library_ui.MetaForm(
            self._zoom_body, name=item["name"], exclude_id=item["id"],
            bg=CARD, on_submit=lambda: self._save_edit_form(cat, item))
        try:
            form.tags_var.set(" ".join(item.get("tags") or []))
        except Exception:
            pass
        form.pack(fill="x", padx=SP["m"], pady=SP["s"])
        self._edit_form = form
        # 마크다운 호출이 무엇인지 두 줄 더 (사용자 결정 2026-07-28) —
        # 위의 "문서에 이렇게 쓰세요" 한 줄만으로는 처음 보는 사람이
        # 그걸 어디에 왜 적는지 알 수 없었다.
        tk.Label(self._zoom_body,
                 text="위 표기가 '마크다운 호출'입니다 — 한글 문서에 \\이름\\ 을 "
                      "적어 두고\n[마크다운 변환]을 누르면 그 자리에 이 물감이 "
                      "통째로 꽂힙니다 (팔레트 버튼과 같은 동작).",
                 font=(FONT, theme.fs(FS["caption"])), bg=CARD, fg=MUTED,
                 justify="left", anchor="w").pack(fill="x", padx=SP["m"],
                                                  pady=(0, SP["s"]))

        acts = tk.Frame(self._zoom_foot, bg=CARD)
        acts.pack(fill="x", padx=SP["m"] - 2, pady=SP["s"])
        RoundButton(acts, text="저장",
                    command=lambda: self._save_edit_form(cat, item),
                    bg=ACCENT, fg="white", radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["body"]), "bold"), outline="",
                    zone_bg=CARD).fit(pad_x=12, pad_y=5).pack(side="right")
        RoundButton(acts, text="취소",
                    command=lambda: self._show_detail(cat, item),
                    bg=SOFT, fg=TEXT, radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["body"])), outline="",
                    zone_bg=CARD).fit(pad_x=12, pad_y=5).pack(
                    side="right", padx=(0, 6))
        if cat in ("템플릿", "양식"):
            RoundButton(acts, text="양식 수정",
                        command=lambda: self._start_content_edit(cat, item),
                        bg=SOFT, fg=TEXT, radius=theme.RADIUS["ctl"],
                        font=(FONT, theme.fs(FS["body"])), outline="",
                        zone_bg=CARD).fit(pad_x=12, pad_y=5).pack(side="left")

    def _save_edit_form(self, cat, item):
        form = self._edit_form
        if form is None or not form.winfo_exists():
            return
        got = form.collect()
        if got is None:
            return                  # 오류창이 떴다 — 폼을 열어 둔 채 고치게
        name, label, tags = got
        label = library.resolve_edited_label(
            item["name"], item.get("label", ""), name, label)
        library.update_item(cat, item["id"], name=name, label=label, tags=tags)
        self._notify(items_changed=True)   # 이름·태그가 바뀜 — 창고 통째 갱신
        fresh = library.find_by_id(cat, item["id"]) or item
        self._show_detail(cat, fresh)

    # ── '양식 수정' — 판이 '고치는 중'이 되고 한글이 그 자리에 도킹 ──
    def _start_content_edit(self, cat, item):
        r"""순서가 곧 품질이다 (2026-07-28 재배치, 사용자 지적 "한글이 엉뚱한
        곳에 생겼다가 도킹된다"):

          ① 판을 먼저 '양식 수정' 모양으로 바꾸고 창 크기를 확정한다
          ② 숨어 있는 한글 창을 **숨긴 채로** 그 자리에 미리 옮겨 둔다
          ③ COM 으로 켠다 — 이미 제자리라 점프 없이 그 자리에서 나타난다
          ④ 문서를 펼친다 (1~3초 — 렌더러가 표시를 소화할 완충)
          ⑤ 도킹 추적 시작

        ②③ 순서는 검은 화면 버그와도 얽혀 있다: COM(Visible)보다 먼저
        SWP_SHOWWINDOW 로 보이게 하면 렌더러가 꺼진 채 검게 뜬다. 미리
        옮기기는 SHOWWINDOW 없이 숨긴 채 이동만 하므로 안전하다.
        """
        if self._edit_ctx is not None:
            return
        windows_before = hwp_engine.visible_window_handles()
        if not library_ui._ensure_hwp(self):
            return
        item = library.find_by_id(cat, item.get("id")) or item
        was_topmost = library_ui._pop_topmost(self)
        # 메인 창의 '항상 위'도 함께 내린다 (사용자 지적 2026-07-28: "양식
        # 수정을 하니 메인 페이지가 중간에 끼어 있습니다").
        #
        # 이 자리에 도킹되는 한글 창은 **남의 창**이라 transient 로 순서를
        # 묶을 수 없다. 메인 창이 topmost 로 남아 있으면 한글과 팔레트 설정
        # 사이에 끼어 버린다. 고치는 동안만 내려 두고 끝나면 되돌린다 —
        # 메인 창은 우리 창들 중 늘 맨 아래여야 한다는 규칙의 연장이다.
        main_was_topmost = library_ui._pop_topmost(self.master)
        self._show_editing_panel(cat, item)     # ① 판 전환
        self._collapse_for_edit()               # ① 창 크기 확정
        hwnd = hwp_engine.connected_hwnd()
        if hwnd:
            hwp_dock.preposition(hwnd, self._zoom_canvas)   # ② 숨긴 채 미리 배치
        hwp_engine.ensure_visible()             # ③ COM 으로 켠다 (렌더러 함께)
        try:                                    # ④ 문서 펼치기
            if cat == "양식":
                session = engine_library.open_form_copy(
                    library.template_path(item), library_ui._FORM_EDIT_NOTE)
            else:
                session = engine_library.open_template_copy(
                    library.template_path(item),
                    library_ui.LibraryManager._EDIT_NOTE)
        except Exception as e:
            applog.exc(f"{cat} 꺼내기 실패", e)
            messagebox.showerror("꺼내기 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            self._exit_dock_layout()            # 판·창 크기 원복
            try:
                engine_library.hide_window_if_ours(windows_before)
            except Exception:
                pass
            for win, was in ((self, was_topmost),
                             (self.master, main_was_topmost)):
                if was:
                    try:
                        win.attributes("-topmost", True)
                    except Exception:
                        pass
            self._show_detail(cat, item)
            return
        self._edit_ctx = {
            "cat": cat, "item": item, "session": session,
            "windows_before": windows_before, "was_topmost": was_topmost,
            "main_was_topmost": main_was_topmost,
        }
        self._start_dock()                      # ⑤ 실시간 추적 시작
        hwp_engine.bring_to_front()             # 도킹된 창에 초점까지 준다
        # 한 박자 뒤 **다시 한 번** (실측 2026-07-28): COM 으로 창을 켠 직후의
        # 활성화는 한글이 표시 처리를 끝내기 전이라 그림이 안 살아나는 채
        # (검은 창) 남는 경우가 있다. 잠깐 뒤 재활성화가 렌더러를 확실히 깨운다.
        self.after(350, lambda: (self._edit_ctx is not None
                                 and hwp_engine.bring_to_front()))
        # Esc = 편집 취소 (창 닫기가 아니라) — 끝나면 _finish 가 되돌린다
        self.bind("<Escape>", lambda e: self._finish_content_edit(False))

    def _show_editing_panel(self, cat, item):
        self._clear_zoom()
        self._edit_form = None
        # 제목·설명이 상태를 말한다 (사용자 결정 2026-07-28)
        self._zoom_title.config(text="양식 수정")
        self.zoom_hint.config(
            text=f"{item['name']} — 한글 문서에서 양식을 수정하고 저장하세요")
        # 판 몸통은 한글 창이 덮는다 — 한글이 다른 데로 가면 보이는 대비용 안내
        tk.Label(self._zoom_body,
                 text="한글 창이 이 자리에 떠 있습니다.\n"
                      "안 보이면 작업 표시줄에서 한글을 눌러 주세요.",
                 font=(FONT, theme.fs(FS["sub"])), bg=CARD, fg=MUTED,
                 justify="left").pack(anchor="nw", padx=SP["m"], pady=SP["m"])
        # 고치는 법 안내는 **여기**에 있다 (사용자 결정 2026-07-28) — 예전에는
        # 한글 문서 맨 위에 빨간 글씨로 넣었는데, 문서를 밀어내고 지저분한
        # 잔재까지 남겼다. 아래 빈 공간을 채우도록 **크게**, 핵심은 파랗게
        # (같은 날 사용자 결정: "글씨 크기를 키우고 강조는 파란색으로").
        guide = disclosure.Disclosure(
            self._zoom_foot, title="양식 문법",
            summary=r"빈칸은 \ 하나 · 이름은 \학년\ 처럼",
            lines=_FORM_SYNTAX_LINES,
            bg=CARD, on_toggle=lambda _o: self._fit_window())
        guide.pack(fill="x", padx=SP["m"] - 2, pady=(SP["xs"], 0))
        acts = tk.Frame(self._zoom_foot, bg=CARD)
        acts.pack(fill="x", padx=SP["m"] - 2, pady=SP["s"])
        RoundButton(acts, text="덮어씌워 저장",
                    command=lambda: self._finish_content_edit(True),
                    bg=ACCENT, fg="white", radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["body"]), "bold"), outline="",
                    zone_bg=CARD).fit(pad_x=12, pad_y=5).pack(side="right")
        RoundButton(acts, text="취소",
                    command=lambda: self._finish_content_edit(False),
                    bg=SOFT, fg=TEXT, radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["body"])), outline="",
                    zone_bg=CARD).fit(pad_x=12, pad_y=5).pack(
                    side="right", padx=(0, 6))

    def _collapse_for_edit(self):
        r"""고치는 동안 격자·창고를 접고 판을 넓힌다 (도킹은 _start_dock 이).

        '둘 다 접기' (사용자 결정 2026-07-27): 넓힌 창(1330px+)은 세로
        주모니터(가상 폭 1080)를 넘는다. 고치는 중에는 격자를 만질 일이
        없으므로 판 하나만 남기면 1060px 안쪽으로 들어온다.
        """
        # winfo_ismapped 가 아니라 **winfo_manager 로** 본다 (실측 2026-07-27):
        # ismapped 는 창이 WM 에 실리기 전이면 packed 상태여도 0 을 줘서,
        # 창고를 "안 보임"으로 오판해 접지 않았고 복귀 순서까지 어긋났다.
        self._dock_saved = {
            "group_packed": self._paint_group.winfo_manager() == "pack",
            "zoom_h": int(self.zoom_pane.cget("height"))}
        self._main_card.pack_forget()
        self._store_grip.pack_forget()
        # 묶음 자체는 접힌 상태였을 수도 있다 — 그때는 다시 펴야 판이 보인다
        if not self._dock_saved["group_packed"]:
            self._paint_group.pack(side="left", fill="y", padx=(SP["s"], 0))
        self._store_card.pack_forget()
        self._paint_div.pack_forget()
        # 높이를 **반드시 함께** 정한다 (실측 2026-07-27, 사용자 버그): 판은
        # 폭만 지정돼 있고 높이는 옆의 격자·창고가 정해 줬다. 그 둘을 접는
        # 순간 높이를 정해 줄 것이 없어져 창이 제목줄만 남기고 쪼그라들었다.
        try:
            _l, _t, _r, _b = screens.monitor_bounds(self)
            avail = (_b - _t) - 160     # 제목줄·바닥 버튼줄·창 테두리 몫
        except Exception:
            avail = 900
        # 높이를 20% 줄였다 (사용자 결정 2026-07-28: "도킹된 창이 너무 높다").
        edit_h = max(480, int(min(1050, avail) * 0.8))
        self.zoom_pane.configure(width=hwp_dock.EDIT_PANE_W, height=edit_h)
        self._fit_window()
        self.update_idletasks()         # 판이 최종 자리를 잡아야 미리 배치가 맞는다

    def _start_dock(self):
        hwnd = hwp_engine.connected_hwnd()
        if hwnd:
            self._dock = hwp_dock.Dock(self, self._zoom_canvas, hwnd)
            if not self._dock.start():
                self._dock = None       # 도킹 실패 — 한글은 제자리에 그냥 뜬다

    def _exit_dock_layout(self, pre_restore=None):
        r"""도킹을 멈추고 판을 원래 모습으로. pre_restore 는 **창을 되돌리기
        직전**에 부른다 — 숨길 창이면 먼저 숨겨야 '제자리로 튀는' 모션이
        안 보인다 (사용자 지적 2026-07-28: "저장하면 깜빡거린다")."""
        if self._dock is not None:
            self._dock.stop_follow()
            if pre_restore:
                try:
                    pre_restore()
                except Exception as e:
                    applog.exc("한글 창 정리 실패 (빈 창이 남을 수 있음)", e)
            self._dock.restore()
            self._dock = None
        elif pre_restore:
            try:
                pre_restore()
            except Exception as e:
                applog.exc("한글 창 정리 실패 (빈 창이 남을 수 있음)", e)
        saved = getattr(self, "_dock_saved", None) or {}
        self.zoom_pane.configure(width=ZOOM_W, height=saved.get("zoom_h", 0))
        # 원래 순서(격자·손잡이·묶음)로 — 각각 묶음 앞에 차례로 끼운다.
        # 묶음 안쪽은 창고·구분선이 미리보기 앞에 와야 한다.
        self._main_card.pack(side="left", fill="both", expand=True,
                             before=self._paint_group)
        self._store_grip.pack(side="left", fill="y", before=self._paint_group)
        self._store_card.pack(side="left", fill="y", before=self.zoom_pane)
        self._paint_div.pack(side="left", fill="y", before=self.zoom_pane)
        if not saved.get("group_packed", True):
            self._paint_group.pack_forget()     # 접어 뒀던 상태를 그대로 돌려준다
        self._fit_window()

    def _finish_content_edit(self, save):
        """저장이든 취소든 '고치는 중'을 끝내고 판·창·topmost 를 되돌린다."""
        ctx = self._edit_ctx
        if ctx is None:
            return
        if save:
            # 저장은 한글 COM 작업이라 1~3초 걸린다 — 그동안 아무 표시가
            # 없으면 "멈췄나?" 가 된다 (사용자 지적 2026-07-28). 손모래시계와
            # 문구로 '일하는 중'을 먼저 보여준다.
            try:
                self.config(cursor="watch")
                self.zoom_hint.config(text="저장하는 중…")
                self.update_idletasks()
            except Exception:
                pass
            ok, _closed = library_ui.overwrite_content(
                ctx["session"], ctx["cat"], ctx["item"], parent=self)
            try:
                self.config(cursor="")
            except Exception:
                pass
            if not ok:
                self.zoom_hint.config(
                    text=f"{ctx['item']['name']} — 한글 문서에서 양식을 "
                         "수정하고 저장하세요")
                return              # 오류창이 떴다 — 편집 상태를 유지한다
        else:
            # 취소도 **고치던 탭을 닫는다** (사용자 지적 2026-07-28:
            # "취소를 해버리면 한글 창이 그대로 남아 있습니다"). 남기면
            # 문서가 하나 더 있는 셈이라 빈 창 정리가 비껴갔다.
            try:
                if ctx["session"] is not None:
                    ctx["session"].close()
                    ctx["session"].cleanup()
            except Exception as e:
                applog.exc("취소 시 고치던 탭 닫기 실패", e)
        self._edit_ctx = None

        def restore():
            # 숨길 창이면 **되돌리기 전에** 숨긴다 — 도킹 자리에서 옛 자리로
            # 튀어가는 모션이 화면에 안 보인다 (깜빡임 제거의 핵심 순서).
            self._exit_dock_layout(pre_restore=lambda: (
                engine_library.hide_window_if_ours(ctx["windows_before"])))
            for win, was in ((self, ctx["was_topmost"]),
                             (self.master, ctx.get("main_was_topmost"))):
                if was:
                    try:
                        win.attributes("-topmost", True)
                    except Exception:
                        pass
            self.bind("<Escape>", lambda e: self._close())      # Esc 원복
            if save:
                # 내용·미리보기가 바뀜 — 창고 통째 갱신
                self._notify(items_changed=True)
            fresh = library.find_by_id(ctx["cat"], ctx["item"]["id"])
            if fresh is not None:
                self._show_detail(ctx["cat"], fresh)
            else:
                self._clear_zoom()
                self._zoom_title.config(text="물감 미리보기")
                self.zoom_hint.config(text="물감을 고르면 보입니다")

        # **되돌리는 구간을 가린다** (사용자 지적 2026-07-28: "취소나 저장을
        # 누르면 깜빡거리는 모션이 있습니다").
        #
        # 여기서 벌어지는 일은 한 프레임에 다 안 끝난다: 도킹 해제 → 한글 창
        # 숨기기 → 접었던 격자·창고 다시 펴기 → 창 크기 재계산. 그 사이 판이
        # 빈 채로 한두 프레임 비치는 것이 '깜빡임'의 정체다. 순서를 아무리
        # 다듬어도 재배치 자체는 남으므로, 재배치를 **안 보이게** 한다 —
        # 살짝 흐려졌다가(110ms) 다 끝난 새 화면으로 진해진다(160ms).
        ui_fx.veil(self, restore, dim=0.12)

    def _route_wheel(self, e):
        """마우스 휠 중앙 처리 — 커서가 창고 위면 창고를, 미리보기 위면 그쪽을."""
        self.store.on_wheel(e)
        try:
            c = self._zoom_canvas
            if (c.winfo_rootx() <= e.x_root <= c.winfo_rootx() + c.winfo_width()
                    and c.winfo_rooty() <= e.y_root <= c.winfo_rooty() + c.winfo_height()):
                c.yview_scroll(-1 if e.delta > 0 else 1, "units")
        except Exception:
            pass

    def _refresh_store(self):
        try:
            self.store.refresh()
        except Exception as e:
            applog.exc("창고 새로 그리기 실패", e)

    # ── 탭 목록 ──
    def _say(self, msg=None):
        """끌면서 잡은 칸 수 안내 — 지금은 **아무 데도 쓰지 않는다**.

        한때 창 제목에 붙였는데, 제목이 계속 바뀌어 오히려 어수선했다
        (사용자 지적 2026-07-25). 잡은 범위는 격자에 파랗게 칠해져 이미 보이므로
        글로 또 말할 필요가 없다. 호출부를 남겨 둔 것은 나중에 다른 자리에
        붙이고 싶을 때를 위해서다.
        """
        return

    _TAB_NAME_MAX = 12      # 이름이 길어도 드롭다운 버튼이 창 폭을 끌고 다니지 않게

    def _reload_tabs(self):
        r"""탭 상태를 새로 읽어 고르개 글자를 맞추고 격자를 다시 그린다.

        2026-07-27: 왼쪽 세로 버튼 더미를 없애고 머리말의 드롭다운으로
        옮겼다 — 팔레트가 늘수록 그 목록이 세로로 길어져 격자 폭을 갉아먹는
        낭비가 컸다 (사용자 지적). 이제 목록은 눌렀을 때만 잠깐 펼쳐진다.
        """
        tabs = palette.load_tabs()
        if tabs:
            self.sel_tab = min(self.sel_tab, len(tabs) - 1)
        self._sync_tab_pick(tabs)
        self._render_blocks()

    def _sync_tab_pick(self, tabs=None):
        tabs = palette.load_tabs() if tabs is None else tabs
        if not tabs:
            name = "팔레트 없음"
        else:
            name = tabs[min(self.sel_tab, len(tabs) - 1)]["name"]
            if len(name) > self._TAB_NAME_MAX:
                name = name[:self._TAB_NAME_MAX - 1] + "…"
        # set_text 는 글자에 맞춰 폭을 다시 재므로 쓰지 않는다 — 폭은 만들 때
        # 고정했다 (고를 때마다 버튼 크기가 변하면 창이 덜컹거린다)
        self.tab_pick._text = name          # ▾ 는 trailing 이 따로 그린다
        self.tab_pick._redraw()

    def _tab_dropdown(self):
        """팔레트 고르기 — 고르기·관리(⋯)·추가가 모두 이 안에 있다.

        main.py 의 pal_pick 과 같은 얼굴(Popover, 체크 목록)이되, 관리는
        각 팔레트 오른쪽의 ⋯ 로, 추가는 맨 아래 줄로 들어갔다 (사용자 결정
        2026-07-27 — 머리말의 ＋·⋯ 버튼을 없애고 드롭다운 하나로).
        """
        tabs = palette.load_tabs()
        self.tab_pick.retint(bg=ACCENT_SOFT, fg=ACCENT)
        pop = Popover(self, self.tab_pick,
                     on_close=lambda: self.tab_pick.retint(bg=CARD, fg=TEXT))
        for i, t in enumerate(tabs):
            pop.add_check(t["name"], lambda idx=i: self._pick_tab(idx),
                         checked=(i == self.sel_tab),
                         more=lambda idx=i: self._tab_manage_menu(idx))
        pop.separator()
        pop.add("＋ 새 팔레트 만들기", self._add_tab, indent=True)
        pop.show()

    def _tab_manage_menu(self, idx):
        """팔레트 관리 — 드롭다운 각 줄의 ⋯ 가 연다. 이름·순서·내보내기·삭제.

        네이티브 tk.Menu 를 쓴다 — 이 프로그램 전체에서 오른쪽 클릭 메뉴가
        이미 이 모양이라(_tile_menu 등) 통일된다.
        """
        tabs = palette.load_tabs()
        if not (0 <= idx < len(tabs)):
            return
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="이름 바꾸기", command=lambda: self._rename_tab(idx))
        m.add_separator()
        m.add_command(label="▲ 위로", command=lambda: self._move_tab(idx, -1),
                      state="normal" if idx > 0 else "disabled")
        m.add_command(label="▼ 아래로", command=lambda: self._move_tab(idx, 1),
                      state="normal" if idx < len(tabs) - 1 else "disabled")
        m.add_separator()
        m.add_command(label="팔레트 내보내기…",
                      command=lambda: self._export_chip(idx))
        m.add_separator()
        m.add_command(label="삭제", command=lambda: self._del_tab(idx))
        m.tk_popup(*self.winfo_pointerxy())

    def _pick_tab(self, idx):
        if idx == self.sel_tab:
            return
        self.sel_tab = idx
        self._reload_tabs()
        self._refresh_store()       # 코랄(이 탭에 있음)이 새 탭 기준으로 바뀐다

    def _export_chip(self, idx):
        r"""팔레트 탭 하나를 파일로 내보낸다 (탭 우클릭의 지름길).

        실제 흐름은 library_ui.export_palette_flow 한 곳에 있다 — '물감 나누기'
        창의 [팔레트 보내기] 와 **같은 일**이라, 두 벌로 두면 한쪽만 고치는
        사고가 난다 (2026-07-27).
        """
        tabs = palette.load_tabs()
        if not (0 <= idx < len(tabs)):
            return
        library_ui.export_palette_flow(self, tabs[idx])

    def _add_tab(self):
        name = simpledialog.askstring("새 팔레트", "새 팔레트 이름:", parent=self)
        if name:
            palette.add_tab(name)
            self.sel_tab = len(palette.load_tabs()) - 1
            self._reload_tabs()
            self._notify()

    def _rename_tab(self, idx=None):
        """이름 바꾸기 — idx 팔레트를 고른 상태로 만들지 않는다 (2026-07-27).

        드롭다운의 ⋯ 는 **아무 팔레트에서나** 열 수 있으므로, 이름을 바꾼다고
        보고 있던 팔레트가 바뀌어 버리면 안 된다.
        """
        tabs = palette.load_tabs()
        if not tabs:
            return
        idx = self.sel_tab if idx is None else min(idx, len(tabs) - 1)
        if tabs[idx].get("name") == palette.MAIN_TAB:
            messagebox.showinfo("이름 고정",
                "'메인' 탭 이름은 메인 창이 찾는 열쇠라 바꿀 수 없습니다.",
                parent=self)
            return
        cur = tabs[idx]["name"]
        name = simpledialog.askstring("이름 변경", "새 이름:", initialvalue=cur, parent=self)
        if name:
            try:
                palette.rename_tab(idx, name)
            except ValueError as e:
                messagebox.showwarning("이름 충돌", str(e), parent=self)
                return
            self._reload_tabs()
            self._notify()

    def _del_tab(self, idx=None):
        tabs = palette.load_tabs()
        if not tabs:
            return
        idx = self.sel_tab if idx is None else min(idx, len(tabs) - 1)
        if tabs[idx].get("name") == palette.MAIN_TAB:
            messagebox.showinfo(
                "삭제할 수 없음",
                "'메인' 탭은 메인 창의 변환 버튼 옆 버튼칸입니다.\n"
                "탭 자체는 지울 수 없고, 안의 블럭만 비울 수 있습니다.", parent=self)
            return
        if messagebox.askyesno("삭제", f"'{tabs[idx]['name']}' 탭을 삭제할까요?",
                               parent=self):
            palette.delete_tab(idx)
            if self.sel_tab >= idx:        # 앞이 지워지면 보던 것을 따라간다
                self.sel_tab = max(0, self.sel_tab - 1)
            self._reload_tabs()
            self._notify()

    def _move_tab(self, idx, delta):
        """탭 순서 바꾸기 — 드롭다운 ⋯ 메뉴의 ▲▼ 로 한 칸씩.

        보고 있던 팔레트는 그대로 보이게 선택 인덱스를 따라 옮긴다.
        """
        palette.move_tab(idx, delta)
        last = len(palette.load_tabs()) - 1
        target = max(0, min(idx + delta, last))
        if self.sel_tab == idx:
            self.sel_tab = target          # 보던 것을 옮겼다 — 따라간다
        elif self.sel_tab == target:
            self.sel_tab = idx             # 보던 것과 자리를 맞바꿨다
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
                     font=(FONT, theme.fs(FS["body"])), bg=BG, fg=MUTED,
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
            tk.Label(grid, text=str(cc + 1), font=(FONT, theme.fs(FS["caption"])), bg=CARD,
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
            tk.Label(grid, text=str(rr + 1), font=(FONT, theme.fs(FS["caption"])), bg=CARD,
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

        요청 크기가 그대로면 아무것도 안 한다 (2026-07-28, 버벅임 1단계) —
        geometry("") + update_idletasks 두 번은 강제 재배치라, 렌더마다
        무조건 돌면 편집할 때마다 창이 미세하게 들썩였다. 덤으로 사용자가
        창을 늘려 둔 것도 내용이 안 바뀌었으면 더는 되돌리지 않는다.
        """
        self.update_idletasks()
        req = (self.winfo_reqwidth(), self.winfo_reqheight())
        if req == self._last_req:
            return
        self._last_req = req
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
        # 범위 표시는 **칠만 되돌린다** (2026-07-28) — 통째 재렌더는 격자
        # 위젯 수백 개를 다시 만들어, 빈 칸을 끌 때마다 화면이 출렁였다.
        # 블럭이 실제로 생기면 _place 가 어차피 다시 그린다.
        self._clear_range_paint()
        self._pick_tool(row, col, span, rows)

    def _clear_range_paint(self):
        for key in self._empty_map:
            try:
                self.nametowidget(key).config(bg=EMPTY_BG)
            except Exception:
                pass

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
        """자리와 크기를 정한 뒤 '무엇을 넣을지' 고른다.

        창고에서 '팔레트에 놓기'를 누른 뒤라면 무엇을 넣을지는 이미 정해져
        있으므로 묻지 않고 바로 그 자리에 놓는다 (2026-07-27).
        """
        pending = getattr(self, "_pending_block", None)
        if pending is not None:
            self._pending_block = None
            self._pending_area = (row, col, span, rows)
            self._pending_color = None
            self._place(dict(pending))
            self._pending_area = None
            self.pal_hint.config(text=self._pal_hint_text(), fg=MUTED)
            self.bind("<Escape>", lambda e: self._close())
            return
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
        # 곡률도 메인 창과 같다 (RoundTile 머리말 — 같은 물건은 같은 모양이어야
        # 같은 물건으로 읽힌다). highlight* 로 테두리를 바꾸던 기존 코드는
        # RoundTile 이 그대로 받아 준다.
        tile = RoundTile(parent, bg=bg, radius=theme.RADIUS["ctl"],
                         zone_bg=parent.cget("bg"),
                         highlightbackground=ACCENT if selected else BORDER,
                         highlightthickness=2 if selected else 1)
        tile.pack_propagate(False)
        # 아이콘을 이름 **위**에 얹는다 — 메인 창 블럭과 같은 규칙 (H안 2026-07-29).
        # 여기가 그 블럭의 미리보기이므로 얼굴이 다르면 다른 물건으로 보인다.
        # 종류별 배경색이 없어진 뒤로는 이것이 유일한 종류 표시이기도 하다 —
        # 빼먹으면 이 창의 칸이 전부 똑같은 흰 네모가 된다.
        text = self._tile_text(blk, span)
        two_lines = "\n" in text
        # 개인 팔레트 탭에는 아이콘을 안 그린다 — 메인 창이 그렇기 때문이다
        # (2026-07-30). 여기서만 아이콘을 얹으면 **미리보기가 거짓말을 한다**:
        # 설정 창에서는 기호가 보이는데 정작 팔레트에는 없다.
        icon = (theme.block_icon(blk)
                if self._cur_tab_name() == palette.MAIN_TAB else None)
        # 2026-07-30: 아이콘·이름 크기를 메인 창과 **완전히 맞춘다** (사용자
        # 지적 — "두개가 동일하게 보여야하는거고 메인 위젯 포멧을 그대로
        # 팔레트 설정에서 따라하도록"). app._BLOCK_ICON_FS/_2LINE 및
        # size = 8 if two_lines else 9 와 같은 값이다. 순환 임포트를 피해
        # 값만 복제한다 — 나중에 app.py 쪽 값이 바뀌면 여기도 같이 바꿔야 한다.
        parts = []
        if icon:
            icon_fg = (theme.colors()["muted"]
                       if theme.text_on(bg) != "#ffffff" else "#ffffff")
            parts.append(tk.Label(
                tile, text=icon, bg=bg, fg=icon_fg,
                font=(FONT, theme.fs(13 if two_lines else 16))))
            parts[-1].pack(fill="x", pady=(3, 0))
        # 글자색은 배경 밝기에 맞춰 정한다 — 어두운 색을 골라도 읽히게 (제안 18)
        # 아이콘이 있으면 가운데, 없으면 예전처럼 왼쪽에 붙인다
        # (RoundButton.align 과 같은 규칙).
        lab = tk.Label(tile, text=text, bg=bg,
                       fg=theme.text_on(bg),
                       anchor="center" if icon else "w",
                       justify="center" if icon else "left",
                       font=(FONT, theme.fs(8 if two_lines else 9)))
        lab.pack(expand=True, fill="both",
                 padx=(0 if icon else TILE_TEXT_PAD, 0))
        parts.append(lab)
        self._tiles[i] = tile
        for w in [tile] + parts:
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
            tk.Label(tip, text=text, font=(FONT, theme.fs(FS["sub"])), bg="#333333",
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
            # 자유 색 고르개(colorchooser)를 없앴다 (2026-07-27 디자인 개편):
            # 네온 초록 같은 원색이 골라져 화면에서 제일 시끄러운 것이 내용이
            # 아니라 장식이 됐다. 채도를 맞춰 둔 12색 중에서만 고른다.
            dlg = _PastelDialog(self, blk.get("color"))
            self.wait_window(dlg)
            if not dlg.result:
                return
            blk["color"] = dlg.result
        palette.update_block(self.sel_tab, idx, blk)
        self._render_blocks()
        self._notify()

    def _tile_text(self, blk, span=1):
        r"""칸 수에 맞춰 자른다 — 메인 창(app._fit_label)과 **완전히 같은 규칙**.

        2026-07-30: 메인 창은 표시 폭(동아시아 너비) 기준으로 자르는데
        (공백·숫자는 한글의 절반 폭) 여기는 글자 **수**로만 재고 있었다.
        그래서 '마크다운 변환'처럼 공백이 낀 이름이 메인 창에서는 안 잘리는데
        이 미리보기에서는 잘렸다 — 두 화면이 다른 물건처럼 보이는 원인이었다
        (사용자 지적). app._fit_label 을 그대로 옮겨 쓴다(순환 임포트를 피해
        복제하되, 갈라지지 않도록 폰트 크기도 app._BLOCK_ICON_FS 와 맞춘다
        — _make_tile 참고).
        """
        import unicodedata

        def w(ch):
            return 1.0 if unicodedata.east_asian_width(ch) in ("W", "F") else 0.5

        cell = self._cell_px(self._cur_cols())
        char_px = theme.fs(FS["body"]) * 4 / 3     # 메인 창과 같은 기준(body=9)
        width = cell * span + CELL_GAP * (span - 1) - TILE_TEXT_PAD // 2
        limit = max(2.0, width / max(1, char_px))

        lines = (self._block_label(blk) or "").split("\n")
        out = []
        for line in lines:
            if sum(w(c) for c in line) <= limit:
                out.append(line)
                continue
            acc, kept = 0.0, []
            for ch in line:
                if acc + w(ch) > limit - 1.0:      # 말줄임표(…)도 한 자
                    break
                acc += w(ch)
                kept.append(ch)
            out.append("".join(kept) + "…")
        return "\n".join(out)

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
        how = self._ask_delete_scope(blocks[self.sel_block])
        if how == "cancel":
            return
        if how == "block":
            palette.delete_block(self.sel_tab, self.sel_block)
        self.sel_block = None
        self._render_blocks()
        self._notify()

    # 라이브러리 분류 ← 블럭 타입 (물감 보관함까지 지울지 물어보는 데 쓴다)
    _REF_CATS = {"template": "템플릿", "form": "양식"}

    def _ask_delete_scope(self, blk):
        r"""블럭을 지울 때 **물감 보관함의 원본까지** 지울지 묻는다 (2026-07-27).

        팔레트에서 지우는 것은 '자리에서 치우는' 일이라 물감 자체는 남는다.
        그걸 모르면 물감 설정에 안 쓰는 물감이 조용히 쌓이므로 한 번 묻는다.
        반환: "block"(자리만 치움) / "library"(원본까지 지움) / "cancel".
        "library" 면 호출한 쪽은 delete_block 을 또 부르면 안 된다 —
        library._purge_palette_refs 가 그 물감을 가리키던 블럭을 이미 모두
        걷어냈기 때문에, 인덱스로 한 번 더 지우면 엉뚱한 블럭이 사라진다.
        """
        cat = self._REF_CATS.get(blk.get("type"))
        ref = blk.get("ref")
        if not cat or not ref:
            return "block"
        it = library.find_by_id(cat, ref)
        if not it:
            return "block"          # 이미 지워진 물감 — 물어볼 것이 없다
        others = max(0, library.count_palette_refs(cat, ref) - 1)
        msg = "팔레트에서 치워도 물감은 창고에 남습니다."
        if others:
            msg += (f"\n⚠ 이 물감은 다른 자리 {others}곳에도 놓여 있습니다 — "
                    "물감을 없애면 그 블럭들도 함께 사라집니다.")
        choice = messagebox.ask_choice(
            self, f"'{it['name']}' 을(를) 어떻게 지울까요?", msg,
            [("물감까지 없애기", "library", "danger"),
             ("이 자리에서만 치우기", "block", "primary")])
        if choice != "library":
            return choice or "cancel"
        # 되돌릴 수 없는 길 — 한 번 더 묻는다
        if not messagebox.askyesno(
                "정말 없앨까요?",
                f"'{it['name']}' 물감을 창고에서 완전히 지웁니다.\n"
                "조각 파일까지 지워지며 되돌릴 수 없습니다.",
                default="no", icon="warning", parent=self):
            return "cancel"
        library.delete_item(cat, ref)
        return "library"

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
        if self._edit_ctx is not None:
            # 고치는 중에 창을 닫으면 — 취소로 마무리해 한글 창·topmost 를
            # 되돌린 뒤 닫는다 (도킹된 한글이 판 자리에 버려지지 않게)
            self._finish_content_edit(save=False)
        self._notify(immediate=True)     # 미룬 반영이 있으면 지금 마저 한다
        # bind_all 은 창이 죽어도 앱 전역에 남는다 (2026-07-28) — 안 걷으면
        # 파괴된 위젯을 잡는 유령 핸들러가 이벤트마다 예외를 삼키며 돈다.
        for seq in ("<MouseWheel>", "<Control-z>", "<Control-Z>",
                    "<Control-y>", "<Control-Y>"):
            try:
                self.unbind_all(seq)
            except Exception:
                pass
        # 창을 **흐려지며** 닫는다 (사용자 지적 2026-07-28: "팔레트 설정을 끌
        # 때에도 깜빡거림이 있습니다"). 큰 창이 한 프레임에 사라지면 그 뒤에
        # 있던 화면이 갑자기 드러나 번쩍인다 — 120ms 면 눈이 '사라졌다'가 아니라
        # '접혔다'로 읽는다. destroy 는 전환이 끝난 뒤 한 번만 (ui_fx.fade_close).
        ui_fx.fade_close(self, ms=120)

    def _notify(self, items_changed=False, immediate=False):
        r"""팔레트 변경을 창고·메인 창에 알린다 (2026-07-28 부분 갱신).

        여태 블럭 하나만 옮겨도 ①창고 통째 재생성 ②메인 창 통째 재렌더가
        즉시 돌았다 — 편집이 잦은 창에서 이것이 버벅임의 큰 몫이었다.
        이제 창고는 배치 색만 다시 칠하고(목록이 바뀐 때만 통째로), 메인 창
        반영은 400ms 모아 한 번만 한다. 창을 닫을 때는 immediate 로 마저 쏜다.
        """
        if items_changed:
            self._refresh_store()        # 물감 목록 자체가 바뀜 — 통째로
        else:
            try:
                self.store.refresh_states()
            except Exception as e:
                applog.exc("창고 상태 칠하기 실패 — 통째로 다시 그림", e)
                self._refresh_store()
        if not self.on_saved:
            return
        if self._notify_job is not None:
            try:
                self.after_cancel(self._notify_job)
            except Exception:
                pass
            self._notify_job = None
        if immediate:
            self.on_saved()
            return

        def fire():
            self._notify_job = None
            self.on_saved()
        self._notify_job = self.after(400, fire)


class _PastelDialog(tk.Toplevel):
    r"""블럭 색 고르기 — theme.PASTELS 12색 격자 (2026-07-27).

    글자색은 고르게 하지 않는다. 배경마다 읽히는 짝(theme.text_on)이 정해져
    있어서, 사용자가 대비를 고민할 일이 없어야 한다.
    """

    def __init__(self, master, current=None):
        super().__init__(master)
        self.result = None
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(master)
        tk.Label(self, text="블럭 색", font=(FONT, theme.fs(theme.FS["head"]), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=theme.SP["l"],
                                      pady=(theme.SP["m"], 2))
        tk.Label(self, text="어느 색을 골라도 화면이 안 깨지도록 맞춰 둔 12색입니다.",
                 font=(FONT, theme.fs(theme.FS["sub"])), bg=BG, fg=MUTED
                 ).pack(anchor="w", padx=theme.SP["l"])
        grid = tk.Frame(self, bg=BG, padx=theme.SP["l"], pady=theme.SP["m"])
        grid.pack()
        cur = (current or "").lower()
        for i, (name, hexv) in enumerate(theme.pastels()):
            sel = (hexv.lower() == cur)
            cell = tk.Frame(grid, bg=hexv, cursor="hand2",
                            highlightbackground=ACCENT if sel else BORDER,
                            highlightthickness=2 if sel else 1)
            cell.grid(row=i // 6, column=i % 6, padx=3, pady=3)
            lbl = tk.Label(cell, text=name, bg=hexv, fg=theme.text_on(hexv),
                           font=(FONT, theme.fs(theme.FS["caption"])),
                           width=5, height=2)
            lbl.pack()
            for w in (cell, lbl):
                w.bind("<Button-1>", lambda e, v=hexv: self._pick(v))
        foot = tk.Frame(self, bg=BG, padx=theme.SP["l"], pady=(0, theme.SP["m"]))
        foot.pack(fill="x")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        screens.place_beside(self, master, follow=False)
        self.grab_set()
        ui_fx.attach_all(self)

    def _pick(self, hexv):
        self.result = hexv
        self.destroy()


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
                    fg="white", radius=theme.RADIUS["ctl"], font=(FONT, theme.fs(FS["head"]), "bold"),
                    zone_bg=BG).fit(pad_x=14, pad_y=10,
                                    min_w=260).pack(fill="x")
        tk.Label(body, text="한글에서 표·영역을 선택해두고 누르세요. 등록과 배치가 한 번에.",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED).pack(anchor="w", pady=(3, 10))

        # RoundButton 은 state=disabled 가 없어 이 버튼만 tk.Button 을 유지한다
        state = "normal" if has_registered else "disabled"
        tk.Button(body, text="📚  이미 등록된 템플릿에서 고르기",
                  command=lambda: self._pick("registered"),
                  font=(FONT, theme.fs(FS["head"])), bg=CARD, fg=TEXT, bd=1, pady=8,
                  cursor="hand2", state=state).pack(fill="x")
        if not has_registered:
            tk.Label(body, text="(아직 등록된 템플릿이 없습니다)",
                     font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED).pack(anchor="w", pady=(3, 0))

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
        tk.Label(self, text=title, font=(FONT, theme.fs(FS["head"]), "bold"), bg=BG, fg=TEXT).pack(
            anchor="w", padx=16, pady=(12, 6))
        self.var = tk.StringVar(value=options[0])
        ttk.Combobox(self, textvariable=self.var, values=options, width=24,
                     state="readonly", font=(FONT, theme.fs(FS["head"]))).pack(padx=16)
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
                 font=(FONT, theme.fs(FS["head"]), "bold"), bg=BG, fg=TEXT).pack(
                 anchor="w", padx=16, pady=(12, 8))
        body = tk.Frame(self, bg=BG, padx=16)
        body.pack(fill="x")

        self.font_var = tk.StringVar(value=fmt["font"])
        self.size_var = tk.StringVar(value=str(fmt["size_pt"]))
        self.ls_var = tk.StringVar(value=str(fmt["line_spacing"]))
        self.sp_var = tk.StringVar(value=str(fmt["spacing"]))

        rows = [("글꼴", ttk.Combobox(body, textvariable=self.font_var, width=16,
                                     values=func_catalog.COMMON_FONTS, font=(FONT, theme.fs(FS["body"])))),
                ("크기(pt)", tk.Entry(body, textvariable=self.size_var, width=8,
                                     font=(FONT, theme.fs(FS["body"])), relief="solid", bd=1)),
                ("줄간격(%)", tk.Entry(body, textvariable=self.ls_var, width=8,
                                     font=(FONT, theme.fs(FS["body"])), relief="solid", bd=1)),
                ("자간", tk.Entry(body, textvariable=self.sp_var, width=8,
                                font=(FONT, theme.fs(FS["body"])), relief="solid", bd=1))]
        for i, (lbl, w) in enumerate(rows):
            tk.Label(body, text=lbl, font=(FONT, theme.fs(FS["body"])), bg=BG, fg=TEXT).grid(
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
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED, justify="left").pack(
            anchor="w", padx=16, pady=(0, 8))

        self.box = tk.Text(self, width=24, height=3, font=(FONT, theme.fs(11)),
                           relief="solid", bd=1, wrap="none")
        self.box.pack(padx=16)
        self.box.insert("1.0", caption or "")
        self.box.focus_set()
        self.box.bind("<Control-Return>", lambda e: self._ok())

        tk.Label(self, text=f"지금 이름: {current!r}", font=(FONT, theme.fs(FS["sub"])),
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
                 font=(FONT, theme.fs(FS["head"]), "bold"), bg=BG, fg=TEXT).pack(
            anchor="w", padx=SP["l"], pady=(SP["m"], 2))
        tk.Label(self, text="고르면 그 도구를 만드는 창이 이어서 열립니다.",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED).pack(
            anchor="w", padx=SP["l"], pady=(0, SP["s"]))

        # 항목을 RoundButton 으로 그리지 않는다 (사용자 지적 2026-07-27:
        # "레이아웃이 맞지 않고 내용이 다 안 보인다"). RoundButton 은 Canvas 에
        # 글자를 **가운데 기준**으로 하나만 그려서, '이름 + 설명' 두 줄을
        # 왼쪽 맞춤으로 놓을 수 없고 폭도 글자 길이에 맞춰 잘렸다.
        # 여기서는 Frame + Label 둘로 쌓아 왼쪽 맞춤과 자동 줄바꿈을 얻는다.
        body = tk.Frame(self, bg=BG, padx=SP["l"])
        body.pack(fill="x")
        for key, name, desc in self._TOOLS:
            self._tool_row(body, key, name, desc)

        # 버튼 색 — 기본(종류별 색) 또는 12색 파스텔에서 고르기
        self.color = None
        crow = tk.Frame(self, bg=BG, padx=SP["l"])
        crow.pack(fill="x", pady=(SP["m"], 0))
        tk.Label(crow, text="버튼 색", font=(FONT, theme.fs(FS["sub"])), bg=BG,
                 fg=MUTED).pack(anchor="w")
        sw_box = tk.Frame(crow, bg=BG)
        sw_box.pack(fill="x", pady=(SP["xs"], 0))
        self._color_lbl = tk.Label(sw_box, text="기본",
                                   font=(FONT, theme.fs(FS["sub"])),
                                   bg=CARD, fg=TEXT, relief="solid", bd=1,
                                   padx=SP["s"], pady=2, cursor="hand2")
        self._color_lbl.grid(row=0, column=0, rowspan=2, padx=(0, SP["s"]),
                             sticky="ns")
        self._color_lbl.bind("<Button-1>", lambda e: self._set_color(None))
        # 12색을 6개씩 두 줄로 — 한 줄로 늘어놓으면 창 폭을 끌고 다닌다
        for i, (nm, hexv) in enumerate(theme.pastels()):
            # 견본은 넉넉해야 색이 읽힌다 — 파스텔은 옅어서 작으면 전부
            # 흰색으로 보인다 (실측 2026-07-27)
            sw = tk.Label(sw_box, text=" ", bg=hexv, relief="solid", bd=1,
                          cursor="hand2", width=4, height=1)
            sw.grid(row=i // 6, column=1 + (i % 6), padx=2, pady=2)
            sw.bind("<Button-1>", lambda e, v=hexv: self._set_color(v))
            _tip(sw, nm)

        _dialog_btn(self, "취소", self.destroy).pack(anchor="e",
                                                   padx=SP["l"], pady=SP["m"])

        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        screens.place_beside(self, master, follow=False)
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    _ROW_W = 360        # 항목 줄 폭 — 설명이 잘리지 않게 넉넉히

    def _tool_row(self, parent, key, name, desc):
        """이름(굵게) + 설명(흐리게) 두 줄짜리 항목. 왼쪽 맞춤 · 호버 반응."""
        row = tk.Frame(parent, bg=CARD, highlightbackground=BORDER,
                       highlightthickness=1, cursor="hand2")
        row.pack(fill="x", pady=2)
        nm = tk.Label(row, text=name, font=(FONT, theme.fs(FS["body"]), "bold"),
                      bg=CARD, fg=TEXT, anchor="w")
        nm.pack(fill="x", padx=SP["m"], pady=(SP["s"] - 2, 0))
        ds = tk.Label(row, text=desc, font=(FONT, theme.fs(FS["sub"])),
                      bg=CARD, fg=MUTED, anchor="w", justify="left",
                      wraplength=self._ROW_W)
        ds.pack(fill="x", padx=SP["m"], pady=(0, SP["s"] - 2))
        parts = (row, nm, ds)
        for w in parts:
            w.bind("<Button-1>", lambda e, k=key: self._pick(k))
            w.bind("<Enter>", lambda e: [x.config(bg=ACCENT_SOFT) for x in parts])
            w.bind("<Leave>", lambda e: [x.config(bg=CARD) for x in parts])
        return row

    def _set_color(self, hexv):
        """고른 색을 보여준다. hexv=None 이면 '기본'(블럭 종류별 색)."""
        self.color = hexv
        self._color_lbl.config(text="기본" if not hexv else " ",
                               bg=hexv or CARD)

    def _pick(self, key):
        self.result = key
        self.destroy()


def open_settings(master, on_saved=None):
    win = SettingsWindow(master, on_saved=on_saved)
    ui_fx.attach_all(win)               # 창 안 모든 버튼에 호버 보간
    return win
