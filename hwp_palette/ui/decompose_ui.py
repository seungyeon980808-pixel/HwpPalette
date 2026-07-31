# -*- coding: utf-8 -*-
r"""문서 해체 — 골라 담기 판 (2026-07-31).

무엇을 하는 물건인가 (사용자 기획):
    완성된 시험지를 부품으로 분해해 물감으로 등록한다. 그래야 다음 시험지는
    **만드는 게 아니라 조립**이 된다.

왜 이 모양인가:
    처음 안은 조각마다 창을 띄우고 Enter=등록 / Space=건너뛰기로 자동
    진행하는 것이었다. 사용자가 그건 아니라고 했다 —

        "그 안에 있는 글자를 지우고 뭐하고 자리를 지정하고 이런걸 해야하기
         때문에 양식을 띄워놓고 쉽게 추가할 수 있게끔 하는 작업이 관건"

    담기 전에 **편집**이 필요하다. 그래서 자동 진행 대신 도킹한 채 목록을
    쭉쭉 내리며 고르는 판으로 바꿨다. 편집기는 한글 그 자체다 — 지우기·
    고치기는 한글이 제일 잘하니 우리는 담기만 한다.

화면은 세 층뿐이다:
    머리  — 파일 이름 · "표 N · 문단 N" · [빈칸 넣기] · 끝내기
    목록  — 체크 + 유형 배지 + 한 줄 미리보기 (누르면 한글에서 실물 선택)
    바닥  — [잇닿은 N개 묶어 담기] · [고른 N개 담기]

안전장치 하나: 해체는 **항상 복사본**에서 한다. 담는 중에 문서를 지우고
고치게 되므로, 원본 시험지가 상하는 사고를 이것 하나가 막는다.
"""

import tkinter as tk
from tkinter import ttk

from hwp_palette.core import applog
from hwp_palette.design import dialogs as messagebox
from hwp_palette.design import theme
from hwp_palette.design.roundbtn import RoundButton
from hwp_palette.hwp import doc_scan
from hwp_palette.hwp import engine_library
from hwp_palette.hwp import hwp_engine
from hwp_palette.model import library
from hwp_palette.model import palette

_C = theme.colors()
BG, CARD, BORDER = _C["bg"], _C["card"], _C["border"]
TEXT, MUTED, ACCENT = _C["text"], _C["muted"], _C["accent"]
ACCENT_SOFT = _C["accent_soft"]
FONT, SP, FS = theme.FONT, theme.SP, theme.FS

PANEL_W = 322

# 빈칸 표시 — 기존 '양식 채우기' 와 **같은 문법**이라야 담긴 조각이 바로
# "빈칸 N" 물감이 된다 (library.count_slots 가 세는 그것).
SLOT_MARK = "\\\\"


def _btn(parent, text, command, primary=False, zone_bg=None):
    bg = ACCENT if primary else CARD
    b = RoundButton(parent, text=text, command=command, bg=bg,
                    fg="white" if primary else TEXT,
                    radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["sub"])),
                    outline="" if primary else BORDER,
                    zone_bg=zone_bg or parent.cget("bg"))
    return b.fit(pad_x=10, pad_y=4)


class DecomposePanel(tk.Frame):
    """골라 담기 판 — 도킹된 창의 오른쪽에 임시로 선다."""

    def __init__(self, master, doc_name="", on_finish=None):
        super().__init__(master, bg=CARD, width=PANEL_W,
                         highlightbackground=BORDER, highlightthickness=1)
        self.pack_propagate(False)
        self.on_finish = on_finish
        self.pieces = []
        self.checked = set()        # 체크한 조각의 차례(index)
        self.taken = set()          # 이미 담은 것 (목록에서의 차례)
        self.taken_names = []       # 담은 물감 이름 — 끝내며 팔레트 탭에 쓴다
        self._rows = {}

        head = tk.Frame(self, bg=CARD, padx=SP["s"], pady=SP["s"])
        head.pack(fill="x")
        tk.Label(head, text="문서 해체", font=(FONT, theme.fs(FS["head"]), "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        self._sub = tk.Label(head, text=doc_name or "", anchor="w",
                             font=(FONT, theme.fs(FS["caption"])),
                             bg=CARD, fg=MUTED, wraplength=PANEL_W - 24,
                             justify="left")
        self._sub.pack(fill="x")
        acts = tk.Frame(head, bg=CARD)
        acts.pack(fill="x", pady=(SP["xs"], 0))
        _btn(acts, "빈칸 넣기", self._insert_slot, zone_bg=CARD).pack(side="left")
        _btn(acts, "다시 훑기", self.rescan, zone_bg=CARD).pack(side="left", padx=(4, 0))
        _btn(acts, "끝내기", self._finish, zone_bg=CARD).pack(side="right")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # 바닥 줄을 **먼저** 붙인다 — 목록이 길어도 밀려나지 않는다
        foot = tk.Frame(self, bg=CARD, padx=SP["s"], pady=SP["s"])
        foot.pack(side="bottom", fill="x")
        tk.Frame(self, bg=BORDER, height=1).pack(side="bottom", fill="x")
        self._bundle_btn = _btn(foot, "묶어 담기", self._take_bundle, zone_bg=CARD)
        self._bundle_btn.pack(side="left")
        self._take_btn = _btn(foot, "담기", self._take_each, primary=True,
                              zone_bg=CARD)
        self._take_btn.pack(side="right")

        wrap = tk.Frame(self, bg=CARD)
        wrap.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0)
        messagebox.style_scrollbars(self)
        bar = ttk.Scrollbar(wrap, orient="vertical",
                            style="App.Vertical.TScrollbar",
                            command=self._canvas.yview)
        self._body = tk.Frame(self._canvas, bg=CARD)
        self._body.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._win = self._canvas.create_window((0, 0), window=self._body,
                                               anchor="nw")
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._win, width=e.width))
        self._canvas.configure(yscrollcommand=bar.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

    # ── 훑기 ──────────────────────────────────
    def rescan(self):
        try:
            hwp_engine.connect()
            self.pieces = doc_scan.scan()
        except Exception as e:
            applog.exc("문서 해체: 훑기 실패", e)
            self.pieces = []
        self.checked.clear()
        self._draw()

    def _draw(self):
        for w in self._body.winfo_children():
            w.destroy()
        self._rows = {}
        tables = sum(1 for p in self.pieces if p["kind"] == "표")
        paras = len(self.pieces) - tables
        self._sub.config(
            text=(f"표 {tables} · 문단 {paras} — 표 안 문단은 표에 포함되어 "
                  "목록에서 뺐습니다"))
        if not self.pieces:
            tk.Label(self._body, text="조각을 찾지 못했습니다.\n"
                                      "문서를 열고 [다시 훑기]를 눌러 주세요.",
                     justify="center", font=(FONT, theme.fs(FS["sub"])),
                     bg=CARD, fg=MUTED).pack(pady=SP["xl"])
            self._sync_foot()
            return
        for i, p in enumerate(self.pieces):
            self._rows[i] = self._make_row(i, p)
        self._sync_foot()

    def _make_row(self, i, p):
        r = tk.Frame(self._body, bg=CARD, padx=6, pady=4, cursor="hand2")
        r.pack(fill="x")
        var = tk.BooleanVar(value=i in self.checked)
        cb = tk.Checkbutton(r, variable=var, bg=CARD, activebackground=CARD,
                            selectcolor=CARD,
                            command=lambda n=i, v=var: self._toggle(n, v))
        cb.pack(side="left")
        badge = tk.Label(r, text=p["kind"], font=(FONT, theme.fs(FS["caption"])),
                         bg=ACCENT_SOFT if p["kind"] == "표" else "#eef1f4",
                         fg=ACCENT if p["kind"] == "표" else MUTED, padx=4)
        badge.pack(side="left", padx=(2, 6))
        txt = p.get("preview") or p.get("title") or ""
        lb = tk.Label(r, text=txt or p["title"], anchor="w",
                      font=(FONT, theme.fs(FS["sub"])), bg=CARD, fg=TEXT)
        lb.pack(side="left", fill="x", expand=True)
        done = tk.Label(r, text="담음" if i in self.taken else "",
                        font=(FONT, theme.fs(FS["caption"])),
                        bg="#e8f7ee" if i in self.taken else CARD,
                        fg="#0a6b2e")
        done.pack(side="right")
        for w in (r, badge, lb):
            w.bind("<Button-1>", lambda e, n=i: self._focus(n))
        r._parts = (badge, lb, done, var)
        return r

    # ── 조작 ──────────────────────────────────
    def _toggle(self, i, var):
        if var.get():
            self.checked.add(i)
        else:
            self.checked.discard(i)
        self._sync_foot()

    def _focus(self, i):
        """행을 누르면 한글에서 실물이 선택된다 — 도킹 화면이 곧 미리보기."""
        if not (0 <= i < len(self.pieces)):
            return
        try:
            doc_scan.select_piece(self.pieces[i])
        except Exception as e:
            applog.exc("문서 해체: 조각 짚기 실패", e)

    def _sync_foot(self):
        n = len(self.checked)
        try:
            # RoundButton 은 Canvas 라 config(text=…) 가 안 먹는다 — 글자는
            # set_text 로 바꾼다(폭도 함께 다시 잡힌다).
            self._take_btn.set_text(f"고른 {n}개 담기" if n else "담기",
                                    pad_x=10, pad_y=4)
            run = _runs(sorted(self.checked))
            bundle = max((len(r) for r in run), default=0)
            self._bundle_btn.set_text(
                f"잇닿은 {bundle}개 묶어 담기" if bundle > 1 else "묶어 담기",
                pad_x=10, pad_y=4)
        except Exception as e:
            applog.exc("문서 해체: 바닥 단추 글자 갱신 실패", e)

    def _insert_slot(self):
        r"""[빈칸 넣기] — 커서 자리에 빈칸 표시를 심는다.

        기존 '양식 채우기'와 같은 문법(\\)이라, 담긴 조각이 그대로 "빈칸 N"
        물감이 된다. 새 문법을 만들지 않는다.
        """
        try:
            hwp_engine.connect()
            hwp_engine.insert_plain(SLOT_MARK)
        except Exception as e:
            applog.exc("문서 해체: 빈칸 넣기 실패", e)
            messagebox.showwarning("빈칸을 넣지 못했습니다",
                                   "한글에서 넣을 자리를 클릭한 뒤 다시 눌러 주세요.",
                                   parent=self)

    # ── 담기 ──────────────────────────────────
    def _take_each(self):
        """고른 것을 **낱개로** 하나씩 담는다."""
        idxs = sorted(self.checked)
        if not idxs:
            messagebox.showinfo("고른 것이 없습니다",
                                "담을 조각을 체크해 주세요.", parent=self)
            return
        done = 0
        for i in idxs:
            if self._take_one(i):
                done += 1
        self._after_take(done)

    def _take_bundle(self):
        r"""잇닿은 조각들을 **한 물감으로** 담는다.

        시험지의 한 문항은 보통 발문 문단 + 보기 표 + 선지 문단의 묶음이라,
        낱개로만 담으면 '문항 틀'이 세 조각으로 흩어진다.
        """
        run = max(_runs(sorted(self.checked)), key=len, default=[])
        if len(run) < 2:
            messagebox.showinfo("묶을 것이 없습니다",
                                "잇닿은 조각을 둘 이상 체크해 주세요.", parent=self)
            return
        try:
            hwp_engine.connect()
            first, last = self.pieces[run[0]], self.pieces[run[-1]]
            if not doc_scan.relocate(first):
                raise RuntimeError("첫 조각을 찾지 못했습니다")
            hwp = hwp_engine.hwp
            hwp.SetPos(*first["pos"])
            hwp.MoveSelPos(last["pos"][0], last["pos"][1], 0)
            hwp.MoveSelParaEnd()
            ok = self._save_selection(_bundle_name(self.pieces, run))
        except Exception as e:
            applog.exc("문서 해체: 묶어 담기 실패", e)
            ok = False
        if ok:
            self.taken.update(run)
        self._after_take(1 if ok else 0)

    def _take_one(self, i):
        p = self.pieces[i]
        try:
            hwp_engine.connect()
            # 담기 **직전에 다시 찾는다** — 고르는 동안 한글에서 지우고 고쳤으면
            # 훑을 때 적어 둔 위치가 밀려 있다 (사용자 결정 2026-07-31).
            if not doc_scan.relocate(p):
                return False
            if self._save_selection(_auto_name(p)):
                self.taken.add(i)
                return True
        except Exception as e:
            applog.exc(f"문서 해체: '{_auto_name(p)}' 담기 실패", e)
        return False

    def _save_selection(self, name):
        """지금 선택을 템플릿 물감으로 저장 — 기존 캡처 흐름을 그대로 쓴다."""
        if not hwp_engine.has_selection():
            return False
        try:
            text = hwp_engine.read_selection_text(retries=4)
        except Exception:
            text = ""
        slots = library.count_slots(text or "")
        try:
            item_id = library.add_template_from_capture(
                name, engine_library.capture_fragment, slot_count=slots)
            # 이름이 겹치면 라이브러리가 뒤에 번호를 붙인다 — 실제로 붙은
            # 이름을 적어 둬야 팔레트 탭이 엉뚱한 물감을 집지 않는다.
            saved = library.find_by_id("템플릿", item_id)
            self.taken_names.append((saved or {}).get("name", name))
            return True
        except Exception as e:
            applog.exc(f"문서 해체: '{name}' 저장 실패", e)
            return False

    def _after_take(self, done):
        self.checked.clear()
        self._draw()
        if done:
            self._sub.config(text=f"{done}개를 창고에 담았습니다")

    # ── 끝내기 ────────────────────────────────
    def _finish(self):
        if self.on_finish:
            try:
                self.on_finish(list(self.taken_names))
            except Exception as e:
                applog.exc("문서 해체: 끝내기 처리 실패", e)


def _runs(idxs):
    """잇닿은 번호 묶음들 — [1,2,3,7,8] → [[1,2,3],[7,8]]"""
    out, cur = [], []
    for i in idxs:
        if cur and i == cur[-1] + 1:
            cur.append(i)
        else:
            if cur:
                out.append(cur)
            cur = [i]
    if cur:
        out.append(cur)
    return out


def _auto_name(p):
    """자동 이름 — 표는 크기로, 문단은 첫 글자로. 고칠 것만 고치면 된다."""
    if p["kind"] == "표":
        return p.get("title") or "표"
    text = (p.get("preview") or "").strip().rstrip("…")
    return (text[:12] or "문단").strip()


def _bundle_name(pieces, run):
    return _auto_name(pieces[run[0]]) + f" 묶음{len(run)}"


def make_palette_tab(name, taken_names):
    r"""담은 것들로 새 팔레트 탭을 만든다 — 해체의 마무리.

    배치는 담은 차례대로 채운다. 다시 놓고 싶으면 환경설정에서 평소처럼 끈다.
    """
    try:
        palette.add_tab(name)
        tabs = palette.load_tabs()
        idx = len(tabs) - 1
        for nm in taken_names:
            it = library.get_item("템플릿", name=nm)
            if not it:
                continue
            palette.add_block(idx, {"type": "template", "ref": it["id"],
                                    "template": it["name"],
                                    "span": 2, "rows": 1})
        return True
    except Exception as e:
        applog.exc("문서 해체: 팔레트 탭 만들기 실패", e)
        return False
