# -*- coding: utf-8 -*-
r"""도움말 창 — 왼쪽 기능 목록 + 오른쪽 설명 (2026-07-25, 기획 3번).

'?' 버튼의 도움말 항목이 연다. 내용은 help_content.TOPICS 에서 온다 —
설명을 고칠 일이 생기면 그 파일만 고치면 된다.
"""

import tkinter as tk

from hwp_palette.core import appinfo
from hwp_palette.ui import help_content
from hwp_palette.core import screens                     # 창 자리 규칙 (메인 창 옆)
from hwp_palette.design import theme
from hwp_palette.design import ui_fx                     # 제자리에서 번지며 나타나기 (reveal)
from hwp_palette.design.roundbtn import RoundButton

_C = theme.colors()
BG = _C["bg"]
CARD = _C["card"]
ACCENT = _C["accent"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
SUBBG = _C["subbg"]
FONT = theme.FONT

# 왼쪽 목록 폭 — 150 이던 시절 "팔레트 통째로 주고받기" 같은 긴 제목이
# 잘렸다 (2026-07-31). 제목도 짧게 고쳤지만 폭도 한 뼘 넓혀 여유를 둔다.
_TOPIC_W = 170


class HelpWindow(tk.Toplevel):

    def __init__(self, master):
        super().__init__(master)
        # 다 만들 때까지 숨긴다 (2026-07-31, SettingsWindow 와 같은 이유) —
        # 기본 자리에 깜빡 그려졌다가 place_beside 로 건너오는 것이 보였다.
        self.withdraw()
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._btns = []
        self._cur = 0

        tk.Label(self, text="도움말", font=(FONT, theme.fs(12), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(14, 8))
        self.bind("<Escape>", lambda e: self.destroy())      # Esc 로 닫기

        main = tk.Frame(self, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        main.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        left = tk.Frame(main, bg=CARD, width=_TOPIC_W)
        left.pack(side="left", fill="y", padx=(8, 0), pady=8)
        left.pack_propagate(False)
        tk.Frame(main, bg=BORDER, width=1).pack(side="left", fill="y")

        # 본문 — 읽기 전용 Text (복사가 되도록 Label 대신 Text)
        right = tk.Frame(main, bg=SUBBG)
        right.pack(side="left", fill="both", expand=True)
        self._body = tk.Text(right, width=52, height=22,
                             font=(FONT, theme.fs(9)), bg=SUBBG, fg=TEXT,
                             relief="flat", wrap="word", padx=14, pady=12,
                             cursor="arrow")
        self._body.pack(fill="both", expand=True)

        for i, (title, _) in enumerate(help_content.TOPICS):
            b = RoundButton(left, text=title,
                            command=lambda idx=i: self._show(idx),
                            bg=CARD, fg=TEXT, radius=7,
                            font=(FONT, theme.fs(9)), outline="",
                            zone_bg=CARD, justify="left")
            b.fit(pad_x=10, pad_y=5, min_w=_TOPIC_W - 8)
            b.pack(anchor="w", pady=1)
            self._btns.append(b)

        self._show(0)
        self.update_idletasks()          # 자리 계산 전에 요청 크기를 굳힌다
        ui_fx.reveal(self, place=lambda: screens.place_beside(self, master))

    def _show(self, idx):
        self._cur = idx
        for i, b in enumerate(self._btns):
            on = i == idx
            b.retint(bg=ACCENT if on else CARD, fg="white" if on else TEXT)
        title, body = help_content.TOPICS[idx]
        self._body.config(state="normal")
        self._body.delete("1.0", "end")
        self._body.insert("1.0", body)
        self._body.config(state="disabled")    # 읽기 전용 (복사는 가능)


def open_help(master):
    return HelpWindow(master)
