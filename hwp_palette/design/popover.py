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
  · 바깥 클릭 · Esc → 닫힘 (바깥 클릭은 **닫히면서 원래 목적지로 통과**한다)
  · 항목 호버 = 옅은 파랑, 클릭 = 닫고 실행
  · show() 는 tk.Menu.tk_popup 과 달리 **바로 돌아온다** — 호출부는
    on_close 콜백으로 '닫힘'을 알 수 있다 (설정 버튼의 켜짐 표시용)
"""

import tkinter as tk

from hwp_palette.core import screens                   # 여러 모니터를 합친 좌표 (팝업이 딴 화면으로 안 가게)
from hwp_palette.design import theme

_C = theme.colors()

# ── 열려 있는 판들과 바깥 클릭 감시 (2026-08-01, 피드백 038-b) ──
#
# 예전에는 판마다 `grab_set()` 으로 마우스를 잡고, 창 밖 클릭도 이 창의
# 이벤트로 받아 좌표로 걸러 닫았다. 그래서 **바깥을 누른 첫 클릭은 판을 닫는
# 데 쓰이고 원래 목적지로는 가지 않았다** — 창의 ✕ 를 눌러도 안 꺼지던 정체다.
#
# 이제 잡기를 쓰지 않는다. 판이 열려 있는 동안만 `bind_all` 로 클릭을 엿듣고,
# 판 밖이면 닫는다. Tk 의 바인딩 차례상 위젯 제 처리가 **먼저** 돌고 이것이
# 나중에 도므로, 클릭은 원래 목적지(✕·다른 버튼)에 그대로 닿는다 —
# 사용자 관점에서 '닫히면서 통과'다.
_open = []                  # 지금 열려 있는 판 (계단식이면 여럿)
_watch_host = None          # bind_all 을 걸어 둔 위젯 (판보다 오래 사는 부모)

_shown_hooks = []           # 판이 열릴 때마다 부를 것 (도킹 창 순서 재조정 등)


def on_shown(fn):
    r"""판이 열릴 때마다 부를 함수를 등록한다.

    쓰는 곳: 한글 도킹 중에는 판이 뜨는 순간 창 순서를 다시 잡아야 한다
    (피드백 035 — 판이 활성이 되면 우리 창 무리가 앞으로 나와 한글이 뒤로
    밀렸다). design 층이 hwp 층을 직접 부르지 않도록 갈고리만 둔다.
    """
    _shown_hooks.append(fn)


def _fire_shown():
    for fn in list(_shown_hooks):
        try:
            fn()
        except Exception:
            pass                # 갈고리 하나가 실패해도 메뉴는 떠야 한다


def _inside(widget, pop):
    """그 위젯이 이 판(또는 그 안쪽)에 속하는가 — 위젯 이름길로 본다."""
    w, p = str(widget), str(pop)
    return w == p or w.startswith(p + ".")


def _outside_click(e):
    for pop in list(_open):
        try:
            if not pop._muted and not _inside(e.widget, pop):
                pop.close()
        except Exception:
            pass


def _watch_start(pop):
    global _watch_host
    if pop in _open:
        return
    _open.append(pop)
    if _watch_host is None:
        # 판이 아니라 **부모**에 건다 — 판이 죽어도 걷어낼 위젯이 남아 있어야 한다
        _watch_host = pop._parent
        try:
            _watch_host.bind_all("<ButtonPress-1>", _outside_click, add="+")
        except Exception:
            _watch_host = None


def _watch_stop(pop):
    global _watch_host
    if pop in _open:
        _open.remove(pop)
    if _open or _watch_host is None:
        return                  # 계단식으로 아직 열려 있는 판이 있다
    try:
        _watch_host.unbind_all("<ButtonPress-1>")
    except Exception:
        pass
    _watch_host = None


class Popover(tk.Toplevel):

    def __init__(self, parent, anchor=None, on_close=None):
        # anchor 는 show() 에만 필요하다 — show_at(커서 자리)로 열 때는 없어도 된다
        super().__init__(parent)
        self._parent = parent
        self._anchor = anchor
        self._on_close = on_close
        self._closed = False
        self._muted = False          # 하위 메뉴가 열린 동안은 바깥 클릭을 무시
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
        self._arm()
        return self

    def show_at(self, x, y, min_width=None):
        r"""**커서 자리**에 펼친다 — 우클릭(맥락) 메뉴 전용 (2026-07-31).

        왜 앵커 위젯이 아니라 커서인가 (사용자 지적: "물감의 오른쪽 버튼을
        눌렀을 때 나오는 세부 조정탭이 엉뚱한 곳에 나옵니다"):
            show() 는 앵커 위젯의 winfo_rootx/rooty 로 자리를 잡는다. 그런데
            우클릭 메뉴의 앵커는 격자 안 타일이라, 판이 다시 그려지는 중이거나
            (선택 표시·접기·스크롤) 아직 화면에 실리기 전이면 그 좌표가
            창 밖의 엉뚱한 값으로 나온다. 맥락 메뉴는 **누른 자리**에 뜨는 것이
            운영체제 관례이기도 하므로, 위젯 기하에 아예 기대지 않는다.

        아래로 자리가 없으면 커서 위로 펼친다. 화면 밖은 늘 안으로 민다.
        """
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), min_width or 0)
        h = self.winfo_reqheight()
        x, y = int(x), int(y)
        if not screens.fits_below(self, y, h):
            y = y - h                       # 아래에 자리가 없으면 커서 위로
        x, y = screens.clamp_window(self, x, y, w, h)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self._arm()
        return self

    # ── 계단식 하위 메뉴 (2026-07-31) ───────────────────
    # 탭 관리(⋯)처럼 항목마다 딸린 메뉴는 윈도우 기본 tk.Menu 로 띄웠었는데,
    # 그 순간 이 판이 닫혀 목록이 사라졌고 회색 기본 메뉴는 프로그램의 얼굴과도
    # 달랐다 (사용자 지적). 하위 메뉴도 같은 Popover 로, 항목 줄 오른쪽에
    # 한글의 계단식 메뉴처럼 붙인다.
    def suspend_grab(self):
        """하위 메뉴가 열리는 동안 바깥 클릭 감지를 잠시 끈다.

        (이름은 그대로 둔다 — 호출부가 쓰는 말이고, 하는 일도 같다. 안에서
        잡기(grab)를 쓰지 않게 됐을 뿐이다.)
        """
        self._muted = True

    def resume_grab(self):
        """하위 메뉴가 닫힌 뒤 바깥 클릭 감지를 되살린다."""
        self._muted = False

    def show_beside(self, row):
        """다른 팝오버의 항목 줄(row) **오른쪽**에 계단식으로 펼친다.

        부모 판은 닫히지 않고 그대로 남는다 — 부모는 suspend_grab 으로
        바깥 클릭 감지만 잠시 끄고, 이 판이 닫힐 때 on_close 에서
        resume_grab 한다.
        """
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = row.winfo_rootx() + row.winfo_width() + 2
        y = row.winfo_rooty() - 1
        x, y = screens.clamp_window(self, x, y, w, h)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self._arm()
        return self

    def _arm(self):
        """화면에 띄우고 바깥 클릭·Esc 감시를 건다 (show 세 갈래 공통)."""
        self.deiconify()
        self.lift()
        self.bind("<Escape>", lambda e: self.close())
        try:
            self.focus_set()
        except Exception:
            pass
        _watch_start(self)
        _fire_shown()

    def _run(self, command):
        self.close()
        if command:
            command()

    def close(self):
        if self._closed:
            return
        self._closed = True
        _watch_stop(self)
        try:
            self.destroy()
        except Exception:
            pass
        if self._on_close:
            self._on_close()
