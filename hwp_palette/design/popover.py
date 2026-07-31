# -*- coding: utf-8 -*-
r"""앱과 같은 얼굴을 한 팝업 메뉴 (2026-07-25).

윈도우 기본 tk.Menu 는 크기·여백·글꼴·모서리를 못 고쳐 프로그램의 나머지
화면과 따로 놀았다 (사용자 지적). 이 부품은 테두리 없는 작은 창(Toplevel)에
항목을 직접 그려서, 블럭 버튼과 같은 글꼴·색·호버 규칙을 쓴다.

    Popover(parent, anchor_widget) \
        .add("팔레트 설정", cmd) \
        .add_check("수능", cmd, checked=True) \
        .separator() \
        .add("팔레트 관리…", cmd) \
        .show()

동작 규칙:
  · anchor 버튼 바로 아래에 왼쪽을 맞춰 펼친다 (화면 밖이면 안으로 민다)
  · 바깥 클릭 · Esc · 포커스 이탈 → 닫힘
  · 항목 호버 = 옅은 파랑, 클릭 = 닫고 실행
  · show() 는 tk.Menu.tk_popup 과 달리 **바로 돌아온다** — 호출부는
    on_close 콜백으로 '닫힘'을 알 수 있다 (설정 버튼의 켜짐 표시용)
"""

import tkinter as tk

from hwp_palette.core import screens                   # 여러 모니터를 합친 좌표 (팝업이 딴 화면으로 안 가게)
from hwp_palette.design import theme

_C = theme.colors()


class Popover(tk.Toplevel):

    def __init__(self, parent, anchor, on_close=None):
        super().__init__(parent)
        self._parent = parent
        self._anchor = anchor
        self._on_close = on_close
        self._closed = False
        self.wm_overrideredirect(True)      # 제목줄 없는 순수 판때기
        self.attributes("-topmost", True)
        # 판 둘레에 1px 테두리 — 그림자를 못 그리는 Tk 에서 바탕과 판을 가른다
        self.configure(bg=_C["border"])
        self._body = tk.Frame(self, bg=_C["card"])
        self._body.pack(fill="both", expand=True, padx=1, pady=1)
        self._items = []                    # (frame, label, hover_on) — 색 관리용
        self.withdraw()                     # show() 전까지 숨김

    # ── 항목 만들기 ─────────────────────────────────
    def _font(self, size=9):
        return (theme.FONT, theme.fs(size))

    def add(self, text, command, indent=False):
        """보통 항목. indent=True 면 체크 항목들과 글머리를 맞춘다."""
        return self._item(text, command, lead="    " if indent else "")

    def add_check(self, text, command, checked=False, more=None):
        """체크 표시가 붙는 항목 (지금 선택된 팔레트 등).

        more 를 주면 항목 오른쪽에 ⋯ 단추가 붙는다 — 그 항목에 대한 관리
        메뉴(이름·순서·삭제 등)를 여는 용도. 항목 본체를 누르면 command
        (팝오버를 닫고 실행), ⋯ 를 누르면 **이 판은 열린 채로** more(항목 줄
        위젯)가 불린다 — 계단식 하위 메뉴(show_beside)를 그 줄 옆에 붙이라는
        뜻이다 (2026-07-31, 사용자 지적: ⋯ 를 누르면 목록이 사라졌다).
        """
        return self._item(text, command, lead="✓  " if checked else "    ",
                          bold=checked, more=more)

    def _item(self, text, command, lead="", bold=False, more=None):
        f = tk.Frame(self._body, bg=_C["card"])
        f.pack(fill="x")
        font = ((theme.FONT, theme.fs(9), "bold") if bold
                else (theme.FONT, theme.fs(9)))
        lab = tk.Label(f, text=lead + text, font=font, bg=_C["card"],
                       fg=_C["text"], anchor="w", padx=12, pady=6)
        parts = [f, lab]
        if more is not None:
            # ⋯ 는 자기 바인딩만 갖는다 — 항목 본체(f·lab)의 클릭과 안 섞인다
            dots = tk.Label(f, text="⋯", font=(theme.FONT, theme.fs(9)),
                            bg=_C["card"], fg=_C["muted"], padx=10, pady=6)
            dots.pack(side="right")
            dots.bind("<Enter>", lambda e: dots.config(fg=_C["accent"]))
            dots.bind("<Leave>", lambda e: dots.config(fg=_C["muted"]))
            dots.bind("<ButtonRelease-1>", lambda e, c=more, fr=f: c(fr))
            dots.config(cursor="hand2")
            parts.append(dots)
        lab.pack(side="left", fill="x", expand=True)
        for w in (f, lab):
            w.bind("<Enter>", lambda e, ws=parts: self._hover(ws, True))
            w.bind("<Leave>", lambda e, ws=parts: self._hover(ws, False))
            w.bind("<ButtonRelease-1>", lambda e, c=command: self._run(c))
            w.config(cursor="hand2")
        return self

    def _hover(self, parts, on):
        bg = _C["accent_soft"] if on else _C["card"]
        fg = _C["accent"] if on else _C["text"]
        for w in parts:
            w.config(bg=bg)
        parts[1].config(fg=fg)      # 글자색은 본문 라벨만 — ⋯ 는 제 색을 지킨다

    def separator(self):
        tk.Frame(self._body, bg=_C["border"], height=1).pack(fill="x", pady=3)
        return self

    # ── 열고 닫기 ───────────────────────────────────
    def show(self, min_width=None):
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), min_width or 0,
                self._anchor.winfo_width())
        h = self.winfo_reqheight()
        x = self._anchor.winfo_rootx()
        y = self._anchor.winfo_rooty() + self._anchor.winfo_height() + 2
        # 화면 밖으로 나가면 안으로 민다 — 기준은 **모든 모니터를 합친 범위**다.
        # 주 모니터 크기로 자르면, 주 모니터 밖(예: 왼쪽 모니터라 x 가 음수)에
        # 떠 있는 창의 메뉴가 다른 화면으로 순간이동한다 (2026-07-26 버그).
        if not screens.fits_below(self, y, h):
            y = self._anchor.winfo_rooty() - h - 2      # 자리가 없으면 위로
        x, y = screens.clamp_window(self, x, y, w, h)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.bind("<ButtonPress-1>", self._maybe_close_outside)
        self.bind("<Escape>", lambda e: self.close())
        try:
            self.focus_set()
        except Exception:
            pass
        self._grab()
        return self

    # ── 계단식 하위 메뉴 (2026-07-31) ───────────────────
    # 탭 관리(⋯)처럼 항목마다 딸린 메뉴는 윈도우 기본 tk.Menu 로 띄웠었는데,
    # 그 순간 이 판이 닫혀 목록이 사라졌고 회색 기본 메뉴는 프로그램의 얼굴과도
    # 달랐다 (사용자 지적). 하위 메뉴도 같은 Popover 로, 항목 줄 오른쪽에
    # 한글의 계단식 메뉴처럼 붙인다.
    def suspend_grab(self):
        """하위 메뉴가 클릭을 받도록 grab 을 잠시 내준다."""
        try:
            self.grab_release()
        except Exception:
            pass

    def resume_grab(self):
        """하위 메뉴가 닫힌 뒤 grab 을 되찾는다 — 바깥 클릭 감지가 다시 산다."""
        if not self._closed:
            self._grab()

    def show_beside(self, row):
        """다른 팝오버의 항목 줄(row) **오른쪽**에 계단식으로 펼친다.

        부모 판은 닫히지 않고 그대로 남는다 — 부모는 suspend_grab 으로
        grab 만 내주고, 이 판이 닫힐 때 on_close 에서 resume_grab 한다.
        """
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = row.winfo_rootx() + row.winfo_width() + 2
        y = row.winfo_rooty() - 1
        x, y = screens.clamp_window(self, x, y, w, h)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.bind("<ButtonPress-1>", self._maybe_close_outside)
        self.bind("<Escape>", lambda e: self.close())
        try:
            self.focus_set()
        except Exception:
            pass
        self._grab()
        return self

    def _grab(self, tries=0):
        """바깥 클릭 감지용 grab — 창이 아직 안 떴으면 잠깐 뒤 다시 시도.

        deiconify 직후에는 창이 화면에 실리기 전이라 grab_set 이
        'window not viewable' 로 실패할 수 있다 (Tk 의 타이밍 문제).
        열 번(≈0.3초) 안 되면 포기한다 — grab 없이도 메뉴는 쓸 수 있고,
        영원히 재시도하면 타이머만 계속 돈다.
        """
        if self._closed or not self.winfo_exists():
            return
        try:
            if tries == 0:
                # 창을 화면에 먼저 실어 **재시도 없이 한 번에** 잡는다
                # (2026-07-31) — deiconify 직후에는 창이 안 떠 있어 30ms
                # 재시도를 돌았고, 그 0.3초 동안 클릭이 어디에도 안 먹어
                # 메뉴가 버벅이는 것처럼 느껴졌다.
                self.update_idletasks()
            self.grab_set()
        except Exception:
            if tries < 10:
                self.after(30, lambda: self._grab(tries + 1))

    def _maybe_close_outside(self, e):
        # grab 중에는 창 밖 클릭도 이 창의 이벤트로 온다 — 좌표로 구분
        if not (0 <= e.x_root - self.winfo_rootx() <= self.winfo_width()
                and 0 <= e.y_root - self.winfo_rooty() <= self.winfo_height()):
            self.close()

    def _run(self, command):
        self.close()
        if command:
            command()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        if self._on_close:
            self._on_close()
