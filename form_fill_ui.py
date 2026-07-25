# -*- coding: utf-8 -*-
r"""양식 채우기 창 — 양식을 던지면 '채울 자리'를 뽑아주고, 채운 걸 받아 넣는다.

쓰는 흐름:
  ① 양식 파일 고르기 (.hwp / .hwpx)
  ② [채울 자리 뽑기] → 왼쪽에 목록이 뜨고 클립보드에도 복사된다
  ③ 그걸 Claude 같은 AI에 붙여넣고 "채워줘" → 받은 답을 오른쪽에 붙여넣기
  ④ [채워서 한글로 열기] → 원본 서식 그대로 채워진 문서가 열린다

AI 호출은 이 프로그램이 하지 않는다. 사람이 복사·붙여넣기로 나른다 —
그래서 API 키도, 네트워크도, 비용도 없다. 서식이 보존되는 근거는 form_fill 참고.
"""

import pathlib
import tkinter as tk
from tkinter import filedialog, messagebox

import applog
import engine_library
import form_fill
import hwp_engine

import theme                       # 색은 theme.py 한 곳에서 (밝게/어둡게)
import ui_fx                       # 호버 보간 (애플 A안)

_C = theme.colors()
BG = _C["bg"]
CARD = _C["card"]
ACCENT = _C["accent"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
FONT = theme.FONT
MONO = "Consolas"


class FormFillWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("양식 채우기")
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.src = None          # 사용자가 고른 원본
        self.hwpx = None         # HWPX 로 바꾼 것 (채우기의 실제 대상)

        tk.Label(self, text="양식 채우기", font=(FONT, theme.fs(12), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(self,
                 text="양식을 고르면 채울 자리를 뽑아줍니다. AI에 붙여넣고 채워서 "
                      "오른쪽에 다시 붙여넣으세요.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w", padx=16)

        # ── 파일 고르기 ──
        pick = tk.Frame(self, bg=BG, padx=16, pady=8)
        pick.pack(fill="x")
        tk.Button(pick, text="양식 파일 고르기", command=self._pick,
                  font=(FONT, theme.fs(9)), fg=TEXT, bg=CARD, activebackground=BORDER,
                  bd=1, padx=10, pady=5, cursor="hand2").pack(side="left")
        self.file_lbl = tk.Label(pick, text="(선택 안 됨)", font=(FONT, theme.fs(9)),
                                 bg=BG, fg=MUTED)
        self.file_lbl.pack(side="left", padx=(10, 0))

        # ── 두 칸 ──
        body = tk.Frame(self, bg=BG, padx=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1, uniform="c")
        body.columnconfigure(1, weight=1, uniform="c")
        body.rowconfigure(1, weight=1)

        tk.Label(body, text="① 뽑은 것 — AI에 붙여넣으세요", font=(FONT, theme.fs(9), "bold"),
                 bg=BG, fg=TEXT).grid(row=0, column=0, sticky="w", pady=(4, 2))
        tk.Label(body, text="② 채운 것 — 여기 붙여넣으세요", font=(FONT, theme.fs(9), "bold"),
                 bg=BG, fg=TEXT).grid(row=0, column=1, sticky="w",
                                      padx=(8, 0), pady=(4, 2))

        self.out_box = tk.Text(body, width=46, height=20, font=(MONO, theme.fs(9)),
                               relief="solid", bd=1, wrap="none")
        self.out_box.grid(row=1, column=0, sticky="nsew")
        self.in_box = tk.Text(body, width=46, height=20, font=(MONO, theme.fs(9)),
                              relief="solid", bd=1, wrap="none")
        self.in_box.grid(row=1, column=1, sticky="nsew", padx=(8, 0))

        # ── 버튼 ──
        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        tk.Button(foot, text="채울 자리 뽑기 + 복사", command=self._extract,
                  font=(FONT, theme.fs(9), "bold"), fg=TEXT, bg="#e8e8ed",
                  activebackground=BORDER, bd=0, padx=12, pady=7,
                  cursor="hand2").pack(side="left")
        tk.Button(foot, text="채워서 한글로 열기", command=self._apply,
                  font=(FONT, theme.fs(10), "bold"), fg="white", bg=ACCENT,
                  activebackground="#0077ed", activeforeground="white",
                  bd=0, padx=16, pady=7, cursor="hand2").pack(side="right")

        self.status = tk.StringVar(value="양식 파일을 골라주세요.")
        tk.Label(self, textvariable=self.status, font=(FONT, theme.fs(8)),
                 bg=BG, fg=MUTED, anchor="w").pack(fill="x", padx=16, pady=(0, 10))

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx() - 620}+{master.winfo_rooty() + 40}")
        ui_fx.attach_all(self)         # 창 안 모든 버튼에 호버 보간

    # ── 동작 ──
    def _pick(self):
        path = filedialog.askopenfilename(
            parent=self, title="양식 파일 선택",
            filetypes=[("한글 파일", "*.hwp *.hwpx"), ("모든 파일", "*.*")])
        if not path:
            return
        self.src = pathlib.Path(path)
        self.hwpx = None
        self.file_lbl.config(text=self.src.name, fg=TEXT)
        self.status.set("‘채울 자리 뽑기’를 눌러주세요.")

    def _ensure_hwpx(self):
        r"""채우기 대상 HWPX 를 준비한다. .hwp 면 한글로 변환한다."""
        if self.hwpx is not None:
            return True
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
        dst = self.src.with_suffix(".hwpx")
        if dst.exists():        # 원본 옆에 같은 이름이 있으면 건드리지 않는다
            dst = self.src.with_name(self.src.stem + "_변환.hwpx")
        try:
            engine_library.export_as_hwpx(self.src, dst)
        except Exception as e:
            applog.exc(f"HWPX 변환 실패 ({self.src.name})", e)
            messagebox.showerror("변환 실패",
                                 f"{type(e).__name__}: {e}", parent=self)
            return False
        self.hwpx = dst
        return True

    def _extract(self):
        if self.src is None:
            messagebox.showwarning("파일 없음", "양식 파일을 먼저 골라주세요.",
                                   parent=self)
            return
        if not self._ensure_hwpx():
            return
        try:
            sheet = form_fill.to_worksheet(self.hwpx, title=self.src.stem)
            count = len(form_fill.slots(self.hwpx))
        except Exception as e:
            applog.exc(f"채울 자리 뽑기 실패 ({self.src.name})", e)
            messagebox.showerror("실패", f"{type(e).__name__}: {e}", parent=self)
            return
        self.out_box.delete("1.0", "end")
        self.out_box.insert("1.0", sheet)
        self.clipboard_clear()
        self.clipboard_append(sheet)
        self.status.set(f"채울 자리 {count}개 — 클립보드에 복사했습니다. "
                        "AI에 붙여넣고 채워서 오른쪽에 붙여넣으세요.")

    def _apply(self):
        if self.hwpx is None:
            messagebox.showwarning("준비 안 됨",
                                   "먼저 ‘채울 자리 뽑기’를 눌러주세요.", parent=self)
            return
        answer = self.in_box.get("1.0", "end")
        values = form_fill.parse_worksheet(answer)
        if not values:
            messagebox.showwarning(
                "채운 내용 없음",
                "오른쪽 칸에 채운 내용을 붙여넣어주세요.\n"
                "‘[번호] 내용’ 형태의 줄이 있어야 합니다.", parent=self)
            return
        dst = self.hwpx.with_name(self.hwpx.stem + "_완성.hwpx")
        try:
            n = form_fill.fill(self.hwpx, dst, values)
            left = form_fill.unfilled_marks(dst)
            hwp_engine.connect()
            engine_library.open_form(dst)
        except Exception as e:
            applog.exc(f"양식 채우기 실패 ({self.hwpx.name})", e)
            messagebox.showerror("실패", f"{type(e).__name__}: {e}", parent=self)
            return
        msg = f"✅ {n}개 채워서 열었습니다 — {dst.name}"
        if left:
            msg += f"  (아직 빈칸 {len(left)}개 남음)"
        self.status.set(msg)


def open_form_fill(master):
    return FormFillWindow(master)
