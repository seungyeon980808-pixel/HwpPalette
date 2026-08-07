# -*- coding: utf-8 -*-
r"""자체 입력 부품 — 체크 · 수치 칸 (2026-08-01, 피드백 030 · 범위 ②).

왜 만들었나: 서식 만들기 창이 `tk.Checkbutton`(윈도우 기본 네모)과
`ttk.Spinbox` 기본 룩을 그대로 써서 프로그램의 다른 창과 컨셉이 안 맞았다.
dialogs.py 가 윈도우 기본 대화상자를 몰아낼 때 세운 원칙 그대로다:

    "창 하나 뜰 때마다 '여기까지가 이 프로그램' 이라는 느낌이 깨졌다."

한 번 만들어 두면 이 창 말고 다른 창(문서 해체의 체크 등)도 같은 얼굴이 된다.
"""

import tkinter as tk

from hwp_palette.design import theme

def _c():
    return theme.colors()


class Check(tk.Canvas):
    r"""둥근 네모 체크 — 켜지면 강조색 바탕에 ✓ (앱의 파랑·곡률을 쓴다).

    BooleanVar 를 그대로 받아 기존 코드의 var.get()/set() 이 다 통한다.
    라벨은 붙이지 않는다 — 호출부가 제 글자 위계(FS)로 옆에 단다.
    """

    def __init__(self, parent, variable, command=None, size=None):
        self._size = size or max(14, theme.fs(11))
        super().__init__(parent, width=self._size, height=self._size,
                         bg=parent.cget("bg"), highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.var = variable
        self._command = command
        self.bind("<ButtonRelease-1>", lambda e: self.toggle())
        self.bind("<space>", lambda e: self.toggle())
        self.bind("<Return>", lambda e: self.toggle())
        # 밖에서 var.set() 해도 그림이 따라온다 (한글에서 가져오기 등)
        self._trace = variable.trace_add("write", lambda *_: self._redraw())
        self.bind("<Destroy>", self._untrace, add="+")
        self._redraw()

    def _untrace(self, _e=None):
        try:
            self.var.trace_remove("write", self._trace)
        except Exception:
            pass

    def toggle(self):
        self.var.set(not self.var.get())
        if self._command:
            self._command()

    def _redraw(self):
        if not self.winfo_exists():
            return
        self.delete("all")
        s = self._size
        on = bool(self.var.get())
        r = min(theme.RADIUS["ctl"], s // 3)
        # 둥근 네모 (RoundButton 과 같은 어법 — 호 넷 + 변)
        self.create_rectangle(1, 1, s - 1, s - 1, width=0,
                              fill=_c()["accent"] if on else _c()["card"])
        self.create_rectangle(1, 1, s - 2, s - 2, width=1,
                              outline=_c()["accent"] if on else _c()["border"])
        if on:
            m = s / 2
            self.create_line(m - s * 0.22, m, m - s * 0.05, m + s * 0.18,
                             m + s * 0.26, m - s * 0.2,
                             fill="white", width=2, capstyle="round",
                             joinstyle="round")


class Spin(tk.Frame):
    r"""수치 칸 + ▲▼ — ttk.Spinbox 대신 앱과 같은 얼굴 (직접 입력도 그대로).

    StringVar 를 받아 기존 저장 코드가 안 바뀐다. 눌러 올리고 내리는 눈금은
    func_catalog.SPIN 과 같은 (lo, hi, step) 을 받는다.
    """

    def __init__(self, parent, textvariable, lo=-999, hi=999, step=1, width=6,
                 font=None):
        super().__init__(parent, bg=parent.cget("bg"))
        self.var = textvariable
        self._lo, self._hi, self._step = lo, hi, step
        f = font or (theme.FONT, theme.fs(9))
        self.entry = tk.Entry(self, textvariable=textvariable, width=width,
                              font=f, relief="solid", bd=1)
        self.entry.pack(side="left", ipady=1)
        col = tk.Frame(self, bg=parent.cget("bg"))
        col.pack(side="left", padx=(2, 0))
        asz = max(7, theme.fs(6))
        for glyph, d in (("▴", +1), ("▾", -1)):
            b = tk.Label(col, text=glyph, font=(theme.FONT, asz),
                         bg=_c()["card"], fg=_c()["muted"], cursor="hand2",
                         padx=3, pady=0,
                         highlightbackground=_c()["border"], highlightthickness=1)
            b.pack()
            b.bind("<ButtonRelease-1>", lambda e, dd=d: self._bump(dd))
            b.bind("<Enter>", lambda e, w=b: w.config(fg=_c()["accent"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=_c()["muted"]))
        self.entry.bind("<Up>", lambda e: self._bump(+1))
        self.entry.bind("<Down>", lambda e: self._bump(-1))

    def _bump(self, d):
        try:
            cur = float(self.var.get() or 0)
        except ValueError:
            cur = 0
        new = min(self._hi, max(self._lo, cur + d * self._step))
        # 정수 눈금이면 정수로 보여준다 — 10.0 은 10 으로
        self.var.set(str(int(new)) if float(new).is_integer() else str(new))
