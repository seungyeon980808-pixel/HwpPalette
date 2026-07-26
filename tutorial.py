# -*- coding: utf-8 -*-
r"""따라하기 튜토리얼 — 실제 화면 위에서 한 곳씩 짚어 주는 안내 (기획 3번).

방식: 대상 위젯 둘레에 파란 테두리(halo)를 두르고, 그 옆에 설명 창(coach)을
띄운다. [다음]으로 진행, [그만]으로 언제든 종료. 화면을 가리는 반투명 덮개는
쓰지 않는다 — 실제 화면이 그대로 보여야 "아 저거구나"가 된다.

steps: [step, ...]  — step 은 dict:
    {"widget": 위젯을 돌려주는 함수 (없으면 화면 가운데 안내만),
     "title": 제목, "text": 설명,
     "action": 이 단계로 들어올 때 한 번 실행할 일 (없어도 됨),
     "wait": True 면 '다음' 대신 사용자가 한글에서 할 일을 기다린다는 뜻(문구만)}

위젯을 함수로 받는 이유: 튜토리얼을 켜는 시점의 실제 위젯을 잡기 위해서다
(팔레트는 다시 그려질 때마다 위젯이 새로 만들어진다). action 은 한글에
연습용 문서를 만들어 주는 등 '화면 밖의 준비'를 맡는다.
"""

import tkinter as tk

import applog
import screens                  # 여러 모니터를 합친 좌표
import theme

_C = theme.colors()
ACCENT = _C["accent"]
ACCENT_SOFT = _C["accent_soft"]
BG = _C["bg"]
CARD = _C["card"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
ROWBG = _C["subbg"]
FONT = theme.FONT

_HALO_PX = 3            # 테두리 두께
_HOLE_PAD = 7           # 흐림에서 파낼 구멍이 대상보다 얼마나 큰가 (테두리보다 커야)
_DIM_ALPHA = 0.55       # 흐림 정도 — 글자가 읽히되 '지금 여기가 아니다'가 보이게


# 지금 돌고 있는 튜토리얼 (2026-07-26). 하나만 살아 있어야 한다 —
# 이전 것을 안 끄고 새로 시작하면 흐림 패널이 겹쳐 남아 화면이 지저분해지고,
# '완료'를 눌러도 안 사라지는 것처럼 보인다 (사용자 지적).
_active = None


class Tutorial:

    def __init__(self, root, steps, on_done=None, title=""):
        self.root = root
        self.steps = steps
        self.on_done = on_done
        self.title = title      # 코스 이름 — 코치 창 머리에 함께 보인다
        self.i = 0
        self._halo = []         # 테두리 조각 4개
        self._dim = []          # 흐림 패널 (대상만 남기고 덮는다)
        self._coach = None
        self._base = root       # 지금 단계가 기준으로 삼는 창
        self._target = None     # 지금 단계가 짚는 위젯
        self._binds = []        # (위젯, 이벤트, funcid) — 끝낼 때 떼기 위해
        self._reflow_job = None
        self._done = False
        self._busy = False      # 다시 그리는 중 (그동안 온 이벤트는 무시)
        self._last_geo = None   # 마지막으로 그린 기준 창의 자리
        self._root_topmost = None   # 튜토리얼 동안 잠시 내렸다가 되돌릴 값

    def start(self):
        global _active
        if _active is not None and _active is not self:
            _active._finish()           # 앞엣것을 확실히 끝내고 시작한다
        _active = self
        if not self.steps:
            self._finish()
            return
        # 메인 창의 '항상 위' 를 잠시 내린다 (2026-07-26).
        # 흐림 패널도 '항상 위' 라, 둘 다 켜져 있으면 윈도우가 z-순서를 두고
        # 다투며 흐림이 나타났다 사라졌다 했다 — 깜빡임의 다른 한 축이다.
        try:
            self._root_topmost = bool(self.root.attributes("-topmost"))
            if self._root_topmost:
                self.root.attributes("-topmost", False)
        except Exception:
            self._root_topmost = None
        self._show(0)

    # ── 한 단계 ─────────────────────────────────────
    def _show(self, i):
        if self._done:
            return
        # 단계를 넘길 때 **흐림 패널은 그대로 두고** 안내창만 지운다.
        # 매번 다 부수고 다시 만들면 단계마다 화면이 한 번씩 번쩍인다
        # (흐림은 _draw_dim 이 자리만 옮겨 준다, 2026-07-26).
        self._close_coach()
        if i >= len(self.steps):
            self._finish(completed=True)
            return
        self.i = i
        step = self.steps[i]
        if isinstance(step, tuple):         # 옛 형식 (위젯, 제목, 설명)
            step = {"widget": step[0], "title": step[1], "text": step[2]}
        if step.get("action"):
            try:
                if step["action"]() is False:   # 준비 실패 — 여기서 멈춘다
                    self._finish()
                    return
            except Exception as e:
                applog.exc(f"튜토리얼 {i}단계 준비 실패 — 중단", e)
                self._finish()
                return
        w = None
        if step.get("widget"):
            try:
                w = step["widget"]()
                if w is None or not w.winfo_exists():
                    w = None
            except Exception as e:
                applog.exc(f"튜토리얼 {i}단계 대상 없음 — 안내만 보여줌", e)
                w = None
        self._target = w
        try:
            self._base = w.winfo_toplevel() if w is not None else self.root
        except Exception:
            self._base = self.root
        self._draw_dim(w)               # 대상만 남기고 나머지를 흐리게
        if w is not None:
            self._draw_halo(w)
        self._draw_coach(w, step["title"], step["text"],
                         last=(i == len(self.steps) - 1))
        self._last_geo = self._geo()    # 이 자리를 기준으로 '움직였나' 를 잰다
        self._track()                   # 창이 움직이면 따라오게

    # ── 창을 따라다니기 (2026-07-26 사용자 지적) ────
    #
    # 흐림·테두리·코치는 화면 좌표로 찍어 둔 별개의 창이라, 프로그램 창을
    # 옮기면 제자리에 남아 회색 판이 엉뚱한 곳에 떠 있었다. 창이 움직이거나
    # 크기가 바뀌면 지금 단계를 그대로 다시 그린다.
    def _track(self):
        # **먼저 떼고 다시 건다** — 단계마다 그냥 걸기만 하면 감시가 쌓여
        # 창을 한 번 움직일 때마다 열 번씩 다시 그렸다 (깜빡임의 주범,
        # 2026-07-26). 기준 창이 단계마다 바뀔 수 있어 매번 다시 건다.
        self._untrack()
        for wdg in {self.root, self._base}:
            try:
                fid = wdg.bind("<Configure>", self._on_move, add="+")
                self._binds.append((wdg, "<Configure>", fid))
            except Exception:
                pass

    def _untrack(self):
        for wdg, ev, fid in self._binds:
            try:
                wdg.unbind(ev, fid)
            except Exception:
                pass
        self._binds = []

    def _geo(self):
        """기준 창의 지금 자리·크기 — 진짜 움직였는지 재기 위한 값."""
        try:
            b = self._base if self._base.winfo_exists() else self.root
            return (b.winfo_rootx(), b.winfo_rooty(),
                    b.winfo_width(), b.winfo_height())
        except Exception:
            return None

    def _on_move(self, _e=None):
        if self._done or self._reflow_job is not None or self._busy:
            return
        # 자리가 **실제로 바뀌었을 때만** 다시 그린다 (2026-07-26).
        # 흐림 패널을 만들고 지우는 것 자체가 다시 <Configure> 를 불러,
        # 그냥 반응하면 다시 그리기가 서로를 부르며 화면이 깜빡였다.
        if self._geo() == self._last_geo:
            return
        self._reflow_job = self.root.after(120, self._reflow)

    def _reflow(self):
        self._reflow_job = None
        if self._done or self._coach is None:
            return
        self._busy = True                   # 다시 그리는 동안 온 이벤트는 무시
        try:
            w = self._target
            if w is not None and not w.winfo_exists():
                w = self._target = None
            self._draw_dim(w)               # 있는 패널을 **옮긴다** (재생성 아님)
            self._draw_halo(w)
            self._place_coach(self._coach, w)
            self._last_geo = self._geo()
        except Exception as e:
            applog.exc("튜토리얼 위치 갱신 실패 — 안내는 그대로 둔다", e)
        finally:
            self._busy = False

    def _draw_dim(self, w):
        r"""**눌러야 할 것만 남기고 나머지를 흐리게** (사용자 결정 2026-07-26).

        Tk 는 창에 '구멍'을 뚫지 못한다. 대신 반투명 검은 패널 네 장으로
        대상 둘레에 액자를 만들면 같은 효과가 난다 — 가운데(대상)만 원래
        밝기로 남고, 그 자리는 패널이 없으니 그대로 누를 수도 있다.

        대상이 다른 창(물감 설정 등)에 있으면 **그 창**을 기준으로 덮는다.
        짚을 것이 없는 단계(한글에서 할 일)는 이 프로그램 창 전체를 덮어
        "지금은 여기가 아니라 한글을 보라"는 뜻이 되게 한다.
        """
        base = self.root
        if w is not None:
            try:
                base = w.winfo_toplevel()
            except Exception:
                base = self.root
        bx, by = base.winfo_rootx(), base.winfo_rooty()
        bw, bh = base.winfo_width(), base.winfo_height()
        if bw <= 1 or bh <= 1:
            return
        if w is None:
            rects = [(bx, by, bw, bh)]
        else:
            p = _HOLE_PAD
            tx, ty = w.winfo_rootx() - p, w.winfo_rooty() - p
            tw, th = w.winfo_width() + 2 * p, w.winfo_height() + 2 * p
            rects = [
                (bx, by, bw, ty - by),                          # 위
                (bx, ty + th, bw, by + bh - (ty + th)),         # 아래
                (bx, ty, tx - bx, th),                          # 왼쪽
                (tx + tw, ty, bx + bw - (tx + tw), th),         # 오른쪽
            ]
        rects = [r for r in rects if r[2] > 0 and r[3] > 0]
        # 판을 **부수지 않고 옮긴다** — 매번 새로 만들면 창이 생겼다 사라지며
        # 화면이 깜빡이고, 그 자체가 다시 그리기를 부른다 (2026-07-26).
        while len(self._dim) > len(rects):
            d = self._dim.pop()
            try:
                d.destroy()
            except Exception:
                pass
        while len(self._dim) < len(rects):
            try:
                d = tk.Toplevel(self.root)
                d.wm_overrideredirect(True)
                d.configure(bg="#000000")
                d.attributes("-topmost", True)
                d.attributes("-alpha", _DIM_ALPHA)
                self._dim.append(d)
            except Exception as e:
                applog.exc("흐림 패널 생성 실패 — 강조 없이 계속", e)
                break
        for d, (x, y, ww, hh) in zip(self._dim, rects):
            try:
                d.geometry(f"{int(ww)}x{int(hh)}+{int(x)}+{int(y)}")
            except Exception:
                pass

    def _clear_dim(self):
        for d in self._dim:
            try:
                d.destroy()
            except Exception:
                pass
        self._dim = []

    def _draw_halo(self, w):
        """대상 둘레 4변에 파란 띠.

        **대상이 있는 창** 위에 그린다 — 물감 설정 창의 버튼을 짚을 때도
        같은 코드로 동작해야 하므로 root 가 아니라 그 창을 기준으로 잡는다.
        """
        for f in self._halo:                # 이전 띠는 걷어낸다
            try:
                f.destroy()
            except Exception:
                pass
        self._halo = []
        if w is None:
            return
        base = w.winfo_toplevel()
        rx = w.winfo_rootx() - base.winfo_rootx()
        ry = w.winfo_rooty() - base.winfo_rooty()
        ww, wh = w.winfo_width(), w.winfo_height()
        p = _HALO_PX
        rects = ((rx - p, ry - p, ww + 2 * p, p),          # 위
                 (rx - p, ry + wh, ww + 2 * p, p),         # 아래
                 (rx - p, ry - p, p, wh + 2 * p),          # 왼쪽
                 (rx + ww, ry - p, p, wh + 2 * p))         # 오른쪽
        for x, y, fw, fh in rects:
            f = tk.Frame(base, bg=ACCENT)
            f.place(x=x, y=y, width=fw, height=fh)
            f.lift()
            self._halo.append(f)

    def _draw_coach(self, w, title, text, last):
        c = self._coach = tk.Toplevel(self.root)
        c.wm_overrideredirect(True)
        c.attributes("-topmost", True)
        c.configure(bg=ACCENT)          # 코치 창도 파란 테두리 — 짚은 곳과 한 짝
        body = tk.Frame(c, bg=CARD)
        body.pack(fill="both", expand=True, padx=2, pady=2)
        head = tk.Frame(body, bg=CARD)
        head.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(head, text=f"{self.i + 1} / {len(self.steps)}",
                 font=(FONT, theme.fs(8), "bold"), bg=ACCENT_SOFT, fg=ACCENT,
                 padx=7, pady=1).pack(side="left")
        if self.title:
            tk.Label(head, text=self.title, font=(FONT, theme.fs(8)),
                     bg=CARD, fg=MUTED).pack(side="left", padx=(6, 0))
        tk.Label(body, text=title, font=(FONT, theme.fs(10), "bold"),
                 bg=CARD, fg=TEXT, anchor="w", padx=12,
                 justify="left", wraplength=270).pack(fill="x", pady=(2, 4))
        tk.Label(body, text=text, font=(FONT, theme.fs(9)), bg=CARD, fg=TEXT,
                 justify="left", wraplength=270, padx=12).pack(anchor="w")
        foot = tk.Frame(body, bg=CARD, padx=12, pady=8)
        foot.pack(fill="x")
        nxt = tk.Label(foot, text="완료 ✓" if last else "다음 →",
                       font=(FONT, theme.fs(9), "bold"), bg=CARD, fg=ACCENT,
                       cursor="hand2")
        nxt.pack(side="right")
        nxt.bind("<Button-1>", lambda e: self._show(self.i + 1))
        quit_ = tk.Label(foot, text="그만", font=(FONT, theme.fs(8)),
                         bg=CARD, fg=MUTED, cursor="hand2")
        quit_.pack(side="right", padx=(0, 12))
        quit_.bind("<Button-1>", lambda e: self._finish())
        c.bind("<Escape>", lambda e: self._finish())
        self._place_coach(c, w)
        # 한 박자 뒤 한 번 더 — 창을 막 만든 순간에는 크기·자리가 아직
        # 확정되지 않아 첫 계산이 빗나갈 때가 있다(첫 단계에서 안내가 화면
        # 왼쪽 위로 튀던 원인, 2026-07-26). 같은 계산이라 두 번 해도 무해하다.
        c.after(60, lambda: (self._place_coach(c, w)
                             if (not self._done and c.winfo_exists()) else None))

    def _place_coach(self, c, w):
        r"""안내창은 **창 바깥 오른쪽**에 띄운다 (사용자 결정 2026-07-26).

        화면을 하나도 가리지 않는 것이 첫째 조건이라 창 바깥에 둔다.
        그중 오른쪽인 이유: 이 프로그램 창은 세로로 길어서 위쪽에 두면
        안내가 한글 문서 위를 덮고, 짚은 곳(아래)과 눈이 멀어진다.
        오른쪽에 자리가 없으면 왼쪽 바깥, 그것도 없으면 위쪽으로 물러난다.

        세로 위치는 **짚은 것과 같은 높이** — 안내와 강조가 한눈에 들어온다.
        """
        try:
            c.update_idletasks()
            cw, ch = c.winfo_reqwidth(), c.winfo_reqheight()
            base = self._base if self._base.winfo_exists() else self.root
            bx, by = base.winfo_rootx(), base.winfo_rooty()
            bw, bh = base.winfo_width(), base.winfo_height()
            dx, dy, dw, dh = screens.desktop_bounds(c)

            x = bx + bw + 12                        # 창 오른쪽 바깥
            if x + cw > dx + dw:                    # 오른쪽에 자리가 없으면
                x = bx - cw - 12                    # 왼쪽 바깥
            top_room = by - ch - 10 >= dy + 4
            if x < dx and top_room:                 # 좌우 둘 다 안 되면 위로
                x = max(dx + 4, min(bx, dx + dw - cw))
                y = by - ch - 10
            else:
                # 짚은 것과 같은 높이로. 창 범위를 크게 벗어나지 않게 잡는다.
                anchor_cy = (w.winfo_rooty() + w.winfo_height() // 2
                             if w is not None else by + bh // 3)
                y = anchor_cy - ch // 3
                y = max(by - 40, min(y, by + bh + 40 - ch))
            x, y = screens.clamp_window(c, x, y, cw, ch)
            c.geometry(f"+{x}+{y}")
            c.lift()
        except Exception as e:
            applog.exc("안내창 위치 잡기 실패 — 기본 자리에 둔다", e)

    # ── 정리 ────────────────────────────────────────
    def _close_coach(self):
        if self._coach is not None:
            try:
                self._coach.destroy()
            except Exception:
                pass
            self._coach = None

    def _clear(self):
        self._clear_dim()
        for f in self._halo:
            try:
                f.destroy()
            except Exception:
                pass
        self._halo = []
        if self._coach is not None:
            try:
                self._coach.destroy()
            except Exception:
                pass
            self._coach = None

    def _finish(self, completed=False):
        r"""튜토리얼 종료. completed=True 는 마지막 단계까지 마친 것.

        '그만' 으로 끝냈을 때는 on_done(목록 다시 열기)을 부르지 않는다 —
        끄려고 눌렀는데 다른 창이 뜨면 "안 닫힌다"로 읽힌다 (사용자 지적).
        """
        global _active
        if self._done:
            return
        self._done = True
        if self._reflow_job is not None:
            try:
                self.root.after_cancel(self._reflow_job)
            except Exception:
                pass
            self._reflow_job = None
        self._untrack()
        self._clear()
        if self._root_topmost:              # 내려 뒀던 '항상 위' 를 되돌린다
            try:
                self.root.attributes("-topmost", True)
            except Exception:
                pass
        if _active is self:
            _active = None
        if completed and self.on_done:
            self.on_done()


class Picker(tk.Toplevel):
    r"""튜토리얼 목록 — 코스를 골라 시작한다 (사용자 결정 2026-07-26).

    하나짜리 긴 튜토리얼은 "지금 나에게 필요한 것"을 고를 수 없었다. 주제별로
    나눠 놓으면 오늘 필요한 것(예: 표 만들기)만 5분 안에 짚고 갈 수 있다.
    """

    def __init__(self, master, courses, title="튜토리얼"):
        super().__init__(master)
        self.master_win = master
        self.courses = courses
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.bind("<Escape>", lambda e: self.destroy())

        tk.Label(self, text="튜토리얼", font=(FONT, theme.fs(12), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="하고 싶은 것을 고르세요. 화면에서 눌러야 할 곳만 "
                            "밝게 남고 나머지는 흐려집니다.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED,
                 wraplength=380, justify="left").pack(anchor="w", padx=16,
                                                      pady=(0, 10))
        for c in courses:
            self._row(c)
        tk.Frame(self, bg=BG, height=8).pack()
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx() + 40}+{master.winfo_rooty() + 40}")

    def _row(self, course):
        row = tk.Frame(self, bg=ROWBG, highlightbackground=BORDER,
                       highlightthickness=1)
        row.pack(fill="x", padx=16, pady=3)
        info = tk.Frame(row, bg=ROWBG, padx=12, pady=8)
        info.pack(side="left", fill="both", expand=True)
        tk.Label(info, text=course["title"], font=(FONT, theme.fs(10), "bold"),
                 bg=ROWBG, fg=TEXT, anchor="w").pack(anchor="w")
        tk.Label(info, text=course["desc"], font=(FONT, theme.fs(8)),
                 bg=ROWBG, fg=MUTED, anchor="w", wraplength=300,
                 justify="left").pack(anchor="w")
        tk.Label(row, text=f"{len(course['steps'])}단계",
                 font=(FONT, theme.fs(8)), bg=ROWBG, fg=MUTED,
                 padx=12).pack(side="right")
        for wdg in (row, info, *info.winfo_children()):
            wdg.bind("<Button-1>", lambda e, c=course: self._start(c))
            wdg.config(cursor="hand2")
            wdg.bind("<Enter>", lambda e, r=row: self._tint(r, ACCENT_SOFT))
            wdg.bind("<Leave>", lambda e, r=row: self._tint(r, ROWBG))

    @staticmethod
    def _tint(row, bg):
        row.config(bg=bg)
        for w in row.winfo_children():
            w.config(bg=bg)
            for c in w.winfo_children():
                c.config(bg=bg)

    def _start(self, course):
        self.destroy()          # 목록은 비켜 준다 — 화면을 가리면 안 된다
        # 코스가 끝나면 목록으로 돌아온다 — 이어서 다음 코스를 하기 쉽게
        Tutorial(self.master_win, course["steps"], title=course["title"],
                 on_done=lambda: self.master_win.after(
                     300, lambda: open_picker(self.master_win, self.courses))
                 ).start()


def open_picker(master, courses):
    return Picker(master, courses)
