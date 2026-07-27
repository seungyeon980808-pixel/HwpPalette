# -*- coding: utf-8 -*-
r"""개인 라이브러리(물감 설정) 창 — 2026-07-25 재구축.

화면 구조:
    탭(서식·특수기호·템플릿·양식·사진·내장) → 검색·분류 필터 → 추가 버튼
    → **스크롤 목록** (분류별로 접었다 펼 수 있는 표) → 하단 동작바

예전 구조에서 바꾼 것 (사용자 결정):
  · 행마다 붙어 있던 버튼 3개(적용·✎·삭제)를 **하단 동작바 하나**로 —
    같은 버튼이 수십 번 반복돼 목록이 소음이 됐다.
  · 스크롤이 없어 항목 20개면 창이 화면 밖으로 나가던 것 → Canvas 스크롤.
  · 분류(그룹)별로 묶어 접기 — 자산이 늘어도 목록이 안 길어진다.
  · 사진 폴더 지정이 메인에 상시 노출되던 것 → '사진' 탭 안으로.
  · 물감 나누기(구 내보내기/가져오기) → 설정(⚙) 메뉴의 대화상자로 (open_share).
  · 탭의 저장 키(key)와 표시 이름(label)을 분리 — '문자'는 화면에서만
    '특수기호'로 보인다. 저장 데이터(library.json)의 키는 영원히 그대로다.
"""

import pathlib
import tkinter as tk
from tkinter import filedialog, simpledialog, ttk
import dialogs as messagebox   # 윈도우 기본 대화상자 대신 프로그램과 같은 얼굴 (2026-07-27)

import applog
import chip                      # 물감·팔레트 파일 만들기·읽기·등록
import clipboard                  # 윈도우 클립보드 (Tk 클립보드 금지)
import hwp_engine
import engine_library
import library
import palette                    # 보낼 팔레트 목록 (팔레트 보내기)
import builtin_chars
import settings

import appinfo
import form_fill                   # 자리 토큰 규칙 (\\ · \이름\)
import form_markdown               # 양식→AI 프롬프트 (기획 18번)
import screens                     # 창 자리 규칙 (메인 창 옆)
import theme                       # 색은 theme.py 한 곳에서 (밝게/어둡게)
import ui_fx                       # 호버 보간 (애플 A안)
from roundbtn import RoundButton   # 둥근 모서리 버튼 (애플 A안)
from popover import Popover        # 앱과 같은 얼굴의 팝업 메뉴

_C = theme.colors()
BG = _C["bg"]
CARD = _C["card"]
ACCENT = _C["accent"]
TEXT = _C["text"]
MUTED = _C["muted"]
BORDER = _C["border"]
ROWBG = _C["subbg"]
SOFT = _C["yellow"]            # 옅은 회색 버튼 바탕 (예전 #e8e8ed 하드코딩)
ACCENT_SOFT = _C["accent_soft"]    # 선택 행·켜진 칩의 옅은 파랑
FONT = theme.FONT
SP = theme.SP        # 간격 토큰 (4의 배수)
FS = theme.FS        # 글자 위계 (역할 이름)

# 탭 정의 — key 는 저장 데이터(library.json)의 키라 **절대 불변**,
# label 만 화면에 보인다. '문자'→'특수기호' 개명이 표시만 바뀌는 이유다.
CATS = (
    {"key": "서식",   "label": "서식"},
    {"key": "문자",   "label": "특수기호"},
    {"key": "템플릿", "label": "템플릿"},
    {"key": "양식",   "label": "양식"},
    {"key": "사진",   "label": "사진"},
)
# '내장' 탭은 없앴다 (사용자 결정 2026-07-26) — 내장 기호와 내가 등록한 기호는
# 쓰는 사람 입장에서 같은 것("문서에 \라벨\ 로 부르는 기호")인데 탭이 갈려 있어
# 두 곳을 뒤져야 했다. 이제 '특수기호' 한 탭에서 문자표처럼 함께 보여준다.
MY_GROUP_CHIP = "내가 등록"
CAT_LABEL = {c["key"]: c["label"] for c in CATS}
TABS = tuple(c["key"] for c in CATS)    # open_manager(cat=...) 검사용

TAB_DESC = {
    "서식": "문서에서 캡처한 글자 모양(굵기·색상·자간 등) 일부만 저장해 "
            "아무 글자에나 입히는 기능 "
            "— 팔레트의 '서식 조합'은 캡처 대신 목록에서 직접 고르는 쪽",
    "문자": "기호·문구를 눌러 삽입하거나, 문서에 \\라벨\\ 로 불러 씁니다 "
            "(내장 기호는 등록 없이 바로 쓸 수 있습니다)",
    "템플릿": "표·결재란처럼 문서 '일부'를 저장해 커서 자리에 꽂아 넣는 기능",
    "양식": "hwp 파일 '전체'를 저장해 새 문서로 여는 기능 "
            "(용지·여백·머리말까지 그대로 — 표지·통신문용)",
    "사진": "그림이 든 폴더를 연결해 둡니다. 문서에서 \\파일이름\\ 으로 부르거나 "
            "팔레트의 '사진' 버튼에서 골라 넣습니다 (하위 폴더는 읽지 않습니다)",
}

# 글자 수 상한 (개선안 23 — 흩어져 있던 매직넘버에 이름을 붙임)
ROW_PREVIEW_MAX = 16     # 목록 행에 보여줄 내용 미리보기 길이
AUTO_NAME_MAX = 10       # 문자 등록 시 내용에서 이름을 자동으로 뽑는 길이
SUMMARY_MAX = 34         # 행 요약(한 줄)의 글자 수 상한
LIST_H_PX = 360          # 스크롤 목록의 고정 높이
LIST_W_PX = 520          # 스크롤 목록의 폭 (기호판이 한 줄에 여러 개 들어가게)
SIDE_W_PX = 132          # 왼쪽 분류 목록의 폭 (특수기호 탭)


def _dialog_btn(parent, text, command, primary=False, zone_bg=None):
    """대화상자 공용 버튼 — 저장/확인은 파랑, 취소는 옅은 회색 (애플 A안)."""
    font = (FONT, theme.fs(FS["body"]), "bold") if primary else (FONT, theme.fs(FS["body"]))
    b = RoundButton(parent, text=text, command=command,
                    bg=ACCENT if primary else SOFT,
                    fg="white" if primary else TEXT, radius=theme.RADIUS["ctl"], font=font,
                    outline="", zone_bg=zone_bg or parent.cget("bg"))
    return b.fit(pad_x=16, pad_y=6)


def ime_composing_text(widget):
    r"""위젯에서 지금 조합 중인 IME 글자를 읽는다. 없으면 빈 문자열.

    '기본문항'을 치는 동안 마지막 '항'은 확정 전까지 위젯에 없다 — IME 가
    화면에만 그리고 있다. 위젯 값만 읽는 미리보기는 그래서 늘 한 글자 늦었다.
    Windows IMM API(ImmGetCompositionStringW)로 조합 중인 문자열을 직접 물어봐서
    위젯 값 뒤에 붙이면 미리보기가 실시간이 된다.

    이 함수는 '보여주기' 전용이다. 저장은 여전히 commit_ime(조합 확정) 뒤의
    위젯 값을 쓴다 — 조합 문자열은 '항' 이전에 'ㅎ','하' 같은 중간 상태도
    지나가므로 저장 값으로는 못 쓴다.
    """
    try:
        import ctypes
        imm32 = ctypes.windll.imm32
        GCS_COMPSTR = 0x0008
        hwnd = widget.winfo_id()
        himc = imm32.ImmGetContext(hwnd)
        if not himc:
            return ""
        try:
            nbytes = imm32.ImmGetCompositionStringW(himc, GCS_COMPSTR, None, 0)
            if nbytes <= 0:
                return ""
            buf = ctypes.create_unicode_buffer(nbytes // 2 + 1)
            imm32.ImmGetCompositionStringW(himc, GCS_COMPSTR, buf, nbytes)
            return buf.value[:nbytes // 2]
        finally:
            imm32.ImmReleaseContext(hwnd, himc)
    except Exception:
        return ""       # 미리보기 보조일 뿐 — 실패해도 조용히 넘어간다


def commit_ime(window):
    r"""한글 IME 로 조합 중인 글자를 확정시킨다. 값을 읽기 **직전에** 부른다.

    '기본문'을 치는 도중 마지막 '문'은 IME 가 화면에만 그리고 있을 뿐, 위젯에는
    아직 안 들어와 있다(실측 2026-07-19 — 위젯에 실제로 들어간 글자는 즉시
    변수에 반영되는 것을 확인했으므로, 코드 순서 문제가 아니라 IME 조합 때문).
    그 상태에서 값을 읽으면 '기본'만 저장된다.

    포커스를 옮기면 조합이 확정되므로 한 번 옮겨 주고, 반영될 때까지 기다린다.
    """
    try:
        window.focus_set()              # 입력칸 → 창 자체로 포커스 이동
        window.update_idletasks()       # 확정 결과가 변수에 반영될 때까지
    except Exception as e:
        applog.exc("IME 조합 확정 실패 — 마지막 글자가 빠질 수 있음", e)


def _ensure_hwp(parent):
    try:
        hwp_engine.connect()
        return True
    except Exception as e:
        messagebox.showerror("연결 실패", f"한글을 먼저 실행해주세요.\n{e}", parent=parent)
        return False


class StyleFieldDialog(tk.Toplevel):
    """서식 캡처 시 '체크한 항목만' 담기 위한 체크리스트."""

    def __init__(self, master):
        super().__init__(master)
        self.result = None
        self.title("캡처할 항목 선택")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        tk.Label(self, text="선택 영역에서 어떤 항목을 저장할까요?",
                 font=(FONT, theme.fs(FS["head"]), "bold"), bg=BG, fg=TEXT).pack(
                 anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="체크한 항목만 저장돼, 나중에 그 항목만 다른 글자에 입혀집니다.",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        self.vars = {}
        body = tk.Frame(self, bg=BG, padx=16)
        body.pack(fill="x")
        for label in engine_library.CHARSHAPE_FIELD_LABELS:
            v = tk.BooleanVar(value=False)
            self.vars[label] = v
            tk.Checkbutton(body, text=label, variable=v, font=(FONT, theme.fs(FS["head"])),
                           bg=BG, fg=TEXT, activebackground=BG,
                           selectcolor=CARD, cursor="hand2").pack(anchor="w", pady=2)

        foot = tk.Frame(self, bg=BG, padx=16, pady=14)
        foot.pack(fill="x")
        _dialog_btn(foot, "다음", self._ok, primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+40}+{master.winfo_rooty()+40}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _ok(self):
        checked = [k for k, v in self.vars.items() if v.get()]
        if not checked:
            messagebox.showwarning("선택 없음", "하나 이상 체크해주세요.", parent=self)
            return
        self.result = checked
        self.destroy()


class MetaDialog(tk.Toplevel):
    """이름 / 마크다운 라벨 / 태그를 한 창에서 입력."""

    def __init__(self, master, title="등록 정보", name="", label="", extra_note="",
                 exclude_id=None):
        super().__init__(master)
        self.result = None
        self.exclude_id = exclude_id        # 수정 중인 자기 자신은 충돌에서 제외
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        body = tk.Frame(self, bg=BG, padx=16, pady=12)
        body.pack(fill="x")

        # ── 이름만 물어본다. 라벨·태그는 대부분 기본값이면 충분하므로 접어둠 ──
        tk.Label(body, text="이름", font=(FONT, theme.fs(FS["body"])), bg=BG, fg=TEXT).grid(
            row=0, column=0, sticky="w", pady=3)
        self.name_var = tk.StringVar(value=name)
        name_entry = tk.Entry(body, textvariable=self.name_var, width=26,
                              font=(FONT, theme.fs(FS["head"])), relief="solid", bd=1)
        name_entry.grid(row=0, column=1, pady=3, padx=(8, 0))
        name_entry.focus_set()
        name_entry.bind("<Return>", lambda e: self._ok())
        self.name_entry = name_entry
        # 한글 IME 로 조합 중인 글자는 아직 위젯에 안 들어와 있어서 미리보기가
        # 한 글자 뒤처져 보인다(실측). 조합이 끝나는 순간을 잡으려고 키를 뗄 때와
        # 포커스가 빠질 때도 다시 그린다.
        name_entry.bind("<KeyRelease>", lambda e: self._update_preview())
        name_entry.bind("<FocusOut>", lambda e: self._update_preview())

        self.label_var = tk.StringVar(value=label)
        self.tags_var = tk.StringVar(value="")
        self._preview = tk.Label(body, text="", font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=ACCENT)
        self._preview.grid(row=1, column=1, sticky="w", padx=(8, 0))
        self.name_var.trace_add("write", lambda *a: self._update_preview())
        self.label_var.trace_add("write", lambda *a: self._update_preview())

        if extra_note:
            tk.Label(body, text=extra_note, font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED,
                     wraplength=320, justify="left").grid(
                row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # ── 태그 — 늘 펼쳐 둔다 (2026-07-27) ──
        # '자세히'로 접어 뒀더니 태그가 있다는 것 자체를 모르고 지나쳤다.
        # 마크다운 라벨 칸은 없앴다 — **이름이 곧 라벨**로 통일했다(사용자 결정).
        # 두 개를 따로 두니 이름만 고쳤을 때 라벨이 옛 이름으로 남는 사고가 났다.
        adv = tk.Frame(self, bg=BG, padx=16)
        adv.pack(fill="x")
        # '태그' 이름표를 입력칸 **옆**에 둔다 (사용자 지적 2026-07-27) —
        # 위 '이름' 줄과 같은 짜임이어야 눈이 줄 단위로 훑으면 된다.
        trow = tk.Frame(adv, bg=BG)
        trow.pack(fill="x", pady=(4, 0))
        tk.Label(trow, text="태그", font=(FONT, theme.fs(FS["body"])), bg=BG,
                 fg=TEXT).pack(side="left")
        self.tag_entry = tk.Entry(trow, width=26, font=(FONT, theme.fs(FS["head"])),
                                  relief="solid", bd=1)
        self.tag_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        # 엔터로 담는다 (사용자 결정 2026-07-27) — 띄어쓰기로 나열하는 방식은
        # 무엇이 이미 담겼는지 눈에 안 보이고, 지우려면 글자를 찾아 지워야 했다.
        self.tag_entry.bind("<Return>", lambda e: self._commit_tag())
        tk.Label(adv, text="적고 Enter — 담긴 태그는 ✕ 로 뺍니다 (한글 5글자 이내)",
                 font=(FONT, theme.fs(FS["caption"])), bg=BG, fg=MUTED).pack(anchor="w")
        self._tag_box = tk.Frame(adv, bg=BG)
        self._tag_box.pack(anchor="w", fill="x", pady=(4, 0))
        # 이미 쓰고 있는 태그는 눌러서 담는다 — **오타로 태그가 번식하는 것을
        # 막는 장치**다(#수능 / #수능문제 / #수능_문제 가 따로 생기면 안 쓰느니만
        # 못하다).
        known = library.list_tags()[:8]
        if known:
            row = tk.Frame(adv, bg=BG)
            row.pack(anchor="w", fill="x", pady=(4, 0))
            tk.Label(row, text="쓰던 태그", font=(FONT, theme.fs(FS["caption"])),
                     bg=BG, fg=MUTED).pack(side="left", padx=(0, 4))
            for t in known:
                c = tk.Label(row, text=f"#{t}", font=(FONT, theme.fs(FS["sub"])),
                             bg=SOFT, fg=ACCENT, padx=6, pady=2, cursor="hand2")
                c.pack(side="left", padx=(0, 4))
                c.bind("<Button-1>", lambda e, tag=t: self._add_tag(tag))
        self.tags_var.trace_add("write", lambda *a: self._draw_tags())
        self._draw_tags()

        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        self.foot = foot            # 부르는 쪽이 버튼을 더 붙일 수 있게 (수정 창)
        _dialog_btn(foot, "저장", self._ok, primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))

        self._update_preview()
        self._poll_preview()        # IME 조합 중 글자까지 실시간 반영
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+40}+{master.winfo_rooty()+60}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _commit_tag(self):
        """입력칸의 글자를 태그로 담는다 (Enter). 칸은 비워 다음 것을 받는다."""
        commit_ime(self)
        text = self.tag_entry.get().strip()
        self.tag_entry.delete(0, "end")
        if text:
            self._add_tag(text)

    def _add_tag(self, tag):
        """태그 하나를 담는다 (중복은 무시)."""
        cur = library.normalize_tags(self.tags_var.get())
        for t in library.split_tag_input(tag):
            if t not in cur:
                cur.append(t)
        self.tags_var.set(" ".join(cur))

    def _remove_tag(self, tag):
        cur = [t for t in library.normalize_tags(self.tags_var.get())
               if t != tag]
        self.tags_var.set(" ".join(cur))

    def _draw_tags(self):
        """담긴 태그를 칩으로 — 각 칩의 ✕ 로 뺀다."""
        if not hasattr(self, "_tag_box"):
            return
        for w in self._tag_box.winfo_children():
            w.destroy()
        for t in library.normalize_tags(self.tags_var.get()):
            chip = tk.Frame(self._tag_box, bg=ACCENT_SOFT,
                            highlightbackground=ACCENT, highlightthickness=1)
            chip.pack(side="left", padx=(0, 4), pady=2)
            tk.Label(chip, text=f"#{t}", font=(FONT, theme.fs(FS["sub"])),
                     bg=ACCENT_SOFT, fg=ACCENT).pack(side="left", padx=(6, 2))
            x = tk.Label(chip, text="✕", font=(FONT, theme.fs(FS["caption"])),
                         bg=ACCENT_SOFT, fg=MUTED, cursor="hand2")
            x.pack(side="left", padx=(0, 5))
            x.bind("<Button-1>", lambda e, tag=t: self._remove_tag(tag))

    def _live_value(self, var, entry):
        """위젯 값 + 그 칸에서 지금 조합 중인 IME 글자. 미리보기 전용."""
        v = var.get()
        try:
            if entry is not None and self.focus_get() is entry:
                v += ime_composing_text(entry)
        except Exception:
            pass                    # 미리보기 보조 — 실패해도 위젯 값은 보여준다
        return v

    def _update_preview(self):
        """문서에 어떻게 쓰는지 실물로 보여준다 (\\ 헷갈림 방지).

        조합 중인 글자(ime_composing_text)까지 합쳐서 그린다 — 안 그러면
        '기본문항'을 치는 동안 미리보기가 '기본문'에서 멈춰 한 글자 늦어 보인다.
        """
        lab = library.normalize_label(
            self._live_value(self.name_var, getattr(self, "name_entry", None)))
        self._preview.config(text=f"문서에 이렇게 쓰세요:  \\{lab}\\" if lab else "")

    def _poll_preview(self):
        """조합 상태는 이벤트만으로 다 못 잡아서(마우스로 후보 선택 등) 주기적으로도 그린다."""
        if not self.winfo_exists():
            return
        self._update_preview()
        self.after(150, self._poll_preview)

    def _ok(self):
        commit_ime(self)
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("이름 없음", "이름을 입력해주세요.", parent=self)
            return
        # 이름이 곧 라벨이다 (2026-07-27) — 따로 두지 않는다
        label = name
        if not self._confirm_label(label):
            return
        tags = self._checked_tags()
        if tags is None:            # 규칙에 어긋난 태그 — 고칠 기회를 준다
            return
        self.result = (name, label, tags)
        self.destroy()

    def _checked_tags(self):
        r"""입력칸의 태그를 검사한다. 통과하면 목록, 아니면 None(저장 중단).

        **조용히 버리지 않는다** — 규칙(한글 5글자)에 어긋난 것을 말없이
        떨구면 사용자는 "분명히 달았는데 없다"를 겪는다. 무엇이 왜 걸렸는지
        말하고 창을 열어 둔 채 고치게 한다.
        """
        raw = library.split_tag_input(self.tags_var.get())
        bad = [t for t in raw if not library.is_valid_tag(t)]
        if bad:
            messagebox.showwarning(
                "태그 규칙",
                "태그는 **한글 5글자 이내**여야 합니다.\n"
                "(띄어쓰기는 태그를 나누는 구분자입니다)\n\n"
                "쓸 수 없는 태그: " + ", ".join(bad[:5]),
                parent=self)
            return None
        return library.normalize_tags(raw)

    def _confirm_label(self, label):
        r"""라벨이 이미 쓰이고 있으면 물어본다. 계속할지 여부를 반환.

        막지는 않는다 — 팔레트 버튼으로만 쓸 거라면 라벨이 겹쳐도 상관없다.
        다만 \라벨\ 로는 호출되지 않는다는 사실을 알고 넘어가야 한다.
        """
        owner = library.find_label_owner(label, exclude_id=self.exclude_id)
        if owner is None:
            return True
        cat, item = owner
        return messagebox.askyesno(
            "라벨이 겹칩니다",
            f"\\{library.normalize_label(label)}\\ 은(는) 이미 "
            f"[{cat}] '{item.get('name')}' 이(가) 쓰고 있습니다.\n\n"
            "이대로 저장하면 이 항목은 팔레트 버튼으로는 동작하지만,\n"
            "마크다운 변환에서는 호출되지 않습니다.\n\n"
            "그래도 저장할까요?  (아니오 = 라벨을 고치러 돌아가기)",
            parent=self)


def capture_template_dialog(parent):
    r"""한글의 현재 선택(또는 커서가 든 표)을 템플릿으로 등록한다.

    반환: 등록된 항목 id. 사용자가 취소했거나 실패하면 None.

    **라이브러리 창과 환경설정(팔레트) 창이 같은 코드를 쓰게 하려고 떼어냈다**
    (2026-07-25). 예전에는 두 벌로 복사돼 있었고, 팔레트 쪽 복사본은 MetaDialog 를
    임포트하지 않아 NameError 로 죽었다 — "라이브러리 창에서만 템플릿 추가가
    되던" 원인. 한 벌로 합치면 이런 어긋남이 다시 생기지 않는다.
    """
    if not _ensure_hwp(parent):
        return None
    if not hwp_engine.has_selection():
        # 드래그가 없어도, 표 안을 클릭만 해뒀으면 표 전체를 자동 선택
        if not engine_library.auto_select_table_if_inside():
            messagebox.showwarning("선택 없음",
                "한글에서 템플릿으로 저장할 영역을 드래그로 선택하거나,\n"
                "표를 저장하려면 표 안을 클릭만 해둬도 됩니다.", parent=parent)
            return None
    # 자리 스캔 — \\ (또는 \이름\) 하나가 자리 하나. 홑 \ 는 옛 문법.
    captured = hwp_engine.read_selection_text(retries=6)
    slot_count = library.count_slots(captured)
    tokens = form_fill.token_list(captured)
    names = [t for t in tokens if t]
    singles = sum(1 for m in form_fill.TOKEN_RE.finditer(captured)
                  if m.group(1) is None and len(m.group(0)) == 1)
    if slot_count:
        note = (f"자리 {slot_count}개 발견 — 마크다운 변환 시 아랫줄이 "
                "위에서부터 순서대로 채워집니다. (비울 칸에는 '-' 한 줄)")
        if names:
            note += ("\n칸 이름: " + " · ".join(dict.fromkeys(names))
                     + "\n→ 이름이 있어 팔레트에서 누르면 채우기 표가 뜹니다.")
        if singles:
            note += (f"\n옛 표시(홑 \\) {singles}개는 \\\\ 로 정리해 저장합니다.")
    elif "/" in captured:
        # 실제로 겪은 혼동: 자리를 슬래시(/)로 찍으면 인식 안 됨 (2026-07-16)
        note = ("⚠ 자리 표시가 없습니다. 혹시 슬래시(/)를 쓰셨나요?\n"
                "   자리는 \\\\ 로 표시합니다 — 한글에서 ₩₩ 로 보이는 그 키입니다.")
    else:
        note = ("자리 표시(\\\\)가 없습니다. 글자가 들어갈 자리에 \\\\ 를 넣으면\n"
                "마크다운 변환 때 아랫줄 내용이 순서대로 채워집니다.\n"
                "이름을 넣어 \\배점\\ 처럼 쓰면 누를 때 채우기 표가 뜹니다.")
    meta = MetaDialog(parent, title="템플릿 등록", extra_note=note)
    parent.wait_window(meta)
    if not meta.result:
        return None
    name, label, tags = meta.result
    # add_template_from_capture 의 두 번째 인자는 **함수**다 (목적지를 받아 거기
    # 저장하는 함수). 조각을 최종 이름으로 바로 저장하므로 이름 바꾸기가 없고,
    # 한글이 파일을 물고 있어 나던 WinError 32 도 생기지 않는다 (2026-07-19).
    try:
        item_id = library.add_template_from_capture(
            name, engine_library.capture_fragment, label=label,
            tags=tags, slot_count=slot_count)
    except Exception as e:
        applog.exc("템플릿 캡처 실패", e)
        messagebox.showerror("캡처 실패", str(e), parent=parent)
        return None
    make_clean_preview("템플릿", item_id)
    # 구버전이 한글에 열어둔 _tmp 문서가 있으면 닫고 디스크에서도 청소
    try:
        engine_library.close_stale_temp_docs()
        library.cleanup_temp_fragments()
    except Exception as e:
        applog.exc("임시 파일 청소 실패 (무해)", e)
    return item_id


def make_clean_preview(cat, item_id):
    r"""물감을 저장한 직후, 자리표시(\) 없는 미리보기 그림을 만들어 둔다.

    실패해도 조용히 넘어간다 — 그림이 없으면 파일 안의 것(표시가 찍힌)을
    쓰면 되고, 등록 자체가 실패로 보여서는 안 된다.
    """
    try:
        # 옛 그림을 먼저 지운다 — 새로 만들다 실패했을 때 **고치기 전 모습**이
        # 남아 있으면 내용과 다른 미리보기를 보여주게 된다. 그림이 없으면
        # 파일 안의 것으로 물러나므로 내용은 항상 맞는다.
        import preview
        preview.cached_path(item_id).unlink(missing_ok=True)
        item = library.find_by_id(cat, item_id)
        if item:
            engine_library.build_clean_preview(library.template_path(item),
                                               item_id)
    except Exception as e:
        applog.exc(f"미리보기 만들기 실패 (무해) — {item_id}", e)


class TextInputDialog(tk.Toplevel):
    """문자/문구 등록 입력창."""

    def __init__(self, master, prefill=""):
        super().__init__(master)
        self.result = None
        self.title("문자/문구 내용")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        tk.Label(self, text="저장할 내용을 입력하세요 (한글에서 선택했다면 자동으로 채워집니다)",
                 font=(FONT, theme.fs(FS["body"])), bg=BG, fg=MUTED, justify="left").pack(
                 anchor="w", padx=16, pady=(14, 6))

        self.text = tk.Text(self, width=44, height=5, font=(FONT, theme.fs(FS["head"])),
                             wrap="word", relief="solid", bd=1)
        self.text.pack(padx=16)
        self.text.insert("1.0", prefill)

        foot = tk.Frame(self, bg=BG, padx=16, pady=14)
        foot.pack(fill="x")
        _dialog_btn(foot, "다음", self._ok, primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+40}+{master.winfo_rooty()+40}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _ok(self):
        commit_ime(self)                # 조합 중인 마지막 글자가 빠지지 않게
        self.result = self.text.get("1.0", "end-1c")
        self.destroy()


class LibraryManager(tk.Toplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.on_saved = on_saved
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.current_cat = "서식"
        self._sel = None                # 지금 선택된 행 {"cat","item","row"}
        self._builtin_group = "전체"     # 특수기호 탭의 묶음 칩 선택

        tk.Label(self, text="물감 설정", font=(FONT, theme.fs(FS["title"]), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(14, 2))

        # 탭 버튼 — 표시는 label, 내부는 key (저장 데이터 키와 한 몸)
        tab_row = tk.Frame(self, bg=BG, padx=16)
        tab_row.pack(fill="x", pady=(4, 0))
        self.tab_btns = {}
        for c in CATS:
            b = RoundButton(tab_row, text=c["label"],
                            command=lambda k=c["key"]: self._switch_tab(k),
                            bg=CARD, fg=TEXT, radius=theme.RADIUS["ctl"],
                            font=(FONT, theme.fs(FS["body"]), "bold"), outline="",
                            zone_bg=BG)
            b.fit(pad_x=12, pad_y=6)
            b.pack(side="left", padx=(0, 4))
            self.tab_btns[c["key"]] = b

        self.desc_label = tk.Label(self, font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED,
                                    justify="left", wraplength=440)
        self.desc_label.pack(anchor="w", padx=16, pady=(6, 8))

        # 검색칸 하나로 끝낸다 (2026-07-26 — 분류 콤보·분류 관리 버튼을 걷어냈다).
        #
        # 예전에는 [검색] + [분류 콤보] + [분류 관리 ⋯] 세 개가 한 줄에 있었다.
        # 분류가 태그로 바뀌면서 '하나만 고르는 콤보'는 뜻이 없어졌고, 태그
        # 필터를 따로 만들면 화면이 다시 늘어난다. 그래서 **검색칸이 둘 다 한다**:
        #     사진      → 이름·라벨에 '사진' 이 든 물감
        #     #수능     → '수능' 태그가 달린 물감
        #     #수능 사진 → 둘 다 만족하는 물감
        filter_row = tk.Frame(self, bg=BG, padx=16)
        filter_row.pack(fill="x")
        tk.Label(filter_row, text="검색", font=(FONT, theme.fs(FS["sub"])), fg=MUTED, bg=BG).pack(side="left")
        self.search_var = tk.StringVar(value="")
        se = tk.Entry(filter_row, textvariable=self.search_var, width=20,
                      font=(FONT, theme.fs(FS["body"])), relief="solid", bd=1)
        se.pack(side="left", padx=(6, 8))
        self.search_var.trace_add("write", lambda *a: self._refresh())
        tk.Label(filter_row, text="#태그 로 태그만 골라 볼 수 있습니다",
                 font=(FONT, theme.fs(FS["caption"])), fg=MUTED, bg=BG).pack(side="left")

        # 특수기호 탭은 칩 대신 **왼쪽 분류 목록**을 쓴다 (사용자 결정 2026-07-26).
        # 기호가 200개를 넘으면서 칩 줄이 여러 줄로 접혔다 — 한글 문자표처럼
        # 왼쪽에 분류, 오른쪽에 기호판을 두면 분류가 몇 개든 줄이 안 늘어난다.
        self._chip_btns = {}

        # 추가 버튼(탭마다 동작이 다름) — 자리는 항상 구분선 앞 (앵커 = _sep)
        self.add_btn = tk.Button(self, font=(FONT, theme.fs(FS["body"]), "bold"), bg=SOFT,
                                  fg=TEXT, bd=0, padx=10, pady=8, cursor="hand2")
        self.add_btn.pack(fill="x", padx=16, pady=(8, 0))

        self._sep = tk.Frame(self, bg=BORDER, height=1)
        self._sep.pack(fill="x", padx=16, pady=(10, 6))

        # ── 목록 영역 = [왼쪽 분류 목록] + [스크롤 목록] ──
        # 왼쪽 목록은 특수기호 탭에서만 나타난다 (다른 탭은 분류가 적어 필요 없다).
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16)
        self.side = tk.Frame(body, bg=CARD, width=SIDE_W_PX,
                             highlightbackground=BORDER, highlightthickness=1)
        self.side.pack_propagate(False)

        # ── 스크롤 목록 (2026-07-25 재구축의 핵심) ──
        # 예전에는 스크롤이 없어 항목 20개면 창이 화면 밖으로 나갔다.
        wrap = tk.Frame(body, bg=BG)
        wrap.pack(side="left", fill="both", expand=True)
        self._canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                                 height=LIST_H_PX, width=LIST_W_PX)
        messagebox.style_scrollbars(self)
        sb = ttk.Scrollbar(wrap, orient="vertical",
                           style="App.Vertical.TScrollbar",
                           command=self._canvas.yview)
        self.list_area = tk.Frame(self._canvas, bg=BG)
        self._canvas_win = self._canvas.create_window(
            (0, 0), window=self.list_area, anchor="nw")
        self.list_area.bind(
            "<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))
        # 행이 캔버스 폭을 꽉 채우게 — 안 하면 행 폭이 내용에 따라 들쭉날쭉
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfigure(self._canvas_win, width=e.width))
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        # 휠 스크롤 — 이 창 위에 있을 때만 (bind_all 을 창 진입/이탈로 켜고 끈다)
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all(
            "<MouseWheel>", self._on_wheel))
        self._canvas.bind("<Leave>", lambda e: self._canvas.unbind_all(
            "<MouseWheel>"))

        # ── 하단 동작바 — 행마다 버튼을 반복하지 않고 여기 한 벌만 ──
        bar = tk.Frame(self, bg=BG, padx=16, pady=10)
        bar.pack(fill="x")
        self.sel_hint = tk.Label(bar, text="", font=(FONT, theme.fs(FS["sub"])),
                                 bg=BG, fg=MUTED, anchor="w")
        self.sel_hint.pack(side="left", fill="x", expand=True)
        # 주 동작(삽입/적용/열기)이 맨 오른쪽 — 먼저 pack 할수록 오른쪽에 붙는다
        self.act_main = _dialog_btn(bar, "삽입", self._act_selected, primary=True)
        self.act_edit = _dialog_btn(bar, "수정", self._edit_selected)
        self.act_del = _dialog_btn(bar, "삭제", self._del_selected)
        # ⋯ = 템플릿·양식 전용 추가 동작 (꺼내서 고치기 · AI 프롬프트)
        self.act_more = _dialog_btn(bar, "⋯", self._more_menu)
        self.act_main.pack(side="right", padx=(6, 0))
        self.act_edit.pack(side="right", padx=(6, 0))
        self.act_del.pack(side="right", padx=(6, 0))

        # Esc 로 닫기 · 화살표로 항목 이동 (사용자 결정 2026-07-26).
        # 물감 설정은 '고르고 실행하는' 창이라 목록 조작이 키보드로 돼야 한다.
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Up>", lambda e: self._move_sel(-1))
        self.bind("<Down>", lambda e: self._move_sel(1))
        self.bind("<Left>", lambda e: self._move_sel(-1, horizontal=True))
        self.bind("<Right>", lambda e: self._move_sel(1, horizontal=True))
        self.bind("<Return>", lambda e: self._act_selected())

        self._switch_tab("서식")
        self.update_idletasks()
        screens.place_beside(self, master)

    # ── 키보드로 목록 이동 ───────────────────────────
    def _move_sel(self, delta, horizontal=False):
        r"""화살표로 다음/이전 항목 선택. 격자에서는 위아래가 '한 줄'만큼 뛴다.

        검색칸에 글자를 치는 중이면 가로 화살표는 커서 이동이어야 하므로
        건드리지 않는다 (Tk 는 포커스가 Entry 면 그쪽이 먼저 받는다).
        """
        nav = getattr(self, "_nav", [])
        if not nav:
            return "break"
        step = delta
        if not horizontal and self._nav_cols > 1:
            step = delta * self._nav_cols      # 격자: 위아래 = 한 줄
        cur = -1
        if self._sel is not None:
            for i, e in enumerate(nav):
                if e.get("row") is self._sel.get("row"):
                    cur = i
                    break
        nxt = 0 if cur < 0 else max(0, min(len(nav) - 1, cur + step))
        self._select(nav[nxt])
        self._scroll_into_view(nav[nxt].get("row"))
        return "break"                          # 창 기본 스크롤과 겹치지 않게

    def _scroll_into_view(self, row):
        """고른 줄이 화면 밖이면 그만큼만 스크롤한다."""
        if row is None or not row.winfo_exists():
            return
        try:
            self._canvas.update_idletasks()
            top = row.winfo_rooty() - self._canvas.winfo_rooty()
            bottom = top + row.winfo_height()
            h = self._canvas.winfo_height()
            total = max(1, self.list_area.winfo_height())
            if top < 0:
                self._canvas.yview_moveto(
                    max(0.0, (self._canvas.canvasy(0) + top) / total))
            elif bottom > h:
                self._canvas.yview_moveto(
                    max(0.0, (self._canvas.canvasy(0) + bottom - h) / total))
        except Exception:
            pass                                # 이동 편의 기능 — 실패해도 그만

    def _on_wheel(self, e):
        try:
            self._canvas.yview_scroll(-1 * (e.delta // 120), "units")
        except Exception:
            pass

    # ── 탭 전환 ──────────────────────────────────────
    def _switch_tab(self, cat):
        self.current_cat = cat
        self._select(None)              # 탭이 바뀌면 선택도 초기화
        for k, b in self.tab_btns.items():
            active = k == cat
            b.retint(bg=ACCENT if active else CARD,
                     fg="white" if active else TEXT)
        self.desc_label.config(text=TAB_DESC[cat])

        # 추가 버튼 — 자리는 항상 구분선 앞 (앵커 없이 다시 pack 하면
        # 맨 아래로 떨어진다, 2026-07-25 버그)
        add_spec = {
            "서식":   ("+ 지금 선택한 글자에서 캡처해서 추가", self._add_style),
            "문자":   ("+ 새 특수기호/문구 추가", self._add_char),
            "템플릿": ("+ 지금 선택 영역을 템플릿으로 저장", self._add_template),
            "양식":   ("+ hwp 파일을 양식으로 등록", self._add_form),
            "사진":   ("+ 사진 폴더 연결 (여러 개 가능)", self._pick_photo_dir),
        }.get(cat)
        if add_spec:
            self.add_btn.config(text=add_spec[0], command=add_spec[1])
            self.add_btn.pack(fill="x", padx=16, pady=(8, 0), before=self._sep)
        else:
            self.add_btn.pack_forget()

        # 왼쪽 분류 목록은 특수기호 탭에서만 (다른 탭은 분류가 적어 필요 없다)
        if cat == "문자":
            self.side.pack(side="left", fill="y", padx=(0, 8))
            self._build_chips()
        else:
            self.side.pack_forget()

        # 동작바 — 탭마다 쓸 수 있는 동작이 다르다. 순서가 흐트러지지 않게
        # 전부 뗐다가 정해진 차례로 다시 붙인다 (주 동작이 맨 오른쪽).
        # 사진 탭은 '폴더 관리' 화면이라 동작바 자체가 필요 없다.
        main_label = {"서식": "적용", "양식": "열기"}.get(cat, "삽입")
        self.act_main.set_text(main_label, pad_x=16, pad_y=6)
        for b in (self.act_main, self.act_edit, self.act_del, self.act_more):
            b.pack_forget()
        if cat != "사진":
            self.act_main.pack(side="right", padx=(6, 0))
            self.act_edit.pack(side="right", padx=(6, 0))
            self.act_del.pack(side="right", padx=(6, 0))
        if cat in ("템플릿", "양식"):       # 꺼내서 고치기 · AI 프롬프트
            self.act_more.pack(side="right", padx=(6, 0))
        self._refresh(cat)

    def _build_chips(self):
        """왼쪽 분류 목록 — 한글 문자표처럼 '분류를 고르면 기호판이 바뀐다'.

        분류가 200개 기호를 열몇 갈래로 나누므로 세로 목록이 맞다. 가로 칩으로
        늘어놓으면 줄이 접혀 화면 위쪽을 다 먹는다 (사용자 지적 2026-07-26).
        """
        for w in self.side.winfo_children():
            w.destroy()
        self._chip_btns = {}
        groups = ["전체", MY_GROUP_CHIP]
        for _, _, g in builtin_chars.BUILTINS:
            if g not in groups:
                groups.append(g)
        if self._builtin_group not in groups:
            self._builtin_group = "전체"
        # 분류가 많아지면 이 목록도 스크롤이 필요하다 — 기호판과 같은 방식
        cv = tk.Canvas(self.side, bg=CARD, highlightthickness=0,
                       width=SIDE_W_PX - 2, height=LIST_H_PX - 2)
        inner = tk.Frame(cv, bg=CARD)
        cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.pack(fill="both", expand=True)
        cv.bind("<Enter>", lambda e: cv.bind_all(
            "<MouseWheel>",
            lambda ev: cv.yview_scroll(-1 * (ev.delta // 120), "units")))
        cv.bind("<Leave>", lambda e: cv.unbind_all("<MouseWheel>"))
        for g in groups:
            on = g == self._builtin_group
            b = RoundButton(inner, text=g,
                            command=lambda gg=g: self._pick_chip(gg),
                            bg=ACCENT if on else CARD,
                            fg="white" if on else TEXT, radius=theme.RADIUS["ctl"],
                            font=(FONT, theme.fs(FS["sub"])), outline="",
                            zone_bg=CARD, justify="left")
            b.fit(pad_x=8, pad_y=5, min_w=SIDE_W_PX - 12)
            b.pack(anchor="w", padx=4, pady=1)
            self._chip_btns[g] = b

    def _pick_chip(self, group):
        self._builtin_group = group
        for g, b in self._chip_btns.items():
            on = g == group
            b.retint(bg=ACCENT if on else CARD, fg="white" if on else TEXT)
        self._refresh()

    def _refresh(self, cat=None):
        cat = cat or self.current_cat
        self._select(None)
        # 화살표 이동용 목록 — 그리면서 순서대로 쌓는다 (보이는 차례 그대로)
        self._nav = []
        self._nav_cols = 1
        for w in self.list_area.winfo_children():
            w.destroy()
        self._canvas.yview_moveto(0)
        query = self.search_var.get().strip()

        if cat == "문자":
            self._render_char_grid(query)
            return

        if cat == "사진":
            self._render_photo_list(query)
            return

        items = self._filter(cat, library.list_items(cat), query)
        if not items:
            self._empty_note("해당하는 항목이 없습니다.")
            return
        for item in items:
            self._render_row(cat, item)

    def _empty_note(self, text):
        tk.Label(self.list_area, text=text, font=(FONT, theme.fs(FS["body"])),
                 bg=BG, fg=MUTED).pack(anchor="w", pady=8)

    def _search_blob(self, cat, item):
        parts = [item.get("name", ""), item.get("label", "")]
        parts += item.get("tags") or []
        if cat == "문자":
            parts.append(item.get("text", ""))
        return " ".join(parts).lower()

    @staticmethod
    def split_query(query):
        r"""검색어를 (태그 조건, 글자 조건) 으로 가른다.

        '#수능 사진' → (['수능'], '사진')
        태그는 **모두** 만족해야 하고(#수능 #사진 = 둘 다 달린 것),
        글자는 이름·라벨·태그 어디에든 들어 있으면 된다.
        """
        tags, words = [], []
        for tok in (query or "").split():
            if tok.startswith("#") and len(tok) > 1:
                tags.append(tok[1:].strip())
            elif tok:
                words.append(tok)
        return tags, " ".join(words)

    def _filter(self, cat, items, query):
        """검색칸 하나로 태그 필터 + 글자 검색을 함께 건다."""
        tags, words = self.split_query(query)
        if tags:
            items = [it for it in items
                     if all(t in (it.get("tags") or []) for t in tags)]
        if words:
            wl = words.lower()
            items = [it for it in items if wl in self._search_blob(cat, it)]
        return items

    # ── 행 그리기 ────────────────────────────────────

    def _make_row(self, cat, item, kind="item"):
        """행 한 줄의 껍데기 — 클릭=선택, 더블클릭=주 동작/수정."""
        row = tk.Frame(self.list_area, bg=ROWBG, highlightbackground=BORDER,
                       highlightthickness=1)
        row.pack(fill="x", pady=1)
        return row

    def _wire_row(self, row, cat, item, kind):
        """행(과 그 자식들)에 선택·더블클릭을 걸고, 화살표 이동 목록에 넣는다."""
        self._nav.append({"cat": cat, "item": item, "row": row, "kind": kind})
        def all_widgets(w):
            yield w
            for c in w.winfo_children():
                yield from all_widgets(c)
        for w in all_widgets(row):
            w.bind("<Button-1>",
                   lambda e, r=row, c=cat, it=item, k=kind:
                   self._select({"cat": c, "item": it, "row": r, "kind": k}))
            if kind == "item":
                w.bind("<Double-Button-1>",
                       lambda e, c=cat, it=item: self._edit(c, it))
            else:                       # 내장·사진 — 더블클릭 = 바로 삽입
                w.bind("<Double-Button-1>",
                       lambda e: self._act_selected())
            w.config(cursor="hand2")

    def _render_row(self, cat, item):
        row = self._make_row(cat, item)
        info = tk.Frame(row, bg=ROWBG, padx=10, pady=5)
        info.pack(side="left", fill="both", expand=True)
        if cat == "문자":
            # 특수기호는 내용 자체가 제목 (그 문자 그대로 보이게)
            t = item["text"].replace("\n", " ")
            title = (t if len(t) <= ROW_PREVIEW_MAX
                     else t[:ROW_PREVIEW_MAX] + "…")
            title_font = (FONT, theme.fs(11))
        else:
            title = item["name"]
            title_font = (FONT, theme.fs(FS["body"]), "bold")
        tk.Label(info, text=title, font=title_font,
                 bg=ROWBG, fg=TEXT, anchor="w").pack(side="left")
        summary = self._summary(cat, item)
        if summary:
            tk.Label(info, text=summary, font=(FONT, theme.fs(FS["sub"])),
                     bg=ROWBG, fg=MUTED, anchor="w").pack(side="left",
                                                          padx=(8, 0))
        # 라벨은 오른쪽 끝에 — 반복되는 꼬리표 대신 호출 이름만 조용히 보여준다
        lab = item.get("label") or item.get("name", "")
        tk.Label(row, text=f"\\{lab}\\", font=(FONT, theme.fs(FS["sub"])), bg=ROWBG,
                 fg=MUTED, padx=10).pack(side="right")
        # 태그 칩 — **누르면 그 태그로 걸러진다** (2026-07-26).
        # 태그를 보여주기만 하면 "그래서 어쩌라고"가 된다. 누르는 순간
        # 검색칸에 #태그 가 들어가므로, 따로 태그 목록 화면을 만들지 않아도
        # 태그가 눈에 띄고 바로 쓰인다.
        for t in (item.get("tags") or [])[:3]:
            chip = tk.Label(row, text=f"#{t}", font=(FONT, theme.fs(FS["caption"])),
                            bg=ROWBG, fg=ACCENT, padx=4, cursor="hand2")
            chip.pack(side="right")
            chip.bind("<Button-1>", lambda e, tag=t: self._filter_by_tag(tag))
        self._wire_row(row, cat, item, "item")

    def _filter_by_tag(self, tag):
        """태그 칩 클릭 — 검색칸에 넣으면 _refresh 가 알아서 걸러 준다."""
        self.search_var.set(f"#{tag}")
        return "break"          # 행 선택으로 번지지 않게

    # ── 특수기호: 한글 문자표처럼 격자로 (사용자 결정 2026-07-26) ──
    #
    # 한 줄에 기호 하나씩 늘어놓으니 78개 기호가 화면 열 몇 개를 잡아먹으면서도
    # 정작 한 번에 열 개도 못 봤다. 격자로 모으면 한 화면에 다 들어오고,
    # 무엇을 고르든 **호출 방법은 아래 한 곳**에서 말해 주면 된다.
    def _char_entries(self, query):
        """내가 등록한 기호 + 내장 기호를 한 목록으로 (등록한 것이 먼저)."""
        chip = self._builtin_group
        ql = query.lower()
        out = []
        if chip in ("전체", MY_GROUP_CHIP):
            for it in library.list_items("문자"):
                if ql and ql not in self._search_blob("문자", it):
                    continue
                out.append({"kind": "item", "cat": "문자", "item": it,
                            "text": it.get("text", ""),
                            "label": it.get("label") or it["name"],
                            # 내가 등록한 것은 내장 기호의 묶음(원문자·수학…)에
                            # 속하지 않는다 — 칩에서는 '내가 등록'으로만 걸린다
                            "group": MY_GROUP_CHIP})
        if chip != MY_GROUP_CHIP:
            for label, text, group in builtin_chars.search(query):
                if chip not in ("전체", group):
                    continue
                out.append({"kind": "builtin", "cat": "문자",
                            "item": {"name": label, "label": label,
                                     "text": text, "group": group},
                            "text": text, "label": label, "group": group})
        return out

    def _render_char_grid(self, query):
        entries = self._char_entries(query)
        if not entries:
            self._empty_note("해당하는 기호가 없습니다.")
            return
        # 칸은 정사각형. 목록 폭에 몇 개가 들어가는지 재서 줄을 나눈다.
        cell = int(round(46 * (theme.FONT_SCALE if theme.FONT_SCALE else 1)))
        avail = max(self._canvas.winfo_width(), LIST_W_PX) - 8
        cols = max(4, avail // (cell + 4))
        grid = tk.Frame(self.list_area, bg=BG)
        grid.pack(anchor="w")
        self._cells = []
        for i, e in enumerate(entries):
            f = tk.Frame(grid, bg=ROWBG, width=cell, height=cell,
                         highlightbackground=BORDER, highlightthickness=1)
            f.pack_propagate(False)
            f.grid(row=i // cols, column=i % cols, padx=2, pady=2)
            # 문구가 긴 항목(자주 쓰는 문장)은 앞부분만 — 전체는 툴팁·아래 줄에서
            shown = e["text"].replace("\n", " ")
            size = 13 if len(shown) <= 2 else (10 if len(shown) <= 4 else 8)
            if len(shown) > 6:
                shown = shown[:5] + "…"
            tk.Label(f, text=shown, font=(FONT, theme.fs(size)), bg=ROWBG,
                     fg=TEXT).pack(expand=True)
            e["row"] = f
            self._nav.append(e)
            self._wire_cell(f, e)
        self._nav_cols = cols
        # 내가 등록한 것과 내장 기호가 섞이므로, 무엇이 무엇인지 아래 줄이 말한다
        tk.Label(self.list_area,
                 text=f"{len(entries)}개  ·  누르면 아래에 부르는 법이 나옵니다",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED).pack(anchor="w",
                                                                 pady=(6, 0))

    def _wire_cell(self, f, entry):
        for w in (f, *f.winfo_children()):
            w.bind("<Button-1>", lambda e, en=entry: self._select(en))
            w.bind("<Double-Button-1>", lambda e: self._act_selected())
            w.config(cursor="hand2")

    def _render_photo_list(self, query):
        r"""사진 탭 = **폴더 관리** 화면 (사용자 결정 2026-07-26).

        예전에는 폴더 안 그림을 한 장씩 행으로 늘어놓았다. 그림이 수백 장인
        폴더에서는 목록이 끝없이 길어지고, 정작 여기서 할 일(어느 폴더를
        연결해 둘지)은 안 보였다. 그림을 고르는 일은 팔레트의 '사진' 버튼이
        맡는다 — 그때가 실제로 문서에 넣는 순간이다.
        """
        folders = library.photo_folders_summary()
        if not folders:
            self._empty_note(
                "연결된 사진 폴더가 없습니다.\n"
                "위 버튼으로 폴더를 연결하면, 문서에 \\파일이름\\ 으로 그림을\n"
                "넣을 수 있고 팔레트의 '사진' 버튼에서 골라 넣을 수도 있습니다.")
            return
        tk.Label(self.list_area,
                 text="연결한 순서대로 찾습니다 — 같은 이름의 그림이 여러 폴더에 "
                      "있으면 위쪽 폴더가 이깁니다.",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED,
                 wraplength=LIST_W_PX - 20, justify="left").pack(
                 anchor="w", pady=(2, 6))
        for i, f in enumerate(folders):
            row = tk.Frame(self.list_area, bg=ROWBG,
                           highlightbackground=BORDER, highlightthickness=1)
            row.pack(fill="x", pady=2)
            info = tk.Frame(row, bg=ROWBG, padx=10, pady=6)
            info.pack(side="left", fill="both", expand=True)
            name = pathlib.Path(f["path"]).name or f["path"]
            tk.Label(info, text=f"{i + 1}. {name}",
                     font=(FONT, theme.fs(FS["body"]), "bold"), bg=ROWBG,
                     fg=TEXT, anchor="w").pack(anchor="w")
            detail = (f"그림 {f['count']}장" if f["exists"]
                      else "⚠ 폴더를 찾을 수 없습니다 (옮겼거나 지워짐)")
            tk.Label(info, text=f"{detail}   ·   {f['path']}",
                     font=(FONT, theme.fs(FS["sub"])), bg=ROWBG,
                     fg=MUTED if f["exists"] else "#9b1c1c",
                     anchor="w").pack(anchor="w")
            RoundButton(row, text="연결 해제",
                        command=lambda p=f["path"]: self._unlink_photo_dir(p),
                        bg=SOFT, fg=TEXT, radius=theme.RADIUS["ctl"], font=(FONT, theme.fs(FS["sub"])),
                        outline="", zone_bg=ROWBG).fit(pad_x=10, pad_y=4).pack(
                        side="right", padx=10)

    def _unlink_photo_dir(self, path):
        if not messagebox.askyesno(
                "연결 해제",
                f"이 폴더 연결을 해제할까요?\n{path}\n\n"
                "폴더와 그림 파일은 그대로 있습니다.", parent=self):
            return
        settings.remove_photo_dir(path)
        self._refresh("사진")
        self._notify()

    def _summary(self, cat, item):
        """행 요약 한 줄 — 라벨·분류는 다른 곳에서 보이므로 **내용만** 말한다."""
        if cat == "서식":
            text = ", ".join(f"{k}:{v}" for k, v in item["fields"].items())
        elif cat == "문자":
            # 제목이 내용이므로, 이름이 내용과 다를 때만 보탠다
            text = item["name"] if item["name"] not in item["text"] else ""
        else:
            slots = int(item.get("slot_count") or 0)
            head = library.get_preview(item).splitlines()
            parts = [f"빈칸 {slots}" if slots else ""]
            if head:
                parts.append(head[0])
            text = " · ".join(p for p in parts if p)
        if len(text) > SUMMARY_MAX:
            text = text[:SUMMARY_MAX] + "…"
        return text

    # ── 선택과 동작바 ────────────────────────────────
    def _select(self, sel):
        """행 선택 — 이전 행의 색을 되돌리고 새 행을 옅은 파랑으로."""
        old = self._sel
        if old and old.get("row"):
            try:
                self._tint_row(old["row"], ROWBG)
            except Exception:
                pass
        self._sel = sel
        if sel and sel.get("row"):
            self._tint_row(sel["row"], ACCENT_SOFT)
        if not hasattr(self, "sel_hint"):
            return
        if sel is None:
            self.sel_hint.config(text="항목을 누르면 아래 버튼으로 실행합니다")
        else:
            self.sel_hint.config(text=self._sel_hint_text(sel))
        # 내장 기호는 내 것이 아니라 고칠 수 없다 — 버튼을 흐리게 두는 대신
        # 눌렀을 때 이유를 말한다(_edit_selected). 여기서는 안내만 바꾼다.

    def _sel_hint_text(self, sel):
        r"""고른 것이 무엇이고 문서에서 어떻게 부르는지 — 한 줄로.

        특수기호는 격자로 보여 주므로 이름·라벨이 칸에 안 들어간다. 대신
        고르는 순간 여기서 '\원1\ 로 부릅니다' 를 말해 준다 (사용자 요청).
        """
        it = sel["item"]
        kind = sel.get("kind")
        name = it.get("name") or it.get("label") or ""
        label = it.get("label") or name
        if sel.get("cat") == "문자":
            text = (it.get("text") or "").replace("\n", " ")
            if len(text) > 20:
                text = text[:19] + "…"
            source = "내장" if kind == "builtin" else "내가 등록"
            return f"{text}   ·   문서에서  \\{label}\\   ·   {source}"
        if kind == "photo":
            return f"{name}   ·   문서에서  \\{label}\\"
        return name

    @staticmethod
    def _tint_row(row, bg):
        row.config(bg=bg)
        for w in row.winfo_children():
            w.config(bg=bg)
            for c in w.winfo_children():
                c.config(bg=bg)

    def _need_sel(self):
        if self._sel is None:
            messagebox.showinfo("선택 없음", "목록에서 항목을 먼저 눌러주세요.",
                                parent=self)
            return False
        return True

    def _act_selected(self):
        if not self._need_sel():
            return
        cat, item = self._sel["cat"], self._sel["item"]
        kind = self._sel["kind"]
        if not _ensure_hwp(self):
            return
        try:
            if kind == "builtin":
                hwp_engine.insert_plain(item["text"])
            elif kind == "photo":
                engine_library.insert_photo(item["path"])
            elif cat == "서식":
                if not hwp_engine.has_selection():
                    messagebox.showwarning("선택 없음",
                        "서식을 입힐 글자를 한글에서 먼저 선택해주세요.", parent=self)
                    return
                engine_library.apply_charshape_delta(item["fields"])
            elif cat == "문자":
                hwp_engine.insert_plain(item["text"])
            elif cat == "양식":
                # 물감 설정의 [열기] 도 손으로 채워 쓰는 경우 — 자리표시는 지운다
                engine_library.open_form(library.template_path(item),
                                         strip_markers=True)
            else:
                engine_library.insert_fragment(library.template_path(item))
        except Exception as e:
            messagebox.showerror("오류", f"{type(e).__name__}: {e}", parent=self)

    _READONLY_WHY = ("내장 기호는 프로그램에 들어 있는 것이라 고치거나 지울 수 "
                     "없습니다.\n내 것으로 만들고 싶으면 '+ 새 특수기호/문구 "
                     "추가'로 등록하세요.")

    def _edit_selected(self):
        if not self._need_sel():
            return
        if self._sel["kind"] != "item":
            messagebox.showinfo("수정 불가", self._readonly_msg(), parent=self)
            return
        cat, item = self._sel["cat"], self._sel["item"]
        # 템플릿은 두 갈래다 (사용자 결정 2026-07-26):
        #   이름·라벨 / 내용 고치기
        # 처음에는 '내용 수정'과 '양식(빈칸) 수정'을 나눴는데, 실제로 하는 일이
        # 똑같았다 — 둘 다 한글에 펼쳐 고치고 덮어쓰는 것이고, 빈칸 \ 도 그
        # 화면에서 함께 보인다. 갈래만 늘고 고르는 부담만 생겨 하나로 합쳤다.
        # 양식도 내용을 고칠 수 있어야 한다 (사용자 지적 2026-07-27) —
        # 여태 양식은 이름·라벨만 고칠 수 있고 안에 든 내용은 손댈 수 없었다.
        if cat in ("템플릿", "양식"):
            (Popover(self, self.act_edit)
             .add("이름·라벨 수정", lambda: self._edit(cat, item))
             .add("내용 고치기  (한글에 펼쳐서 수정)",
                  lambda: edit_content(self, cat, item))
             .show())
            return
        self._edit(cat, item)

    def _del_selected(self):
        if not self._need_sel():
            return
        if self._sel["kind"] != "item":
            messagebox.showinfo("삭제 불가", self._readonly_msg(), parent=self)
            return
        self._delete(self._sel["cat"], self._sel["item"])

    def _readonly_msg(self):
        if self._sel and self._sel.get("kind") == "photo":
            return ("사진은 폴더의 파일이라 여기서 고칠 수 없습니다.\n"
                    "파일 이름을 바꾸면 부르는 이름(\\파일이름\\)도 바뀝니다.")
        return self._READONLY_WHY

    # ── 템플릿·양식 추가 동작 (⋯) ────────────────────
    def _more_menu(self):
        if not self._need_sel():
            return
        cat = self._sel["cat"]
        pop = Popover(self, self.act_more)
        if cat in ("템플릿", "양식"):
            pop.add("내용 고치기  (한글에 펼쳐서 수정)",
                    lambda: edit_content(self, cat, self._sel["item"]))
            pop.separator()
        pop.add("AI 프롬프트 복사  (빈칸을 AI 에게 채우게)",
                self._copy_ai_prompt)
        pop.show()

    # 고치는 동안 한글 문서 맨 위에 붙는 안내 (mode 별로 말이 다르다)
    # 고치는 동안 한글 문서 맨 위에 붙는 안내 (저장할 때 자동으로 빠진다)
    _EDIT_NOTE = [
        "이 문서를 원하는 대로 고치세요 — 글자·표·빈칸 모두 여기서 고칩니다.",
        "역슬래시(\\) 하나가 나중에 내용 한 줄이 들어갈 '빈칸'입니다.",
        "(평소 문서에 넣을 때는 안 보이고, 채울 내용으로 바뀝니다)",
        "빈칸을 늘리려면 \\ 를 더 넣고, 없애려면 지우면 됩니다.",
        "채워지는 순서는 위에서 아래, 왼쪽에서 오른쪽입니다.",
        "다 고쳤으면 HwpPalette 의 [이 내용으로 덮어쓰기]를 누르세요.",
        "(이 안내 줄들은 저장할 때 자동으로 빠집니다)",
    ]

    def _extract_edit(self):
        r"""꺼내서 고치기 (기획 15번) — 실제 일은 모듈 함수 edit_content 가 한다.

        본체를 밖으로 뺀 이유(2026-07-27): 물감 창고에서도 같은 일을 해야 하는데,
        이 창의 메서드로 두면 창고가 관리 창을 띄워야만 쓸 수 있다.
        """
        edit_content(self, self._sel["cat"], self._sel["item"])

    def _copy_ai_prompt(self):
        r"""AI 프롬프트 복사 (기획 18번) — 양식 구조(표 포함)를 보여주고,
        답은 마크다운 변환이 이미 아는 문법으로 받게 하는 프롬프트."""
        item = self._sel["item"]
        if not _ensure_hwp(self):       # 구조를 읽으려면 한글이 필요하다
            return
        try:
            md, slots = form_markdown.build_structure_md(
                library.template_path(item))
        except Exception as e:
            applog.exc("양식 구조 읽기 실패", e)
            messagebox.showerror("구조 읽기 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            return
        if not slots:
            messagebox.showinfo(
                "빈칸 없음",
                "이 항목에는 빈칸(\\)이 없어 AI 가 채울 것이 없습니다.\n"
                "'꺼내서 고치기'로 빈칸 자리에 \\ 를 넣어두면 쓸 수 있습니다.",
                parent=self)
            return
        label = item.get("label") or item["name"]
        prompt = form_markdown.build_prompt(item["name"], label, md, slots)
        # Tk 클립보드가 아니라 윈도우 클립보드로 담는다 — Tk 로 담으면 그 뒤
        # 우리가 한글의 선택 내용을 읽지 못한다 (clipboard.py 머리말)
        clipboard.set_text(prompt, widget=self)
        messagebox.showinfo(
            "프롬프트 복사 완료",
            f"빈칸 {slots}개짜리 프롬프트를 복사했습니다.\n\n"
            "① ChatGPT·Claude 등에 붙여넣어 답을 받으세요\n"
            "② 답 전체를 복사해 한글 문서에 붙여넣으세요\n"
            "③ 그 부분을 드래그로 선택 → Ctrl+Alt+T\n"
            "→ 진짜 양식이 삽입되면서 빈칸이 채워집니다", parent=self)

    # ── 서식 ─────────────────────────────────────────
    def _add_style(self):
        if not _ensure_hwp(self):
            return
        if not hwp_engine.has_selection():
            messagebox.showwarning("선택 없음",
                "한글에서 저장할 서식이 적용된 글자를 먼저 선택해주세요.", parent=self)
            return
        dlg = StyleFieldDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        delta = engine_library.capture_charshape(dlg.result)
        if not delta:
            messagebox.showwarning("캡처 실패", "선택한 항목을 읽지 못했습니다.", parent=self)
            return
        meta = MetaDialog(self, title="서식 등록")
        self.wait_window(meta)
        if not meta.result:
            return
        name, label, tags = meta.result
        library.add_style(name, delta, label=label, tags=tags)
        self._refresh("서식")
        self._notify()

    # ── 문자 ─────────────────────────────────────────
    def _read_selected_text(self):
        return hwp_engine.read_selection_text()

    def _add_char(self):
        if not _ensure_hwp(self):
            return
        prefill = self._read_selected_text() if hwp_engine.has_selection() else ""
        dlg = TextInputDialog(self, prefill)
        self.wait_window(dlg)
        if dlg.result is None or not dlg.result.strip():
            return
        content = dlg.result
        default_name = content.strip().replace("\n", " ")[:AUTO_NAME_MAX]
        meta = MetaDialog(self, title="문자/문구 등록", name=default_name)
        self.wait_window(meta)
        if not meta.result:
            return
        name, label, tags = meta.result
        library.add_char(name, content, label=label, tags=tags)
        self._refresh("문자")
        self._notify()

    # ── 템플릿 ───────────────────────────────────────
    def _add_template(self):
        # 등록 절차는 환경설정 창과 공유한다 (capture_template_dialog)
        if capture_template_dialog(self) is None:
            return
        self._refresh("템플릿")
        self._notify()

    # ── 양식 ─────────────────────────────────────────
    def _add_form(self):
        """hwp 파일을 통째로 양식으로 등록 (한글을 안 열어도 됨)."""
        path = filedialog.askopenfilename(
            title="양식으로 등록할 한글 파일 선택",
            filetypes=[("한글 파일", "*.hwp *.hwpx"), ("모든 파일", "*.*")],
            parent=self)
        if not path:
            return
        # 빈칸(\) 개수 세기 — 한글이 **이미 연결돼 있을 때만** 시도한다.
        #
        # 여기서 connect() 를 부르면 안 된다 (실측 2026-07-24): 한글이 꺼져 있으면
        # 실행·연결을 기다리는 동안 Tkinter 단일 스레드가 통째로 묶여 **창이 멈춘
        # 것처럼** 보인다. "양식 추가를 눌러도 무반응"의 원인이 이것이었다.
        # 빈칸 개수는 안내용일 뿐 등록에 필수가 아니므로, 못 세면 그냥 넘어간다.
        # (예전엔 except: pass 라 실패해도 아무 단서가 안 남았다 → 반드시 기록한다)
        slot_count = None               # None = 못 셈, 0 = 세어 봤더니 없음
        slot_names = []
        if hwp_engine.is_connected():
            try:
                tokens = engine_library.slot_tokens_in_file(path)
                slot_names = tokens
                slot_count = len(tokens)
            except Exception as e:
                applog.exc(f"양식 등록: 빈칸 세기 실패 — {path}", e)
        if slot_count:
            note = (f"자리 {slot_count}개 발견 — \\라벨\\ 변환 시 아랫줄 "
                    f"{slot_count}줄이 순서대로 채워집니다. (비울 칸엔 '-')")
            names = [t for t in slot_names if t]
            if names:
                note += ("\n칸 이름: " + " · ".join(dict.fromkeys(names))
                         + " — 누르면 채우기 표가 뜹니다.")
        elif slot_count == 0:
            note = ("빈칸(\\)이 없습니다. 양식에 \\ 를 넣어두면 변환 때 채울 수 있습니다.\n"
                    "지금 등록해도 '새 문서로 열기'는 됩니다.")
        else:
            note = ("한글에 연결돼 있지 않아 빈칸(\\) 수를 세지 못했습니다.\n"
                    "등록과 '새 문서로 열기'는 그대로 됩니다. 빈칸 채우기까지 쓰려면\n"
                    "한글을 켠 뒤 다시 등록해주세요.")
        default_name = pathlib.Path(path).stem
        meta = MetaDialog(self, title="양식 등록", name=default_name,
                          extra_note=note)
        self.wait_window(meta)
        if not meta.result:
            return
        name, label, tags = meta.result
        try:
            item_id = library.add_form_from_file(name, path, label=label,
                                                 tags=tags,
                                                 slot_count=slot_count,
                                                 slot_names=slot_names)
        except Exception as e:
            messagebox.showerror("등록 실패", str(e), parent=self)
            return
        make_clean_preview("양식", item_id)
        self._refresh("양식")
        self._notify()

    # ── 공통: 삭제 (적용/삽입은 하단 동작바 _act_selected 가 맡는다) ──
    def _delete(self, cat, item):
        name = item["name"]
        used = library.count_palette_refs(cat, item["id"])
        msg = f"'{name}' 항목을 삭제할까요?"
        if used:
            msg += (f"\n\n⚠ 팔레트 {used}곳에서 사용 중입니다."
                    "\n   그 블럭들도 함께 삭제됩니다.")
        if messagebox.askyesno("삭제", msg, parent=self):
            library.delete_item(cat, item["id"])
            self._refresh(cat)
            self._notify()

    # ── 사진 폴더 (\사진이름\ 변환) — '사진' 탭에서만 보인다 ──
    def _pick_photo_dir(self):
        """폴더를 **추가**한다 (여러 개 연결 가능 — 해제는 각 줄의 버튼)."""
        dirs = settings.get_photo_dirs()
        path = filedialog.askdirectory(
            parent=self, title="연결할 사진 폴더 선택",
            initialdir=dirs[-1] if dirs else None)
        if not path:
            return
        if not settings.add_photo_dir(path):
            messagebox.showinfo("이미 연결됨", "그 폴더는 이미 연결돼 있습니다.",
                                parent=self)
            return
        self._refresh("사진")
        self._notify()

    def _edit(self, cat, item):
        """등록된 항목의 이름·라벨·태그 수정 (id 유지 → 팔레트 연결 안 깨짐)."""
        meta = MetaDialog(self, title=f"{CAT_LABEL.get(cat, cat)} 수정",
                          name=item["name"],
                          label=item.get("label", ""), exclude_id=item["id"])
        try:
            meta.tags_var.set(" ".join(item.get("tags") or []))
        except Exception:
            pass
        self.wait_window(meta)
        if not meta.result:
            return
        name, label, tags = meta.result
        # 이름만 고쳤을 때 라벨이 옛 이름으로 남는 것을 막는다 (라벨 칸이 '자세히'
        # 안에 접혀 있어 사용자 눈에 안 보인다). 규칙은 resolve_edited_label 참고.
        label = library.resolve_edited_label(
            item["name"], item.get("label", ""), name, label)
        library.update_item(cat, item["id"], name=name, label=label, tags=tags)
        self._refresh(cat)
        self._notify()

    def _notify(self):
        if self.on_saved:
            self.on_saved()


class _RecaptureCoach(tk.Toplevel):
    r"""'꺼내서 고치기'의 안내 창 — 한글에서 고치는 동안 옆에 떠 있는다.

    modal(grab)이 아니다 — 사용자는 이 창을 둔 채 한글에서 자유롭게 편집한다.
    [덮어쓰기]는 **지금 한글에 떠 있는 문서 전체**를 다시 캡처해 같은 항목에
    저장한다. 문서 전체 = 아까 펼쳐 준 새 탭의 내용이라는 전제인데, 사용자가
    다른 문서로 갈아탔을 수도 있으므로 문구로 분명히 말해 둔다.
    """

    def __init__(self, master, item, cat="템플릿", on_saved=None,
                 master_was_topmost=False, session=None,
                 windows_before=None):
        super().__init__(master)
        self._manager = master
        self._item = item
        self._cat = cat
        self._on_saved = on_saved
        self._master_was_topmost = master_was_topmost
        # 펼쳐 준 문서를 그대로 들고 있는다 — 저장·닫기가 '활성 문서'라는
        # 가정에 기대지 않게 (engine_library.EditSession 머리말 참고)
        self._session = session
        # 고치기 **전에** 보이던 한글 창 핸들 — 끝난 뒤 '우리가 띄운 창'인지
        # 가리는 데 쓴다 (edit_content 머리말 참고)
        self._windows_before = windows_before or set()
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.bind("<Escape>", lambda e: self._close())
        # X 로 닫아도 topmost 를 되돌려야 한다 — 기본 동작(그냥 destroy)에
        # 맡기면 master 가 계속 꺼진 채로 남는다.
        self.protocol("WM_DELETE_WINDOW", self._close)
        tk.Label(self, text=f"'{item['name']}' 고치는 중",
                 font=(FONT, theme.fs(11), "bold"), bg=BG, fg=TEXT).pack(
                 anchor="w", padx=16, pady=(14, 2))
        tk.Label(self,
                 text=f"한글에 {cat}을(를) 펼쳐 두었습니다 "
                      "(자세한 안내는 그 문서 맨 위에 있습니다).\n"
                      "고친 뒤 아래 [이 내용으로 덮어쓰기]를 누르세요.\n"
                      f"지금 한글에 보이는 문서 전체가 이 {cat}으로 저장되고,\n"
                      "고치던 탭은 저장이 끝나면 알아서 닫힙니다.",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED,
                 justify="left").pack(anchor="w", padx=16, pady=(0, 10))
        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "이 내용으로 덮어쓰기", self._overwrite,
                    primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self._close).pack(side="right", padx=(0, 6))
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+40}+{master.winfo_rooty()+80}")

    def _close(self):
        """되돌리고 닫는다 — 취소·Esc·X·덮어쓰기 완료가 전부 이 길을 거친다."""
        # 고치려고 **우리가 띄우거나 켠** 한글 창이면 원래대로 되돌린다
        # (사용자 지적 2026-07-27: "수정하고 닫은 다음에 빈 문서 하나가
        # 남는다", "한글 창이 없는 상태에서도 안 사라진다").
        # 고치기 전부터 보이던 창이면 사용자 것이라 손대지 않고, 사용자가
        # 쓰던 문서가 하나라도 있으면 hide_window_if_idle 이 알아서 비껴간다.
        try:
            engine_library.hide_window_if_ours(self._windows_before)
        except Exception as e:
            applog.exc("한글 창 되돌리기 실패 (빈 창이 남을 수 있음)", e)
        if self._master_was_topmost:
            try:
                self._manager.attributes("-topmost", True)
            except Exception:
                pass
        self.destroy()

    def _overwrite(self):
        if not _ensure_hwp(self):
            return
        try:
            if self._session is not None:
                # 고치던 그 탭을 확실히 활성으로 — 사용자가 다른 탭으로
                # 갈아탔더라도 엉뚱한 문서를 저장하지 않는다
                self._session.activate()
            engine_library.strip_edit_note()   # 안내문은 저장물에 넣지 않는다
            # 템플릿도 양식과 **같은 길**로 저장한다 (2026-07-27). 예전에는
            # 템플릿만 select_all→복사→새 탭에 붙여넣기→저장(capture_fragment)
            # 이었는데, 편집 탭이 이미 저장할 내용 그대로라 임시 탭이 헛돌았다.
            # 그 임시 탭의 개폐가 "창이 여러 개 닫히는 모션"의 절반이었다.
            ok = library.replace_template_fragment(
                self._item["id"], engine_library.save_active_as,
                category=self._cat)
        except Exception as e:
            applog.exc("템플릿 덮어쓰기 실패", e)
            messagebox.showerror("덮어쓰기 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            return
        if not ok:
            messagebox.showerror("덮어쓰기 실패",
                                 "이 템플릿이 라이브러리에서 사라졌습니다.",
                                 parent=self)
            self._close()
            return
        # 미리보기 뽑기와 탭 닫기를 **한 탭 안에서** 끝낸다 (사용자 결정
        # 2026-07-26: 고치던 탭은 프로그램이 닫는다 — 남아 있으면 "이건 저장된
        # 건가?" 하고 헷갈린다).
        closed = True
        if self._session is not None:
            try:
                import preview as _preview
                _preview.cached_path(self._item["id"]).unlink(missing_ok=True)
            except Exception as e:
                applog.exc("옛 미리보기 그림 지우기 실패 (무해)", e)
            try:
                _made, closed = engine_library.finish_edit_session(
                    self._session, self._item["id"])
            except Exception as e:
                applog.exc("고치기 마무리 실패", e)
                closed = False
        else:
            make_clean_preview(self._cat, self._item["id"])
            closed = engine_library.close_active_doc()
        self._close()
        # 이 창은 관리 창의 자식이라, 여기가 살아 있으면 관리 창도 살아 있다
        try:
            self._manager._refresh(self._cat)
            self._manager._notify()
        except Exception:
            pass                      # 창고에서 부른 경우엔 관리 창이 없다
        if self._on_saved:
            try:
                self._on_saved()
            except Exception as e:
                applog.exc("고치기 후 새로 그리기 실패", e)
        tail = ("" if closed else
                "\n(고치던 한글 탭은 직접 닫아 주세요)")
        messagebox.showinfo("덮어쓰기 완료",
                            f"'{self._item['name']}' 을(를) 새 내용으로 "
                            f"저장했습니다.{tail}",
                            parent=self._manager)


class ShareDialog(tk.Toplevel):
    r"""물감 나누기 — 메인 창 설정(⚙) 메뉴에서 연다 (사용자 결정
    2026-07-25: "내가 만든 탭을 남에게 주는 일"이라 물감 설정 화면이 아니라
    설정의 하위 기능으로 뺐다).

    **먼저 무엇을 보낼지 고른다** (사용자 결정 2026-07-27). 예전에는 물감
    내보내기만 이 창에 있고 팔레트는 팔레트 설정의 탭 우클릭에 숨어 있어서,
    그런 기능이 있다는 것 자체를 모르면 못 찾았다. 두 갈래를 나란히 두면
    "이 프로그램은 물감도 팔레트도 보낼 수 있다"가 화면에서 바로 읽힌다.

    받는 쪽 입구는 여전히 **하나**다 — 받은 파일이 어느 쪽인지는 프로그램이
    열어 보고 판단한다.
    """

    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.on_saved = on_saved
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.bind("<Escape>", lambda e: self.destroy())      # Esc 로 닫기
        tk.Label(self, text="물감 나누기",
                 font=(FONT, theme.fs(FS["title"]), "bold"), bg=BG, fg=TEXT).pack(
                 anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="내가 만든 것을 파일 하나로 묶어 동료와 주고받습니다.",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED,
                 justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        tk.Label(self, text="무엇을 보낼까요?", font=(FONT, theme.fs(FS["body"]), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(0, 4))
        self._card("물감 보내기",
                   "등록한 서식·기호·템플릿·양식 중 골라서", self._send_paints)
        self._card("팔레트 보내기",
                   "팔레트 하나를 통째로 (쓰이는 물감도 함께)",
                   self._send_palette)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=16, pady=12)

        row2 = tk.Frame(self, bg=BG, padx=16)
        row2.pack(fill="x", pady=(0, 14))
        # 입구는 하나 — 팔레트가 들었든 물감만 들었든 같은 버튼이다.
        # 받는 사람은 파일이 어느 쪽인지 모르는 게 정상이라, 열어 보고
        # 프로그램이 판단한다 (사용자 결정 2026-07-26).
        tk.Label(row2, text="받은 것을", font=(FONT, theme.fs(FS["body"])), bg=BG,
                 fg=TEXT).pack(side="left")
        _dialog_btn(row2, "불러오기…", self._import).pack(side="left",
                                                        padx=(8, 0))
        tk.Label(row2, text="(내 물감·팔레트는 덮어쓰지 않습니다)",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED).pack(
                 side="left", padx=(8, 0))

        self.update_idletasks()
        screens.place_beside(self, master)

    def _card(self, title, desc, command):
        """고르는 카드 한 장 — 튜토리얼 목록과 같은 생김새로 맞춘다.

        **글자만 쓴다** (CLAUDE.md 디자인: AI티 금지 — emoji 남발 금지).
        아이콘을 붙이면 두 갈래가 장식으로 구분되는데, 정작 구분해야 할 것은
        '무엇이 담기는가'라 설명 한 줄이 훨씬 정확하다.
        """
        row = tk.Frame(self, bg=ROWBG, highlightbackground=BORDER,
                       highlightthickness=1)
        row.pack(fill="x", padx=16, pady=3)
        info = tk.Frame(row, bg=ROWBG, padx=12, pady=8)
        info.pack(side="left", fill="both", expand=True)
        tk.Label(info, text=title, font=(FONT, theme.fs(FS["head"]), "bold"),
                 bg=ROWBG, fg=TEXT, anchor="w").pack(anchor="w")
        tk.Label(info, text=desc, font=(FONT, theme.fs(FS["sub"])), bg=ROWBG,
                 fg=MUTED, anchor="w", justify="left").pack(anchor="w")
        for wdg in (row, info, *info.winfo_children()):
            wdg.config(cursor="hand2")
            wdg.bind("<Button-1>", lambda e: command())
            wdg.bind("<Enter>", lambda e, r=row: self._tint(r, ACCENT_SOFT))
            wdg.bind("<Leave>", lambda e, r=row: self._tint(r, ROWBG))

    @staticmethod
    def _tint(row, bg):
        row.config(bg=bg)
        for w in row.winfo_children():
            w.config(bg=bg)
            for c in w.winfo_children():
                c.config(bg=bg)

    # ── 보내기 두 갈래 ───────────────────────────────
    def _send_paints(self):
        """물감 보내기 — 항목을 골라서 (창고는 목록이라 일부만 빼도 안 깨진다)."""
        dlg = PaintPickDialog(self)
        self.wait_window(dlg)

    def _send_palette(self):
        """팔레트 보내기 — 통째로 (배치가 곧 값이라 쪼개면 뜻이 없다)."""
        dlg = PalettePickDialog(self)
        self.wait_window(dlg)

    def _import(self):
        r"""불러오기 — **입구는 하나** (사용자 결정 2026-07-26).

        팔레트가 든 파일인지 물감만 든 파일인지는 받는 사람이 알 수 없다.
        파일을 열어 프로그램이 판단하고, **넣기 전에 무엇이 들어오는지 보여준다.**
        예전에는 넣은 뒤에 "이름이 겹쳐 바꿨습니다"라고 사후 통보했다 —
        남의 파일이 내 창고에 섞이는 일이라 순서가 반대였다.
        """
        path = filedialog.askopenfilename(
            parent=self, title="불러오기",
            filetypes=[("HwpPalette 물감·팔레트 파일", f"*{chip.CHIP_EXT} *.zip"),
                       ("모든 파일", "*.*")])
        if not path:
            return
        try:
            info = chip.peek(path)
        except Exception as e:
            applog.exc(f"파일을 열지 못했습니다 ({path})", e)
            messagebox.showerror(
                "열 수 없는 파일",
                f"이 파일은 HwpPalette 의 물감·팔레트 파일이 아닌 것 같습니다.\n\n"
                f"{type(e).__name__}: {e}", parent=self)
            return

        dlg = ChipInstallDialog(self, info, pathlib.Path(path).name)
        self.wait_window(dlg)
        if not dlg.ok:
            return
        try:
            r = chip.install(path)
        except Exception as e:
            applog.exc(f"불러오기 실패 ({path})", e)
            messagebox.showerror("등록 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            return

        lines = [f"물감 {r['added']}개를 등록했습니다. (기존 물감은 그대로입니다)"]
        if r["reused"]:
            lines.append(f"이미 갖고 있던 {r['reused']}개는 다시 만들지 "
                         "않고 그대로 씁니다.")
        if r["tab_name"]:
            lines.append(f"\n팔레트 '{r['tab_name']}' 이(가) 더해졌습니다.")
            if r["lost"]:
                lines.append(f"(버튼 {r['lost']}개는 가리킬 물감이 없어 "
                             "눌러도 동작하지 않습니다)")
        if r["renamed"]:
            lines.append("\n이름이 겹쳐 바꾼 물감:")
            lines += [f"  {a} → {b}" for a, b in r["renamed"][:6]]
        if r["relabeled"]:
            lines.append("\n라벨이 겹쳐 바꾼 물감:")
            lines += [f"  \\{a}\\ → \\{b}\\" for a, b in r["relabeled"][:6]]
            lines.append("(라벨을 그대로 두면 마크다운 변환에서 호출되지 않습니다)")
        lines.append("\n마음에 안 들면 ⚙ → 물감 설정에서 지우거나, "
                     "직전 상태로 되돌릴 수 있습니다.")
        messagebox.showinfo("등록 완료", "\n".join(lines), parent=self)
        if self.on_saved:
            self.on_saved()


class ChipInstallDialog(tk.Toplevel):
    r"""등록 전 미리보기 — 무엇이 들어오고 무엇과 겹치는지 먼저 보여준다.

    팔레트 배치를 그림으로 보여주는 것도 생각했지만, 1단계에서는 **버튼 이름
    목록**으로 둔다(사용자 결정 2026-07-26) — 격자를 그리는 코드를 미리보기용
    으로 한 벌 더 만들 값이 지금은 크다. 필요해지면 그때 올린다.
    """

    def __init__(self, master, info, filename):
        super().__init__(master)
        self.ok = False
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.bind("<Escape>", lambda e: self.destroy())

        tab = info.get("tab")
        kind = "팔레트" if tab else "물감"
        tk.Label(self, text=f"{kind} 등록", font=(FONT, theme.fs(FS["title"]), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text=info["name"], font=(FONT, theme.fs(FS["head"]), "bold"),
                 bg=BG, fg=ACCENT).pack(anchor="w", padx=16)
        sub = " · ".join(x for x in (info.get("author"), info.get("made_with"),
                                     filename) if x)
        tk.Label(self, text=sub, font=(FONT, theme.fs(FS["caption"])), bg=BG, fg=MUTED,
                 wraplength=380, justify="left").pack(anchor="w", padx=16)
        if info.get("note"):
            tk.Label(self, text=f"“{info['note']}”", font=(FONT, theme.fs(FS["sub"])),
                     bg=BG, fg=TEXT, wraplength=380, justify="left").pack(
                     anchor="w", padx=16, pady=(6, 0))

        box = tk.Frame(self, bg=ROWBG, highlightbackground=BORDER,
                       highlightthickness=1)
        box.pack(fill="x", padx=16, pady=(10, 4))
        inner = tk.Frame(box, bg=ROWBG, padx=12, pady=8)
        inner.pack(fill="x")

        if tab:
            names = [b.get("template") or b.get("form") or b.get("value")
                     or b.get("name") or "도구" for b in tab.get("blocks", [])]
            self._line(inner, "팔레트",
                       f"'{tab.get('name')}' 탭 — 버튼 {len(names)}개")
            self._line(inner, "", "  " + " · ".join(names[:8])
                       + (" …" if len(names) > 8 else ""), faint=True)
        counts = {}
        for rec in info["items"]:
            counts[rec.get("category", "?")] = counts.get(
                rec.get("category", "?"), 0) + 1
        self._line(inner, "물감",
                   " · ".join(f"{k} {v}개" for k, v in counts.items())
                   or "없음")

        warn = []
        c = info["conflicts"]
        if info.get("known"):
            warn.append(f"이미 갖고 있는 물감 {info['known']}개 "
                        "→ 다시 만들지 않고 그대로 씁니다")
        if c["names"]:
            warn.append(f"이름이 겹치는 물감 {len(c['names'])}개 "
                        "→ 번호를 붙입니다 (내 것은 그대로)")
        if c["labels"]:
            warn.append(f"라벨이 겹치는 물감 {len(c['labels'])}개 "
                        "→ 번호를 붙입니다")
        if c["tab"]:
            warn.append(f"'{c['tab']}' 팔레트가 이미 있습니다 "
                        "→ 새 이름으로 더합니다 (내 것은 그대로)")
        for w in warn:
            self._line(inner, "확인", w, warn=True)

        tk.Label(self, text="받은 물감은 태그 없이 들어오고, 어느 파일에서 "
                            "왔는지 꼬리표가 남습니다.\n"
                            "내 물감·팔레트는 덮어쓰지 않습니다.",
                 font=(FONT, theme.fs(FS["caption"])), bg=BG, fg=MUTED,
                 justify="left").pack(anchor="w", padx=16)

        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "등록", self._go, primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))

        self.update_idletasks()
        screens.place_beside(self, master)
        self.grab_set()
        ui_fx.attach_all(self)

    @staticmethod
    def _line(parent, head, text, faint=False, warn=False):
        row = tk.Frame(parent, bg=ROWBG)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=head, font=(FONT, theme.fs(FS["sub"]), "bold"), bg=ROWBG,
                 fg=MUTED, width=5, anchor="w").pack(side="left")
        tk.Label(row, text=text, font=(FONT, theme.fs(FS["sub"])), bg=ROWBG,
                 fg=(ACCENT if warn else MUTED if faint else TEXT),
                 anchor="w", justify="left", wraplength=330).pack(side="left")

    def _go(self):
        self.ok = True
        self.destroy()


class PaintPickDialog(tk.Toplevel):
    r"""물감 보내기 — 보낼 항목을 **골라서** 담는다 (사용자 결정 2026-07-27).

    예전에는 분류(서식/특수기호/템플릿/양식) 하나를 고르면 그 안이 통째로
    나갔다. 템플릿 11개 중 2개만 주고 싶어도 방법이 없었다.
    창고는 목록이라 일부만 빼도 아무것도 안 깨지므로, 골라 담는 것이 맞다.
    (팔레트는 반대다 — 배치가 곧 값이라 통째로만 나간다)
    """

    def __init__(self, master):
        super().__init__(master)
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.bind("<Escape>", lambda e: self.destroy())

        tk.Label(self, text="물감 보내기", font=(FONT, theme.fs(FS["title"]), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="보낼 것에 체크하세요. 태그는 함께 가지 않습니다 "
                            "(내 정리 습관이라 남에게는 뜻이 없습니다).",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED,
                 wraplength=380, justify="left").pack(anchor="w", padx=16,
                                                      pady=(0, 8))

        wrap = tk.Frame(self, bg=BG, padx=16)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                           height=int(280 * (theme.FONT_SCALE or 1)))
        sb = ttk.Scrollbar(wrap, orient="vertical",
                           style="App.Vertical.TScrollbar",
                           command=canvas.yview)
        body = tk.Frame(canvas, bg=BG)
        win = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(
                -1 if ev.delta > 0 else 1, "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # 사진은 로컬 폴더 경로라 남에게 못 보낸다 (파일이 아니라 '연결'이다)
        self.vars = []          # [(분류, 항목, BooleanVar), ...]
        for c in CATS:
            if c["key"] == "사진":
                continue
            items = library.list_items(c["key"])
            if not items:
                continue
            head = tk.Frame(body, bg=BG)
            head.pack(fill="x", pady=(8, 2))
            tk.Label(head, text=c["label"], font=(FONT, theme.fs(FS["body"]), "bold"),
                     bg=BG, fg=MUTED).pack(side="left")
            tk.Label(head, text=f"{len(items)}개", font=(FONT, theme.fs(FS["sub"])),
                     bg=BG, fg=MUTED).pack(side="left", padx=(6, 0))
            for it in items:
                v = tk.BooleanVar(value=False)
                self.vars.append((c["key"], it, v))
                tk.Checkbutton(
                    body, text=f"{it['name']}   \\{it.get('label') or it['name']}\\",
                    variable=v, font=(FONT, theme.fs(FS["body"])), bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, anchor="w", cursor="hand2").pack(
                    anchor="w", fill="x")

        if not self.vars:
            tk.Label(body, text="아직 등록한 물감이 없습니다.",
                     font=(FONT, theme.fs(FS["body"])), bg=BG, fg=MUTED).pack(
                     anchor="w", pady=10)

        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "내보내기…", self._export, primary=True).pack(
            side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))
        _dialog_btn(foot, "모두 선택", lambda: self._all(True)).pack(side="left")
        _dialog_btn(foot, "모두 해제", lambda: self._all(False)).pack(
            side="left", padx=(6, 0))

        self.update_idletasks()
        screens.place_beside(self, master)
        self.grab_set()
        ui_fx.attach_all(self)

    def _all(self, on):
        for _cat, _it, v in self.vars:
            v.set(on)

    def _export(self):
        pairs = [(cat, it) for cat, it, v in self.vars if v.get()]
        if not pairs:
            messagebox.showwarning("고른 것이 없습니다",
                                   "보낼 물감에 하나 이상 체크해주세요.",
                                   parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="물감 내보내기",
            defaultextension=chip.CHIP_EXT,
            initialfile=f"내 물감{chip.CHIP_EXT}",
            filetypes=[("HwpPalette 물감·팔레트 파일", f"*{chip.CHIP_EXT}")])
        if not path:
            return
        name = pathlib.Path(path).stem
        note = simpledialog.askstring(
            "설명 (없어도 됩니다)",
            "받는 사람에게 한 줄로 알려줄 말:", parent=self) or ""
        try:
            r = chip.export_items(pairs, path, name=name, note=note)
        except Exception as e:
            applog.exc("물감 내보내기 실패", e)
            messagebox.showerror("내보내기 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            return
        skipped = len(pairs) - r["items"]
        msg = (f"물감 {r['items']}개를 내보냈습니다.\n"
               f"  {pathlib.Path(path).name}\n\n"
               "받는 사람은 ⚙ → 물감 나누기 → [불러오기] 로 등록합니다.")
        if skipped:
            msg += f"\n\n(조각 파일이 없어 {skipped}개는 빠졌습니다 — 기록 참고)"
        messagebox.showinfo("물감을 내보냈습니다", msg, parent=self)
        self.destroy()


class PalettePickDialog(tk.Toplevel):
    r"""팔레트 보내기 — 어느 팔레트를 보낼지 고른다.

    고른 뒤는 **통째로** 나간다. 담을 물감은 블럭의 ref 를 훑어 자동으로
    정해지므로 사용자가 따로 고를 것이 없다.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.bind("<Escape>", lambda e: self.destroy())

        tk.Label(self, text="팔레트 보내기", font=(FONT, theme.fs(FS["title"]), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="보낼 팔레트를 고르세요. 그 팔레트가 쓰는 물감도 "
                            "함께 담깁니다.",
                 font=(FONT, theme.fs(FS["sub"])), bg=BG, fg=MUTED,
                 wraplength=380, justify="left").pack(anchor="w", padx=16,
                                                      pady=(0, 8))

        tabs = [t for t in palette.load_tabs()
                if t.get("name") != palette.MAIN_TAB]
        if not tabs:
            tk.Label(self, text="보낼 팔레트가 없습니다.\n"
                                "팔레트 설정에서 먼저 만들어 주세요.",
                     font=(FONT, theme.fs(FS["body"])), bg=BG, fg=MUTED,
                     justify="left").pack(anchor="w", padx=16, pady=8)
        for tab in tabs:
            n = len(tab.get("blocks", []))
            uses = len(chip.required_items(tab))
            self._card(tab, f"버튼 {n}개 · 물감 {uses}개")

        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "닫기", self.destroy).pack(side="right")

        self.update_idletasks()
        screens.place_beside(self, master)
        self.grab_set()
        ui_fx.attach_all(self)

    def _card(self, tab, desc):
        row = tk.Frame(self, bg=ROWBG, highlightbackground=BORDER,
                       highlightthickness=1)
        row.pack(fill="x", padx=16, pady=3)
        info = tk.Frame(row, bg=ROWBG, padx=12, pady=8)
        info.pack(side="left", fill="both", expand=True)
        tk.Label(info, text=tab.get("name", "이름 없음"),
                 font=(FONT, theme.fs(FS["head"]), "bold"), bg=ROWBG, fg=TEXT,
                 anchor="w").pack(anchor="w")
        tk.Label(info, text=desc, font=(FONT, theme.fs(FS["sub"])), bg=ROWBG,
                 fg=MUTED, anchor="w").pack(anchor="w")
        for wdg in (row, info, *info.winfo_children()):
            wdg.config(cursor="hand2")
            wdg.bind("<Button-1>", lambda e, t=tab: self._pick(t))
            wdg.bind("<Enter>", lambda e, r=row: ShareDialog._tint(
                r, ACCENT_SOFT))
            wdg.bind("<Leave>", lambda e, r=row: ShareDialog._tint(r, ROWBG))

    def _pick(self, tab):
        self.grab_release()             # 파일 대화상자가 뒤에 깔리지 않게
        if export_palette_flow(self, tab):
            self.destroy()
        else:
            self.grab_set()


def export_palette_flow(parent, tab):
    r"""팔레트 하나를 파일로 내보내는 **공용 흐름**. 내보냈으면 True.

    두 곳에서 부른다 — '물감 나누기 → 팔레트 보내기' 와 팔레트 설정의 탭
    우클릭(지름길). 같은 일이라 한 곳에 둔다: 두 벌로 두면 한쪽만 고치는
    사고가 난다 (2026-07-27).
    """
    if not tab.get("blocks"):
        messagebox.showinfo("빈 팔레트", "이 팔레트에는 버튼이 없습니다.",
                            parent=parent)
        return False

    missing = chip.missing_refs(tab)
    if missing:
        # 지워진 물감을 가리키는 버튼은 내보낼 수 없다. 조용히 빼면
        # 받는 쪽에서 "왜 이 버튼만 안 되지"가 되므로 먼저 알린다.
        if not messagebox.askokcancel(
                "빠지는 버튼이 있습니다",
                "다음 버튼이 가리키는 물감이 라이브러리에 없어\n"
                "내보내지 않습니다:\n\n  "
                + "\n  ".join(missing[:8])
                + "\n\n그대로 내보낼까요?", parent=parent):
            return False

    items = chip.required_items(tab)
    path = filedialog.asksaveasfilename(
        parent=parent, title=f"'{tab['name']}' 팔레트 내보내기",
        defaultextension=chip.CHIP_EXT,
        initialfile=f"{tab['name']}{chip.CHIP_EXT}",
        filetypes=[("HwpPalette 물감·팔레트 파일", f"*{chip.CHIP_EXT}")])
    if not path:
        return False
    note = simpledialog.askstring(
        "설명 (없어도 됩니다)",
        "받는 사람에게 한 줄로 알려줄 말:", parent=parent) or ""
    try:
        r = chip.export_tab(tab, path, note=note)
    except Exception as ex:
        applog.exc(f"팔레트 내보내기 실패 ({tab['name']})", ex)
        messagebox.showerror("내보내기 실패", f"{type(ex).__name__}: {ex}",
                             parent=parent)
        return False
    messagebox.showinfo(
        "팔레트를 내보냈습니다",
        f"'{tab['name']}' 팔레트를 파일로 내보냈습니다.\n\n"
        f"  버튼 {r['blocks']}개 · 물감 {r['items']}개\n"
        f"  {pathlib.Path(path).name}\n\n"
        "받는 사람은 ⚙ → 물감 나누기 → [불러오기] 로 등록합니다.\n"
        "물감은 그 사람 창고에 들어가 다른 팔레트에서도 쓸 수 있습니다.",
        parent=parent)
    if items and not r["items"]:
        applog.warn("팔레트 내보내기: 담긴 물감이 없습니다")
    return True


# 양식을 고칠 때 문서 맨 위에 붙는 안내 (템플릿용과 말이 다르다 — 양식은
# 파일 통째라 '이 문서가 곧 양식'이고, 빈칸 대신 이름표를 설명해야 한다)
_FORM_EDIT_NOTE = [
    "이 문서가 곧 양식입니다 — 용지·여백·머리말까지 그대로 저장됩니다.",
    "채울 자리는 역슬래시(\\) 로 표시합니다.",
    "이름을 붙이면 채우기 표에 그 이름이 나옵니다 — 예: \\학년\\",
    "이름표는 값으로 통째로 바뀌므로, 단위 글자는 밖에 두세요 (\\월\\월).",
    "다 고쳤으면 HwpPalette 의 [이 내용으로 덮어쓰기]를 누르세요.",
    "(이 안내 줄들은 저장할 때 자동으로 빠집니다)",
]


def edit_item_dialog(master, cat, item, on_saved=None):
    r"""물감 '수정' — 이름 창을 띄우고, 그 안에서 내용까지 고칠 수 있게 한다.

    왜 이렇게 묶었나 (사용자 지적 2026-07-27): 버튼 이름이 '고치기' 하나였을 때
    **템플릿 자체를 고친다는 것인지 이름을 고친다는 것인지** 알 수 없었다.
    이제 입구는 '수정' 하나이고, 흔한 일(이름 바꾸기)이 먼저 보이며,
    내용은 그 창 안의 버튼으로 한 걸음 더 들어간다.
    """
    meta = MetaDialog(master, title=f"{CAT_LABEL.get(cat, cat)} 수정",
                      name=item["name"], label=item.get("label", ""),
                      exclude_id=item["id"])
    try:
        meta.tags_var.set(" ".join(item.get("tags") or []))
    except Exception:
        pass
    if cat in ("템플릿", "양식"):
        _dialog_btn(meta.foot, "내용 고치기…",
                    lambda: (meta.destroy(),
                             edit_content(master, cat, item, on_saved))
                    ).pack(side="left")
    master.wait_window(meta)
    if not meta.result:
        return
    name, label, tags = meta.result
    label = library.resolve_edited_label(
        item["name"], item.get("label", ""), name, label)
    library.update_item(cat, item["id"], name=name, label=label, tags=tags)
    if on_saved:
        on_saved()


def edit_content(master, cat, item, on_saved=None):
    r"""물감 내용을 한글에 펼쳐 고치게 한다 (템플릿·양식 공용, 2026-07-27).

    물감 설정 창 안에만 있던 '꺼내서 고치기'를 밖으로 뺐다 — 물감 창고에서도
    같은 일을 해야 하기 때문. 창고가 설정 메뉴의 물감 설정을 대신한다.

    템플릿은 새 탭에 펼치고(원본 잠금 회피), 양식은 사본을 연다
    (용지·여백·머리말이 내용의 일부라 insert 로는 안 따라온다).
    """
    # 한글에 **손대기 전에** 보이는 창 목록을 재 둔다 (사용자 지적 2026-07-27:
    # "한글 창이 없는 상태에서도 빈 창이 안 사라진다"). connect() 는 한글이
    # 없으면 새로 띄우는데, 그 창은 처음부터 보이는 상태라 연결 뒤에 재면
    # "원래 있던 창"으로 오인된다. 그래서 _ensure_hwp 보다 먼저 잰다.
    windows_before = hwp_engine.visible_window_handles()
    if not _ensure_hwp(master):
        return False
    # 화면 목록이 들고 있던 item 은 **옛 파일명**일 수 있다 (2026-07-27).
    # 덮어쓰기는 조각을 새 uuid 파일로 갈아치우고 옛 파일을 지우므로,
    # 갱신 전 목록으로 펼치면 이미 없는 파일을 가리켜 빈 탭이 떴다.
    item = library.find_by_id(cat, item.get("id")) or item
    try:
        if cat == "양식":
            session = engine_library.open_form_copy(
                library.template_path(item), _FORM_EDIT_NOTE)
        else:
            session = engine_library.open_template_copy(
                library.template_path(item), LibraryManager._EDIT_NOTE)
    except Exception as e:
        applog.exc(f"{cat} 꺼내기 실패", e)
        messagebox.showerror("꺼내기 실패", f"{type(e).__name__}: {e}",
                             parent=master)
        return False
    # 고칠 문서를 **눈앞에** 띄운다 — 우리 창 뒤에 있으면 무엇을 고치라는
    # 것인지 모른다 (사용자 지적 2026-07-27).
    #
    # 실측(2026-07-27): "한글 창을 열면 한글창이 나오지 않는다" — bring_to_front
    # 로 한글에 초점을 줘도, master(물감·팔레트 설정 창)가 **-topmost** 라서
    # 한글 창이 그 뒤에 완전히 가려졌다. 윈도우의 topmost 는 '초점'과 무관하게
    # z-순서를 최상단에 고정하는 속성이라, 초점만 옮겨선 그 뒤에서 못 나온다.
    # 게다가 이 창은 최근 개편으로(창고·미리보기 확장) 화면 대부분을 덮을 만큼
    # 넓어져 이 문제가 더 두드러진다. 편집하는 동안만 master 의 topmost 를 끄고,
    # 안내 창이 닫힐 때 되돌린다 — _RecaptureCoach 자체는 계속 topmost 로 둔다
    # (작아서 화면을 덮지 않고, 편집 중 돌아올 자리를 보여줘야 한다).
    master_was_topmost = _pop_topmost(master)
    hwp_engine.bring_to_front()
    _RecaptureCoach(master, item, cat=cat, on_saved=on_saved,
                    master_was_topmost=master_was_topmost, session=session,
                    windows_before=windows_before)
    return True


def _pop_topmost(win):
    """창의 topmost 를 끄고, 원래 켜져 있었는지를 돌려준다 (되돌릴 때 씀)."""
    try:
        was = bool(win.attributes("-topmost"))
    except Exception:
        return False
    if was:
        try:
            win.attributes("-topmost", False)
        except Exception:
            pass
    return was


def open_share(master, on_saved=None):
    """물감 나누기 창 — 메인 창 설정(⚙) 메뉴가 부른다."""
    return ShareDialog(master, on_saved=on_saved)


def open_manager(master, on_saved=None, cat=None):
    """라이브러리 창을 연다. cat 을 주면 그 탭으로 바로 연다 ('내장' 등)."""
    win = LibraryManager(master, on_saved=on_saved)
    ui_fx.attach_all(win)              # 추가 버튼 등 tk.Button 에 호버 보간
    if cat in TABS and cat != win.current_cat:
        try:
            # _refresh 가 아니라 _switch_tab — 탭 버튼 색·설명·동작바까지 함께
            win._switch_tab(cat)
        except Exception as e:
            applog.exc(f"라이브러리 '{cat}' 탭으로 열기 실패 — 기본 탭으로 엽니다", e)
    return win
