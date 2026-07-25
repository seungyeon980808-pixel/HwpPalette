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
  · 내보내기/가져오기 → 메인 창 설정(⚙) 메뉴의 공유 대화상자로 (open_share).
  · 탭의 저장 키(key)와 표시 이름(label)을 분리 — '문자'는 화면에서만
    '특수기호'로 보인다. 저장 데이터(library.json)의 키는 영원히 그대로다.
"""

import pathlib
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import applog
import hwp_engine
import engine_library
import library
import builtin_chars
import settings

import appinfo
import form_markdown               # 양식→AI 프롬프트 (기획 18번)
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

# 탭 정의 — key 는 저장 데이터(library.json)의 키라 **절대 불변**,
# label 만 화면에 보인다. '문자'→'특수기호' 개명이 표시만 바뀌는 이유다.
CATS = (
    {"key": "서식",   "label": "서식"},
    {"key": "문자",   "label": "특수기호"},
    {"key": "템플릿", "label": "템플릿"},
    {"key": "양식",   "label": "양식"},
    {"key": "사진",   "label": "사진"},
    {"key": "내장",   "label": "내장"},
)
CAT_LABEL = {c["key"]: c["label"] for c in CATS}
TABS = tuple(c["key"] for c in CATS)    # open_manager(cat=...) 검사용

TAB_DESC = {
    "서식": "문서에서 캡처한 글자 모양(굵기·색상·자간 등) 일부만 저장해 "
            "아무 글자에나 입히는 기능 "
            "— 팔레트의 '서식 조합'은 캡처 대신 목록에서 직접 고르는 쪽",
    "문자": "특수기호나 자주 쓰는 문구를 저장해 바로 삽입하는 기능",
    "템플릿": "표·결재란처럼 문서 '일부'를 저장해 커서 자리에 꽂아 넣는 기능",
    "양식": "hwp 파일 '전체'를 저장해 새 문서로 여는 기능 "
            "(용지·여백·머리말까지 그대로 — 표지·통신문용)",
    "사진": "연결한 폴더의 그림을 \\파일이름\\ 으로 부르거나 여기서 바로 삽입 "
            "(하위 폴더는 읽지 않습니다)",
    "내장": "등록 없이 바로 쓰는 기본 기호. 문서에 \\원1\\ \\로마3\\ \\홑낫표\\ 로 호출",
}

# 글자 수 상한 (개선안 23 — 흩어져 있던 매직넘버에 이름을 붙임)
ROW_PREVIEW_MAX = 16     # 목록 행에 보여줄 내용 미리보기 길이
AUTO_NAME_MAX = 10       # 문자 등록 시 내용에서 이름을 자동으로 뽑는 길이
SUMMARY_MAX = 34         # 행 요약(한 줄)의 글자 수 상한
LIST_H_PX = 360          # 스크롤 목록의 고정 높이


def _dialog_btn(parent, text, command, primary=False, zone_bg=None):
    """대화상자 공용 버튼 — 저장/확인은 파랑, 취소는 옅은 회색 (애플 A안)."""
    font = (FONT, theme.fs(9), "bold") if primary else (FONT, theme.fs(9))
    b = RoundButton(parent, text=text, command=command,
                    bg=ACCENT if primary else SOFT,
                    fg="white" if primary else TEXT, radius=7, font=font,
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
                 font=(FONT, theme.fs(10), "bold"), bg=BG, fg=TEXT).pack(
                 anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="체크한 항목만 저장돼, 나중에 그 항목만 다른 글자에 입혀집니다.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        self.vars = {}
        body = tk.Frame(self, bg=BG, padx=16)
        body.pack(fill="x")
        for label in engine_library.CHARSHAPE_FIELD_LABELS:
            v = tk.BooleanVar(value=False)
            self.vars[label] = v
            tk.Checkbutton(body, text=label, variable=v, font=(FONT, theme.fs(10)),
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
    """이름 / 마크다운 라벨 / 분류를 한 창에서 입력."""

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

        # ── 이름만 물어본다. 라벨·분류는 대부분 기본값이면 충분하므로 접어둠 ──
        tk.Label(body, text="이름", font=(FONT, theme.fs(9)), bg=BG, fg=TEXT).grid(
            row=0, column=0, sticky="w", pady=3)
        self.name_var = tk.StringVar(value=name)
        name_entry = tk.Entry(body, textvariable=self.name_var, width=26,
                              font=(FONT, theme.fs(10)), relief="solid", bd=1)
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
        self.group_var = tk.StringVar(value=library.DEFAULT_GROUP)
        self._preview = tk.Label(body, text="", font=(FONT, theme.fs(8)), bg=BG, fg=ACCENT)
        self._preview.grid(row=1, column=1, sticky="w", padx=(8, 0))
        self.name_var.trace_add("write", lambda *a: self._update_preview())
        self.label_var.trace_add("write", lambda *a: self._update_preview())

        if extra_note:
            tk.Label(body, text=extra_note, font=(FONT, theme.fs(8)), bg=BG, fg=MUTED,
                     wraplength=320, justify="left").grid(
                row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # ── 자세히 (라벨·분류) — 필요할 때만 펼침 ──
        self._adv_open = False
        self._adv = tk.Frame(self, bg=BG, padx=16)
        tk.Label(self._adv, text="마크다운 라벨", font=(FONT, theme.fs(9)), bg=BG,
                 fg=TEXT).grid(row=0, column=0, sticky="w", pady=3)
        self.label_entry = tk.Entry(self._adv, textvariable=self.label_var,
                                    width=24, font=(FONT, theme.fs(10)), relief="solid", bd=1)
        self.label_entry.grid(row=0, column=1, pady=3, padx=(8, 0))
        self.label_entry.bind("<KeyRelease>", lambda e: self._update_preview())
        tk.Label(self._adv, text="비우면 이름을 그대로 씁니다.",
                 font=(FONT, theme.fs(7)), bg=BG, fg=MUTED).grid(
            row=1, column=1, sticky="w", padx=(8, 0))
        tk.Label(self._adv, text="분류", font=(FONT, theme.fs(9)), bg=BG, fg=TEXT).grid(
            row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(self._adv, textvariable=self.group_var, width=21,
                     values=library.list_groups(), font=(FONT, theme.fs(10))).grid(
            row=2, column=1, pady=3, padx=(8, 0))

        self._adv_btn = tk.Button(self, text="▸ 자세히 (라벨·분류)",
                                  command=self._toggle_adv, font=(FONT, theme.fs(8)),
                                  fg=MUTED, bg=BG, activebackground=BG,
                                  bd=0, cursor="hand2", anchor="w")
        self._adv_btn.pack(fill="x", padx=16)

        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "저장", self._ok, primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))

        self._update_preview()
        self._poll_preview()        # IME 조합 중 글자까지 실시간 반영
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+40}+{master.winfo_rooty()+60}")
        self.grab_set()
        ui_fx.attach_all(self)   # 창 안 모든 버튼에 호버 보간

    def _toggle_adv(self):
        if self._adv_open:
            self._adv.pack_forget()
            self._adv_btn.config(text="▸ 자세히 (라벨·분류)")
        else:
            self._adv.pack(fill="x", before=self._adv_btn)
            self._adv_btn.config(text="▾ 자세히 (라벨·분류)")
        self._adv_open = not self._adv_open

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
            self._live_value(self.label_var, getattr(self, "label_entry", None))) \
            or library.normalize_label(
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
        label = self.label_var.get().strip() or name
        if not self._confirm_label(label):
            return
        self.result = (name, label,
                       self.group_var.get().strip() or library.DEFAULT_GROUP)
        self.destroy()

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
    # 빈칸 스캔 — \ 하나가 빈칸 하나
    captured = hwp_engine.read_selection_text(retries=6)
    slot_count = captured.count("\\")
    if slot_count:
        note = (f"빈칸(\\) {slot_count}개 발견 — 마크다운 변환 시 아랫줄 "
                f"{slot_count}줄이 위에서부터 순서대로 채워집니다.\n"
                "   (비울 칸에는 '-' 한 줄)")
    elif "/" in captured:
        # 실제로 겪은 혼동: 빈칸을 슬래시(/)로 찍으면 인식 안 됨 (2026-07-16)
        note = ("⚠ 빈칸 표시가 없습니다. 혹시 슬래시(/)를 쓰셨나요?\n"
                "   빈칸은 역슬래시(\\)여야 합니다 — 한글에서 ₩ 로 보이는 그 키입니다.")
    else:
        note = ("빈칸 표시(\\)가 없습니다. 글자가 들어갈 자리에 \\ 를 넣어두면\n"
                "마크다운 변환 때 아랫줄 내용이 순서대로 채워집니다.")
    meta = MetaDialog(parent, title="템플릿 등록", extra_note=note)
    parent.wait_window(meta)
    if not meta.result:
        return None
    name, label, group = meta.result
    # add_template_from_capture 의 두 번째 인자는 **함수**다 (목적지를 받아 거기
    # 저장하는 함수). 조각을 최종 이름으로 바로 저장하므로 이름 바꾸기가 없고,
    # 한글이 파일을 물고 있어 나던 WinError 32 도 생기지 않는다 (2026-07-19).
    try:
        item_id = library.add_template_from_capture(
            name, engine_library.capture_fragment, label=label,
            group=group, slot_count=slot_count)
    except Exception as e:
        applog.exc("템플릿 캡처 실패", e)
        messagebox.showerror("캡처 실패", str(e), parent=parent)
        return None
    # 구버전이 한글에 열어둔 _tmp 문서가 있으면 닫고 디스크에서도 청소
    try:
        engine_library.close_stale_temp_docs()
        library.cleanup_temp_fragments()
    except Exception as e:
        applog.exc("임시 파일 청소 실패 (무해)", e)
    return item_id


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
                 font=(FONT, theme.fs(9)), bg=BG, fg=MUTED, justify="left").pack(
                 anchor="w", padx=16, pady=(14, 6))

        self.text = tk.Text(self, width=44, height=5, font=(FONT, theme.fs(10)),
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
        self._collapsed = set()         # 접힌 분류 {(cat, group), ...}
        self._builtin_group = "전체"     # 내장 탭의 그룹 칩 선택

        tk.Label(self, text="물감 설정", font=(FONT, theme.fs(12), "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(14, 2))

        # 탭 버튼 — 표시는 label, 내부는 key (저장 데이터 키와 한 몸)
        tab_row = tk.Frame(self, bg=BG, padx=16)
        tab_row.pack(fill="x", pady=(4, 0))
        self.tab_btns = {}
        for c in CATS:
            b = RoundButton(tab_row, text=c["label"],
                            command=lambda k=c["key"]: self._switch_tab(k),
                            bg=CARD, fg=TEXT, radius=7,
                            font=(FONT, theme.fs(9), "bold"), outline="",
                            zone_bg=BG)
            b.fit(pad_x=12, pad_y=6)
            b.pack(side="left", padx=(0, 4))
            self.tab_btns[c["key"]] = b

        self.desc_label = tk.Label(self, font=(FONT, theme.fs(8)), bg=BG, fg=MUTED,
                                    justify="left", wraplength=440)
        self.desc_label.pack(anchor="w", padx=16, pady=(6, 8))

        # 검색 + 분류 필터 (+ 분류 관리)
        filter_row = tk.Frame(self, bg=BG, padx=16)
        filter_row.pack(fill="x")
        tk.Label(filter_row, text="검색", font=(FONT, theme.fs(8)), fg=MUTED, bg=BG).pack(side="left")
        self.search_var = tk.StringVar(value="")
        se = tk.Entry(filter_row, textvariable=self.search_var, width=14,
                      font=(FONT, theme.fs(9)), relief="solid", bd=1)
        se.pack(side="left", padx=(6, 12))
        self.search_var.trace_add("write", lambda *a: self._refresh())
        self.group_lbl = tk.Label(filter_row, text="분류", font=(FONT, theme.fs(8)),
                                   fg=MUTED, bg=BG)
        self.group_lbl.pack(side="left")
        self.group_filter = tk.StringVar(value="전체")
        self.group_combo = ttk.Combobox(filter_row, textvariable=self.group_filter,
                                        width=12, state="readonly", font=(FONT, theme.fs(9)))
        self.group_combo.pack(side="left", padx=(6, 0))
        self.group_combo.bind("<<ComboboxSelected>>",
                              lambda e: self._refresh())
        # 분류 관리 (이름 바꾸기·삭제) — 분류는 사용자가 만들고 지울 수 있어야 한다
        self.group_manage = RoundButton(filter_row, text="⋯",
                                        command=self._group_menu, bg=CARD,
                                        fg=MUTED, radius=6,
                                        font=(FONT, theme.fs(9)),
                                        outline=BORDER, zone_bg=BG)
        self.group_manage.fit(pad_x=7, pad_y=3)
        self.group_manage.pack(side="left", padx=(4, 0))

        # 내장 탭 전용: 그룹 칩 (원문자·숫자 / 로마숫자 / 낫표 …)
        self.chip_row = tk.Frame(self, bg=BG, padx=16)
        self._chip_btns = {}

        # 추가 버튼(탭마다 동작이 다름) — 자리는 항상 구분선 앞 (앵커 = _sep)
        self.add_btn = tk.Button(self, font=(FONT, theme.fs(9), "bold"), bg=SOFT,
                                  fg=TEXT, bd=0, padx=10, pady=8, cursor="hand2")
        self.add_btn.pack(fill="x", padx=16, pady=(8, 0))

        self._sep = tk.Frame(self, bg=BORDER, height=1)
        self._sep.pack(fill="x", padx=16, pady=(10, 6))

        # ── 스크롤 목록 (2026-07-25 재구축의 핵심) ──
        # 예전에는 스크롤이 없어 항목 20개면 창이 화면 밖으로 나갔다.
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=16)
        self._canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                                 height=LIST_H_PX, width=460)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self._canvas.yview)
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
        self.sel_hint = tk.Label(bar, text="", font=(FONT, theme.fs(8)),
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

        self._switch_tab("서식")
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()-320}+{master.winfo_rooty()}")

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
            "사진":   ("사진 폴더 연결/변경…", self._pick_photo_dir),
        }.get(cat)
        if add_spec:
            self.add_btn.config(text=add_spec[0], command=add_spec[1])
            self.add_btn.pack(fill="x", padx=16, pady=(8, 0), before=self._sep)
        else:                           # 내장 — 추가 불가(읽기 전용)
            self.add_btn.pack_forget()

        # 분류 필터 — 서식·특수기호·템플릿·양식에서만. 내장은 그룹 칩, 사진은 없음
        show_group = cat not in ("내장", "사진")
        if show_group:
            self.group_lbl.pack(side="left")
            self.group_combo.pack(side="left", padx=(6, 0))
            self.group_manage.pack(side="left", padx=(4, 0))
        else:
            self.group_lbl.pack_forget()
            self.group_combo.pack_forget()
            self.group_manage.pack_forget()
        if cat == "내장":
            self._build_chips()
            self.chip_row.pack(fill="x", pady=(6, 0), before=self.add_btn
                               if add_spec else self._sep)
        else:
            self.chip_row.pack_forget()

        # 동작바 — 탭마다 쓸 수 있는 동작이 다르다. 순서가 흐트러지지 않게
        # 전부 뗐다가 정해진 차례로 다시 붙인다 (주 동작이 맨 오른쪽).
        main_label = {"서식": "적용", "양식": "열기"}.get(cat, "삽입")
        self.act_main.set_text(main_label, pad_x=16, pad_y=6)
        for b in (self.act_main, self.act_edit, self.act_del, self.act_more):
            b.pack_forget()
        self.act_main.pack(side="right", padx=(6, 0))
        if cat not in ("내장", "사진"):     # 읽기 전용 — 수정·삭제 없음
            self.act_edit.pack(side="right", padx=(6, 0))
            self.act_del.pack(side="right", padx=(6, 0))
        if cat in ("템플릿", "양식"):       # 꺼내서 고치기 · AI 프롬프트
            self.act_more.pack(side="right", padx=(6, 0))
        self._refresh(cat)

    def _build_chips(self):
        """내장 탭의 그룹 칩 — 무엇이 들었는지 종류별로 보인다 (사용자 요청)."""
        for w in self.chip_row.winfo_children():
            w.destroy()
        self._chip_btns = {}
        groups = ["전체"]
        for _, _, g in builtin_chars.BUILTINS:
            if g not in groups:
                groups.append(g)
        if self._builtin_group not in groups:
            self._builtin_group = "전체"
        for g in groups:
            on = g == self._builtin_group
            b = RoundButton(self.chip_row, text=g,
                            command=lambda gg=g: self._pick_chip(gg),
                            bg=ACCENT_SOFT if on else CARD,
                            fg=ACCENT if on else MUTED, radius=10,
                            font=(FONT, theme.fs(8)),
                            outline="" if on else BORDER, zone_bg=BG)
            b.fit(pad_x=9, pad_y=3)
            b.pack(side="left", padx=(0, 4))
            self._chip_btns[g] = b

    def _pick_chip(self, group):
        self._builtin_group = group
        for g, b in self._chip_btns.items():
            on = g == group
            b.retint(bg=ACCENT_SOFT if on else CARD,
                     fg=ACCENT if on else MUTED)
        self._refresh()

    # ── 분류 관리 (이름 바꾸기 / 삭제) ────────────────
    def _group_menu(self):
        cur = self.group_filter.get()
        pop = Popover(self, self.group_manage)
        if cur in ("전체", library.DEFAULT_GROUP):
            pop.add("분류를 먼저 골라주세요 (위 목록에서)", lambda: None)
            pop.add(f"'{library.DEFAULT_GROUP}' 분류는 바꿀 수 없습니다",
                    lambda: None)
        else:
            pop.add(f"'{cur}' 이름 바꾸기…", lambda: self._rename_group(cur))
            pop.add(f"'{cur}' 삭제 (항목은 '{library.DEFAULT_GROUP}'으로)",
                    lambda: self._delete_group(cur))
        pop.separator()
        pop.add("새 분류는 항목을 등록·수정할 때 '자세히'에서 만듭니다",
                lambda: None)
        pop.show()

    def _rename_group(self, old):
        dlg = _AskTextDialog(self, title="분류 이름 바꾸기",
                             prompt=f"'{old}' 의 새 이름", value=old)
        self.wait_window(dlg)
        new = (dlg.result or "").strip()
        if not new or new == old:
            return
        n = library.rename_group(old, new)
        self.group_filter.set(new)
        self._refresh()
        self._notify()
        messagebox.showinfo("분류 이름 바꾸기",
                            f"{n}개 항목의 분류를 '{new}' 로 바꿨습니다.",
                            parent=self)

    def _delete_group(self, name):
        if not messagebox.askyesno(
                "분류 삭제",
                f"'{name}' 분류를 삭제할까요?\n\n항목은 지워지지 않고 "
                f"'{library.DEFAULT_GROUP}' 분류로 옮겨집니다.", parent=self):
            return
        n = library.delete_group(name)
        self.group_filter.set("전체")
        self._refresh()
        self._notify()
        messagebox.showinfo("분류 삭제",
                            f"{n}개 항목을 '{library.DEFAULT_GROUP}' 으로 옮겼습니다.",
                            parent=self)

    def _refresh(self, cat=None):
        cat = cat or self.current_cat
        self._select(None)
        for w in self.list_area.winfo_children():
            w.destroy()
        self._canvas.yview_moveto(0)
        query = self.search_var.get().strip()

        if cat == "내장":
            results = builtin_chars.search(query)
            if self._builtin_group != "전체":
                results = [r for r in results if r[2] == self._builtin_group]
            if not results:
                self._empty_note("검색 결과가 없습니다.")
                return
            for label, text, group in results[:200]:
                self._render_builtin_row(label, text, group)
            if len(results) > 200:
                tk.Label(self.list_area,
                         text=f"…외 {len(results)-200}개 (검색으로 좁혀주세요)",
                         font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(anchor="w", pady=4)
            return

        if cat == "사진":
            self._render_photo_list(query)
            return

        # 분류 콤보 갱신 (선택 유지)
        groups = ["전체"] + library.list_groups()
        cur = self.group_filter.get()
        self.group_combo["values"] = groups
        if cur not in groups:
            self.group_filter.set("전체")
            cur = "전체"
        items = library.list_items(cat)
        if cur != "전체":
            items = [it for it in items
                     if (it.get("group") or library.DEFAULT_GROUP) == cur]
        if query:
            ql = query.lower()
            items = [it for it in items if ql in self._search_blob(cat, it)]
        if not items:
            self._empty_note("해당하는 항목이 없습니다.")
            return

        # ── 분류별로 묶어서, 접을 수 있는 머리글 아래에 그린다 ──
        by_group = {}
        for it in items:
            by_group.setdefault(it.get("group") or library.DEFAULT_GROUP,
                                []).append(it)
        one_group = len(by_group) == 1
        for group, group_items in by_group.items():
            # 분류가 하나뿐이면 머리글이 정보를 안 보태므로 생략
            if not one_group:
                self._render_group_header(cat, group, len(group_items))
                if (cat, group) in self._collapsed:
                    continue
            for item in group_items:
                self._render_row(cat, item)

    def _empty_note(self, text):
        tk.Label(self.list_area, text=text, font=(FONT, theme.fs(9)),
                 bg=BG, fg=MUTED).pack(anchor="w", pady=8)

    def _search_blob(self, cat, item):
        parts = [item.get("name", ""), item.get("label", ""),
                 item.get("group", "")]
        if cat == "문자":
            parts.append(item.get("text", ""))
        return " ".join(parts).lower()

    # ── 행 그리기 ────────────────────────────────────
    def _render_group_header(self, cat, group, count):
        """분류 머리글 — 누르면 접었다 편다. ▾/▸ 로 상태를 보여준다."""
        closed = (cat, group) in self._collapsed
        head = tk.Label(self.list_area,
                        text=f"{'▸' if closed else '▾'} {group} ({count})",
                        font=(FONT, theme.fs(8), "bold"), bg=BG, fg=MUTED,
                        anchor="w", cursor="hand2", pady=3)
        head.pack(fill="x", pady=(6, 1))
        head.bind("<Button-1>",
                  lambda e, key=(cat, group): self._toggle_group(key))

    def _toggle_group(self, key):
        if key in self._collapsed:
            self._collapsed.discard(key)
        else:
            self._collapsed.add(key)
        self._refresh()

    def _make_row(self, cat, item, kind="item"):
        """행 한 줄의 껍데기 — 클릭=선택, 더블클릭=주 동작/수정."""
        row = tk.Frame(self.list_area, bg=ROWBG, highlightbackground=BORDER,
                       highlightthickness=1)
        row.pack(fill="x", pady=1)
        return row

    def _wire_row(self, row, cat, item, kind):
        """행(과 그 자식들)에 선택·더블클릭을 건다."""
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
            title_font = (FONT, theme.fs(9), "bold")
        tk.Label(info, text=title, font=title_font,
                 bg=ROWBG, fg=TEXT, anchor="w").pack(side="left")
        summary = self._summary(cat, item)
        if summary:
            tk.Label(info, text=summary, font=(FONT, theme.fs(8)),
                     bg=ROWBG, fg=MUTED, anchor="w").pack(side="left",
                                                          padx=(8, 0))
        # 라벨은 오른쪽 끝에 — 반복되는 '\라벨\ · 분류' 꼬리표를 없앤 대신
        # 호출 이름만 조용히 보여준다 (분류는 위 머리글이 말한다)
        lab = item.get("label") or item.get("name", "")
        tk.Label(row, text=f"\\{lab}\\", font=(FONT, theme.fs(8)), bg=ROWBG,
                 fg=MUTED, padx=10).pack(side="right")
        self._wire_row(row, cat, item, "item")

    def _render_builtin_row(self, label, text, group):
        item = {"name": label, "label": label, "text": text, "group": group}
        row = self._make_row("내장", item, "builtin")
        info = tk.Frame(row, bg=ROWBG, padx=10, pady=4)
        info.pack(side="left", fill="both", expand=True)
        tk.Label(info, text=text, font=(FONT, theme.fs(12)), bg=ROWBG,
                 fg=TEXT, anchor="w").pack(side="left")
        tk.Label(row, text=f"\\{label}\\", font=(FONT, theme.fs(8)), bg=ROWBG,
                 fg=MUTED, padx=10).pack(side="right")
        self._wire_row(row, "내장", item, "builtin")

    def _render_photo_list(self, query):
        """사진 탭 — 연결된 폴더의 그림 목록. 폴더가 없으면 안내만."""
        d = settings.get_photo_dir()
        if not d:
            self._empty_note("사진 폴더가 연결돼 있지 않습니다.\n"
                             "위 버튼으로 폴더를 연결하면 파일 이름이 여기 나오고,\n"
                             "문서에 \\파일이름\\ 으로 그림을 넣을 수 있습니다.")
            return
        tk.Label(self.list_area, text=d, font=(FONT, theme.fs(8)), bg=BG,
                 fg=MUTED, anchor="w").pack(fill="x", pady=(2, 4))
        photos = library._photo_lookup()
        entries = [entry for _, entry in sorted(photos.items())]
        if query:
            ql = query.lower()
            entries = [e for e in entries if ql in e[1]["name"].lower()]
        if not entries:
            self._empty_note("폴더에 그림 파일이 없습니다."
                             if not query else "검색 결과가 없습니다.")
            return
        for _cat, it in entries:
            row = self._make_row("사진", it, "photo")
            info = tk.Frame(row, bg=ROWBG, padx=10, pady=5)
            info.pack(side="left", fill="both", expand=True)
            tk.Label(info, text=it["name"], font=(FONT, theme.fs(9), "bold"),
                     bg=ROWBG, fg=TEXT, anchor="w").pack(side="left")
            ext = pathlib.Path(it["path"]).suffix.lower().lstrip(".")
            tk.Label(info, text=ext, font=(FONT, theme.fs(8)), bg=ROWBG,
                     fg=MUTED).pack(side="left", padx=(8, 0))
            tk.Label(row, text=f"\\{it['label']}\\", font=(FONT, theme.fs(8)),
                     bg=ROWBG, fg=MUTED, padx=10).pack(side="right")
            self._wire_row(row, "사진", it, "photo")

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
            it = sel["item"]
            self.sel_hint.config(
                text=it.get("name") or it.get("label") or "")

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
                engine_library.open_form(library.template_path(item))
            else:
                engine_library.insert_fragment(library.template_path(item))
        except Exception as e:
            messagebox.showerror("오류", f"{type(e).__name__}: {e}", parent=self)

    def _edit_selected(self):
        if not self._need_sel():
            return
        if self._sel["kind"] != "item":
            messagebox.showinfo("수정 불가",
                                "내장·사진 항목은 여기서 수정할 수 없습니다.",
                                parent=self)
            return
        self._edit(self._sel["cat"], self._sel["item"])

    def _del_selected(self):
        if not self._need_sel():
            return
        if self._sel["kind"] != "item":
            messagebox.showinfo("삭제 불가",
                                "내장·사진 항목은 여기서 삭제할 수 없습니다.",
                                parent=self)
            return
        self._delete(self._sel["cat"], self._sel["item"])

    # ── 템플릿·양식 추가 동작 (⋯) ────────────────────
    def _more_menu(self):
        if not self._need_sel():
            return
        cat = self._sel["cat"]
        pop = Popover(self, self.act_more)
        if cat == "템플릿":
            pop.add("꺼내서 고치기…  (한글에 펼쳐서 수정 후 덮어쓰기)",
                    self._extract_edit)
        pop.add("AI 프롬프트 복사  (빈칸을 AI 에게 채우게)",
                self._copy_ai_prompt)
        pop.show()

    def _extract_edit(self):
        r"""템플릿 꺼내서 고치기 (기획 15번).

        조각을 한글 **새 탭**에 펼쳐 주고, 다 고치면 떠 있는 안내 창의
        [덮어쓰기]가 그 문서 전체를 다시 캡처해 같은 항목에 저장한다.
        id 가 유지되므로 팔레트 블럭 연결이 안 끊긴다.
        """
        item = self._sel["item"]
        if not _ensure_hwp(self):
            return
        try:
            engine_library.open_template_copy(library.template_path(item))
        except Exception as e:
            applog.exc("템플릿 꺼내기 실패", e)
            messagebox.showerror("꺼내기 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            return
        _RecaptureCoach(self, item)

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
        self.clipboard_clear()
        self.clipboard_append(prompt)
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
        name, label, group = meta.result
        library.add_style(name, delta, label=label, group=group)
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
        name, label, group = meta.result
        library.add_char(name, content, label=label, group=group)
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
        if hwp_engine.is_connected():
            try:
                slot_count = engine_library.count_slots_in_file(path)
            except Exception as e:
                applog.exc(f"양식 등록: 빈칸 세기 실패 — {path}", e)
        if slot_count:
            note = (f"빈칸(\\) {slot_count}개 발견 — \\라벨\\ 변환 시 아랫줄 "
                    f"{slot_count}줄이 순서대로 채워집니다. (비울 칸엔 '-')")
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
        name, label, group = meta.result
        try:
            library.add_form_from_file(name, path, label=label, group=group,
                                       slot_count=slot_count)
        except Exception as e:
            messagebox.showerror("등록 실패", str(e), parent=self)
            return
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
        cur = settings.get_photo_dir()
        path = filedialog.askdirectory(
            parent=self, title="사진 폴더 선택 (취소하면 연결 해제 여부를 묻습니다)",
            initialdir=cur or None)
        if path:
            settings.set_photo_dir(path)
        elif cur and messagebox.askyesno(
                "연결 해제", "사진 폴더 연결을 해제할까요?\n"
                f"(현재: {cur})", parent=self):
            settings.set_photo_dir("")
        self._refresh()

    def _edit(self, cat, item):
        """등록된 항목의 이름·라벨·분류 수정 (id 유지 → 팔레트 연결 안 깨짐)."""
        meta = MetaDialog(self, title=f"{CAT_LABEL.get(cat, cat)} 수정",
                          name=item["name"],
                          label=item.get("label", ""), exclude_id=item["id"])
        try:
            meta.group_var.set(item.get("group", library.DEFAULT_GROUP))
        except Exception:
            pass
        self.wait_window(meta)
        if not meta.result:
            return
        name, label, group = meta.result
        # 이름만 고쳤을 때 라벨이 옛 이름으로 남는 것을 막는다 (라벨 칸이 '자세히'
        # 안에 접혀 있어 사용자 눈에 안 보인다). 규칙은 resolve_edited_label 참고.
        label = library.resolve_edited_label(
            item["name"], item.get("label", ""), name, label)
        library.update_item(cat, item["id"], name=name, label=label, group=group)
        self._refresh(cat)
        self._notify()

    def _notify(self):
        if self.on_saved:
            self.on_saved()


class _AskTextDialog(tk.Toplevel):
    """짧은 문자열 하나를 묻는 작은 창 (분류 이름 바꾸기 등)."""

    def __init__(self, master, title="입력", prompt="", value=""):
        super().__init__(master)
        self.result = None
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        tk.Label(self, text=prompt, font=(FONT, theme.fs(9)), bg=BG,
                 fg=TEXT).pack(anchor="w", padx=16, pady=(14, 4))
        self.var = tk.StringVar(value=value)
        ent = tk.Entry(self, textvariable=self.var, width=24,
                       font=(FONT, theme.fs(10)), relief="solid", bd=1)
        ent.pack(padx=16)
        ent.focus_set()
        ent.select_range(0, "end")
        ent.bind("<Return>", lambda e: self._ok())
        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "확인", self._ok, primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+60}+{master.winfo_rooty()+60}")
        self.grab_set()

    def _ok(self):
        commit_ime(self)
        self.result = self.var.get()
        self.destroy()


class _RecaptureCoach(tk.Toplevel):
    r"""'꺼내서 고치기'의 안내 창 — 한글에서 고치는 동안 옆에 떠 있는다.

    modal(grab)이 아니다 — 사용자는 이 창을 둔 채 한글에서 자유롭게 편집한다.
    [덮어쓰기]는 **지금 한글에 떠 있는 문서 전체**를 다시 캡처해 같은 항목에
    저장한다. 문서 전체 = 아까 펼쳐 준 새 탭의 내용이라는 전제인데, 사용자가
    다른 문서로 갈아탔을 수도 있으므로 문구로 분명히 말해 둔다.
    """

    def __init__(self, master, item):
        super().__init__(master)
        self._manager = master
        self._item = item
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        tk.Label(self, text=f"'{item['name']}' 고치는 중",
                 font=(FONT, theme.fs(11), "bold"), bg=BG, fg=TEXT).pack(
                 anchor="w", padx=16, pady=(14, 2))
        tk.Label(self,
                 text="한글 새 탭에 템플릿을 펼쳐 두었습니다.\n"
                      "내용을 고친 뒤 아래 [이 내용으로 덮어쓰기]를 누르세요.\n"
                      "지금 한글에 보이는 문서 **전체**가 이 템플릿으로 저장됩니다.\n"
                      "(고치던 탭은 저장하지 않고 닫아도 됩니다)",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED,
                 justify="left").pack(anchor="w", padx=16, pady=(0, 10))
        foot = tk.Frame(self, bg=BG, padx=16, pady=12)
        foot.pack(fill="x")
        _dialog_btn(foot, "이 내용으로 덮어쓰기", self._overwrite,
                    primary=True).pack(side="right")
        _dialog_btn(foot, "취소", self.destroy).pack(side="right", padx=(0, 6))
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+40}+{master.winfo_rooty()+80}")

    def _overwrite(self):
        if not _ensure_hwp(self):
            return
        try:
            engine_library.select_all()     # 지금 문서 전체를 캡처 대상으로
            ok = library.replace_template_fragment(
                self._item["id"], engine_library.capture_fragment)
        except Exception as e:
            applog.exc("템플릿 덮어쓰기 실패", e)
            messagebox.showerror("덮어쓰기 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            return
        if not ok:
            messagebox.showerror("덮어쓰기 실패",
                                 "이 템플릿이 라이브러리에서 사라졌습니다.",
                                 parent=self)
            self.destroy()
            return
        self.destroy()
        # 이 창은 관리 창의 자식이라, 여기가 살아 있으면 관리 창도 살아 있다
        try:
            self._manager._refresh("템플릿")
            self._manager._notify()
        except Exception:
            pass
        messagebox.showinfo("덮어쓰기 완료",
                            f"'{self._item['name']}' 을(를) 새 내용으로 "
                            "저장했습니다.\n고치던 한글 탭은 닫으셔도 됩니다.",
                            parent=self._manager)


class ShareDialog(tk.Toplevel):
    r"""물감 내보내기/가져오기 — 메인 창 설정(⚙) 메뉴에서 연다 (사용자 결정
    2026-07-25: "내가 만든 탭을 남에게 주는 일"이라 물감 설정 화면이 아니라
    설정의 하위 기능으로 뺐다).

    내보내기 = 고른 분류(탭) 전체를 조각 파일까지 zip 하나로.
    가져오기 = zip 을 추가만 한다 (덮어쓰기 없음 — 이름·라벨 충돌은 자동 개명).
    """

    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.on_saved = on_saved
        self.title(appinfo.WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        tk.Label(self, text="물감 내보내기 / 가져오기",
                 font=(FONT, theme.fs(12), "bold"), bg=BG, fg=TEXT).pack(
                 anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="내가 만든 물감을 zip 한 개로 묶어 동료와 주고받습니다.",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(
                 anchor="w", padx=16, pady=(0, 10))

        row = tk.Frame(self, bg=BG, padx=16)
        row.pack(fill="x")
        tk.Label(row, text="내보낼 물감", font=(FONT, theme.fs(9)), bg=BG,
                 fg=TEXT).pack(side="left")
        # 내장·사진은 파일/프로그램에 딸린 것이라 내보낼 게 없다
        self._exportable = [c for c in CATS
                            if c["key"] not in ("내장", "사진")]
        self.cat_var = tk.StringVar(value=self._exportable[0]["label"])
        ttk.Combobox(row, textvariable=self.cat_var, state="readonly",
                     width=10, font=(FONT, theme.fs(9)),
                     values=[c["label"] for c in self._exportable]).pack(
                     side="left", padx=(8, 8))
        _dialog_btn(row, "내보내기…", self._export, primary=True).pack(side="left")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=16, pady=10)

        row2 = tk.Frame(self, bg=BG, padx=16)
        row2.pack(fill="x", pady=(0, 14))
        tk.Label(row2, text="받은 zip 을", font=(FONT, theme.fs(9)), bg=BG,
                 fg=TEXT).pack(side="left")
        _dialog_btn(row2, "가져오기…", self._import).pack(side="left", padx=(8, 0))
        tk.Label(row2, text="(기존 물감은 그대로, 추가만 합니다)",
                 font=(FONT, theme.fs(8)), bg=BG, fg=MUTED).pack(
                 side="left", padx=(8, 0))

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+30}+{master.winfo_rooty()+50}")

    def _cat_key(self):
        label = self.cat_var.get()
        for c in self._exportable:
            if c["label"] == label:
                return c["key"]
        return self._exportable[0]["key"]

    def _export(self):
        cat = self._cat_key()
        label = CAT_LABEL.get(cat, cat)
        items = library.list_items(cat)
        if not items:
            messagebox.showinfo("항목 없음",
                                f"'{label}' 에 내보낼 항목이 없습니다.",
                                parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, title=f"'{label}' 내보내기",
            defaultextension=".zip", initialfile=f"hwp_palette_{label}.zip",
            filetypes=[("hwp_palette 라이브러리", "*.zip")])
        if not path:
            return
        try:
            n = library.export_items([(cat, it) for it in items], path)
        except Exception as e:
            applog.exc(f"라이브러리 내보내기 실패 ({cat})", e)
            messagebox.showerror("내보내기 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            return
        skipped = len(items) - n
        msg = f"'{label}' {n}개를 내보냈습니다.\n{pathlib.Path(path).name}"
        if skipped:
            msg += f"\n\n(조각 파일이 없어 {skipped}개는 빠졌습니다 — app.log 참고)"
        messagebox.showinfo("내보내기 완료", msg, parent=self)

    def _import(self):
        path = filedialog.askopenfilename(
            parent=self, title="라이브러리 가져오기",
            filetypes=[("hwp_palette 라이브러리", "*.zip"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            r = library.import_archive(path)
        except Exception as e:
            applog.exc(f"라이브러리 가져오기 실패 ({path})", e)
            messagebox.showerror("가져오기 실패", f"{type(e).__name__}: {e}",
                                 parent=self)
            return
        lines = [f"{r['added']}개를 가져왔습니다. (기존 항목은 그대로 둡니다)"]
        if r["renamed"]:
            lines.append("\n이름이 겹쳐 바꾼 항목:")
            lines += [f"  {a} → {b}" for a, b in r["renamed"][:8]]
        if r["relabeled"]:
            lines.append("\n라벨이 겹쳐 바꾼 항목:")
            lines += [f"  \\{a}\\ → \\{b}\\" for a, b in r["relabeled"][:8]]
            lines.append("(라벨을 그대로 두면 마크다운 변환에서 호출되지 않습니다)")
        messagebox.showinfo("가져오기 완료", "\n".join(lines), parent=self)
        if self.on_saved:
            self.on_saved()


def open_share(master, on_saved=None):
    """내보내기/가져오기 창 — 메인 창 설정(⚙) 메뉴가 부른다."""
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
