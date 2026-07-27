# -*- coding: utf-8 -*-
r"""양식 채우기 표 — 채울 자리를 표로 보여주고, 손으로 채워 한글로 연다.

왜 따로 만드는가 (2026-07-27):
    기존 form_fill_ui 는 "자리 목록을 뽑아 클립보드로 → AI 에게 → 답을 붙여넣기"
    구조라, **손으로 채우려면** `[3] 내용` 형식을 사람이 직접 타이핑해야 했다.
    원안지처럼 학년·교과명·날짜 일곱 칸을 채우는 일에는 표가 압도적으로 낫다.
    AI 로 넘기는 길은 여기서도 버튼 두 개(복사/붙여넣기)로 남겨 둔다.

자리를 어떻게 아는가:
    양식에 `\학년\` 처럼 이름표를 심어두면 그 이름이 곧 칸 이름이 된다
    (form_fill.named_slots). 이름을 안 심은 옛 양식은 홑 `\` 가 순서대로
    '빈칸 1, 2 …' 로 나오고, 왼쪽 미리보기 그림과 견주며 채우면 된다.

한글이 필요한 지점:
    .hwp 는 HWPX 로 바꿔야 채울 수 있어 그때 한 번(engine_library.export_as_hwpx),
    그리고 다 채운 결과를 열 때 한 번. 표를 띄우고 값을 치는 동안은 필요 없다.
"""

import pathlib
import tkinter as tk
from tkinter import ttk
import dialogs as messagebox   # 윈도우 기본 대화상자 대신 프로그램과 같은 얼굴 (2026-07-27)

import applog
import clipboard                  # 윈도우 클립보드 (Tk 클립보드 금지 — clipboard.py 머리말)
import engine_library
import form_fill
import hwp_engine
import paths
import preview                    # 물감 미리보기 그림 (hwp 안의 PrvImage)

import appinfo
import screens                    # 창 자리 규칙 (메인 창 옆)
import theme
import ui_fx
from roundbtn import RoundButton

_C = theme.colors()
BG = _C["bg"]
CARD = _C["card"]
ACCENT = _C["accent"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
ROWBG = _C["subbg"]
SOFT = _C["yellow"]
FONT = theme.FONT
SP = theme.SP
FS = theme.FS

PREVIEW_W, PREVIEW_H = 300, 420
ROW_H = 30


class FormTableWindow(tk.Toplevel):
    def __init__(self, master, src_path, title=None):
        super().__init__(master)
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.src = pathlib.Path(src_path)
        self.form_name = title or self.src.stem
        self.hwpx = None
        self.slots = []                 # [(이름, 나온 횟수)]
        self.vars = {}                  # 이름 → StringVar
        self._photo = None              # ⚠ 참조를 붙들어야 그림이 안 사라진다

        tk.Label(self, text=f"양식 채우기 — {self.form_name}",
                 font=(FONT, theme.fs(FS["title"]), "bold"), bg=BG, fg=TEXT
                 ).pack(anchor="w", padx=SP["l"], pady=(SP["m"], 2))
        self.sub = tk.Label(self, text="채울 자리를 읽는 중…",
                            font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED)
        self.sub.pack(anchor="w", padx=16)

        body = tk.Frame(self, bg=BG, padx=SP["l"], pady=SP["s"])
        body.pack(fill="both", expand=True)

        # 왼쪽 — 한글이 그려둔 미리보기 그림
        left = tk.Frame(body, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        left.pack(side="left", fill="y")
        self.pv_label = tk.Label(left, bg=CARD, fg=MUTED, font=(FONT, theme.fs(FS["sub"])),
                                 text="미리보기 없음", width=34, height=22)
        self.pv_label.pack(padx=8, pady=8)

        # 오른쪽 — 채울 표
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        head = tk.Frame(right, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="칸", font=(FONT, theme.fs(FS["sub"]), "bold"), bg=BG,
                 fg=MUTED, width=16, anchor="w").pack(side="left")
        tk.Label(head, text="값", font=(FONT, theme.fs(FS["sub"]), "bold"), bg=BG,
                 fg=MUTED, anchor="w").pack(side="left")

        # 자리가 많으면 스크롤이 필요하다 (원안지는 7개지만 양식마다 다르다)
        wrap = tk.Frame(right, bg=BG)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, width=380)
        messagebox.style_scrollbars(self)
        bar = ttk.Scrollbar(wrap, orient="vertical",
                            style="App.Vertical.TScrollbar",
                            command=self.canvas.yview)
        self.rows = tk.Frame(self.canvas, bg=BG)
        self.rows.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.rows, anchor="nw")
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        foot = tk.Frame(self, bg=BG, padx=SP["l"], pady=SP["m"])
        foot.pack(fill="x")
        RoundButton(foot, text="채워서 한글로 열기", command=self._apply,
                    bg=ACCENT, fg="white", radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["head"]), "bold"), outline="", zone_bg=BG
                    ).fit(pad_x=16, pad_y=8).pack(side="right")
        RoundButton(foot, text="마크다운 붙여넣기", command=self._paste_md,
                    bg=SOFT, fg=TEXT, radius=theme.RADIUS["ctl"], font=(FONT, theme.fs(FS["body"])),
                    outline="", zone_bg=BG).fit(pad_x=12, pad_y=7).pack(side="left")
        RoundButton(foot, text="마크다운으로 복사", command=self._copy_md,
                    bg=SOFT, fg=TEXT, radius=theme.RADIUS["ctl"], font=(FONT, theme.fs(FS["body"])),
                    outline="", zone_bg=BG).fit(pad_x=12, pad_y=7).pack(
                    side="left", padx=(8, 0))

        self.status = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status, font=(FONT, theme.fs(FS["sub"])),
                 bg=BG, fg=MUTED, anchor="w").pack(fill="x", padx=SP["l"], pady=(0, SP["s"]))

        screens.place_beside(self, master)
        ui_fx.attach_all(self)
        self.after(60, self._load)      # 창을 먼저 띄우고 읽는다 (한글 변환은 느리다)

    # ── 준비 ──────────────────────────────────────
    def _load(self):
        self._show_preview()
        if not self._ensure_hwpx():
            self.destroy()
            return
        try:
            self.slots = form_fill.named_slots(self.hwpx)
        except Exception as e:
            applog.exc(f"채울 자리 읽기 실패 ({self.src.name})", e)
            messagebox.showerror("실패", f"{type(e).__name__}: {e}", parent=self)
            self.destroy()
            return
        if not self.slots:
            messagebox.showinfo(
                "채울 자리 없음",
                "이 양식에는 채울 자리(\\)가 없습니다.\n"
                "그냥 열어서 쓰시면 됩니다.", parent=self)
            self.destroy()
            engine_library.open_form(self.src, strip_markers=True)
            return
        self._build_rows()
        named = sum(1 for n, _ in self.slots
                    if not n.startswith(form_fill.UNNAMED_PREFIX))
        self.sub.config(text=(f"채울 자리 {len(self.slots)}개"
                              + (f" (이름표 {named}개)" if named else
                                 " — 이름표가 없어 순서대로 나열했습니다")))

    def _show_preview(self):
        try:
            photo = preview.tk_photo(self.src, PREVIEW_W, PREVIEW_H)
        except Exception as e:
            applog.exc(f"미리보기 그림 실패 ({self.src.name})", e)
            photo = None
        if photo is None:
            return
        self._photo = photo             # 참조 유지 (없으면 빈칸으로 보인다)
        self.pv_label.config(image=photo, text="", width=0, height=0)

    def _ensure_hwpx(self):
        r"""채우기 대상 HWPX 를 준비한다. .hwp 면 한글로 변환한다.

        결과물은 **작업 폴더**에 둔다 — 물감 조각이 있는 fragments/ 에 쓰면
        찌꺼기가 물감 목록 옆에 쌓인다.
        """
        if self.src.suffix.lower() == ".hwpx":
            self.hwpx = self.src
            return True
        try:
            hwp_engine.connect()
        except Exception as e:
            applog.exc("양식 채우기: 한글 연결 실패", e)
            messagebox.showerror("연결 실패",
                                 f"한글을 먼저 실행해주세요.\n{e}", parent=self)
            return False
        dst = self._work_dir() / (self.src.stem + ".hwpx")
        try:
            engine_library.export_as_hwpx(self.src, dst)
        except Exception as e:
            applog.exc(f"HWPX 변환 실패 ({self.src.name})", e)
            messagebox.showerror("변환 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            return False
        self.hwpx = dst
        return True

    def _work_dir(self):
        d = paths.data_dir() / "양식작업"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _build_rows(self):
        for w in self.rows.winfo_children():
            w.destroy()
        self.vars.clear()
        for i, (name, n) in enumerate(self.slots):
            row = tk.Frame(self.rows, bg=ROWBG if i % 2 else BG)
            row.pack(fill="x")
            label = name + (f"  ×{n}" if n > 1 else "")
            tk.Label(row, text=label, font=(FONT, theme.fs(FS["body"])),
                     bg=row["bg"], fg=TEXT, width=16, anchor="w"
                     ).pack(side="left", padx=(2, 6), pady=3)
            var = tk.StringVar()
            self.vars[name] = var
            # 포커스 링이 있는 입력칸 — 키보드로 옮겨 다닐 때 지금 어느 칸에
            # 있는지 보여야 한다 (2026-07-27 디자인 개편)
            box, ent = messagebox.field(row, textvariable=var)
            box.pack(side="left", fill="x", expand=True, padx=(0, SP["xs"]),
                     pady=2)
            # 표처럼 위아래로 옮겨 다니게 — 손으로 채울 때 손이 마우스로 안 가게
            ent.bind("<Return>", lambda e: e.widget.tk_focusNext().focus())
            ent.bind("<Down>", lambda e: e.widget.tk_focusNext().focus())
            ent.bind("<Up>", lambda e: e.widget.tk_focusPrev().focus())
            if i == 0:
                ent.focus_set()

    # ── 동작 ──────────────────────────────────────
    def _values(self):
        return {name: var.get().strip() for name, var in self.vars.items()}

    def _copy_md(self):
        md = form_fill.to_named_markdown(self.slots, self._values(),
                                         title=self.form_name)
        clipboard.set_text(md, widget=self)
        self.status.set("복사했습니다 — AI 에 붙여넣고 채워서 받아오세요.")

    def _paste_md(self):
        text = clipboard.get_text() or ""
        vals = form_fill.parse_named_markdown(text)
        if not vals:
            messagebox.showwarning(
                "읽을 것 없음",
                "클립보드에서 '이름: 값' 형태의 줄을 찾지 못했습니다.",
                parent=self)
            return
        hit = 0
        for name, var in self.vars.items():
            if name in vals:
                var.set(vals[name])
                hit += 1
        self.status.set(f"{hit}칸을 채웠습니다." if hit else
                        "이름이 맞는 칸이 없습니다 — 이름을 바꾸지 마세요.")

    def _apply(self):
        values = {k: v for k, v in self._values().items() if v}
        if not values:
            if not messagebox.askyesno(
                    "빈 채로 열기",
                    "채운 칸이 하나도 없습니다.\n"
                    "이대로 열면 채울 자리 표시가 모두 지워집니다. 계속할까요?",
                    parent=self):
                return
        dst = self._work_dir() / (self.src.stem + "_완성.hwpx")
        try:
            filled, wiped = form_fill.fill_named(self.hwpx, dst, values)
            hwp_engine.connect()
            engine_library.open_form(dst)
        except Exception as e:
            applog.exc(f"양식 채우기 실패 ({self.src.name})", e)
            messagebox.showerror("실패", f"{type(e).__name__}: {e}", parent=self)
            return
        # 이 창이 -topmost 라 방금 연 한글 문서가 그 뒤에 가려 안 보이는
        # 문제와 같은 원인이다 (library_ui.edit_content 진단 참고, 2026-07-27).
        # 채우기가 끝나면 이 창의 역할도 끝난 것이므로 그냥 꺼 둔다.
        self.attributes("-topmost", False)
        hwp_engine.bring_to_front()
        msg = f"{filled}자리를 채워 열었습니다."
        if wiped:
            msg += f" (안 채운 자리 {wiped}개는 지웠습니다)"
        self.status.set(msg)


def open_form_table(master, src_path, title=None):
    """양식 채우기 표 창을 연다."""
    win = FormTableWindow(master, src_path, title=title)
    win.focus_force()
    return win


class TemplateTableWindow(tk.Toplevel):
    r"""이름 있는 템플릿의 채우기 표 (2026-07-27).

    양식 표(FormTableWindow)와 다른 점: 양식은 파일을 고쳐서 **새 문서로
    열지만**, 템플릿은 값을 받아 **커서 자리에 꽂는다**. HWPX 변환도 없다 —
    삽입과 채우기 모두 마크다운 변환과 같은 엔진(fill_slots)을 쓴다.

    표의 줄은 물감에 적어 둔 자리 목록(slot_names) 순서다. 같은 이름이 여러
    번 나오면 한 줄로 합치고, 채울 때 그 값을 나온 횟수만큼 넣는다.
    """

    def __init__(self, master, item, src_path):
        super().__init__(master)
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.item = item
        self.src = pathlib.Path(src_path)
        self.tokens = list(item.get("slot_names") or [])
        self.vars = {}                  # 표 줄 키 → StringVar
        self._photo = None

        tk.Label(self, text=f"채우기 — {item.get('name', '')}",
                 font=(FONT, theme.fs(FS["title"]), "bold"), bg=BG, fg=TEXT
                 ).pack(anchor="w", padx=SP["l"], pady=(SP["m"], 2))
        tk.Label(self, text="채우면 한글 커서 자리에 완성된 채로 들어갑니다. "
                            "빈 칸은 비워진 채 들어갑니다.",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED
                 ).pack(anchor="w", padx=16)

        body = tk.Frame(self, bg=BG, padx=SP["l"], pady=SP["s"])
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        left.pack(side="left", fill="y")
        pv = tk.Label(left, bg=CARD, fg=MUTED, font=(FONT, theme.fs(FS["sub"])),
                      text="미리보기 없음", width=30, height=16)
        pv.pack(padx=8, pady=8)
        try:
            photo = preview.tk_photo_for_item(item, self.src, 260, 340)
            if photo is not None:
                self._photo = photo
                pv.config(image=photo, text="", width=0, height=0)
        except Exception as e:
            applog.exc(f"템플릿 미리보기 실패 — {item.get('name')}", e)

        rows = tk.Frame(body, bg=BG)
        rows.pack(side="left", fill="both", expand=True, padx=(12, 0))
        # 표 줄: 이름 있는 자리는 이름으로 합치고, 없는 자리는 순번으로
        self.row_keys = []              # 표 줄 순서 (이름 or "빈칸 n")
        counts = {}
        unnamed = 0
        for tok in self.tokens:
            if tok:
                if tok not in counts:
                    self.row_keys.append(tok)
                counts[tok] = counts.get(tok, 0) + 1
            else:
                unnamed += 1
                self.row_keys.append(f"빈칸 {unnamed}")
        first = None
        for i, key in enumerate(self.row_keys):
            row = tk.Frame(rows, bg=ROWBG if i % 2 else BG)
            row.pack(fill="x")
            n = counts.get(key, 1)
            tk.Label(row, text=key + (f"  ×{n}" if n > 1 else ""),
                     font=(FONT, theme.fs(FS["body"])), bg=row["bg"], fg=TEXT,
                     width=14, anchor="w").pack(side="left", padx=(2, 6), pady=3)
            var = tk.StringVar()
            self.vars[key] = var
            # 포커스 링이 있는 입력칸 — 키보드로 옮겨 다닐 때 지금 어느 칸에
            # 있는지 보여야 한다 (2026-07-27 디자인 개편)
            box, ent = messagebox.field(row, textvariable=var)
            box.pack(side="left", fill="x", expand=True, padx=(0, SP["xs"]),
                     pady=2)
            ent.bind("<Return>", lambda e: e.widget.tk_focusNext().focus())
            ent.bind("<Down>", lambda e: e.widget.tk_focusNext().focus())
            ent.bind("<Up>", lambda e: e.widget.tk_focusPrev().focus())
            first = first or ent
        if first:
            first.focus_set()

        foot = tk.Frame(self, bg=BG, padx=SP["l"], pady=SP["m"])
        foot.pack(fill="x")
        RoundButton(foot, text="커서 자리에 넣기", command=self._apply,
                    bg=ACCENT, fg="white", radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["head"]), "bold"), outline="", zone_bg=BG
                    ).fit(pad_x=16, pad_y=8).pack(side="right")
        self.status = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status, font=(FONT, theme.fs(FS["sub"])),
                 bg=BG, fg=MUTED, anchor="w").pack(fill="x", padx=16,
                                                   pady=(0, 10))
        screens.place_beside(self, master)
        ui_fx.attach_all(self)

    def _apply(self):
        values = {k: v.get().strip() for k, v in self.vars.items()}
        # 자리 순서대로 값을 늘어놓는다 — 같은 이름은 같은 값이 여러 번 들어간다
        fills, unnamed = [], 0
        for tok in self.tokens:
            if tok:
                key = tok
            else:
                unnamed += 1
                key = f"빈칸 {unnamed}"
            fills.append(values.get(key) or None)   # 빈 칸은 비워 넣는다
        try:
            hwp_engine.connect()
            filled, want = engine_library.insert_template_filled(
                library_template_path(self.item), fills,
                slot_count=len(self.tokens))
        except Exception as e:
            applog.exc(f"템플릿 채워 넣기 실패 — {self.item.get('name')}", e)
            messagebox.showerror("실패", f"{type(e).__name__}: {e}", parent=self)
            return
        # 같은 이유로(이 창의 -topmost 가 방금 채운 문서를 가림) 끄고 앞으로.
        self.attributes("-topmost", False)
        hwp_engine.bring_to_front()
        self.status.set(f"{filled}자리를 채워 넣었습니다.")


def library_template_path(item):
    import library                  # 지역 import — 이 모듈은 library 에 안 기댄다
    return library.template_path(item)


def open_template_table(master, item):
    win = TemplateTableWindow(master, item, library_template_path(item))
    win.focus_force()
    return win
