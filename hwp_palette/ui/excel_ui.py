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
from hwp_palette.hwp import hwp_engine        # [한글에 바로 넣기]
from hwp_palette.model import excel_blocks    # 덩어리 틀(xlsm) — 형태 B
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

    def __init__(self, master, on_convert=None):
        super().__init__(master)
        # 마크다운 변환 함수 — 여는 쪽이 건네준다 (ui 층은 app 을 모른다)
        self.on_convert = on_convert
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
            "· [엑셀 틀 만들기] — 버튼이 든 엑셀(xlsm)을 만듭니다. 창고의 꾸러미·이름 붙은 템플릿이 드롭다운에 들어갑니다\n"
            "· 엑셀에서: B1 드롭다운으로 꾸러미를 고르고 [＋ 덩어리 추가] — 빈칸 이름들이 깔리면 값 칸(B열)만 채웁니다\n"
            "· [엑셀 파일 고르기] — 채워 온 엑셀을 읽어 시험지 마크다운과 정답표를 만듭니다 (예전 표 방식 파일도 읽힙니다)\n"
            "· [한글에 바로 넣기] 한 번이면 붙여넣기·선택·변환까지 이어집니다 — 등록해 둔 조각 서식 그대로 시험지가 완성됩니다"),
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

    # ── ① 문항 틀 만들기 (xlsm) ──────────────────────────
    # 유형(합답형·정답형·서술형) 드롭다운 세 개는 없앴다 (2026-07-31, 형태 B
    # 확정): 유형→템플릿 연결을 여기서 고르는 대신, **엑셀 안의 드롭다운**이
    # 창고의 꾸러미·이름 붙은 템플릿을 전부 보여준다. 창이 할 일은 틀을
    # 구워 주는 것뿐이다.
    def _build_make(self):
        box = tk.Frame(self, bg=BG, padx=16)
        box.pack(fill="x", pady=(12, 4))
        tk.Label(box, text="① 문항 틀 만들기", font=(FONT, theme.fs(9), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(box, text="버튼이 든 엑셀(xlsm)을 만듭니다 — 엑셀에서 꾸러미를 "
                           "골라 [＋ 덩어리 추가]로 문항을 쌓으세요.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w",
                                                                 pady=(0, 6))
        btns = tk.Frame(box, bg=BG)
        btns.pack(fill="x", pady=(4, 0))
        RoundButton(btns, text="엑셀 틀 만들기", command=self._make_blocks,
                    bg=ACCENT, fg="white", radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(9), "bold"), outline="",
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
        # [한글에 바로 넣기] — 창 밖에서 손으로 하던 네 걸음(복사 → 붙여넣기
        # → 선택 → 변환)을 단추 하나로 잇는다 (2026-07-31). 이 창이 어렵던
        # 이유의 절반이 "일이 창 밖에서 벌어진다"였다.
        # [마크다운 복사]도 **남긴다** — 다른 곳에 붙여넣고 싶을 때가 있다.
        RoundButton(foot, text="한글에 바로 넣기", command=self._send_to_hwp,
                    bg=ACCENT, fg="white", radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(10), "bold"), outline="",
                    zone_bg=BG).fit(pad_x=16, pad_y=6).pack(side="right")
        RoundButton(foot, text="마크다운 복사", command=self._copy_md,
                    bg=CARD, fg=TEXT, radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(9)), outline=BORDER,
                    zone_bg=BG).fit(pad_x=14, pad_y=5).pack(side="right", padx=(0, 8))

    # ── 동작 ────────────────────────────────────────────
    def _make_blocks(self):
        """[엑셀 틀 만들기] — 버튼(VBA)이 든 xlsm 을 굽고 바로 열어 준다."""
        pack_list = excel_blocks.packs()
        if not pack_list:
            messagebox.showinfo(
                "올릴 꾸러미가 없습니다",
                "이름 붙은 빈칸(\\발문\\ \\선1\\ …)을 가진 템플릿이나 꾸러미가 "
                "있어야 엑셀 드롭다운에 올라갑니다.\n"
                "창고에서 템플릿을 등록하거나 물감을 섞어 만들어 주세요.",
                parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="문항 틀 저장", defaultextension=".xlsm",
            initialfile="문항틀.xlsm",
            filetypes=[("매크로 엑셀", "*.xlsm")])
        if not path:
            return
        try:
            n = excel_blocks.build_xlsm(path, pack_list)
        except PermissionError:
            messagebox.showwarning(
                "저장하지 못했습니다",
                "같은 이름의 파일이 엑셀에서 열려 있는 것 같습니다.\n"
                "닫고 다시 눌러 주세요.", parent=self)
            return
        except Exception as e:
            applog.exc("문항 틀 만들기 실패", e)
            messagebox.showerror("문항 틀을 만들지 못했습니다", str(e), parent=self)
            return
        self.status.set(f"꾸러미 {n}개를 담아 만들었습니다 — 엑셀에서 채운 뒤 ②로 불러오세요.")
        # 매크로 파일이라 처음 열면 엑셀이 노란 띠(콘텐츠 사용)를 띄운다 —
        # 안내를 한 번은 해 줘야 버튼이 안 눌린다고 오해하지 않는다.
        if messagebox.askyesno(
                "만들었습니다",
                "지금 엑셀로 열어볼까요?\n\n"
                "처음 열면 위쪽 노란 띠의 [콘텐츠 사용]을 눌러야\n"
                "[＋ 덩어리 추가] 버튼이 동작합니다.", parent=self):
            try:
                os.startfile(path)
            except Exception as e:
                applog.exc("문항 틀 열기 실패 (파일은 만들어졌다)", e)

    def _load(self):
        path = filedialog.askopenfilename(
            parent=self, title="채운 엑셀 고르기",
            filetypes=[("엑셀 파일", "*.xlsm *.xlsx"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            # 덩어리 틀(시험지 시트)인지 먼저 본다 — 아니면 예전 표 방식으로.
            # 옛 파일을 버리지 않는다: 이미 채워 둔 학기 자료가 있을 수 있다.
            blocks = excel_blocks.read_blocks(path)
            if blocks is not None:
                md, report, answers = excel_blocks.to_markdown(blocks)
            else:
                md, report, answers = excel_read.read_workbook(path)
        except Exception as e:
            applog.exc("문항 엑셀 읽기 실패", e)
            messagebox.showerror("엑셀을 읽지 못했습니다", str(e), parent=self)
            return

        self.md, self.answers = md, answers
        self._set(self.report_box, "\n".join(report))
        self._set(self.md_box, md)
        self.status.set("문항 %d개 — 한글에서 넣을 자리를 클릭하고 [한글에 바로 넣기]."
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

    def _send_to_hwp(self):
        r"""[한글에 바로 넣기] — 커서 자리에 넣고 그 부분만 변환까지 한다.

        사용자가 손으로 하던 네 걸음을 대신한다. 변환 함수는 **선택 영역**을
        읽어 바꾸므로, 넣은 뒤 그 범위를 정확히 선택해 넘겨야 한다 — 넣기
        전 위치를 기억했다가 넣은 뒤 그 자리부터 끝까지 선택한다.
        """
        if not self.md.strip():
            self.status.set("먼저 채운 엑셀을 불러오세요.")
            return
        try:
            hwp_engine.connect()
        except Exception as e:
            applog.exc("문항 엑셀: 한글 연결 실패", e)
            self.status.set("한글을 찾지 못했습니다 — 한글을 켜고 다시 눌러 주세요.")
            return
        try:
            hwp = hwp_engine.hwp
            start = hwp.GetPos()
            hwp_engine.insert_plain(self.md)
            end = hwp.GetPos()
            hwp.SetPos(*start)
            hwp.MoveSelPos(*end)
        except Exception as e:
            applog.exc("문항 엑셀: 한글에 넣기 실패", e)
            self.status.set("한글에 넣지 못했습니다 — [마크다운 복사]를 쓰세요.")
            return
        # 변환은 **넘겨받은 함수**로 부른다 — ui 층이 app 을 임포트하면 층
        # 규칙(test_layers)이 깨진다. 이 창을 여는 쪽(app.fn_open_excel)이
        # 제 변환 함수를 건네준다.
        if self.on_convert is None:
            self.status.set("넣었습니다 — 그 부분을 선택한 뒤 [마크다운 변환]을 눌러 주세요.")
            return
        self.status.set("한글에 넣었습니다 — 변환하는 중…")
        self.after(60, self._run_convert)

    def _run_convert(self):
        try:
            self.on_convert()
            self.status.set("시험지가 완성됐습니다.")
        except Exception as e:
            applog.exc("문항 엑셀: 변환 실패", e)
            self.status.set("변환에 실패했습니다 — 한글에서 직접 [마크다운 변환]을 눌러 주세요.")

    def _copy_answers(self):
        if not self.answers:
            self.status.set("먼저 채운 엑셀을 불러오세요.")
            return
        clipboard.set_text(excel_read.answers_to_text(self.answers), self)
        self.status.set("정답표를 복사했습니다 — 엑셀·한글 표에 그대로 붙습니다.")


def open_excel(master, on_convert=None):
    return ExcelWindow(master, on_convert=on_convert)
