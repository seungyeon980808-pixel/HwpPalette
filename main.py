# -*- coding: utf-8 -*-
"""
hwp_palette — 한글(HWP) 커스텀 팔레트 · 마크다운 변환 도구 (UI)
(30_exam_edit → exam_scribe → hwp_palette 로 발전)

버전 정보
─────────────────────────────────────────
v1.3.0 (2026-07-05)
  [기능 추가] 보기박스 시각 편집 — 도식을 보며 수치 조절
  - bogi_visual_ui.py 추가: 캔버스에 보기박스를 축척으로 그리고 슬라이더로 실시간
    재렌더, 지금 조절 중인 치수를 파란 화살표로 강조(어떤 숫자가 어디인지 보며 수정)
  - '실제 한글에 미리 삽입' 버튼으로 미저장 값 즉시 실물 확인
  - 설정창 보기박스 그룹에 '🖼 도식 보며 편집' 진입 버튼
v1.2.1 (2026-07-05)
  [버그 수정] 양식 설정에서 단 폭을 바꿔도 표 크기가 안 변하던 문제 (실측 검증)
  - WidthType=0은 '명시적 너비'가 아니라 '단에 맞춤'(지정 무시)이었음 → 2로 수정.
    하드코딩 93.99mm가 실제 단 폭과 우연히 일치해 지금까지 은폐돼 있었음
  - 표 폭 보정: ColWidth는 셀 '내용' 폭이라 열마다 좌우 여백 3.6mm가 더 붙음
    → 열 폭에서 미리 빼서 완성 폭이 지정값과 일치하게 함
  - 표 탈출 버그: 보기박스처럼 셀 병합(선택 상태)으로 끝나면 CloseEx가 표 밖으로
    안 나가서 다음 표(선지 등)가 보기박스 셀 안에 중첩되던 문제
    → Cancel 후 본문(list 0) 도달까지 CloseEx 반복으로 수정
  - 행 높이는 '최소값'으로 동작(내용이 크면 늘어남)함을 설정창에 명시
v1.2.0 (2026-07-05)
  [기능 추가] 빠른 입력 버튼 편집 — 원하는 칸에 유니코드 기호를 넣어 버튼 생성
  - quickbuttons_ui.py(편집 창) 추가, 저장은 전역 config(프리셋과 무관)
  - 기호 직접 붙여넣기 또는 U+2126 형식 코드포인트 입력 지원
  - 과학 교사용 기본 기호(Ω → ℃ ± ² ₁ α β Δ …) 시드
v1.1.0 (2026-07-05)
  [기능 추가] 양식 프리셋 — 표/박스/글꼴의 모든 스펙을 프로그램 안에서 수정
  - settings.py(프리셋 저장소) / settings_ui.py(설정 창) 추가
  - 학교·시험지별로 양식을 이름 붙여 저장·전환, JSON으로 내보내/가져와 공유
  - 단 폭(2단↔1단)·글꼴·글자크기·박스 높이·줄간격·셀 여백·테두리 전부 설정화
  - hwp_engine의 하드코딩 치수를 활성 프리셋 참조로 교체
v1.0.0 (2026-07-05)
  [이관] 30_exam_edit의 마크다운 변환기를 exam_scribe 프로젝트로 이식
  - parser.py(마크다운 파싱) / hwp_engine.py(한컴 자동화) / main.py(UI) 3파일로 분리
  - [버그 수정] 마크다운 변환·원문자 삽입 시 클립보드를 임시 Tk 인스턴스로 읽어
    간헐적으로 빈 값이 반환되던 문제 — 메인 root 클립보드 + 재시도로 통일
─────────────────────────────────────────
"""

import appinfo                     # 이름·버전·슬로건 한 곳 모음
VERSION = appinfo.VERSION
RELEASE_DATE = appinfo.RELEASE_DATE

# 전역 단축키 — 한글에서 작업하는 중에 눌러도 먹는다 (등록은 파일 끝에서).
# 버튼 라벨과 실제 등록이 어긋나지 않도록 **한 곳에서만** 정한다
# (버튼엔 Ctrl+T 라고 적혀 있는데 실제로는 다른 키인 상태를 겪었다).
CONVERT_HOTKEY = "ctrl+alt+t"
CONVERT_HOTKEY_LABEL = "Ctrl+Alt+T"

import pathlib
import tkinter as tk
from tkinter import messagebox, filedialog

import applog
import paths
import theme
import onboarding
import parser as md_parser
import hwp_engine
import engine_library
import exam_engine
import settings
import form_fill_ui
import library
import library_ui
import palette
import palette_ui
import builtin_actions               # 팔레트에 놓는 '도구' 블럭 카탈로그
import hotkey                        # 한글에서도 먹는 전역 단축키
import ui_fx                         # 호버 보간·누름 피드백 (애플 A안)
from roundbtn import RoundButton     # 둥근 모서리 버튼
from popover import Popover          # 앱과 같은 얼굴의 팝업 메뉴

# 설정 파일 입출력은 settings 모듈로 통합
load_config = settings.load_config
save_config = settings.save_config


print(f"{'='*45}")
print(f"  hwp_palette v{VERSION}")
print(f"  실행: python {pathlib.Path(__file__).name}")
print(f"{'='*45}")


# ── 활성 양식 프리셋 로드 (시작 시 + 설정 저장 시) ──────
hwp_engine.set_active_spec(settings.get_active_spec())

# 구버전이 남긴 _tmp_*.hwp 찌꺼기 청소 (WinError 32 로 실패했던 캡처의 잔재)
library.cleanup_temp_fragments()


# ── 창 하나만 (2026-07-25) ──────────────────────────────
# 버튼을 두 번 누르면 같은 창이 두 개 떠서, 한쪽에서 고친 것이 다른 쪽에
# 안 보이는 혼란이 있었다. 이미 떠 있으면 새로 만들지 않고 **그 창을 앞으로**.
_open_windows = {}


def _single(key, make):
    win = _open_windows.get(key)
    try:
        if win is not None and win.winfo_exists():
            win.deiconify()
            win.lift()
            win.focus_force()
            return win
    except Exception:
        pass                        # 파괴된 참조 — 새로 만든다
    win = make()
    _open_windows[key] = win
    return win


def fn_open_library(cat=None):
    """라이브러리 창. cat 을 주면 그 탭으로 바로 연다 (특수문자 → '내장')."""
    win = _single("library", lambda: library_ui.open_manager(root, cat=cat))
    # 이미 떠 있던 창이라도 요청한 탭('내장' 등)으로는 이동시킨다
    if cat:
        try:
            win._refresh(cat)
        except Exception as e:
            applog.exc(f"라이브러리 '{cat}' 탭 이동 실패 (무해)", e)
    return win


def fn_open_form_fill():
    """양식 채우기 — 채울 자리를 뽑아 AI에 넘기고, 채운 걸 받아 넣는다."""
    return _single("form_fill", lambda: form_fill_ui.open_form_fill(root))


# ── 한컴 연결 ───────────────────────────────────────────
def ensure_hwp():
    try:
        hwp_engine.connect()
        return True
    except Exception as e:
        applog.exc("한글 연결 실패", e)
        messagebox.showerror("연결 실패", f"한글을 먼저 실행해주세요.\n{e}")
        return False


# ── 알림 (UI 제안 3·16) ────────────────────────────────
# 예전엔 성공·경고·오류가 모두 같은 회색 한 줄이라 눈에 안 들어왔고, 다음 메시지가
# 오면 이전 것이 사라져 "무슨 경고였지?"를 다시 볼 수 없었다.
# 색 상수(MUTED/BG)는 아래 UI 절에서 정의되므로 theme 에서 직접 받는다
_NOTICE_COLORS = theme.notice_colors()      # 종류 → (글자색, 배경색)
_notices = []               # 최근 알림 [(시각, 종류, 내용), ...]
_NOTICE_KEEP = 20


def notify(kind, text, detail=""):
    """상태줄에 색으로 알리고, 최근 목록에도 남긴다(클릭해 다시 볼 수 있게)."""
    import datetime
    _notices.append((datetime.datetime.now().strftime("%H:%M:%S"), kind,
                     text + (f"\n{detail}" if detail else "")))
    del _notices[:-_NOTICE_KEEP]
    try:
        fg, bg = _NOTICE_COLORS.get(kind, _NOTICE_COLORS["info"])
        status_var.set(text)            # 여기서 notify 를 부르면 무한 재귀다
        status_lbl.config(fg=fg, bg=bg)
        set_dot(kind)                   # 알림등도 같은 상태로 (초록/주황/빨강)
    except Exception:
        pass                # UI 가 아직 없는 시점 — 목록에는 이미 남았다


def _show_notice_log():
    """상태줄을 누르면 최근 알림을 펼쳐 보여준다."""
    if not _notices:
        messagebox.showinfo("최근 알림", "아직 알림이 없습니다.")
        return
    win = tk.Toplevel(root)
    win.title("최근 알림")
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    tk.Label(win, text="최근 알림 (새 것이 위)", font=_font(10, "bold"),
             bg=BG, fg=TEXT).pack(anchor="w", padx=14, pady=(12, 6))
    box = tk.Text(win, width=60, height=min(20, len(_notices) * 2 + 2),
                  font=("Consolas", 9), relief="solid", bd=1, wrap="word")
    box.pack(fill="both", expand=True, padx=14)
    for t, kind, text in reversed(_notices):
        mark = {"ok": "정상", "warn": "주의", "error": "오류"}.get(kind, "안내")
        box.insert("end", f"[{t}] {mark}  {text}\n")
    box.config(state="disabled")
    tk.Button(win, text="닫기", command=win.destroy, font=_font(9),
              bg=ACCENT, fg="white", bd=0, padx=14,
              pady=5, cursor="hand2").pack(anchor="e", padx=14, pady=10)


def report_error(what, error, detail=False):
    """실패를 세 곳에 동시에 남긴다 (개선안 12).

    창을 닫으면 사라지는 메시지박스만으로는 "왜 안 됐지"가 남지 않았다.
      · app.log  — 나중에 원인을 찾기 위한 기록
      · 메시지박스 — 지금 당장 알아야 하니까
      · 상태표시줄 — 메시지박스를 닫은 뒤에도 남아 있게
    """
    applog.exc(what, error, detail=detail)
    messagebox.showerror(what, f"{type(error).__name__}: {error}")
    try:
        notify("error", what)
    except Exception:
        pass        # UI가 아직 안 만들어진 시점 — 로그는 이미 남았다


def read_selected_text():
    """선택 텍스트 읽기 — 윈도우 클립보드 직접 접근(hwp_engine)으로 통일.
    (Tk 클립보드는 한글 Copy와 타이밍이 어긋나 빈 값이 잦았음, 2026-07-15)"""
    return hwp_engine.read_selection_text()


# ── 버튼 함수 ───────────────────────────────────────────
def _form_plan_conflict(ops):
    r"""양식 변환이 다른 내용을 삼키게 되는 상황이면 안내 문구를, 아니면 None.

    양식(\양식라벨\)은 문서 전체를 여는 것이라, **양식보다 앞에 있는 내용**은
    그 문서가 열리는 순간 갈 곳이 없어진다. 반면 양식 **뒤에** 오는 내용은
    양식 문서의 본문 자리에 이어서 들어가므로 문제가 없다 (2026-07-24).
    그래서 막아야 하는 것은 '섞였는가'가 아니라 '양식이 맨 앞인가'다.
    """
    forms = [i for i, o in enumerate(ops) if o[0] == "form"]
    if not forms:
        return None
    if len(forms) > 1:
        names = ", ".join(ops[i][1].get("name", "?") for i in forms)
        return (f"양식이 여러 개 선택됐습니다: {names}\n\n"
                "양식은 문서 전체를 여는 것이라 한 번에 하나만 변환할 수 있습니다.")
    # 양식 앞에 실제 내용이 있으면 그것은 사라진다 (빈 줄은 무시)
    before = [o for o in ops[:forms[0]]
              if not (o[0] == "line" and not o[1].strip())]
    if before:
        return ("양식 라벨 앞에 다른 내용이 있습니다.\n\n"
                "양식은 문서 전체를 새로 여는 것이라, 그보다 앞에 쓴 내용은\n"
                "들어갈 곳이 없어 사라집니다. 양식 라벨을 맨 위로 옮겨주세요.")
    return None


def _plan_summary(ops, warns):
    """실행 계획을 한눈에 보이는 문구로 (UI 제안 5)."""
    kinds = {}
    slots = 0
    for op in ops:
        kinds[op[0]] = kinds.get(op[0], 0) + 1
        if op[0] in ("template", "form"):
            slots += len(op[2])
    label = {"line": "글자 줄", "rich_line": "서식 적용 줄",
             "template": "템플릿", "form": "양식", "table": "표"}
    parts = [f"{label.get(k, k)} {v}개" for k, v in kinds.items()]
    if slots:
        parts.append(f"빈칸 {slots}개 채움")
    if warns:
        parts.append(f"주의 {len(warns)}건")
    return " · ".join(parts) or "바꿀 내용 없음"


def _confirm_plan(ops, warns):
    """되돌리기 어려운 변환 전에 무엇이 일어날지 보여주고 확인받는다.

    변환은 선택 영역을 지우고 시작하므로, 잘못 누르면 한글에서 Ctrl+Z 를 여러 번
    눌러야 한다. 파서가 이미 계획(ops)을 다 계산해 두므로 보여주는 비용은 0이다.
    주의가 있거나 문서를 크게 바꿀 때만 묻는다 — 매번 물으면 성가시다.
    """
    heavy = sum(1 for o in ops if o[0] in ("template", "form", "table"))
    if not warns and heavy == 0:
        return True                     # 글자만 바꾸는 가벼운 변환은 그냥 진행
    lines = ["이렇게 바꿉니다:", "", "  " + _plan_summary(ops, warns)]
    if warns:
        lines += ["", "주의:"] + [f"  · {w}" for w in warns[:6]]
        if len(warns) > 6:
            lines.append(f"  … 외 {len(warns) - 6}건")
    lines += ["", "진행할까요?"]
    return messagebox.askokcancel("변환 미리보기", "\n".join(lines))


def fn_convert():
    """선택 영역 마크다운 변환 — 시험문제 문법 또는 라이브러리 \\라벨\\ 문법"""
    hwp_engine._diag("fn_convert: 버튼 눌린 직후")
    if not ensure_hwp(): return
    hwp_engine._diag("fn_convert: ensure_hwp 후")
    try:
        selected = read_selected_text()
        hwp_engine._diag("fn_convert: read_selected_text(Copy) 후")
        if not selected or not selected.strip():
            messagebox.showwarning("선택 없음",
                "한글에서 변환할 텍스트를 드래그로 선택해주세요.")
            return
        data = md_parser.parse(selected)
        if md_parser.has_recognized_content(data):
            # 시험문제 변환 (기존 동작)
            hwp_engine.delete_selection()
            should_increment = exam_engine.insert_question(data, num_var.get(), num_use.get())
            hwp_engine._diag("fn_convert: insert_question(시험문제 변환) 후")
            if should_increment:
                num_var.set(num_var.get() + 1)
            notify("ok", "변환 완료!")
            return
        if md_parser.has_library_tokens(selected):
            # 라이브러리 변환: \라벨\ → 문자 치환 / 템플릿 삽입 + 빈칸 채움
            lookup = library.label_lookup()
            ops, warns = md_parser.build_library_plan(selected, lookup)
            # 양식은 '새 문서를 여는' 것이라, 같은 선택에 딸린 다른 내용은 갈 곳이
            # 없다. 예전에는 선택을 지운 뒤에야 그 사실이 드러나 사용자 글이 조용히
            # 사라졌다 → 지우기 전에 막는다.
            blocked = _form_plan_conflict(ops)
            if blocked:
                messagebox.showwarning("양식은 따로 변환해주세요", blocked)
                notify("warn", "양식은 라벨만 따로 선택해 변환해주세요")
                return
            if not _confirm_plan(ops, warns):
                notify("info", "변환을 취소했습니다")
                return
            # 표 안에서는 '선택을 통째로 지우고 한 곳에 다시 쓰기'를 하면 안 된다.
            # 셀마다 리스트가 따로라 경계가 사라져, 여러 셀의 내용이 한 셀에 쌓인다
            # (셀마다 사진 하나씩 넣었을 때 한 칸에 몰리던 버그). 제자리 변환으로 간다.
            # 템플릿·양식은 마커를 심는 2단계 방식이 필요해 기존 경로를 그대로 쓴다.
            simple_only = all(op[0] in ("line", "rich_line") for op in ops)
            if simple_only and hwp_engine.in_table():
                hwp_engine.cancel_selection()
                anchor = hwp_engine.current_pos()
                units = md_parser.split_selection_units(selected)
                changed = engine_library.convert_units_in_place(
                    units, lambda u: md_parser.build_library_plan(u, lookup), anchor)
                hwp_engine._diag("fn_convert: convert_units_in_place(표 안) 후")
                msg = f"✅ 라이브러리 변환: 셀 {changed}곳"
                if warns:
                    notify("warn", f"{msg}  (주의 {len(warns)}건 — 눌러서 보기)",
                           detail="\n".join(warns))
                else:
                    notify("ok", msg)
                return
            hwp_engine.delete_selection()
            result = engine_library.execute_library_plan(
                ops, library.template_path, form_path_fn=library.template_path)
            hwp_engine._diag("fn_convert: execute_library_plan 후")
            if result.get("error"):
                applog.warn(f"라이브러리 변환 실패: {result['error']}")
                messagebox.showerror("변환 실패", result["error"])
                notify("warn", f"{result['error']}")
                return
            # 빈칸을 다 못 채우고 멈추는 일이 있다(사진 뒤에서 멈추던 문제).
            # 조용히 넘기면 인쇄물을 보고서야 알게 되므로 눈에 띄게 알린다.
            short = result.get("slots_wanted", 0) - result["slots_filled"]
            if short > 0:
                warns = list(warns) + [
                    f"빈칸 {short}개를 채우지 못하고 멈췄습니다 "
                    f"({result['slots_filled']}/{result.get('slots_wanted')}개 채움). "
                    "템플릿의 빈칸 수와 넣으려는 줄 수가 맞는지 확인해주세요."]
            if result.get("forms"):
                msg = f"✅ 양식 열기 완료 (빈칸 {result['slots_filled']}개 채움)"
            else:
                msg = (f"✅ 라이브러리 변환: 템플릿 {result['templates']}개, "
                       f"빈칸 {result['slots_filled']}개")
            if warns:
                # 경고를 목록에도 남긴다 — 창을 닫아도 상태줄 클릭으로 다시 본다
                notify("warn", f"{msg}  (주의 {len(warns)}건 — 눌러서 보기)",
                       detail="\n".join(warns))
                messagebox.showwarning("변환 주의", "\n".join(warns[:8]))
            else:
                notify("ok", msg)
            return
        messagebox.showwarning("파싱 실패",
            "마크다운 형식을 인식하지 못했어요.\n"
            "시험문제: '발문:', '자료:', '질문:', '보기:', '선지:'\n"
            "라이브러리: \\라벨\\ (등록한 라벨)")
        notify("warn", "마크다운 형식을 인식하지 못했습니다")
    except Exception as e:
        # detail=True — 변환은 단계가 많아 스택 없이는 원인 지점을 못 찾는다
        report_error("마크다운 변환 실패", e, detail=True)


def fn_reset_format():
    """선택 영역을 환경설정의 기본 서식으로 되돌림 (원문자 삭제 포함)."""
    if not ensure_hwp(): return
    try:
        if not hwp_engine.has_selection():
            messagebox.showwarning("선택 없음",
                "기본으로 되돌릴 영역을 드래그로 선택해주세요.")
            return
        selected = read_selected_text()
        if not selected:
            messagebox.showwarning("읽기 실패",
                "선택 내용을 읽지 못했어요. 영역을 다시 드래그한 뒤 시도해주세요.")
            return
        cleaned = md_parser.strip_circled_markers(selected)
        engine_library.apply_default_format(palette.get_default_format(), text=cleaned)
        notify("ok", "기본 서식으로 변환")
    except Exception as e:
        report_error("기본 서식 변환 실패", e)


def fn_open_palette_settings():
    return _single("settings",
                   lambda: palette_ui.open_settings(root, on_saved=render_palette))


def fn_pick_photo():
    """사진 삽입 — 파일 선택 후 커서 위치(셀)에 삽입 (따로 뺀 기능)."""
    if not ensure_hwp(): return
    path = filedialog.askopenfilename(
        title="삽입할 사진 선택",
        filetypes=[("이미지", "*.png *.jpg *.jpeg *.gif *.bmp *.tif *.tiff *.webp"),
                   ("모든 파일", "*.*")])
    if not path:
        return
    try:
        hwp_engine.insert_picture_to_cell(path)
        notify("ok", f"사진 삽입: {pathlib.Path(path).name}")
    except Exception as e:
        report_error(f"사진 삽입 실패: {pathlib.Path(path).name}", e)


def _template_path_by_ref(block):
    """블럭이 가리키는 템플릿의 조각 경로. ref(id) 우선, 없으면 이름(구 데이터)."""
    it = library.get_item("템플릿", item_id=block.get("ref"),
                          name=block.get("template"))
    return library.template_path(it) if it else None


def _template_slot_count_by_ref(block):
    r"""블럭이 가리키는 템플릿의 빈칸(\) 개수. 빈칸 청소 범위를 개수로 제한한다."""
    it = library.get_item("템플릿", item_id=block.get("ref"),
                          name=block.get("template"))
    return int(it.get("slot_count") or 0) if it else None


def _form_path_by_ref(block):
    """블럭/항목이 가리키는 양식 파일 경로."""
    it = library.get_item("양식", item_id=block.get("ref") or block.get("id"),
                          name=block.get("form") or block.get("name"))
    return library.template_path(it) if it else None


# 프로그램 기능 블럭('도구') → 실제 함수. 키는 builtin_actions 가 정한다.
# 여기서 잇는 이유: builtin_actions 는 데이터만 갖고 UI 를 임포트하지 않는다.
BUILTIN_DISPATCH = {
    "convert":      lambda: fn_convert(),
    "reset_format": lambda: fn_reset_format(),
    "photo":        lambda: fn_pick_photo(),
    "special":      lambda: fn_open_library(cat="내장"),
    "form_fill":    lambda: fn_open_form_fill(),
    "library":      lambda: fn_open_library(),
    "search":       lambda: _open_search(),
}


def run_palette_block(block):
    """팔레트 블럭 클릭 — 종류에 따라 삽입/적용."""
    if block.get("type") == "builtin":
        # 프로그램 기능은 한글 연결 없이도 여는 것이 있다(라이브러리·찾기).
        # 연결이 필요한 것은 각 함수가 스스로 ensure_hwp 를 한다.
        key = block.get("key")
        run = BUILTIN_DISPATCH.get(key)
        if run is None:
            notify("warn", f"모르는 도구입니다: {key}")
            return
        try:
            run()
        except Exception as e:
            report_error(f"도구 실행 실패: {builtin_actions.name_of(key)}", e,
                         detail=True)
        return
    if not ensure_hwp(): return
    try:
        ok, msg = engine_library.run_block(
            block, template_path_fn=_template_path_by_ref,
            form_path_fn=_form_path_by_ref,
            slot_count_fn=_template_slot_count_by_ref)
        if not ok:
            applog.warn(f"팔레트 블럭 실행 거부: {msg}")
        notify("ok" if ok else "warn", msg)
    except Exception as e:
        report_error("팔레트 블럭 실행 실패", e, detail=True)


# ── UI 색 ─────────────────────────────────────
# 값은 theme.py 에 있다 (밝게/어둡게 두 벌). 여기서는 이름만 받아 쓴다 —
# 아래 코드가 BG/TEXT 를 수백 번 참조하므로 이름은 그대로 둔다.
_C     = theme.colors()
BG     = _C["bg"]
CARD   = _C["card"]
ACCENT = _C["accent"]
GREEN  = _C["green"]
YELLOW = _C["yellow"]
TEXT   = _C["text"]
MUTED  = _C["muted"]
FAINT  = _C["faint"]              # MUTED 보다 흐림 (저작권 등 '있는 글'용)
BORDER = _C["border"]
ACCENT_SOFT = _C["accent_soft"]   # 강조색의 옅은 판 ('지금 켜져 있음' 표시)
SUBBG  = _C["subbg"]
FONT   = theme.FONT

# 화면 크기 모드 — '크게'(1.3배)로 두면 글자·칸이 모두 30% 커진다.
# 위젯을 만든 뒤에는 일괄 변경이 안 되므로(각각 폰트를 다시 줘야 함),
# 시작할 때 읽어서 모든 크기에 곱하고, 전환 시에는 프로그램을 다시 시작한다.
SCALE = settings.get_ui_scale()


def _font(size, weight=None):
    # 배율(25% 확대)과 Pretendard 보정은 theme.fs 한 곳에서 — 다른 창들과 같은 규칙
    n = theme.fs(int(round(size * SCALE)))
    return (FONT, n) if weight is None else (FONT, n, weight)


root = tk.Tk()
root.title(appinfo.WINDOW_TITLE)
root.configure(bg=BG)
root.resizable(False, False)
root.attributes("-topmost", True)

# ── 앱 아이콘 (사용자 제작 hwp-final.svg 를 PNG 로 구운 것) ──
# 창 안 제목줄을 없앤 뒤로는 제목표시줄·작업표시줄용 한 벌만 있으면 된다
# (창 안 표기용 24px 축소본과 창 끌기 함수도 같이 필요 없어졌다).
_ICON_96 = paths.RESOURCE_DIR / "assets" / "icon-96.png"
_icon_img = None
try:
    _icon_img = tk.PhotoImage(file=str(_ICON_96))
    root.iconphoto(True, _icon_img)                    # 작업표시줄/제목표시줄
except Exception as e:
    applog.exc("앱 아이콘 로드 실패 — 기본 아이콘으로 실행", e)


# '어둡게 / 크게' 전환은 화면에서 뺐다 (사용자 결정 2026-07-25 — "심플한 게 제일").
# 그 버튼들만 쓰던 _restart / _toggle_scale / _toggle_theme 도 함께 지웠다.
# 값은 config.json 의 ui_scale · theme 에 그대로 살아 있어 theme.py·settings.py 가
# 읽는다. 다시 고르게 하고 싶어지면 메인 화면이 아니라 환경설정 창에 넣는 게 맞다.


# 창 안의 제목줄은 두지 않는다 (2026-07-25).
#
# 윈도우 제목표시줄이 이미 아이콘 + "hwp_palette v1.3.0" 을 보여주는데 창 안에서
# 똑같은 것을 한 번 더 그리고 있었다 — 아이콘도 이름도 두 번씩 나와 난잡했다.
# 제목표시줄이 창 이동·최소화·닫기를 다 해 주므로 직접 그릴 이유가 없다.
# 여기에만 있던 **한글 연결 표시등**은 아래 구역3(설정·기타) 줄로 옮겼다.

# ══════════════════════════════════════════════════════
# 구역 3 — 설정·기타 (2026-07-25)
#
# 화면을 세 구역으로 나눈다: ③설정·기타 → ①공통도구 → ②상황별도구.
# 설정을 맨 위에 둔 이유(사용자 결정): 작업 도구가 아니므로 위로 밀어두면
# 아래 두 구역이 '손이 가는 곳'으로 붙어 이어진다.
# 바탕을 CARD 로 깔아 **작업 도구가 아님**을 눈으로 구분한다.
#
# 예전에 이 줄에 있던 것들을 뺀 이유:
#   새 문서 · 열기 · 저장 — 한글이 이미 가진 기능이라 중복이었다.
#   양식(조판 스펙 설정) — 템플릿으로 골격을 저장하는 방식이 자리를 잡아 안 쓴다.
#   환경설정 — 아래 '설정' 과 같은 창이라 하나로 합쳤다.
# ══════════════════════════════════════════════════════
misc_row = tk.Frame(root, bg=CARD, padx=10, pady=2)
misc_row.pack(fill="x")


# 설정은 **버튼 하나**로 모은다 (사용자 결정 2026-07-25).
#
# '라이브러리'와 '설정'이 나란히 있으면 둘 다 설정인데 이름만 다른 것처럼
# 보였다. 톱니 하나를 누르면 무엇을 설정할지 고르게 하면, 평소 화면에서는
# 버튼 한 개만 보이고 관계도 분명해진다.
#   팔레트 설정 = 버튼(물감)을 어디에 놓을지     (palette_ui)
#   물감 설정   = 무엇을 넣어 둘지 (서식·문자·템플릿·양식)  (library_ui)
# 메뉴는 윈도우 기본 tk.Menu 가 아니라 자체 팝오버(popover.py)로 그린다
# (사용자 지적 2026-07-25: 기본 메뉴가 프로그램의 나머지와 따로 놀았다).
# 버튼은 메뉴가 떠 있는 동안 켜져 있다가(on_close 로) 닫힐 때 꺼진다.
def _settings_menu(anchor_widget):
    _bar_active(anchor_widget, True)
    (Popover(root, anchor_widget,
             on_close=lambda: _bar_active(anchor_widget, False))
     .add("팔레트 설정", fn_open_palette_settings)
     .add("물감 설정", lambda: fn_open_library())
     .show())


# 이 줄의 생김새 (사용자 결정 2026-07-25 — "심플하게").
#
# 글자 버튼 두 개를 아래 블럭과 같은 크기로 맞춰 봤더니, 안 쓰는 버튼이 화면에서
# 가장 큰 덩어리가 되고 상자 안은 텅 비어 보였다. 그래서 **기호만 남기고 상자를
# 벗긴다**:
#   · 정사각 기호 버튼 — 톱니(설정) · 물음표(사용법). 이름은 툴팁으로 말한다.
#   · 모서리는 6px — 아래 블럭(8px)보다 조여, 같은 계열이되 도구가 아님을 알린다.
#   · 평소엔 테두리도 배경도 없다. 마우스를 올리면 옅은 회색, 눌러서 무언가
#     열려 있는 동안(메뉴·사용법)에는 옅은 파랑 + 파란 기호.
#   · 줄 높이는 버튼 크기 그대로 — 예전 두 칸 높이의 절반쯤이다.
_BAR_BTN_PX = int(round(26 * SCALE))     # 정사각 한 변


def _bar_btn(text, cmd, tip):
    b = RoundButton(misc_row, text=text, command=cmd, bg=CARD, fg=MUTED,
                    radius=6, font=_font(9), outline="", zone_bg=CARD)
    b.config(width=_BAR_BTN_PX, height=_BAR_BTN_PX)   # fit() 대신 정사각 고정
    # 기호만 있으므로 이름은 툴팁이 맡는다. _add_tooltip 은 이 줄보다 아래에서
    # 정의되므로(파일 순서), 화면이 다 만들어진 뒤에 붙인다.
    root.after_idle(lambda: _add_tooltip(b, tip))
    return b


def _bar_active(btn, on):
    """켜짐 표시 — 눌러서 연 것(메뉴·사용법)이 닫힐 때까지 옅은 파랑으로 둔다."""
    btn.retint(bg=ACCENT_SOFT if on else CARD, fg=ACCENT if on else MUTED)


_gear = _bar_btn("⚙", lambda: _settings_menu(_gear), "설정")
_gear.pack(side="left")
# 도움말은 물음표 — 가장 널리 쓰이는 관습이라 글자를 안 읽어도 안다
_help_btn = _bar_btn("?", lambda: _toggle_guide(), "사용법")
_help_btn.pack(side="left", padx=(4, 0))

# 상태줄(최근 알림)을 이 줄 오른쪽 빈 자리에 둔다 (2026-07-25).
#
# 맨 아래에 따로 한 줄을 쓰던 것을 옮겼다 — 여기는 어차피 비어 있던 공간이고,
# 알림은 **작업 중 눈이 가는 위쪽**에 있어야 보인다. 누르면 지난 알림이 펼쳐진다.
# 초기값을 짧게 두는 이유: 이 줄의 일은 '방금 무슨 일이 있었는지'를 말하는 것이라
# 늘 같은 안내가 박혀 있으면 정작 알림이 와도 눈에 안 들어온다.
# 처음에는 비워 둔다 — 알림이 왔을 때만 말한다 ('준비됨'은 뜻이 없었다)
status_var = tk.StringVar(value="")
status_lbl = tk.Label(misc_row, textvariable=status_var, font=_font(8),
                      fg=MUTED, bg=CARD, cursor="hand2", anchor="e")
status_lbl.pack(side="right")
status_lbl.bind("<Button-1>", lambda e: _show_notice_log())

# 한글 연결 표시등 (UI 제안 4) — 눌러서 실패해야 알던 것을 미리 보여준다.
# 알림 **바로 왼쪽**에 둔다: 둘 다 '지금 상태'를 말하는 것이라 붙어 있어야 읽힌다.
# (side="right" 는 나중에 붙일수록 왼쪽으로 간다 — 그래서 알림 다음에 넣는다)
# 알림등 (2026-07-25) — 한글 연결 표시등이던 자리를 물려받았다.
#
# 연결 여부는 버튼을 눌러 보면 그때 알 수 있어 늘 지켜볼 이유가 없었다.
# 대신 **방금 한 일이 잘 됐는지**를 색으로 말한다: 초록이면 괜찮고, 빨강이면
# 무언가 잘못됐다. 눌러 보면 지난 알림이 펼쳐진다.
_DOT_COLORS = {"ok": "#34c759", "info": "#34c759",
               "warn": "#ff9500", "error": "#ff3b30"}
conn_dot = tk.Label(misc_row, text="●", font=_font(9),
                    fg=_DOT_COLORS["ok"], bg=CARD, cursor="hand2")
conn_dot.pack(side="right", padx=(0, 6))
conn_dot.bind("<Button-1>", lambda e: _show_notice_log())


def set_dot(kind):
    """알림등 색 — ok/info 초록, warn 주황, error 빨강."""
    try:
        conn_dot.config(fg=_DOT_COLORS.get(kind, _DOT_COLORS["ok"]))
    except Exception:
        pass

# '어둡게 / 크게' 버튼은 뺐다 (사용자 결정 2026-07-25 — "심플한 게 제일").
# 값 자체는 config 에 남아 있어 theme.py·settings.py 가 그대로 읽는다.
tk.Frame(root, bg=BORDER, height=1).pack(fill="x")

# 안내 (접이식)
#
# **래퍼 프레임에 넣지 않고 root 에 직접 붙인다** (2026-07-25).
# 예전에는 guide_wrap 안에 넣었는데, 자식을 pack_forget 해도 래퍼가 **원래
# 높이를 계속 붙들고 있어** 창이 안 줄어들었다(실측: 펼침 357 → 접음 357).
# 자식을 destroy 해도 마찬가지였다. root 에 직접 붙이면 357 → 51 로 제대로 준다.
_guide_open = [False]
guide_body = tk.Frame(root, bg=SUBBG, highlightbackground=BORDER,
                      highlightthickness=1)

GUIDE_TEXT = (
    "■ 시험문제 문법 (한 문항을 통째로 변환)\n"
    "  발문:  …   → 1. …  (문항 번호 자동)\n"
    "  질문:  …   → 들여쓴 질문 문단\n"
    "  보기:      → 〈보 기〉 박스, 아랫줄이 ㄱ.ㄴ.ㄷ.\n"
    "  선지:      → ① ② ③ … 표 배치 (선지1/선지3/선지5)\n"
    "\n"
    "■ 라이브러리 문법 (등록한 항목 호출)\n"
    "  \\라벨\\        → 문자·문구 삽입 / 템플릿 삽입\n"
    "  \\원1\\ \\로마3\\ → 내장 문자 (① Ⅲ …)\n"
    "  \\사진이름\\     → 사진 폴더의 그림 삽입 (라이브러리 창에서 폴더 연결)\n"
    "\n"
    "■ 서식 적용 (LaTeX 스타일 — \\명령{적용할 부분})\n"
    "  \\굵게{중요}          → 그 부분만 굵게\n"
    "  \\굵게\\기울임\\15{…}  → 명령을 원하는 만큼 쌓기 (숫자=크기 pt)\n"
    "  \\크기15 \\자간-5 \\색빨강 \\함초롬바탕 \\글꼴나눔고딕\n"
    "  \\내강조{…}           → 등록해 둔 서식도 명령처럼\n"
    "  { } 안에는 \\라벨\\ 도, 빈칸 \\ 도, 다른 서식도 넣을 수 있습니다\n"
    "  글자 그대로의 역슬래시가 필요하면 \\\\ 로 씁니다\n"
    "  템플릿은 단독 줄로 쓰고, 아랫줄들이\n"
    "  템플릿 속 빈칸 \\ 에 위에서부터 순서대로 채워집니다.\n"
    "  (비울 칸에는 '-' 한 줄)\n"
    "\n"
    "■ 단축키\n"
    "  Ctrl+Alt+T  마크다운 변환 — 한글에서 눌러도 먹습니다\n"
    "  (아래는 이 창이 선택돼 있을 때만)\n"
    "  Ctrl+T  마크다운 변환      Ctrl+K  찾기(블럭·라이브러리)\n"
    "  Ctrl+1~9  지금 탭의 1~9번째 블럭 실행 (위→아래, 왼→오 순서)\n"
    "\n"
    "※ 변환할 부분을 한글에서 드래그 → Ctrl+Alt+T\n"
    "※ 되돌리기: 한글 창에서 Ctrl+Z. 템플릿 삽입·변환은 여러 동작이 묶여\n"
    "   있어 여러 번 눌러야 완전히 돌아갑니다. (되돌리기는 한글이 하는 것이라\n"
    "   이 창의 버튼으로는 취소되지 않습니다)\n"
    "\n"
    # 버전·날짜를 메인 화면 하단에서 여기로 옮겼다 (2026-07-25).
    # 평소엔 볼 일이 없고, 필요할 때는 이 화면에서 찾으면 된다.
    f"■ 버전\n  v{VERSION} · {RELEASE_DATE} · 자유 소프트웨어 (AGPL-3.0)"
)
tk.Label(guide_body, text=GUIDE_TEXT, font=("Consolas", 8),
         fg=TEXT, bg=SUBBG, justify="left").pack(anchor="w", padx=12, pady=10)

def _toggle_guide():
    """사용법 펼치기/접기 — 구역3의 '사용법' 버튼이 부른다.

    예전에는 본문 위에 '마크다운 입력 형식 보기' 링크가 늘 한 줄을 차지했다.
    가끔 보는 것이라 구역3(설정·기타)으로 옮겼다.
    """
    if _guide_open[0]:
        guide_body.pack_forget()
        _guide_open[0] = False
    else:
        # before= 로 자리를 지정한다 — pack 순서는 '부른 순서'라 그냥 pack 하면
        # 창 맨 아래(저작권 밑)에 붙는다. 안내는 설정 줄 바로 밑이어야 한다.
        guide_body.pack(fill="x", padx=10, pady=(6, 0), before=common_zone)
        _guide_open[0] = True
    # 펼쳐 있는 동안 '?' 를 켜 둔다 — 지금 켜져 있음이 버튼에서 보인다
    _bar_active(_help_btn, _guide_open[0])
    # 창 높이를 **이징으로** 목표까지 옮긴다 (2026-07-25). 한 번에 튀면
    # 화면이 순간 이동한 것처럼 보여 '버벅인다'고 느껴진다.
    root.update_idletasks()
    _glide_to_height(root.winfo_reqheight())


_glide_job = [None]


def _glide_to_height(target):
    """창 높이를 ease-out 으로 target 까지. 끝나면 자연 크기로 복귀."""
    if _glide_job[0] is not None:
        try:
            root.after_cancel(_glide_job[0])
        except Exception:
            pass
        _glide_job[0] = None
    start = root.winfo_height()
    width = root.winfo_width()
    if abs(target - start) < 4:             # 티도 안 나는 거리 — 바로 맞춘다
        root.geometry("")
        return

    def step(k):
        _glide_job[0] = None
        t = ui_fx.ease_out(k / ui_fx.STEPS)
        h = int(start + (target - start) * t)
        try:
            if k < ui_fx.STEPS:
                root.geometry(f"{width}x{h}")
                _glide_job[0] = root.after(ui_fx.INTERVAL_MS,
                                           lambda: step(k + 1))
            else:
                # 마지막엔 '내용에 맞춤'으로 되돌린다 — 고정 크기로 남겨두면
                # 이후 탭 전환 때 창이 내용을 안 따라간다
                root.geometry("")
        except Exception:
            root.geometry("")

    step(1)

# 문항 번호 — UI 는 없앴다(사용자 결정 2026-07-19). 시험문제 변환이 여전히
# 번호를 쓰므로 변수만 남겨 자동 증가한다. 초기화는 프로그램 재시작.
num_use = tk.BooleanVar(value=True)
num_var = tk.IntVar(value=1)

# ══════════════════════════════════════════════════════
# 구역 1 — 공통도구 (어느 탭에서나 늘 보이는 것)
#
# 위: 고정 기능. **아이콘만 두지 않고 이름을 글자로 남긴다** — 아이콘만 남기면
#     화면은 깔끔해지지만 무엇인지 못 찾게 되어 손해가 더 크다(사용자 지적).
# 아래: 사용자가 '메인' 탭에 채워 넣은 블럭 (quick_area).
# ══════════════════════════════════════════════════════
def _zone_label(parent, text, bg):
    """구역 이름표 — 그 구역의 바탕색 위에 얹는다."""
    tk.Label(parent, text=text, font=_font(7), fg=MUTED, bg=bg,
             anchor="w").pack(fill="x", padx=10, pady=(5, 0))


# 구역은 **바탕색**으로 가른다 (2026-07-25). 선을 더 긋는 것보다 색이 훨씬 강하게
# 나누고, 구역 사이 여백을 넉넉히 주면 선이 아예 필요 없다.
# 공통도구 = 기본 바탕 / 문서별 팔레트 = 살짝 다른 바탕.
common_zone = tk.Frame(root, bg=BG)
common_zone.pack(fill="x", pady=(0, 12))          # 구역 사이 여백
_zone_label(common_zone, "공통 팔레트", BG)

btn_area = tk.Frame(common_zone, bg=BG, padx=10, pady=2)
btn_area.pack(fill="x")

# 변환 버튼도 이제 **메인 탭의 도구 블럭**이다 (사용자 결정 2026-07-25).
#
# 예전에는 여기 고정 위젯으로 박혀 있고 크기는 별도 설정 창에서 고쳤다.
# 하나뿐인 버튼을 위해 전용 설정 창을 두는 것이 어색했고, 다른 도구는 다
# 블럭인데 이것만 예외인 것도 관성이 어긋났다. 이제 다른 블럭과 똑같이
# 끌어서 옮기고 크기를 바꾸고 이름도 고칠 수 있다.
# 대신 **마지막 하나는 지울 수 없다** (palette.protected_key_of).
quick_area = tk.Frame(btn_area, bg=BG)
quick_area.pack(fill="x")


# ══════════════════════════════════════════════════════
# 구역 2 — 개인 팔레트 (탭으로 갈아끼우는 것)
#
# 이름을 '상황별도구'에서 바꿨다 (사용자 결정 2026-07-25): 탭이 실제로
# 수능·학교 시험문제처럼 **만드는 문서 종류**로 갈리므로, 이름만 보고
# 무슨 기준으로 탭을 만들지 알 수 있어야 한다.
# ══════════════════════════════════════════════════════
doc_zone = tk.Frame(root, bg=SUBBG)
doc_zone.pack(fill="x", pady=(0, 10))

_pal_state = {"tab": 0}

# 팔레트 고르기 = **이름표 옆 드롭다운** (사용자 결정 2026-07-25).
#
# 예전에는 탭 버튼을 한 줄로 늘어놓았다. 팔레트가 늘수록 그 줄이 길어져 창 폭을
# 끌고 다녔고, 이름이 긴 팔레트('학교 시험문제')가 있으면 줄이 통째로 넓어졌다.
# 이름표 오른쪽에 붙이면 '개인 팔레트 [수능 ▾]' 가 한 문장처럼 읽히고, 줄 하나가
# 통째로 없어진다. 대신 고르는 데 두 번 눌러야 한다 — 팔레트가 서넛 이상으로
# 늘어날수록 이쪽이 유리하다는 판단.
pal_head = tk.Frame(doc_zone, bg=SUBBG)
pal_head.pack(fill="x", padx=10, pady=(5, 0))
tk.Label(pal_head, text="개인 팔레트", font=_font(7), fg=MUTED,
         bg=SUBBG).pack(side="left")

_PAL_NAME_MAX = 12      # 이름이 길어도 이 창 폭을 끌고 다니지 않게

pal_pick = RoundButton(pal_head, text="", command=lambda: _pal_menu(),
                       bg=CARD, fg=TEXT, radius=6, font=_font(8),
                       outline=BORDER, focus_color=ACCENT, zone_bg=SUBBG)
pal_pick.pack(side="left", padx=(6, 0))

pal_area = tk.Frame(doc_zone, bg=SUBBG, padx=10, pady=2)
pal_area.pack(fill="x", pady=(3, 6))


def _pal_tabs():
    """개인 팔레트 목록 — '메인' 탭은 위 공통 팔레트로 그려지므로 뺀다."""
    return [t for t in palette.load_tabs()
            if t.get("name") != palette.MAIN_TAB]


def _pal_pick_text(tabs, cur):
    if not tabs:
        return "팔레트 없음  ▾"
    name = tabs[min(cur, len(tabs) - 1)]["name"]
    if len(name) > _PAL_NAME_MAX:
        name = name[:_PAL_NAME_MAX - 1] + "…"
    return f"{name}  ▾"          # ▾ 로 '눌러서 고르는 것'임을 알린다


def _sync_pal_pick(tabs=None, cur=None):
    """고르개에 지금 팔레트 이름을 써 넣는다 (폭도 다시 잰다)."""
    tabs = _pal_tabs() if tabs is None else tabs
    cur = _pal_state["tab"] if cur is None else cur
    pal_pick.set_text(_pal_pick_text(tabs, cur), pad_x=9, pad_y=3)


def _pal_menu():
    """팔레트 고르개 — 지금 것에 ✓ 가 붙고, 맨 아래에서 관리 창으로 간다.

    윈도우 기본 메뉴 대신 자체 팝오버(popover.py) — 블럭과 같은 글꼴·색·호버.
    """
    tabs = _pal_tabs()
    pal_pick.retint(bg=ACCENT_SOFT, fg=ACCENT)      # 열려 있는 동안 켜 둔다
    pop = Popover(root, pal_pick,
                  on_close=lambda: pal_pick.retint(bg=CARD, fg=TEXT))
    for i, t in enumerate(tabs):
        pop.add_check(t["name"], lambda idx=i: _select_pal_tab(idx),
                      checked=(i == _pal_state["tab"]))
    if tabs:
        pop.separator()
    # 팔레트를 새로 만들려고 설정을 뒤지던 것을 여기서 바로 갈 수 있게 한다
    pop.add("팔레트 관리…", fn_open_palette_settings, indent=True)
    pop.show()


def _select_pal_tab(i):
    """탭 전환 — 탭 버튼은 **색만 갈아끼우고** 블럭 영역만 다시 그린다.

    예전에는 render_palette() 가 탭 줄까지 통째로 부수고 다시 만들어, 탭을
    누를 때마다 버튼들이 사라졌다 나타나며 번쩍였다 (2026-07-25).
    같은 버튼을 그대로 두고 색만 바꾸면 그 깜빡임이 사라진다.
    """
    if _pal_state["tab"] == i:
        return                              # 같은 탭 — 아무것도 할 필요 없다
    _pal_state["tab"] = i
    _sync_pal_pick()                    # 고르개에 새 이름을 써 넣는다
    _render_current_tab()
    root.after_idle(_fit_window)        # 탭마다 격자 크기가 달라 창도 맞춘다


def _fit_window():
    """창 크기를 내용에 맞춘다 — 이미 맞으면 건드리지 않는다.

    geometry("") 는 매번 창을 다시 배치해, 탭만 바꿔도 창 전체가 한 번
    번쩍였다 (2026-07-25). 크기가 실제로 달라질 때만 부른다.
    """
    try:
        need = (root.winfo_reqwidth(), root.winfo_reqheight())
        if need != (root.winfo_width(), root.winfo_height()):
            root.geometry("")
    except Exception:
        root.geometry("")


def _render_current_tab(tabs=None):
    r"""지금 탭의 격자를 보여준다 — **탭마다 한 번만 그리고 재사용한다**.

    부수고 다시 그리면 그 사이 빈 화면이 한 프레임 비쳐 전환마다 번쩍였다
    (2026-07-25, '엄청나게 버벅거린다'의 원인). 격자를 탭별로 캐시에 들고
    있다가 pack_forget/pack 만 하면 이미 그려진 픽셀이 그대로 나타난다.
    캐시는 render_palette(설정 변경 시 전체 재빌드)가 비운다.
    """
    if tabs is None:
        tabs = [t for t in palette.load_tabs()
                if t.get("name") != palette.MAIN_TAB]
    if not tabs:
        return
    cur = min(_pal_state["tab"], len(tabs) - 1)

    shown = _pal_state.get("shown_frame")
    if shown is not None:
        try:
            shown.pack_forget()
        except Exception:
            pass

    cache = _pal_state.setdefault("tab_frames", {})
    frame = cache.get(cur)
    if frame is None or not frame.winfo_exists():
        frame = tk.Frame(pal_area, bg=SUBBG)
        tab = tabs[cur]
        if not tab.get("blocks"):
            tk.Label(frame, text="이 탭에 블럭이 없습니다. ‘설정’으로 추가하세요.",
                     font=_font(8), fg=MUTED, bg=SUBBG).pack(anchor="w")
        else:
            _render_block_grid(frame, tab)
        cache[cur] = frame
    frame.pack(anchor="w", fill="x")
    _pal_state["shown_frame"] = frame


def _render_block_grid(parent, tab):
    """탭의 블럭들을 정사각형 격자로 그린다 (팔레트·메인 버튼칸 공용).

    폭을 받지 않는다 — 칸 크기가 먼저 정해지고 **창이 그 결과를 따라간다**.
    """
    cols = max(1, int(tab.get("cols", palette.DEFAULT_COLS)))
    blocks = tab.get("blocks", [])
    cell_px = _adaptive_cell_px(cols)
    # 바탕은 **부모 구역의 색**을 따른다 — 구역마다 바탕이 달라서(공통도구 /
    # 문서별 팔레트) 여기서 BG 로 못박으면 한쪽에서 네모난 얼룩이 생긴다.
    zone_bg = parent.cget("bg")
    grid = tk.Frame(parent, bg=zone_bg)
    grid.pack(anchor="w")
    # 칸을 **실제 쓰는 데까지만** 예약한다 (2026-07-25). 탭의 cols(예: 15)를
    # 전부 잡으면 블럭이 6칸까지만 있어도 창이 15칸 폭으로 벌어진다 — 창 크기는
    # 가장 오른쪽 블럭에 맞아야 한다(빈 칸은 팔레트 설정 창에서나 의미가 있다).
    #
    # 다만 **최소 폭은 지킨다** (사용자 결정 2026-07-25): 블럭이 몇 개 없다고
    # 창이 홀쭉해지면 이름이 잘리고 화면이 초라해 보인다.
    used_cols = max((int(b.get("col", 0)) + max(1, int(b.get("span", 1)))
                     for b in blocks), default=1)
    for i in range(min(cols, max(used_cols, _MIN_GRID_COLS))):
        grid.columnconfigure(i, minsize=cell_px + _BLOCK_GAP_PX, weight=0)
    for blk in blocks:
        span = max(1, min(int(blk.get("span", 1)), cols))
        rows = max(1, int(blk.get("rows", 1)))
        r, c = int(blk.get("row", 0)), int(blk.get("col", 0))
        # 칸을 고정 크기 틀에 넣는다. 버튼을 그냥 grid 에 놓으면 글자 길이에 맞춰
        # 칸이 넓어져 블럭이 정사각형 격자에서 어긋난다.
        cell = tk.Frame(grid, bg=zone_bg,
                        width=cell_px * span + _BLOCK_GAP_PX * (span - 1),
                        height=cell_px * rows + _BLOCK_GAP_PX * (rows - 1))
        cell.pack_propagate(False)
        cell.grid(row=r, column=c, columnspan=span, rowspan=rows,
                  padx=_BLOCK_GAP_PX // 2, pady=_BLOCK_GAP_PX // 2)
        _make_block_button(cell, blk, span).pack(fill="both", expand=True)


def render_palette():
    # 전체 재빌드 (설정 저장·시작 시). 탭 격자 캐시도 여기서 비운다 —
    # 블럭이 바뀌었을 수 있으므로 묵은 격자를 재사용하면 안 된다.
    _pal_state["tab_frames"] = {}
    _pal_state["shown_frame"] = None
    for w in pal_area.winfo_children():
        w.destroy()
    for w in quick_area.winfo_children():
        w.destroy()

    all_tabs = palette.load_tabs()
    # '메인' 탭은 변환 버튼 옆 버튼칸으로 그려진다 — 탭 줄에는 안 나온다
    main_tab = next((t for t in all_tabs
                     if t.get("name") == palette.MAIN_TAB), None)
    tabs = [t for t in all_tabs if t.get("name") != palette.MAIN_TAB]

    if main_tab is not None:
        if main_tab.get("blocks"):
            _render_block_grid(quick_area, main_tab)
        else:
            # 비었을 때 큰 안내문이 자리를 먹지 않게 한 줄 버튼으로 (2026-07-25).
            # 누르면 바로 그 자리를 채우러 갈 수 있어 안내문보다 쓸모 있다.
            tk.Button(quick_area,
                      text="＋ 자주 쓰는 것을 이 자리에 추가",
                      command=lambda: fn_open_palette_settings(),
                      font=_font(8), fg=MUTED, bg=BG,
                      activebackground=BORDER, bd=1, relief="solid",
                      pady=3, cursor="hand2").pack(fill="x")

    if not tabs:
        _sync_pal_pick(tabs, 0)         # 고르개는 '팔레트 없음'으로 두고
        tk.Label(pal_area, text="‘팔레트 관리…’에서 팔레트를 만들어보세요.",
                 font=_font(8), fg=MUTED, bg=SUBBG).pack(anchor="w")
        return
    cur = _pal_state["tab"]
    if cur >= len(tabs):
        cur = _pal_state["tab"] = 0
    # 탭 버튼 줄은 이름표 옆 드롭다운(pal_pick)이 대신한다 — 여기서는 지금
    # 팔레트 이름만 써 넣는다.
    _sync_pal_pick(tabs, cur)

    _render_current_tab(tabs)
    root.after_idle(_fit_window)


# 블럭 종류별 배경색·기호 — 환경설정 미리보기(palette_ui._make_tile/_tile_text)와
# 반드시 같아야 한다. 'form'이 여기에만 빠져 있어서, 양식 블럭이 환경설정에서는
# 📄+연녹색인데 메인 팔레트에서는 ƒ+흰 배경으로 보였다.
# type "function"은 UI에서 '서식 조합'으로 부른다 (개선안 10 — 저장 키는 그대로).
_BLOCK_COLOR = theme.block_colors()

# 팔레트 한 칸의 한 변(px). 칸은 정사각형이고, **칸 수에 맞춰 크기가 변한다** —
# 고정 크기로 두면 칸 수가 적을 때 오른쪽에 빈 공간이 크게 남는다.
# 글자를 25% 키우면서 칸도 같이 키웠다 (34→42) — 안 키우면 두 줄 이름이 넘친다
_BLOCK_CELL_MAX_PX = 42   # SCALE 적용 전 기준값     # 칸 수가 적어도 이보다 크게는 안 키운다
_BLOCK_CELL_MIN_PX = 20     # 칸 수가 많아도 이보다 작아지면 못 누른다
_BLOCK_GAP_PX = 2
# 창이 아무리 홀쭉해져도 이 칸 수만큼은 폭을 잡는다 (사용자 결정 2026-07-25).
# 팔레트 설정 창의 칸 줄이기도 같은 값에서 멈춘다 (palette.MIN_COLS).
_MIN_GRID_COLS = palette.MIN_COLS
# 창 폭을 재서 칸을 맞추던 값들은 필요 없어졌다 (2026-07-25) — 이제 칸 크기가
# 먼저이고 창이 따라간다. 격자가 창 폭을 결정하므로 여백 상수도 쓰지 않는다.


def _adaptive_cell_px(cols):
    """한 칸의 크기(px, 정사각형).

    **칸 수를 늘리면 창이 넓어져야 한다** (사용자 지적 2026-07-25).
    예전에는 지금 창 폭을 칸 수로 나눠 썼다 — 그래서 환경설정에서 칸을 늘려도
    창은 그대로이고 칸만 작아져, 늘린 티가 나지 않았다.
    이제는 칸 크기를 지키고 **창이 내용을 따라 커진다**(render_palette 끝에서
    geometry("") 로 내용에 맞춘다). 세로도 같은 방식이라 줄을 늘리면 창이 길어진다.

    다만 화면 밖으로 나가면 곤란하므로, 그때만 칸을 줄인다.
    """
    if cols <= 0:
        return int(_BLOCK_CELL_MAX_PX * SCALE)
    pref = int(_BLOCK_CELL_MAX_PX * SCALE)
    try:
        screen = root.winfo_screenwidth() - int(120 * SCALE)
    except Exception:
        return pref
    if (pref + _BLOCK_GAP_PX) * cols <= screen:
        return pref
    return max(int(_BLOCK_CELL_MIN_PX * SCALE),
               (screen - _BLOCK_GAP_PX * cols) // cols)


def _block_label_max(span):
    """칸 수에 맞는 **한 줄당** 글자 수 상한.

    칸을 정사각형으로 고정했으므로 긴 이름은 넣을 자리가 없다. 넘치면 잘라서
    보여주고 전체 이름은 툴팁으로 뜬다(_add_tooltip).

    26px 칸에 9pt 한글이 대략 1.7자 들어가므로 칸당 2자로 잡는다.
    이름이 길면 **줄바꿈**을 넣는 게 칸 수를 늘리는 것보다 낫다 — 칸을 늘리면
    창이 그만큼 옆으로 길어진다(2026-07-25).
    """
    return max(2, span * 2)


def _fit_label(text, span):
    r"""블럭에 넣을 글자 — **줄바꿈을 살려서** 줄마다 따로 자른다.

    예전에는 이름 전체를 한 덩어리로 잘라, 긴 이름을 쓰려면 칸을 옆으로 늘리는
    수밖에 없었고 그만큼 창이 좌우로 길어졌다. 이름에 줄바꿈을 넣으면
    '양식\n채우기' 처럼 **좁은 칸에 두 줄**로 들어간다.
    """
    limit = _block_label_max(span)
    lines = (text or "").split("\n")
    return "\n".join(ln if len(ln) <= limit else ln[:limit] + "…"
                     for ln in lines)


def _block_label(blk):
    """블럭에 표시할 이름. 템플릿·양식은 라이브러리의 '현재' 이름을 따라간다."""
    # 사용자가 직접 지은 표시 이름이 있으면 그것이 우선 (줄바꿈 포함 가능).
    # 종류를 가리지 않는다 — 도구·템플릿·양식도 원하는 이름으로 부를 수 있다.
    caption = blk.get("caption")
    if caption:
        return caption
    btype = blk.get("type")
    if btype == "char":
        return blk.get("value", "")
    if btype == "builtin":
        # 이름은 카탈로그에서 — 표기를 고쳐도 기존 블럭이 따라온다
        return builtin_actions.name_of(blk.get("key"))
    if btype in ("template", "form"):
        cat = "양식" if btype == "form" else "템플릿"
        key = "form" if btype == "form" else "template"
        it = library.get_item(cat, item_id=blk.get("ref"), name=blk.get(key))
        return it["name"] if it else f"{blk.get(key, '?')} (삭제됨)"
    return blk.get("name", "")


def _block_tooltip(blk):
    """블럭 툴팁 문구 — 이름뿐 아니라 **내용**까지 보여준다 (UI 제안 6).

    이름만으로는 서식 조합에 뭐가 들었는지, 템플릿에 빈칸이 몇 개인지 알 수 없어
    눌러 봐야 알았다. 툴팁에 미리 적어 두면 잘못 누르는 일이 준다.
    """
    btype = blk.get("type")
    name = _block_label(blk)
    if btype == "builtin":
        key = blk.get("key")
        tip = f"도구 · {name}\n{builtin_actions.hint_of(key)}"
        if key == "convert":    # 단축키는 버튼 글자에 안 적으므로 여기서 알려준다
            tip += f"\n한글에서 드래그한 뒤 {CONVERT_HOTKEY_LABEL} 로도 됩니다"
        return tip
    if btype == "char":
        return f"문자 삽입\n{blk.get('value', '')}"
    if btype == "function":
        parts = []
        for a in blk.get("actions", []):
            v = a.get("value")
            parts.append(a["func"] if v is None else f"{a['func']} {v}")
        return f"서식 조합 · {name}\n" + (" + ".join(parts) or "(비어 있음)")
    if btype in ("template", "form"):
        cat = "양식" if btype == "form" else "템플릿"
        it = library.get_item(cat, item_id=blk.get("ref"),
                              name=blk.get("form" if btype == "form" else "template"))
        if not it:
            return f"{cat} · {name}\n라이브러리에서 삭제된 항목입니다"
        n = int(it.get("slot_count") or 0)
        where = "새 문서로 열기" if btype == "form" else "커서 자리에 삽입"
        blanks = f"빈칸 {n}개 — 변환 시 아랫줄 {n}줄이 채워집니다" if n else "빈칸 없음"
        tip = f"{cat} · {it['name']}\n{where} · {blanks}"
        # 저장할 때 뽑아둔 본문 몇 줄 (UI 제안 7) — 이름이 비슷한 템플릿을
        # 누르기 전에 구별할 수 있게. 예전에 등록한 것은 비어 있어 안 붙는다.
        prev = library.get_preview(it)
        if prev:
            tip += "\n───────────\n" + prev
        return tip
    return name


def _add_tooltip(widget, text, force=False):
    """마우스를 올리면 말풍선을 보여준다 (개선안 15, UI 제안 6).

    블럭 이름은 칸 폭 때문에 잘릴 수밖에 없는데, 잘린 채로는 비슷한 이름을
    구별할 수 없었다. 지금은 이름이 안 잘려도 '내용'을 보여주므로 늘 붙인다.
    force: 문구만 갈아끼우고 싶을 때(연결 표시등처럼 상태가 바뀌는 위젯).
    """
    tip = {"win": None, "text": text, "job": None}
    if force:
        widget._tip_state = tip

    def _show_now():
        tip["job"] = None
        try:
            if not widget.winfo_exists() or tip["win"] is not None:
                return
        except Exception:
            return
        _build_tip()

    def show(_event=None):
        # 바로 띄우지 않고 잠깐 기다린다 (2026-07-25) — 커서가 버튼들 위를
        # 지나갈 때마다 말풍선이 연달아 떴다 사라지며 '버벅이는' 인상을 줬다.
        # 머무를 때만 뜨면 그 소란이 사라진다 (애플 툴팁과 같은 리듬).
        if tip["job"] is None and tip["win"] is None:
            tip["job"] = widget.after(450, _show_now)

    def _build_tip():
        win = tk.Toplevel(widget)
        win.wm_overrideredirect(True)       # 제목표시줄 없는 말풍선
        win.wm_geometry(f"+{widget.winfo_rootx() + 10}"
                        f"+{widget.winfo_rooty() + widget.winfo_height() + 4}")
        # 메인 창이 topmost라 말풍선도 올려주지 않으면 뒤로 숨는다
        win.attributes("-topmost", True)
        tk.Label(win, text=tip["text"], font=_font(8), fg=TEXT, bg="#ffffe0",
                 bd=1, relief="solid", padx=6, pady=3,
                 justify="left").pack()
        tip["win"] = win

    def hide(_event=None):
        if tip["job"] is not None:          # 아직 안 떴으면 예약만 취소
            try:
                widget.after_cancel(tip["job"])
            except Exception:
                pass
            tip["job"] = None
        if tip["win"] is not None:
            tip["win"].destroy()
            tip["win"] = None

    widget.bind("<Enter>", show, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<ButtonPress-1>", hide, add="+")   # 눌렀으면 말풍선은 치운다
    # 탭 전환으로 버튼이 destroy 될 때 <Leave> 가 안 와도 말풍선은 남지 않는다 —
    # Toplevel 을 버튼의 자식으로 만들었기 때문에 Tk 가 함께 정리한다(실측 확인).


def _make_block_button(parent, blk, span=1):
    # 자동 아이콘(▦ ƒ 📄)은 넣지 않는다 — 사용자가 정한 이름 그대로.
    # 종류 구분은 배경색이 하고, 색은 사용자가 지정할 수도 있다(blk["color"]).
    full = _block_label(blk)
    label = _fit_label(full, span)
    bg = theme.block_color(blk)     # 사용자 지정 > 도구 강조(변환) > 종류별 기본
    # 두 줄 이상이면 글자를 한 단계 줄인다 (사용자 결정 2026-07-25) —
    # 9pt 두 줄은 42px 칸에 빈틈없이 꽉 차 답답했다. 칸 크기는 그대로 두고
    # 글자만 줄이면 위아래 숨이 트인다.
    size = 8 if "\n" in label else 9
    # RoundButton (A안): 곡률 8px + 호버 보간 + 누름 침하.
    # 글자색을 TEXT 로 고정하면 사용자가 남색·빨강을 고르거나 어두운 모드로
    # 바꿨을 때 글자가 배경에 묻힌다 (UI 제안 18) — text_on 이 밝기를 재서 정한다.
    # 초점 테두리(키보드 Tab 이동)는 RoundButton 이 자체로 그린다.
    btn = RoundButton(parent, text=label,
                      command=lambda b=blk: run_palette_block(b),
                      bg=bg, fg=theme.text_on(bg), radius=8, font=_font(size),
                      outline=BORDER, focus_color=ACCENT,
                      zone_bg=parent.cget("bg"))
    # 이름이 안 잘려도 '무엇이 들었는지'를 보여주므로 늘 붙인다 (UI 제안 6)
    _add_tooltip(btn, _block_tooltip(blk))
    return btn


render_palette()

# 하단 표기 — 저작권 한 줄만 (사용자 결정 2026-07-25).
#
# 버전은 윈도우 제목표시줄에 이미 있고(hwp_palette v1.3.0), 날짜는 평소에 볼
# 일이 없다. 둘 다 '사용법' 화면 맨 아래로 옮겨 필요할 때만 보이게 했다.
# (CLAUDE.md 의 '하단에 버전+날짜' 규칙에서 벗어나는 부분 — 사용자 확인함)
# 푸터 — 글자를 그 띠의 **한가운데**에 (2026-07-25).
#
# pady 로 맞추려 했지만 계속 위로 붙어 보였다. 위쪽 여백은 이 라벨의 pady 뿐
# 아니라 **바로 위 구역(개인 팔레트)의 아래 여백까지 더해져서**, 라벨만 대칭으로
# 줘도 눈에는 위가 더 넓었다.
# 높이를 고정한 띠를 만들고 그 안에서 expand 로 띄우면, 위에 무엇이 있든
# 글자는 띠의 정중앙에 온다.
# 띠 높이 2.6배→1.9배 (사용자 결정 2026-07-25: "위아래 2mm 더 줄여라").
# 글자색도 MUTED 보다 한 단계 흐린 FAINT — 저작권은 읽으라고 있는 글이
# 아니라 '있다'는 것만 알면 되는 글이다.
_FOOTER_H = int(round(theme.fs(7) * 1.9))
_footer = tk.Frame(root, bg=BG, height=_FOOTER_H)
_footer.pack(fill="x")
_footer.pack_propagate(False)        # 안의 라벨이 높이를 바꾸지 못하게
# 산술 중앙(expand)으로도 눈에는 아래로 처져 보였다 (사용자 확인 2026-07-25) —
# 글자의 시각 무게가 베이스라인 쪽에 쏠려서다. 아래에만 여백을 더해 약 1mm(4px)
# 올린다: pack 은 '라벨+아래 4px' 묶음을 중앙에 놓으므로 글자는 그만큼 위로 간다.
tk.Label(_footer, text=appinfo.COPYRIGHT, font=_font(7), fg=FAINT, bg=BG,
         anchor="center").pack(expand=True, pady=(0, 4))

def _pos_on_screen(x, y):
    """그 위치가 지금 화면 안인가 — 모니터를 뺐을 때 창이 사라지는 것 방지."""
    return (-50 <= x <= root.winfo_screenwidth() - 100
            and -20 <= y <= root.winfo_screenheight() - 80)


def _reading_order(blocks):
    """블럭을 눈으로 읽는 순서(위→아래, 왼→오)로 정렬. 단축키 번호의 기준."""
    return sorted(blocks, key=lambda b: (int(b.get("row", 0)),
                                         int(b.get("col", 0))))


# ── 통합 검색 (UI 제안 8) ───────────────────────────────
def _search_targets():
    """검색 대상 [(분류, 이름, 실행함수), ...] — 블럭·라이브러리·내장 문자."""
    out = []
    for tab in palette.load_tabs():
        for blk in tab.get("blocks", []):
            name = _block_label(blk)
            if name:
                out.append((f"블럭·{tab['name']}", name,
                            lambda b=blk: run_palette_block(b)))
    for label, (cat, item) in library.label_lookup().items():
        if cat == "문자":
            out.append(("문자", f"{label}  →  {item.get('text', '')}",
                        lambda t=item.get("text", ""): _insert_text(t)))
        elif cat == "사진":
            out.append(("사진", label, None))
        else:
            out.append((cat, label, None))
    return out


def _insert_text(text):
    if not ensure_hwp():
        return
    try:
        hwp_engine.insert_plain(text)
        notify("ok", f"삽입: {text[:20]}")
    except Exception as e:
        report_error("삽입 실패", e)


def _open_search():
    """Ctrl+K — 블럭·라이브러리를 한 창에서 찾아 Enter 로 실행."""
    win = tk.Toplevel(root)
    win.title("찾기")
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    win.geometry(f"+{root.winfo_rootx() + 20}+{root.winfo_rooty() + 60}")

    targets = _search_targets()
    var = tk.StringVar()
    ent = tk.Entry(win, textvariable=var, font=_font(11), width=34,
                   relief="solid", bd=1)
    ent.pack(padx=12, pady=(12, 6))
    ent.focus_set()
    listbox = tk.Listbox(win, width=44, height=12, font=_font(9),
                         relief="solid", bd=1, activestyle="none",
                         selectbackground=ACCENT, selectforeground="white")
    listbox.pack(padx=12, pady=(0, 6))
    tk.Label(win, text="Enter 실행 · ↑↓ 이동 · Esc 닫기", font=_font(7),
             bg=BG, fg=MUTED).pack(pady=(0, 10))

    shown = []

    def refresh(*_a):
        q = var.get().strip().lower()
        listbox.delete(0, tk.END)
        shown.clear()
        for cat, name, run in targets:
            if q and q not in name.lower() and q not in cat.lower():
                continue
            shown.append((cat, name, run))
            listbox.insert(tk.END, f"[{cat}] {name}")
            if len(shown) >= 60:
                break
        if shown:
            listbox.selection_set(0)

    def run(_e=None):
        sel = listbox.curselection()
        if not sel:
            return
        cat, name, fn = shown[sel[0]]
        win.destroy()
        if fn is None:
            notify("info", f"{cat} '{name}' 은(는) 팔레트 블럭이나 "
                           "\\라벨\\ 변환으로 씁니다")
        else:
            fn()

    def move(delta):
        if not shown:
            return
        cur = listbox.curselection()
        i = (cur[0] if cur else 0) + delta
        i = max(0, min(i, len(shown) - 1))
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(i)
        listbox.see(i)

    var.trace_add("write", refresh)
    ent.bind("<Return>", run)
    ent.bind("<Down>", lambda e: move(1))
    ent.bind("<Up>", lambda e: move(-1))
    listbox.bind("<Double-Button-1>", run)
    win.bind("<Escape>", lambda e: win.destroy())
    refresh()
    return win


def _tip(widget, text):
    """상태가 바뀌는 위젯의 툴팁 문구를 갈아끼운다 (바인딩은 한 번만)."""
    state = getattr(widget, "_tip_state", None)
    if state is None:
        _add_tooltip(widget, text, force=True)
    else:
        state["text"] = text


# 한글 연결 상태를 2초마다 확인해 표시등을 칠하던 _poll_connection 은 없앴다
# (사용자 결정 2026-07-25). 연결 여부는 버튼을 누르면 그때 알려 주면 되고,
# 그 동그라미는 이제 **알림등**으로 쓴다 — set_dot 참고.
set_dot("ok")

# ── 단축키 ──────────────────────────────────────────────
# 아래 bind_all 은 **이 창이 선택돼 있을 때만** 동작한다. 한글에서 작업하는
# 중에 쓰려면 전역 단축키가 따로 있어야 한다 (CONVERT_HOTKEY, 파일 맨 위에 정의).
root.bind_all("<Control-t>", lambda e: fn_convert())
root.bind_all("<Control-T>", lambda e: fn_convert())
root.bind_all("<Control-k>", lambda e: _open_search())
root.bind_all("<Control-K>", lambda e: _open_search())

# ── 전역 단축키 (한글에서 눌러도 먹는다) ────────────────
#
# 변환 하나만 전역으로 잡는다. Ctrl+1~9(블럭 실행)까지 전역으로 잡으면 다른
# 프로그램의 그 조합을 통째로 뺏어가므로, 그건 이 창 안에서만 두었다.
# 조합에 Alt 를 넣은 이유: 맨 Ctrl+T 를 전역으로 잡으면 브라우저의 '새 탭'
# 처럼 다른 프로그램에서 널리 쓰는 것을 빼앗는다.
_convert_hotkey = hotkey.GlobalHotkey(CONVERT_HOTKEY)


def _pump_hotkey():
    """전역 단축키가 눌렸는지 확인한다 (Tk 스레드에서만 실행하려고 폴링).

    단축키를 받는 쪽은 별도 스레드다. Tk 위젯은 다른 스레드에서 건드리면 안
    되므로, 여기서 꺼내 와서 이 스레드로 실행한다.
    """
    try:
        if _convert_hotkey.poll():
            fn_convert()
    except Exception as e:
        applog.exc("전역 단축키 처리 실패", e)
    root.after(80, _pump_hotkey)


def _start_global_hotkey():
    ok, err = _convert_hotkey.start()
    if ok:
        root.after(80, _pump_hotkey)
    else:
        # 조용히 실패하면 "왜 안 되지"만 남는다 — 반드시 알린다
        notify("warn", f"전역 단축키를 못 켰습니다 ({CONVERT_HOTKEY}) — 눌러서 보기",
               detail=err)


root.after(400, _start_global_hotkey)   # 창이 다 뜬 뒤에 등록


def _run_nth_block(n):
    """Ctrl+1~9 — 지금 탭의 n번째 블럭 실행 (UI 제안 9).

    같은 블럭을 수십 번 누르는 조판 작업에서 마우스 왕복을 없앤다.
    '지금 보는 탭' 기준이라, 탭을 바꾸면 같은 숫자가 다른 블럭이 된다.
    """
    tabs = [t for t in palette.load_tabs()
            if t.get("name") != palette.MAIN_TAB]
    if not tabs:
        return
    cur = min(_pal_state["tab"], len(tabs) - 1)
    blocks = _reading_order(tabs[cur].get("blocks", []))
    if n <= len(blocks):
        run_palette_block(blocks[n - 1])
    else:
        notify("info", f"이 탭에는 {n}번째 블럭이 없습니다")


for _i in range(1, 10):
    root.bind_all(f"<Control-Key-{_i}>", lambda e, n=_i: _run_nth_block(n))

# ── 창 위치 기억 (UI 제안 15) ───────────────────────────
root.update_idletasks()
_saved_pos = settings.get_window_pos()
if _saved_pos and _pos_on_screen(*_saved_pos):
    root.geometry(f"+{_saved_pos[0]}+{_saved_pos[1]}")
else:
    root.geometry(f"+{root.winfo_screenwidth() - root.winfo_width() - 20}+80")


def _remember_pos(quit_after=True):
    """창을 닫을 때 위치를 기억한다 — 멀티 모니터에서 매번 옮기지 않게.

    화면 모드·색 모드 전환(_restart)에서도 부른다. 그때는 창을 닫으면 안 되므로
    quit_after=False — 위치만 남기고 프로세스는 그대로 갈아탄다.
    """
    try:
        settings.set_window_pos(root.winfo_x(), root.winfo_y())
    except Exception as e:
        applog.exc("창 위치 저장 실패", e)
    if quit_after:
        root.destroy()


root.protocol("WM_DELETE_WINDOW", _remember_pos)

# 첫 실행 안내 (UI 제안 11) — exe 를 받은 사람은 여기서 쓰는 법을 배운다.
# mainloop 전에 부르면 창이 아직 안 그려져 위치 계산이 틀어지므로 after_idle.
root.after_idle(lambda: onboarding.maybe_show(root, _font))

root.mainloop()
