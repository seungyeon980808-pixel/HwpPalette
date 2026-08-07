# -*- coding: utf-8 -*-
"""첫 실행 안내 (UI 제안 11).

exe 로 남에게 건네면 받는 사람은 이 프로그램이 **무엇을 하는지** 모른다.
버튼만 있는 작은 창이 떠 있을 뿐이라, 한글을 먼저 켜야 한다는 것도,
`\\굵게{내용}` 같은 문법이 있다는 것도 알 길이 없다.

한 번만 뜨고 다시는 안 뜬다. 나중에 다시 보려면 메인 창의 '안내'를 편다.
"""

import tkinter as tk

from hwp_palette.core import applog
from hwp_palette.core import settings
from hwp_palette.design import theme

SEEN_KEY = "onboarded"

STEPS = [
    ("1. 한글을 먼저 켜 두세요",
     "이 프로그램은 이미 열려 있는 한글 문서를 조작합니다.\n"
     "한글이 꺼져 있으면 제목 옆 표시등이 회색이고, 버튼을 눌러도 아무 일도\n"
     "일어나지 않습니다. 한글을 켜면 표시등이 파랗게 바뀝니다."),
    ("2. 글로 써서 서식을 입힙니다",
     "입력창에 이렇게 쓰고 '변환'을 누르면 서식이 적용된 채로 들어갑니다.\n\n"
     "    \\굵게{중요한 부분}\n"
     "    \\크기15{조금 큰 글자}\n"
     "    \\빨강{빨간 글씨}\n\n"
     "명령은 겹쳐 쓸 수 있습니다 →  \\굵게{\\빨강{굵은 빨강}}"),
    ("3. 자주 쓰는 것은 버튼으로",
     "아래쪽 격자가 팔레트입니다. 문자·서식 조합·표 템플릿을 칸에 넣어두고\n"
     "누르면 바로 들어갑니다.\n"
     "'환경설정'에서 빈칸을 끌어 자리를 정하고 무엇을 넣을지 고르면 됩니다."),
    ("4. 알아두면 편한 것",
     "Ctrl+F    이름으로 찾아서 바로 실행\n"
     "Ctrl+1~9  지금 탭의 1~9번째 블럭 실행\n"
     "제목줄     '어둡게' · '크게' 로 화면 모드 전환\n\n"
     "설정과 라이브러리는 자동으로 3벌까지 백업되므로, 잘못 지워도\n"
     "되돌릴 수 있습니다 (환경설정에서 Ctrl+Z)."),
]


def should_show():
    return not bool(settings.get_config_value(SEEN_KEY, False))


def mark_seen():
    settings.set_config_value(SEEN_KEY, True)


class Onboarding(tk.Toplevel):
    """한 장씩 넘겨 보는 안내. 4쪽뿐이라 스크롤은 두지 않는다."""

    def __init__(self, master, font_fn):
        super().__init__(master)
        c = theme.colors()
        self.title("hwp_palette 처음 오셨네요")
        self.configure(bg=c["bg"], padx=18, pady=14)
        self.transient(master)
        self.resizable(False, False)
        self._font = font_fn
        self._i = 0
        self._c = c

        self.head = tk.Label(self, text="", font=font_fn(12, "bold"),
                             fg=c["text"], bg=c["bg"], anchor="w")
        self.head.pack(fill="x")
        self.body = tk.Label(self, text="", font=font_fn(9), fg=c["text"],
                             bg=c["card"], justify="left", anchor="nw",
                             padx=12, pady=10, width=46, height=9)
        self.body.pack(fill="x", pady=(8, 10))

        row = tk.Frame(self, bg=c["bg"])
        row.pack(fill="x")
        self.dots = tk.Label(row, text="", font=font_fn(8), fg=c["muted"],
                             bg=c["bg"])
        self.dots.pack(side="left")
        self.next_btn = tk.Button(row, text="다음", command=self._next,
                                  font=font_fn(9), fg="#ffffff", bg=c["accent"],
                                  activebackground=c["accent"],
                                  activeforeground="#ffffff",
                                  bd=0, padx=14, pady=4, cursor="hand2")
        self.next_btn.pack(side="right")
        tk.Button(row, text="건너뛰기", command=self._close, font=font_fn(8),
                  fg=c["muted"], bg=c["bg"], activebackground=c["border"],
                  bd=0, padx=8, cursor="hand2").pack(side="right", padx=(0, 8))

        self._render()
        self.bind("<Escape>", lambda e: self._close())
        self.bind("<Return>", lambda e: self._next())
        self.next_btn.focus_set()
        # 부모 창 위에 겹쳐 띄운다 — 화면 구석에 뜨면 못 보고 지나친다
        self.update_idletasks()
        x = master.winfo_rootx() - (self.winfo_width() - master.winfo_width()) // 2
        y = master.winfo_rooty() + 40
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.grab_set()

    def _render(self):
        head, body = STEPS[self._i]
        self.head.config(text=head)
        self.body.config(text=body)
        self.dots.config(text=f"{self._i + 1} / {len(STEPS)}")
        self.next_btn.config(text="시작하기" if self._i == len(STEPS) - 1
                             else "다음")

    def _next(self):
        if self._i >= len(STEPS) - 1:
            return self._close()
        self._i += 1
        self._render()

    def _close(self):
        mark_seen()             # 건너뛰어도 다시 띄우지 않는다 — 봤으면 본 것이다
        self.grab_release()
        self.destroy()


def maybe_show(master, font_fn):
    """첫 실행이면 안내를 띄운다. 실패해도 프로그램은 그대로 뜬다."""
    if not should_show():
        return None
    try:
        result = Onboarding(master, font_fn)
        mark_seen()
        return result
    except Exception as e:
        # 조용히 삼키면 안 된다 — exe 로 만들었을 때 안내가 안 뜨는데 아무 흔적도
        # 없어서 원인을 찾는 데 한참 걸렸다(실측). 로그는 남기고 진행만 계속한다.
        applog.exc("첫 실행 안내를 띄우지 못했습니다 — 안내 없이 시작합니다", e)
        return None
