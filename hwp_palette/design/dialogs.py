# -*- coding: utf-8 -*-
r"""알림·확인 대화상자 — 프로그램과 같은 얼굴 (2026-07-27 디자인 개편).

왜 만들었나:
    여태 tkinter.messagebox 를 썼다. 그러면 **윈도우 기본 회색 창**이 불쑥
    뜬다 — 글꼴도 모서리도 버튼 모양도 프로그램과 전혀 다르다. 창 하나 뜰
    때마다 "여기까지가 이 프로그램" 이라는 느낌이 깨졌다. 알림은 드물게
    보는 화면이 아니라 **뭔가 결정할 때마다** 보는 화면이라 값이 크다.

어떻게 쓰나 — messagebox 와 **같은 이름·같은 인자**다:

    from hwp_palette.design import dialogs as messagebox        # 한 줄만 바꾸면 화면이 바뀐다
    messagebox.showinfo("제목", "내용", parent=self)
    if messagebox.askyesno("제목", "내용", parent=self): ...

messagebox 의 default·icon 인자도 받는다 (무시하지 않고 뜻을 옮긴다):
    default="no"      → 기본 단추를 '아니오' 쪽으로
    icon="warning"    → 위험한 결정임을 색으로 표시

규칙 (Emil Kowalski, emil-design-eng):
  · 기본 단추(Enter)는 **언제나 안전한 쪽**. 지우기·되돌릴 수 없는 것은
    기본이 되지 않는다.
  · Esc 는 언제나 취소. 창을 닫는 방법이 하나여야 손이 헤매지 않는다.
  · 등장 애니메이션 없음 — 결정을 기다리게 하는 움직임은 방해다.
"""

import tkinter as tk

from hwp_palette.core import screens
from hwp_palette.design import theme
from hwp_palette.design import ui_fx
from hwp_palette.design.roundbtn import RoundButton

FONT = theme.FONT
SP = theme.SP
FS = theme.FS

# 위험을 말하는 빨강 — theme 의 알림 색(error)과 같은 계열
DANGER = "#9b1c1c"


def _c():
    return theme.colors()


class _Dialog(tk.Toplevel):
    r"""제목 한 줄 + 설명 + 단추들. 결과는 self.result 에 담긴다.

    buttons: [(라벨, 값, 종류)] — 종류는 "primary" | "normal" | "danger".
      화면에는 **왼쪽부터 danger, 오른쪽 끝에 primary** 로 놓는다.
      위험한 길이 손이 먼저 가는 자리(오른쪽 아래)에 있으면 안 된다.
    """

    def __init__(self, master, title, message, buttons, cancel=None,
                 danger=False):
        super().__init__(master)
        c = _c()
        self.result = cancel
        self._cancel = cancel
        self.title(theme_title())
        self.configure(bg=c["bg"])
        self.resizable(False, False)
        try:
            self.transient(master)
        except tk.TclError:
            pass                       # 부모가 없거나 이미 파괴됨 — 독립 창으로
        body = tk.Frame(self, bg=c["bg"], padx=SP["l"], pady=SP["m"])
        body.pack(fill="both", expand=True)
        tk.Label(body, text=title, font=(FONT, theme.fs(FS["head"]), "bold"),
                 bg=c["bg"], fg=DANGER if danger else c["text"],
                 justify="left", anchor="w", wraplength=380).pack(anchor="w")
        if message:
            tk.Label(body, text=message, font=(FONT, theme.fs(FS["sub"])),
                     bg=c["bg"], fg=c["muted"], justify="left", anchor="w",
                     wraplength=380).pack(anchor="w", pady=(SP["xs"], 0))

        foot = tk.Frame(self, bg=c["bg"], padx=SP["l"], pady=SP["m"])
        foot.pack(fill="x")
        primary = None
        # side="right" 는 **먼저 담은 것이 가장 오른쪽**이라, 목록을 뒤집어
        # 담아야 마지막(기본) 단추가 오른쪽 끝에 온다. 손이 가장 먼저 닿는
        # 자리를 기본 단추가 차지해야 한다.
        for label, value, kind in reversed(buttons):
            if kind == "danger":
                # 되돌릴 수 없는 길 — 단추가 아니라 밑줄 글자로, 왼쪽 끝에.
                # 크기와 자리로 "이건 함부로 누르는 것이 아니다"를 말한다.
                w = tk.Label(foot, text=label, bg=c["bg"], fg=DANGER,
                             font=(FONT, theme.fs(FS["sub"]), "underline"),
                             cursor="hand2", takefocus=1)
                w.pack(side="left")
                w.bind("<Button-1>", lambda e, v=value: self._done(v))
                w.bind("<Return>", lambda e, v=value: self._done(v))
                w.bind("<space>", lambda e, v=value: self._done(v))
                continue
            btn = RoundButton(
                foot, text=label, command=lambda v=value: self._done(v),
                bg=c["accent"] if kind == "primary" else c["yellow"],
                fg="#ffffff" if kind == "primary" else c["text"],
                radius=theme.RADIUS["ctl"],
                font=(FONT, theme.fs(FS["body"]),
                      "bold" if kind == "primary" else "normal"),
                outline="", zone_bg=c["bg"])
            btn.fit(pad_x=SP["m"], pad_y=SP["xs"] + 2)
            btn.pack(side="right", padx=(SP["s"], 0))
            if kind == "primary" and primary is None:
                primary = btn

        self.bind("<Return>", lambda e: self._enter())
        self.bind("<Escape>", lambda e: self._done(self._cancel))
        self.protocol("WM_DELETE_WINDOW", lambda: self._done(self._cancel))
        self._primary = primary
        self.update_idletasks()
        screens.place_beside(self, master, follow=False)
        try:
            self.grab_set()
            if primary is not None:
                primary.focus_set()
        except tk.TclError:
            pass
        ui_fx.attach_all(self)

    def _enter(self):
        if self._primary is not None:
            self._primary._invoke()

    def _done(self, value):
        self.result = value
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def theme_title():
    """창 제목표시줄 문구 — appinfo 를 늦게 읽어 순환 참조를 피한다."""
    try:
        from hwp_palette.core import appinfo
        return appinfo.WINDOW_TITLE
    except Exception:
        return "HwpPalette"


def _ask(parent, title, message, buttons, cancel=None, danger=False):
    master = parent or tk._get_default_root()
    if master is None:                 # Tk 없는 환경(테스트) — 조용히 취소값
        return cancel
    dlg = _Dialog(master, title, message, buttons, cancel=cancel,
                  danger=danger)
    master.wait_window(dlg)
    return dlg.result


# ── messagebox 호환 이름들 ─────────────────────────────
def showinfo(title, message=None, parent=None, **_kw):
    _ask(parent, title, message, [("확인", True, "primary")], cancel=True)
    return "ok"


def showwarning(title, message=None, parent=None, **_kw):
    _ask(parent, title, message, [("확인", True, "primary")], cancel=True)
    return "ok"


def showerror(title, message=None, parent=None, **_kw):
    _ask(parent, title, message, [("확인", True, "primary")], cancel=True,
         danger=True)
    return "ok"


def askyesno(title, message=None, parent=None, default=None, icon=None, **_kw):
    r"""예/아니오. 반환은 True/False.

    default="no" 면 **아니오가 기본 단추**가 된다 — 지우기처럼 되돌릴 수 없는
    물음에서 Enter 가 실수로 '예'를 누르지 않게 하는 장치다.
    """
    danger = (icon == "warning") or (default == "no")
    if default == "no":
        buttons = [("예", True, "normal"), ("아니오", False, "primary")]
    else:
        buttons = [("아니오", False, "normal"), ("예", True, "primary")]
    return bool(_ask(parent, title, message, buttons, cancel=False,
                     danger=danger))


def askyesnocancel(title, message=None, parent=None, default=None, icon=None,
                   **_kw):
    """예/아니오/취소. 반환은 True/False/None (messagebox 와 같다)."""
    return _ask(parent, title, message,
                [("취소", None, "normal"), ("아니오", False, "normal"),
                 ("예", True, "primary")],
                cancel=None, danger=(icon == "warning"))


def askokcancel(title, message=None, parent=None, **_kw):
    return bool(_ask(parent, title, message,
                     [("취소", False, "normal"), ("확인", True, "primary")],
                     cancel=False))


# ── 이 프로그램만의 추가 형태 ──────────────────────────
def field(parent, textvariable=None, width=None, **kw):
    r"""입력칸 — 초점이 오면 테두리가 강조색 2px 로 바뀐다 (포커스 링).

    왜 필요한가: 여태 Entry 가 `relief="solid", bd=1` 로 흩어져 있어 **키보드로
    옮겨 다닐 때 지금 어디에 있는지 보이지 않았다.** 표 창처럼 칸이 여럿인
    화면에서는 이게 곧 "몇 번째 칸을 채우는 중인지 모르겠다"가 된다.

    Tk 는 Entry 테두리 색을 직접 못 바꾼다 — 그래서 Frame 으로 한 겹 감싸고
    그 Frame 의 highlight 를 쓴다. 반환은 (감싼 Frame, Entry) 다.
    """
    c = _c()
    box = tk.Frame(parent, bg=c["card"], highlightbackground=c["border"],
                   highlightcolor=c["accent"], highlightthickness=1)
    ent = tk.Entry(box, textvariable=textvariable, relief="flat", bd=0,
                   bg=c["card"], fg=c["text"], insertbackground=c["text"],
                   font=(FONT, theme.fs(FS["body"])),
                   **({"width": width} if width else {}), **kw)
    ent.pack(fill="both", expand=True, padx=SP["s"] - 2, pady=SP["xs"])
    ent.bind("<FocusIn>", lambda e: box.config(highlightthickness=2,
                                               highlightbackground=c["accent"]))
    ent.bind("<FocusOut>", lambda e: box.config(highlightthickness=1,
                                                highlightbackground=c["border"]))
    return box, ent


def style_scrollbars(widget):
    r"""창 안 스크롤바를 가는 회색 막대로 (ttk 스타일).

    윈도우 기본 스크롤바는 화살표 단추가 달린 옛 모양이라, 다른 것을 아무리
    다듬어도 그 하나가 화면을 옛날 프로그램으로 만든다.
    """
    from tkinter import ttk
    c = _c()
    try:
        style = ttk.Style(widget)
        style.theme_use("clam")     # 색을 바꿀 수 있는 유일한 기본 테마
        for orient in ("Vertical", "Horizontal"):
            style.configure(f"App.{orient}.TScrollbar",
                            background=c["border"], troughcolor=c["bg"],
                            bordercolor=c["bg"], arrowcolor=c["bg"],
                            arrowsize=1, relief="flat", borderwidth=0)
            style.map(f"App.{orient}.TScrollbar",
                      background=[("active", c["muted"])])
        return True
    except Exception:
        return False                # 스타일을 못 바꿔도 스크롤은 된다


def ask_choice(parent, title, message, choices, cancel_label="취소"):
    r"""단추 여러 개 중 하나 고르기 — 예/아니오로 안 나뉘는 결정용.

    choices: [(라벨, 값, 종류)] — 종류는 "primary" | "normal" | "danger".
    삭제 범위 묻기('자리에서만 치우기' vs '물감까지 없애기')처럼 선택지가
    셋 이상인 자리에서 쓴다. 예/아니오로 우겨넣으면 단추 이름이 무엇을 하는지
    말해 주지 못한다.
    """
    return _ask(parent, title, message,
                list(choices) + [(cancel_label, None, "normal")], cancel=None)
