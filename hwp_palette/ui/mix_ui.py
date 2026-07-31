# -*- coding: utf-8 -*-
r"""물감 섞기 — 여러 물감을 섞어 **하나의 물감**을 만든다 (2026-07-31).

왜 필요한가 (사용자 기획):
    시험문제를 뜯어보면 같은 요소가 되풀이되는데 조합만 다르다.
    요소가 1~5 있다면 문항마다 1234 / 1235 / 1245 / 12345 … 로 갈린다.
    지금까지는 조합이 하나 늘 때마다 hwp 조각을 통째로 새로 만들어 왔다 —
    창고에 쌓인 '합답형1사진3선지' '학교합답2사진5선지' 같은 이름들이 바로
    그 흔적이다(이름 자체가 조합 코드다).

    조합에 **이름**을 붙여 두면 그 폭발이 없어진다:

        가 = ①②③④⑤      나 = ①②③④      다 = ①②④⑤

    그러면 시험지 입력이 꾸러미 이름의 나열이 된다 — 나 / 다 / 가 / 가 …

**겹치기(018)와 완전히 다른 개념이다** (사용자 2026-07-31):
    겹치기 = 하나의 위계를 설정하는 것. 한 칸에 포개 두고 쓸 때 **하나만** 고름.
    섞기   = 여러 물감을 섞어 **하나의 물감**을 만드는 것. 전부 이어 붙임.

참조 방식 (사용자 결정):
    꾸러미는 요소를 **가리키기만** 한다. '선지 5택' 하나를 고치면 그것을 쓰는
    꾸러미가 전부 따라 바뀐다 — 시험지 관리에서 이게 핵심이다. 내용을 복사해
    두는(스냅샷) 방식이면 "선지 모양을 바꿨는데 왜 꾸러미는 옛날 모양이지"가
    반드시 온다.

1차는 **템플릿끼리만** 섞는다:
    템플릿은 "문서에 이어 붙이는 것"이라 차례대로 합치는 뜻이 분명하다. 서식은
    "선택한 글자에 입히는 것"이라 섞였을 때 어디에 입혀야 하는지가 애매하다.
"""

import tkinter as tk

from hwp_palette.core import applog
from hwp_palette.design import dialogs as messagebox
from hwp_palette.design import theme
from hwp_palette.design.roundbtn import RoundButton
from hwp_palette.model import library

_C = theme.colors()
BG, CARD, BORDER = _C["bg"], _C["card"], _C["border"]
TEXT, MUTED, ACCENT = _C["text"], _C["muted"], _C["accent"]
FONT, SP, FS = theme.FONT, theme.SP, theme.FS

MIX_BG, MIX_FG = "#f3eefc", "#6639ba"


def _btn(parent, text, command, primary=False, zone_bg=None):
    bg = ACCENT if primary else CARD
    b = RoundButton(parent, text=text, command=command, bg=bg,
                    fg="white" if primary else TEXT,
                    radius=theme.RADIUS["ctl"],
                    font=(FONT, theme.fs(FS["body"])),
                    outline="" if primary else BORDER,
                    zone_bg=zone_bg or parent.cget("bg"))
    return b.fit(pad_x=14, pad_y=5)


class MixDialog(tk.Toplevel):
    """섞기 창 — 요소 목록(차례 있음) + 이름 + 빈칸 합계."""

    def __init__(self, master, member_ids=None, edit_id=None, on_saved=None,
                 subcat=""):
        super().__init__(master)
        self.on_saved = on_saved
        self.edit_id = edit_id
        self.saved = False
        self.title("물감 섞기")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        pool = library.list_items("템플릿")
        # 꾸러미는 요소가 될 수 없다 — 꾸러미 안에 꾸러미를 넣으면 참조가
        # 돌고 돌 수 있어(가→나→가) 빈칸 세기가 끝나지 않는다.
        self._pool = [it for it in pool if not it.get("mix")]
        self._by_id = {it["id"]: it for it in self._pool}

        name0 = ""
        if edit_id:
            cur = library.find_by_id("템플릿", edit_id)
            if cur:
                name0 = cur.get("name", "")
                member_ids = list(cur.get("mix") or [])
                subcat = library.subcat_of(cur)
        self._ids = [i for i in (member_ids or []) if i in self._by_id]

        tk.Label(self, text=("꾸러미 고치기" if edit_id else "여러 물감을 섞어 하나로"),
                 font=(FONT, theme.fs(FS["title"]), "bold"), bg=BG, fg=TEXT
                 ).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="문서에 꽂히는 차례입니다. 위아래로 옮길 수 있습니다.",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED
                 ).pack(anchor="w", padx=16, pady=(0, 10))

        self._rows = tk.Frame(self, bg=BG, padx=16)
        self._rows.pack(fill="x")

        namef = tk.Frame(self, bg=BG, padx=16)
        namef.pack(fill="x", pady=(10, 0))
        tk.Label(namef, text="이름", font=(FONT, theme.fs(FS["body"])),
                 bg=BG, fg=TEXT).pack(side="left")
        self.name_var = tk.StringVar(value=name0)
        tk.Entry(namef, textvariable=self.name_var, width=16,
                 font=(FONT, theme.fs(FS["head"])), relief="solid", bd=1
                 ).pack(side="left", padx=(8, 6))
        tk.Label(namef, text=r"문서에서 \이름\ 으로 부릅니다",
                 font=(FONT, theme.fs(FS["caption"])), bg=BG, fg=MUTED
                 ).pack(side="left")

        # 하위 분류 — 물감이 생기는 모든 창의 규칙 (시안 store-subcats K-2).
        # 꾸러미도 템플릿 분류 안에 사니 템플릿의 하위 분류를 쓴다.
        from hwp_palette.ui import library_ui          # 순환 참조 회피
        subf = tk.Frame(self, bg=BG, padx=16)
        subf.pack(fill="x", pady=(6, 0))
        tk.Label(subf, text="분류", font=(FONT, theme.fs(FS["body"])),
                 bg=BG, fg=TEXT).pack(side="left")
        self._subcat = library_ui.SubcatPicker(subf, "템플릿", value=subcat)
        self._subcat.pack(side="left", padx=(8, 0))

        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        self._sum = tk.Label(foot, text="", font=(FONT, theme.fs(FS["sub"])),
                             bg=BG, fg=MUTED)
        self._sum.pack(side="left")
        _btn(foot, "섞기" if not edit_id else "저장", self._ok,
             primary=True).pack(side="right")
        _btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))

        self._draw()
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+60}+{master.winfo_rooty()+40}")
        self.grab_set()

    # ── 그리기 ────────────────────────────────
    def _draw(self):
        for w in self._rows.winfo_children():
            w.destroy()
        for n, iid in enumerate(self._ids):
            it = self._by_id.get(iid)
            if it is None:
                continue
            r = tk.Frame(self._rows, bg=CARD, padx=8, pady=5,
                         highlightbackground=BORDER, highlightthickness=1)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=str(n + 1), font=(FONT, theme.fs(FS["caption"]), "bold"),
                     bg=ACCENT, fg="white", width=2).pack(side="left")
            tk.Label(r, text=it.get("name", "?"),
                     font=(FONT, theme.fs(FS["body"])), bg=CARD, fg=TEXT,
                     anchor="w").pack(side="left", padx=(8, 0))
            tk.Label(r, text=f"빈칸 {int(it.get('slot_count') or 0)}",
                     font=(FONT, theme.fs(FS["caption"])), bg=CARD, fg=MUTED
                     ).pack(side="left", padx=(8, 0))
            _btn(r, "빼기", lambda i=n: self._remove(i), zone_bg=CARD).pack(side="right")
            _btn(r, "↓", lambda i=n: self._move(i, 1), zone_bg=CARD).pack(side="right", padx=2)
            _btn(r, "↑", lambda i=n: self._move(i, -1), zone_bg=CARD).pack(side="right")
        add = tk.Label(self._rows, text="＋ 물감 추가", cursor="hand2",
                       font=(FONT, theme.fs(FS["body"]), "bold"),
                       bg=BG, fg=ACCENT, pady=6,
                       highlightbackground=ACCENT, highlightthickness=1)
        add.pack(fill="x", pady=(4, 0))
        add.bind("<Button-1>", lambda e: self._add())
        total = sum(int((self._by_id.get(i) or {}).get("slot_count") or 0)
                    for i in self._ids)
        self._sum.config(text=f"물감 {len(self._ids)}개 · 빈칸 합계 {total}")

    # ── 조작 ──────────────────────────────────
    def _remove(self, n):
        if 0 <= n < len(self._ids):
            del self._ids[n]
        self._draw()

    def _move(self, n, delta):
        m = n + delta
        if 0 <= n < len(self._ids) and 0 <= m < len(self._ids):
            self._ids[n], self._ids[m] = self._ids[m], self._ids[n]
        self._draw()

    def _add(self):
        """＋ 물감 추가 — 아직 안 담은 템플릿에서 고른다 (입구 ②)."""
        rest = [it for it in self._pool if it["id"] not in self._ids]
        if not rest:
            messagebox.showinfo("더 담을 물감이 없습니다",
                                "창고의 템플릿을 모두 담았습니다.", parent=self)
            return
        from hwp_palette.design.popover import Popover
        pop = Popover(self, self._rows.winfo_children()[-1])
        for it in rest[:40]:
            pop.add(f"{it.get('name', '?')}  (빈칸 {int(it.get('slot_count') or 0)})",
                    lambda i=it["id"]: self._pick(i))
        pop.show()

    def _pick(self, iid):
        self._ids.append(iid)
        self._draw()

    def _ok(self):
        from hwp_palette.ui import library_ui          # IME 확정 (공용)
        library_ui.commit_ime(self)
        name = (self.name_var.get() or "").strip()
        if len(self._ids) < 2:
            messagebox.showinfo("물감이 모자랍니다",
                                "섞으려면 물감이 둘 이상이어야 합니다.", parent=self)
            return
        if not name:
            messagebox.showinfo("이름이 필요합니다",
                                r"문서에서 \이름\ 으로 부를 이름을 적어 주세요.",
                                parent=self)
            return
        try:
            if self.edit_id:
                library.update_mix(self.edit_id, name=name,
                                   member_ids=self._ids,
                                   subcat=self._subcat.value())
            else:
                library.add_mix(name, self._ids, subcat=self._subcat.value())
        except Exception as e:
            applog.exc("물감 섞기 저장 실패", e)
            messagebox.showerror("저장 실패", "꾸러미를 저장하지 못했습니다.",
                                 parent=self)
            return
        self.saved = True
        self.destroy()
        if self.on_saved:
            try:
                self.on_saved()
            except Exception as e:
                applog.exc("섞기 뒤 창고 갱신 실패", e)


def open_mix_dialog(master, member_ids=None, edit_id=None, on_saved=None,
                    subcat=""):
    dlg = MixDialog(master, member_ids=member_ids, edit_id=edit_id,
                    on_saved=on_saved, subcat=subcat)
    master.wait_window(dlg)
    return dlg.saved
