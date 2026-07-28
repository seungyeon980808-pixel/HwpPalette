# -*- coding: utf-8 -*-
r"""접었다 펴는 안내 (2026-07-28).

왜 만들었나 (사용자 지적):
    "설명을 조금 더 자세하게 할 필요가 있습니다. 어떻게 하면 어떻게 나온다라는
    느낌이 있어야 합니다. 이 영역이 어떤 의미가 있는지에 대해서 이름이 있어야
    합니다. 그리고 한 줄로 간단하게 표현을 해 주고 클릭을 해서 펼쳐야 그 전체
    내용이 보이는 형태로 바뀌어야 합니다."

    여태 안내는 **이름 없는 글 뭉치**였다. 네 줄이 늘 펼쳐진 채 판 아래를
    차지했고, 그 네 줄은 규칙만 말할 뿐 "이렇게 쓰면 이렇게 나온다"를
    보여주지 않았다. 처음 보는 사람에게는 짧아서 못 배우고, 아는 사람에게는
    길어서 방해였다.

무엇을 하나:
    한 줄짜리 머리(▸ 이름 · 요약)만 늘 보이고, 누르면 본문이 펼쳐진다.
    macOS 의 disclosure triangle 과 같은 관습이라 따로 배울 것이 없다.

    ┌───────────────────────────────────────────┐
    │ ▸ 양식 문법   빈칸은 \ 하나, 이름은 \학년\ │   ← 늘 보이는 한 줄
    ├───────────────────────────────────────────┤
    │   \학년\   →  채우기 표에 '학년' 이라고…   │   ← 눌러야 나오는 본문
    └───────────────────────────────────────────┘

본문의 생김새:
    한 줄 = [(글자, 강조여부), …] 목록. 강조는 파란 굵은 글씨다 (사용자 결정
    2026-07-28: "글씨 크기를 키우고 강조는 파란색으로"). 문법 조각과
    결과 예시만 강조하고 나머지 설명은 본문색으로 둔다 — 다 강조하면
    아무것도 강조되지 않는다.
"""

import tkinter as tk

from hwp_palette.design import theme

_C = theme.colors()
FS = theme.FS
SP = theme.SP


class Disclosure(tk.Frame):

    def __init__(self, parent, title, summary, lines, bg=None,
                 open_=False, on_toggle=None, body_height=None):
        bg = bg or _C["card"]
        super().__init__(parent, bg=bg)
        self._lines = lines
        self._open = False
        self._on_toggle = on_toggle
        self._bg = bg
        self._body_height = body_height

        head = tk.Frame(self, bg=bg, cursor="hand2")
        head.pack(fill="x")
        self._arrow = tk.Label(head, text="▸", bg=bg, fg=_C["muted"],
                               font=(theme.FONT, theme.fs(FS["sub"])))
        self._arrow.pack(side="left", padx=(0, 4))
        name = tk.Label(head, text=title, bg=bg, fg=_C["text"],
                        font=(theme.FONT, theme.fs(FS["body"]), "bold"))
        name.pack(side="left")
        # 요약은 **한 줄로 잘린다** — 두 줄이 되면 접어 둔 뜻이 없다
        self._sum = tk.Label(head, text=summary, bg=bg, fg=_C["muted"],
                             font=(theme.FONT, theme.fs(FS["sub"])),
                             anchor="w")
        self._sum.pack(side="left", fill="x", expand=True, padx=(SP["s"], 0))
        for w in (head, self._arrow, name, self._sum):
            w.bind("<Button-1>", lambda e: self.toggle())
            w.bind("<Enter>", lambda e: self._tint(_C["subbg"]))
            w.bind("<Leave>", lambda e: self._tint(bg))
        self._head_parts = (head, self._arrow, name, self._sum)

        self._body = None
        if open_:
            self.toggle()

    def _tint(self, color):
        for w in self._head_parts:
            try:
                w.config(bg=color)
            except tk.TclError:
                pass

    # ── 펼치기 / 접기 ─────────────────────────────────
    def toggle(self):
        if self._open:
            if self._body is not None:
                self._body.destroy()
                self._body = None
            self._arrow.config(text="▸")
            self._open = False
        else:
            self._body = self._make_body()
            self._body.pack(fill="x", pady=(SP["xs"], 0))
            self._arrow.config(text="▾")
            self._open = True
        if self._on_toggle:
            self._on_toggle(self._open)

    @property
    def is_open(self):
        return self._open

    def _make_body(self):
        # Text 를 쓰는 이유: 한 줄 안에서 일부만 파랗게 굵게 하려면 라벨로는
        # 안 되고 태그가 필요하다. 읽기 전용(state=disabled)이라 입력칸으로
        # 오해되지 않고, 커서도 화살표로 둔다.
        rows = self._body_height or min(16, max(4, len(self._lines) + 1))
        body = tk.Text(self, height=rows, bd=0, bg=self._bg,
                       highlightthickness=0, wrap="word", cursor="arrow",
                       font=(theme.FONT, theme.fs(FS["sub"])),
                       fg=_C["text"], padx=SP["m"], pady=SP["xs"], takefocus=0)
        body.tag_configure("hl", foreground=_C["accent"],
                           font=(theme.FONT, theme.fs(FS["sub"]), "bold"))
        body.tag_configure("head", foreground=_C["text"],
                           font=(theme.FONT, theme.fs(FS["sub"]), "bold"),
                           spacing1=6)
        for parts in self._lines:
            if isinstance(parts, str):          # 소제목 한 줄
                body.insert("end", parts + "\n", ("head",))
                continue
            for text, style in parts:
                tags = ("hl",) if style else ()
                body.insert("end", text, tags)
            body.insert("end", "\n")
        body.config(state="disabled")
        # 높이를 **줄 수가 아니라 실제로 그려진 줄 수**로 다시 잡는다.
        #
        # 왜 (2026-07-29 실측): height 는 논리적인 줄 수를 세는데, 화면에서
        # 긴 줄은 접혀서 두 줄을 차지한다. 접히는 줄이 셋 있으면 마지막 세
        # 줄이 판 밖으로 밀려 **글자가 잘린 채 보인다** — 안내가 잘리면
        # 안내가 아니다. 여기서 미리 잴 수 없는 이유는 폭이 아직 안 정해져서다
        # (pack 전이라 wrap 위치를 모른다). 배치가 끝난 뒤 재서 고친다.
        # 줄 수가 아니라 **픽셀**로 재는 이유: 소제목에 spacing1(줄 위 여백)이
        # 붙어 있어서, 줄 수만 맞추면 그 여백만큼(소제목 4개 × 6px) 모자라
        # 마지막 줄이 잘린다 (실측 2026-07-29).
        import tkinter.font as tkfont

        def fit(_e=None):
            try:
                if not body.winfo_exists():
                    return
                got = body.count("1.0", "end", "ypixels")
                if not got:
                    return
                line_px = tkfont.Font(font=body.cget("font")).metrics("linespace")
                # 위아래 안쪽 여백(pady)도 글자가 쓸 자리를 잡아먹는다 —
                # 빼먹으면 딱 한 줄이 모자라 마지막 줄이 반쯤 잘린다.
                want = int(got[0]) + int(body.cget("pady")) * 2
                need = -(-want // max(1, line_px))           # 올림 나눗셈
                if need != int(body.cget("height")):
                    body.config(height=max(3, need))
            except Exception:
                pass            # 못 재면 처음 잡은 높이 그대로 (잘려도 안 죽는다)

        body.after_idle(fit)
        # 창 폭이 바뀌면 접히는 자리도 바뀐다 — 그때마다 다시 잰다
        body.bind("<Configure>", fit, add="+")
        return body
