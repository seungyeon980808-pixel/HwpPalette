# -*- coding: utf-8 -*-
r"""문항 엑셀 창 — 양식을 만들고, 채워 온 것을 마크다운으로 바꾼다.

두 걸음뿐이다 (사용자 기획 2026-07-29):
    ① 양식 만들기  — 유형별 스타일을 고르고 빈 엑셀을 내려받는다
    ② 불러오기     — 채운 엑셀을 고르면 마크다운 + 오류 리포트 + 정답표

**한글이 켜져 있지 않아도 된다.** 여기서는 문서를 건드리지 않는다 — 만든
마크다운을 클립보드에 담아 주고, 변환은 늘 쓰던 [마크다운 변환]이 맡는다.
그 길이 이미 검증돼 있어서, 같은 일을 하는 두 번째 길을 만들지 않는다.
"""

import os
import tkinter as tk
from tkinter import filedialog, ttk

from hwp_palette.core import applog
from hwp_palette.core import clipboard      # 윈도우 클립보드 (Tk 클립보드 금지)
from hwp_palette.core import screens
from hwp_palette.design import dialogs as messagebox
from hwp_palette.design import theme
from hwp_palette.design import ui_fx
from hwp_palette.design.roundbtn import RoundButton
from hwp_palette.model import excel_form
from hwp_palette.model import excel_read

_C = theme.colors()
BG = _C["bg"]
CARD = _C["card"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
ACCENT = _C["accent"]
FONT = theme.FONT
MONO = "Consolas"        # form_fill_ui 와 같은 모노 글꼴


class ExcelWindow(tk.Toplevel):

    def __init__(self, master):
        super().__init__(master)
        # 다 만들 때까지 숨긴다 (2026-07-31, SettingsWindow 와 같은 이유) —
        # 기본 자리에 깜빡 그려졌다가 place_beside 로 건너오는 것이 보였다.
        self.withdraw()
        self.title("문항 엑셀")
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.md = ""
        self.answers = []

        tk.Label(self, text="문항 엑셀", font=(FONT, theme.fs(12), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(self,
                 text="마크다운을 치지 않고 엑셀 표에 채워 시험지를 만듭니다.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w", padx=16)

        # 무엇을 할 수 있는 창인지 첫눈에 읽히게 (사용자 지적 2026-07-31:
        # "어떤 것을 할 수 있다는 것인지 파악이 잘 안됩니다")
        guide = tk.Frame(self, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1)
        guide.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(guide, text="이 창에서 할 수 있는 것",
                 font=(FONT, theme.fs(8), "bold"), bg=CARD, fg=TEXT
                 ).pack(anchor="w", padx=12, pady=(8, 2))
        tk.Label(guide, text=(
            "· 합답형(ㄱㄴㄷ 고르기) · 정답형(오지선다) · 서술형 문항을 엑셀 표에 한 줄에 하나씩 적습니다\n"
            "· [엑셀 양식 만들기] — 열이 미리 짜인 빈 엑셀을 만듭니다. 예시 문항을 넣어 형식을 보고 배울 수 있습니다\n"
            "· [엑셀 파일 고르기] — 채워 온 엑셀을 읽어 시험지 마크다운과 정답표를 만듭니다. 잘못 쓴 칸은 읽기 결과가 짚어 줍니다\n"
            "· [마크다운 복사] 뒤 한글에 붙여넣고 선택 → [마크다운 변환] — 등록해 둔 조각 서식 그대로 시험지가 완성됩니다"),
            font=(FONT, theme.fs(8)), bg=CARD, fg=MUTED, justify="left"
        ).pack(anchor="w", padx=12, pady=(0, 8))

        self._build_make()
        self._build_load()

        self.status = tk.StringVar(value="① 양식을 만들어 엑셀에서 채워 오세요.")
        tk.Label(self, textvariable=self.status, font=(FONT, theme.fs(8)),
                 bg=BG, fg=MUTED, anchor="w").pack(fill="x", padx=16, pady=(0, 10))

        self.update_idletasks()          # 자리 계산 전에 요청 크기를 굳힌다
        ui_fx.attach_all(self)
        ui_fx.reveal(self, place=lambda: screens.place_beside(self, master))

    # ── ① 양식 만들기 ────────────────────────────────────
    def _build_make(self):
        box = tk.Frame(self, bg=BG, padx=16)
        box.pack(fill="x", pady=(12, 4))
        tk.Label(box, text="① 양식 만들기", font=(FONT, theme.fs(9), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(box, text="유형마다 어떤 틀로 뽑을지 고릅니다. "
                           "(등록된 조각이 있는 것만 보입니다)",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w",
                                                                 pady=(0, 6))

        row = tk.Frame(box, bg=BG)
        row.pack(fill="x")
        self.style_vars = {}
        for qtype in excel_form.QTYPES:
            cell = tk.Frame(row, bg=BG)
            cell.pack(side="left", padx=(0, 14))
            tk.Label(cell, text=qtype, font=(FONT, theme.fs(8)),
                     bg=BG, fg=MUTED).pack(anchor="w")
            names = excel_form.styles_for(qtype)
            var = tk.StringVar(value=names[0])
            ttk.Combobox(cell, textvariable=var, values=names, state="readonly",
                         width=14, font=(FONT, theme.fs(9))).pack()
            self.style_vars[qtype] = var

        btns = tk.Frame(box, bg=BG)
        btns.pack(fill="x", pady=(10, 0))
        self.sample_var = tk.BooleanVar(value=True)
        tk.Checkbutton(btns, text="예시 문항 5개 넣기", variable=self.sample_var,
                       font=(FONT, theme.fs(8)), bg=BG, fg=MUTED,
                       activebackground=BG, selectcolor=CARD,
                       bd=0, highlightthickness=0).pack(side="left")
        RoundButton(btns, text="엑셀 양식 만들기", command=self._make,
                    bg=ACCENT, fg="white", radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(9), "bold"), outline="",
                    # fit() 이 없으면 Canvas 기본 크기(378x265)로 나온다 —
                    # 버튼이 화면을 채우던 원인 (사용자 지적 2026-07-31)
                    zone_bg=BG).fit(pad_x=16, pad_y=6).pack(side="right")

    # ── ② 불러오기 ──────────────────────────────────────
    def _build_load(self):
        box = tk.Frame(self, bg=BG, padx=16)
        box.pack(fill="both", expand=True, pady=(14, 4))
        head = tk.Frame(box, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="② 채운 엑셀 불러오기",
                 font=(FONT, theme.fs(9), "bold"), bg=BG, fg=TEXT).pack(side="left")
        RoundButton(head, text="엑셀 파일 고르기", command=self._load,
                    bg=CARD, fg=TEXT, radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(9)), outline=BORDER,
                    zone_bg=BG).fit(pad_x=14, pad_y=5).pack(side="right")

        body = tk.Frame(box, bg=BG)
        body.pack(fill="both", expand=True, pady=(8, 0))
        body.columnconfigure(0, weight=1, uniform="c")
        body.columnconfigure(1, weight=1, uniform="c")
        body.rowconfigure(1, weight=1)

        tk.Label(body, text="읽기 결과", font=(FONT, theme.fs(8), "bold"),
                 bg=BG, fg=TEXT).grid(row=0, column=0, sticky="w")
        tk.Label(body, text="만들어진 마크다운", font=(FONT, theme.fs(8), "bold"),
                 bg=BG, fg=TEXT).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.report_box = tk.Text(body, width=40, height=11, font=(FONT, theme.fs(8)),
                                  relief="solid", bd=1, wrap="word")
        self.report_box.grid(row=1, column=0, sticky="nsew")
        self.md_box = tk.Text(body, width=40, height=11, font=(MONO, theme.fs(8)),
                              relief="solid", bd=1, wrap="none")
        self.md_box.grid(row=1, column=1, sticky="nsew", padx=(8, 0))

        foot = tk.Frame(box, bg=BG)
        foot.pack(fill="x", pady=(10, 0))
        RoundButton(foot, text="정답표 복사", command=self._copy_answers,
                    bg=CARD, fg=TEXT, radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(9)), outline=BORDER,
                    zone_bg=BG).fit(pad_x=14, pad_y=5).pack(side="left")
        RoundButton(foot, text="마크다운 복사", command=self._copy_md,
                    bg=ACCENT, fg="white", radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(10), "bold"), outline="",
                    zone_bg=BG).fit(pad_x=16, pad_y=6).pack(side="right")
        tk.Label(foot, text="한글에 붙여넣고 선택한 뒤 [마크다운 변환]",
                 font=(FONT, theme.fs(8)), bg=BG,
                 fg=MUTED).pack(side="right", padx=(0, 10))

    # ── 동작 ────────────────────────────────────────────
    def _make(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="엑셀 양식 저장", defaultextension=".xlsx",
            initialfile="문항작성양식.xlsx",
            filetypes=[("엑셀 파일", "*.xlsx")])
        if not path:
            return
        styles = {q: v.get() for q, v in self.style_vars.items()}
        try:
            excel_form.build_workbook(path, styles=styles,
                                      with_samples=self.sample_var.get())
        except PermissionError:
            messagebox.showwarning(
                "저장하지 못했습니다",
                "같은 이름의 파일이 엑셀에서 열려 있는 것 같습니다.\n"
                "닫고 다시 눌러 주세요.", parent=self)
            return
        except Exception as e:
            applog.exc("엑셀 양식 만들기 실패", e)
            messagebox.showerror("엑셀 양식을 만들지 못했습니다", str(e), parent=self)
            return

        self.status.set("만들었습니다 — 엑셀에서 채운 뒤 ②로 불러오세요.")
        if messagebox.askyesno("만들었습니다", "지금 엑셀로 열어볼까요?", parent=self):
            try:
                os.startfile(path)
            except Exception as e:
                applog.exc("엑셀 양식 열기 실패 (파일은 만들어졌다)", e)

    def _load(self):
        path = filedialog.askopenfilename(
            parent=self, title="채운 엑셀 고르기",
            filetypes=[("엑셀 파일", "*.xlsx"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            md, report, answers = excel_read.read_workbook(path)
        except Exception as e:
            applog.exc("문항 엑셀 읽기 실패", e)
            messagebox.showerror("엑셀을 읽지 못했습니다", str(e), parent=self)
            return

        self.md, self.answers = md, answers
        self._set(self.report_box, "\n".join(report))
        self._set(self.md_box, md)
        self.status.set("문항 %d개 — [마크다운 복사] 뒤 한글에 붙여넣으세요."
                        % len(answers) if answers
                        else "읽을 문항이 없습니다. 엑셀을 확인해 주세요.")

    @staticmethod
    def _set(box, text):
        box.delete("1.0", "end")
        box.insert("1.0", text)

    def _copy_md(self):
        if not self.md.strip():
            self.status.set("먼저 채운 엑셀을 불러오세요.")
            return
        clipboard.set_text(self.md, self)
        self.status.set("복사했습니다 — 한글에 붙여넣고 선택한 뒤 [마크다운 변환].")

    def _copy_answers(self):
        if not self.answers:
            self.status.set("먼저 채운 엑셀을 불러오세요.")
            return
        clipboard.set_text(excel_read.answers_to_text(self.answers), self)
        self.status.set("정답표를 복사했습니다 — 엑셀·한글 표에 그대로 붙습니다.")


def open_excel(master):
    return ExcelWindow(master)
