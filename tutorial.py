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
CARD = _C["card"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
FONT = theme.FONT

_HALO_PX = 3            # 테두리 두께


class Tutorial:

    def __init__(self, root, steps, on_done=None):
        self.root = root
        self.steps = steps
        self.on_done = on_done
        self.i = 0
        self._halo = []         # 테두리 조각 4개
        self._coach = None

    def start(self):
        if not self.steps:
            return
        self._show(0)

    # ── 한 단계 ─────────────────────────────────────
    def _show(self, i):
        self._clear()
        if i >= len(self.steps):
            self._finish()
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
        if w is not None:
            self._draw_halo(w)
        self._draw_coach(w, step["title"], step["text"],
                         last=(i == len(self.steps) - 1))

    def _draw_halo(self, w):
        """대상 둘레 4변에 파란 띠 — root 좌표계에 place 로 얹는다."""
        rx = w.winfo_rootx() - self.root.winfo_rootx()
        ry = w.winfo_rooty() - self.root.winfo_rooty()
        ww, wh = w.winfo_width(), w.winfo_height()
        p = _HALO_PX
        rects = ((rx - p, ry - p, ww + 2 * p, p),          # 위
                 (rx - p, ry + wh, ww + 2 * p, p),         # 아래
                 (rx - p, ry - p, p, wh + 2 * p),          # 왼쪽
                 (rx + ww, ry - p, p, wh + 2 * p))         # 오른쪽
        for x, y, fw, fh in rects:
            f = tk.Frame(self.root, bg=ACCENT)
            f.place(x=x, y=y, width=fw, height=fh)
            self._halo.append(f)

    def _draw_coach(self, w, title, text, last):
        c = self._coach = tk.Toplevel(self.root)
        c.wm_overrideredirect(True)
        c.attributes("-topmost", True)
        c.configure(bg=BORDER)
        body = tk.Frame(c, bg=CARD)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(body, text=f"{self.i + 1}/{len(self.steps)}  {title}",
                 font=(FONT, theme.fs(9), "bold"), bg=CARD, fg=TEXT,
                 anchor="w", padx=12, pady=6).pack(fill="x")
        tk.Label(body, text=text, font=(FONT, theme.fs(8)), bg=CARD, fg=MUTED,
                 justify="left", wraplength=260, padx=12).pack(anchor="w")
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
        # 대상 오른쪽 옆. 그 모니터를 벗어나면 왼쪽으로 넘긴다.
        # 기준은 **모든 모니터를 합친 범위** — 주 모니터 크기로만 재면 왼쪽
        # 모니터(x 가 음수)에서 안내가 딴 화면으로 튄다 (2026-07-26).
        c.update_idletasks()
        cw, ch = c.winfo_reqwidth(), c.winfo_reqheight()
        dx, _dy, dw, _dh = screens.desktop_bounds(c)
        if w is None:       # 짚을 위젯이 없는 단계 — 이 창 오른쪽에 세워 둔다
            x = self.root.winfo_rootx() + self.root.winfo_width() + 12
            y = self.root.winfo_rooty() + 60
        else:
            x = w.winfo_rootx() + w.winfo_width() + 12
            y = w.winfo_rooty()
            if x + cw > dx + dw:
                x = w.winfo_rootx() - cw - 12
        x, y = screens.clamp_window(c, x, y, cw, ch)
        c.geometry(f"+{x}+{y}")

    # ── 정리 ────────────────────────────────────────
    def _clear(self):
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

    def _finish(self):
        self._clear()
        if self.on_done:
            self.on_done()
