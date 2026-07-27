# -*- coding: utf-8 -*-
"""보기박스 시각 편집 창 (Toplevel).

캔버스에 보기박스를 축척으로 그리고, 슬라이더를 움직이면 즉시 다시 그린다.
지금 조절 중인 치수는 파란 화살표로 강조된다(어떤 숫자가 어디인지 보면서 수정).

- 도식은 근사(실제 한글 렌더가 아님). 100% 확인은 '실제 한글에 미리 삽입' 버튼.
- 저장하면 활성 프리셋의 bogi_box에 반영하고 on_saved 콜백으로 알린다.
"""

import tkinter as tk
import dialogs as messagebox   # 윈도우 기본 대화상자 대신 프로그램과 같은 얼굴 (2026-07-27)

import settings
import exam_engine
import hwp_engine

import theme                       # 색은 theme.py 한 곳에서 (밝게/어둡게)

_C = theme.colors()
BG   = _C["bg"]
CARD = _C["card"]
TEXT = _C["text"]
MUTED = _C["muted"]
ACCENT = _C["accent"]
BORDER = _C["border"]
LINE = _C["border"]
FONT = theme.FONT

# (키, 라벨, 최소, 최대, 스텝, 단위)
CONTROLS = [
    ("content_height_mm",   "내용 칸 높이",  10.0, 45.0, 0.5, "mm"),
    ("title_height_mm",     "제목 위 높이",   0.0, 10.0, 0.5, "mm"),
    ("gap_height_mm",       "제목 아래 높이", 0.0, 10.0, 0.5, "mm"),
    ("cell_margin_left_mm", "셀 좌우 여백",   0.0,  8.0, 0.5, "mm"),
    ("cell_margin_bottom_mm","셀 아래 여백",  0.0, 10.0, 0.5, "mm"),
    ("cell_margin_top_mm",  "셀 위 여백",     0.0,  6.0, 0.5, "mm"),
    ("line_spacing",        "줄간격",       100,  200,    5, "%"),
]


class BogiVisualEditor(tk.Toplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.on_saved = on_saved
        self.title("보기박스 시각 편집")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.spec = settings.get_active_spec()
        self.box = dict(self.spec["bogi_box"])      # 편집 중 사본
        self.active = "content_height_mm"
        self.vars = {}

        wrap = tk.Frame(self, bg=BG, padx=14, pady=12)
        wrap.pack(fill="both", expand=True)

        # 좌: 캔버스 도식
        left = tk.Frame(wrap, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        left.grid(row=0, column=0, sticky="n", padx=(0, 14))
        self.canvas = tk.Canvas(left, width=300, height=230, bg=CARD,
                                highlightthickness=0)
        self.canvas.pack(padx=10, pady=10)

        # 우: 컨트롤
        right = tk.Frame(wrap, bg=BG)
        right.grid(row=0, column=1, sticky="n")
        tk.Label(right, text=f"양식: {settings.get_active_name()}",
                 font=(FONT, theme.fs(9), "bold"), fg=ACCENT, bg=BG).pack(anchor="w", pady=(0, 8))

        for key, label, lo, hi, step, unit in CONTROLS:
            self._add_slider(right, key, label, lo, hi, step, unit)

        tk.Label(right,
                 text="슬라이더를 만지면 도식이 바로 바뀌고,\n"
                      "지금 값이 파란 화살표로 강조됩니다.\n"
                      "높이는 '최소값'이라 내용이 크면 늘어납니다.",
                 font=(FONT, theme.fs(8)), fg=MUTED, bg=BG, justify="left").pack(
                 anchor="w", pady=(10, 0))

        # 하단 버튼
        foot = tk.Frame(self, bg=BG, padx=14, pady=8)
        foot.pack(fill="x", pady=(0, 8))
        tk.Button(foot, text="🖼 실제 한글에 미리 삽입", command=self._preview_hwp,
                  font=(FONT, theme.fs(9)), bg="#e8e8ed", fg=TEXT, bd=0, padx=12, pady=7,
                  cursor="hand2").pack(side="left")
        tk.Button(foot, text="💾 저장", command=self._save,
                  font=(FONT, theme.fs(10), "bold"), bg=ACCENT, fg="white", bd=0,
                  padx=18, pady=7, cursor="hand2").pack(side="right")
        tk.Button(foot, text="닫기", command=self.destroy,
                  font=(FONT, theme.fs(10)), bg="#e8e8ed", fg=TEXT, bd=0,
                  padx=16, pady=7, cursor="hand2").pack(side="right", padx=(0, 6))

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()-380}+{master.winfo_rooty()}")
        self._draw()

    def _add_slider(self, parent, key, label, lo, hi, step, unit):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=3)
        head = tk.Frame(row, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text=label, font=(FONT, theme.fs(9)), fg=TEXT, bg=BG).pack(side="left")
        val = tk.DoubleVar(value=float(self.box.get(key, lo)))
        self.vars[key] = (val, unit)
        out = tk.Label(head, text=self._fmt(val.get(), unit),
                       font=(FONT, theme.fs(9), "bold"), fg=TEXT, bg=BG)
        out.pack(side="right")

        def on_change(v, k=key, o=out, u=unit):
            self.box[k] = float(v) if u != "%" else int(float(v))
            self.active = k
            o.config(text=self._fmt(float(v), u))
            self._draw()

        s = tk.Scale(row, from_=lo, to=hi, resolution=step, orient="horizontal",
                     variable=val, command=on_change, showvalue=0,
                     bg=BG, fg=TEXT, troughcolor="#e8e8ed", highlightthickness=0,
                     bd=0, sliderrelief="flat", length=210, width=12)
        s.pack(fill="x")
        s.bind("<Button-1>", lambda e, k=key: self._set_active(k))

    def _set_active(self, key):
        self.active = key
        self._draw()

    @staticmethod
    def _fmt(v, unit):
        if unit == "%":
            return f"{int(round(v))}%"
        return f"{v:g}mm"

    # ── 도식 그리기 ───────────────────────────────────
    def _draw(self):
        c = self.canvas
        c.delete("all")
        S = 2.6                     # px per mm (높이 축척)
        boxL, boxW, topY = 92, 165, 24
        b = self.box
        title_above = b["title_height_mm"] * S
        content_h = b["content_height_mm"] * S
        cellL = b["cell_margin_left_mm"] * S
        cellT = b["cell_margin_top_mm"] * S
        cellB = b["cell_margin_bottom_mm"] * S

        title_y = topY + title_above
        c_top = title_y
        c_bot = c_top + content_h
        line_gap = 15 * (b["line_spacing"] / 100.0)
        lx = boxL + cellL + 8
        ly0 = c_top + cellT + 14

        def color(k):
            return ACCENT if self.active == k else MUTED

        def arrow(x1, y1, x2, y2, k):
            col = color(k)
            wd = 2 if self.active == k else 1
            c.create_line(x1, y1, x2, y2, fill=col, width=wd,
                          arrow="both", arrowshape=(6, 7, 3))

        def dlabel(x, y, t, k, anchor="w"):
            col = color(k)
            font = (FONT, theme.fs(8), "bold") if self.active == k else (FONT, theme.fs(8))
            c.create_text(x, y, text=t, fill=col, font=font, anchor=anchor)

        # 내용 박스 테두리
        c.create_rectangle(boxL, c_top, boxL + boxW, c_bot,
                           outline=TEXT, width=2)
        # 〈보기〉 — 위 테두리에 걸침
        tcx = boxL + boxW / 2
        c.create_rectangle(tcx - 26, title_y - 8, tcx + 26, title_y + 8,
                           outline="", fill=CARD)
        c.create_text(tcx, title_y, text="〈보 기〉", fill=TEXT, font=(FONT, theme.fs(10)))
        # ㄱㄴㄷ
        for i, lab in enumerate(["ㄱ.", "ㄴ.", "ㄷ."]):
            c.create_text(lx, ly0 + i * line_gap, text=lab, fill=TEXT,
                          font=(FONT, theme.fs(10)), anchor="w")

        # 치수 화살표
        arrow(boxL + boxW + 16, c_top, boxL + boxW + 16, c_bot, "content_height_mm")
        dlabel(boxL + boxW + 22, (c_top + c_bot) / 2, "내용\n높이", "content_height_mm")

        arrow(boxL - 16, topY, boxL - 16, title_y, "title_height_mm")
        dlabel(boxL - 20, (topY + title_y) / 2, "제목위", "title_height_mm", "e")

        arrow(boxL - 16, title_y, boxL - 16, c_top + 0.001 + b["gap_height_mm"] * S, "gap_height_mm") \
            if b["gap_height_mm"] > 0 else None

        arrow(boxL, c_top + 9, boxL + max(cellL, 2), c_top + 9, "cell_margin_left_mm")
        dlabel(boxL + cellL + 6, c_top + 6, "좌우여백", "cell_margin_left_mm")

        arrow(lx + 46, ly0 - 5, lx + 46, ly0 - 5 + line_gap, "line_spacing")
        dlabel(lx + 52, ly0 - 5 + line_gap / 2, "줄간격", "line_spacing")

        arrow(boxL + 20, ly0 + 2 * line_gap + 3, boxL + 20, c_bot, "cell_margin_bottom_mm")
        dlabel(boxL + 26, (ly0 + 2 * line_gap + c_bot) / 2, "아래여백", "cell_margin_bottom_mm")

        arrow(lx - 3, c_top, lx - 3, ly0 - 5, "cell_margin_top_mm")
        dlabel(lx + 2, (c_top + ly0 - 5) / 2, "위여백", "cell_margin_top_mm")

    # ── 미리 삽입 / 저장 ──────────────────────────────
    def _preview_hwp(self):
        try:
            hwp_engine.connect()
        except Exception as e:
            messagebox.showerror("연결 실패",
                                 f"한글을 먼저 실행해주세요.\n{e}", parent=self)
            return
        try:
            spec = settings.get_active_spec()
            spec["bogi_box"] = dict(self.box)      # 현재 미저장 값으로
            hwp_engine.set_active_spec(spec)
            exam_engine.insert_bogi_box(["보기 예시 항목 하나", "보기 예시 항목 둘",
                                        "보기 예시 항목 셋"])
            # 원래 저장된 활성 스펙으로 복원(미저장 상태 반영 방지)
            hwp_engine.set_active_spec(settings.get_active_spec())
        except Exception as e:
            messagebox.showerror("오류", f"{type(e).__name__}: {e}", parent=self)

    def _save(self):
        self.spec["bogi_box"] = dict(self.box)
        settings.save_profile(settings.get_active_name(), self.spec)
        if self.on_saved:
            self.on_saved()
        messagebox.showinfo("저장", "보기박스 양식을 저장했습니다.", parent=self)


def open_editor(master, on_saved=None):
    return BogiVisualEditor(master, on_saved=on_saved)
