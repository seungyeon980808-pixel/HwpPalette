# -*- coding: utf-8 -*-
"""한컴 자동화(pyhwpx) 코어 — 연결·문서·선택·글꼴·표 생성·찾기.

Tkinter/UI에 의존하지 않는다. 표/박스의 모든 치수·글꼴·테두리는 활성 스펙(S)에서
읽는다. S는 settings.py의 프리셋에서 온다. 실패는 예외로 올라간다.
메시지박스/상태표시는 호출부의 책임.

모듈 경계 (개선안 19 — 2026-07-18 분할):
  hwp_engine     (이 파일) 한글을 다루는 원시 동작. 다른 엔진이 공유하는 토대.
  exam_engine    시험문제 조판 (발문·자료박스·보기박스·선지 표).
  engine_library 라이브러리(서식/템플릿/양식) 캡처·적용, 팔레트 블럭 실행,
                 \\라벨\\ 마크다운 변환 실행.
연결 인스턴스(hwp)는 이 모듈이 소유하고, 나머지는 `hwp_engine.hwp` 로 참조한다
— `from hwp_engine import hwp` 로 가져오면 재연결 시 낡은 객체를 붙들게 된다.

지역 import 규칙 (개선안 24):
  함수 안에서 import 하는 경우는 **두 가지뿐**이다.
    1) 순환 참조 회피 — library ↔ palette 처럼 서로를 필요로 하는 경우
    2) 플랫폼/선택적 의존성 — win32gui, win32clipboard 처럼 없을 수도 있고
       ImportError 를 그 자리에서 다뤄야 하는 경우
  그 외(표준 라이브러리 등)는 전부 파일 맨 위로 올린다.
"""

import os
import time

from pyhwpx import Hwp
import pyhwpx.core as pyhwpx_core     # __init__ 우회 시 필요한 기본값(fonts)
import applog
import settings

hwp = None

# 활성 스펙(프리셋). main.py가 시작 시 set_active_spec()으로 주입한다.
S = settings.default_spec()


def set_active_spec(spec):
    """설정 창에서 프리셋을 바꾸거나 저장하면 호출된다."""
    global S
    S = spec


# ── 진단 로거 (창 상태 추적용. 평소엔 꺼둠 — 문제 재현이 필요할 때만 True) ──
DIAG = False
_DIAG_PATH = None


def _diag(tag):
    """현재 한글 창 상태를 파일에 기록. 창을 바꾸는 범인을 찾기 위한 임시 도구."""
    if not DIAG:
        return
    global _DIAG_PATH
    try:
        import win32gui           # 플랫폼 의존 — 없을 수 있어 지역 import
        if _DIAG_PATH is None:
            import paths      # exe 로 묶으면 __file__ 은 지워지는 임시 폴더다
            _DIAG_PATH = str(paths.DATA_DIR / "window_diag.log")
            with open(_DIAG_PATH, "w", encoding="utf-8") as f:
                f.write("=== 창 상태 추적 시작 ===\n")
        lines = []
        for h in _hwp_window_handles():
            pl = win32gui.GetWindowPlacement(h)
            rc = win32gui.GetWindowRect(h)
            state = {1: "보통", 2: "최소", 3: "최대"}.get(pl[1], pl[1])
            lines.append(f"{state} {rc[2]-rc[0]}x{rc[3]-rc[1]}")
        with open(_DIAG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{tag}] {' | '.join(lines) if lines else '(창 없음)'}\n")
    except Exception as e:
        applog.exc("진단 로그 기록 실패", e)


def _hwp_window_handles():
    """현재 떠 있는 한글 창 핸들 목록."""
    try:
        import win32gui
    except ImportError:
        return []
    found = []

    def _cb(hwnd, _):
        try:
            # 클래스명은 'HwndWrapper[Hwp.exe;;...]' — 대소문자가 환경마다 다르므로
            # 반드시 소문자로 비교한다 (실측: Hwp.exe 로 나와 매칭 실패했던 버그)
            if (win32gui.IsWindowVisible(hwnd)
                    and "hwp.exe" in win32gui.GetClassName(hwnd).lower()):
                found.append(hwnd)
        except Exception as e:
            applog.exc(f"창 정보 조회 실패 (hwnd={hwnd})", e)
    try:
        win32gui.EnumWindows(_cb, None)
    except Exception as e:
        applog.exc("창 목록 열거 실패", e)
        return []
    return found


def _connection_error(h):
    r"""연결이 살아 있으면 None, 죽었으면 그 예외를 돌려준다.

    **pyhwpx 의 `hwp.Version` 프로퍼티를 쓰면 안 된다** (실측 2026-07-19):
        return [int(i) for i in self.hwp.Version.split(", ")]
    보다시피 문자열을 파싱한다. 한글이 멀쩡히 살아 있어도 버전 표기가
    `"13, 0, 0, 2151"` 꼴이 아니면 여기서 ValueError 가 난다.

    그걸 '연결이 죽었다'로 오판하면 **변환할 때마다 재연결**하게 되고,
    재연결은 pyhwpx 생성자의 `Visible` 대입 때문에 최대화된 창을 보통 크기로
    되돌린다. 우리가 곧바로 복원하므로 결과는 **"변환을 누르면 창이 작아졌다
    다시 커지는"** 증상이 된다. 실제로 그 버그가 났다.

    그래서 파싱하지 않는 원시 COM 값을 한 번 건드려 살아 있는지만 본다.
    """
    if h is None:
        return ValueError("아직 연결된 적이 없음")
    try:
        _ = h.hwp.Version       # 원시 COM 값 — 파싱하지 않는다
        return None
    except Exception as e:
        return e


def _running_hwp_com():
    """이미 실행 중인 한글의 COM 객체. 없으면 None. (한글을 새로 띄우지 않는다)"""
    import pythoncom
    import win32com.client as win32
    ctx = pythoncom.CreateBindCtx(0)
    pythoncom.CoInitialize()
    rot = pythoncom.GetRunningObjectTable()
    for moniker in rot.EnumRunning():
        if moniker.GetDisplayName(ctx, moniker).startswith("!HwpObject."):
            obj = rot.GetObject(moniker)
            return win32.gencache.EnsureDispatch(
                obj.QueryInterface(pythoncom.IID_IDispatch))
    return None


def _attach_without_resize():
    r"""이미 떠 있는 한글에 **창을 건드리지 않고** 붙는다. 못 하면 None.

    왜 이렇게까지 하나 (실측 2026-07-19):
      pyhwpx 의 Hwp() 생성자는 무조건
          XHwpWindows.Active_XHwpWindow.Visible = visible
      을 실행하는데, 이 대입이 **최대화된 창을 보통 크기로 되돌린다**
      (측정값: 최대 1094x1934 → 보통 1080x802).
      예전엔 창 배치를 저장했다 복원하는 것으로 막으려 했지만, 그건 '되돌리기'라
      사용자 눈에는 여전히 **작아졌다 다시 커지는 깜빡임**으로 보인다.
      → 애초에 생성자를 거치지 않는다.

    pyhwpx.Hwp.__init__ 이 self 에 세팅하는 것은 hwp / on_quit / htf_fonts 세 개뿐이라
    (2026-07-19 확인) 그것만 채워 넣으면 나머지 메서드는 그대로 동작한다.
    pyhwpx 가 올라가면서 필드가 늘어날 수 있으므로, 채운 뒤 실제로 쓸 수 있는지
    확인하고 아니면 None 을 돌려 정상 경로로 넘긴다.
    """
    try:
        com = _running_hwp_com()
        if com is None:
            return None                 # 한글이 안 떠 있음 — 새로 실행해야 한다
        h = Hwp.__new__(Hwp)            # __init__ 을 건너뛴다 (Visible 대입 회피)
        h.hwp = com
        h.on_quit = False
        h.htf_fonts = pyhwpx_core.fonts
        _ = h.hwp.Version               # 실제로 말이 통하는지 확인
        try:
            h.register_module()         # 보안 모듈 등록 (파일 열기/저장에 필요)
        except Exception as e:
            applog.exc("보안 모듈 등록 실패 — 파일 접근 시 확인창이 뜰 수 있음", e)
        return h
    except Exception as e:
        applog.exc("창 보존 연결 실패 — 일반 연결로 넘어감(창이 한 번 깜빡일 수 있음)", e)
        return None


def is_connected():
    """지금 한글에 붙어 있는가 (표시등용). 연결을 새로 만들지 않는다.

    주기적으로 부를 것이므로 **절대 무거워지면 안 된다** — 새 연결을 시도하거나
    문서를 건드리면 사용자가 타자를 치는 중에 한글을 방해한다. 이미 잡아 둔
    객체의 원시 COM 값을 한 번 읽어 보는 것으로 끝낸다.
    """
    return _connection_error(hwp) is None


def connect():
    """이미 연결돼 있으면 재사용, 아니면 새로 연결. 실패 시 예외 발생.

    창 크기가 변하지 않게 하는 순서 (실측 2026-07-19):
      1) 이미 붙어 있으면 그대로 재사용 — 아무것도 안 건드린다
      2) 한글이 떠 있으면 생성자를 거치지 않고 붙는다(_attach_without_resize)
      3) 한글이 아예 없을 때만 Hwp() 로 새로 실행 — 이때는 보존할 최대화 상태가
         없으므로 창이 줄어들 일도 없다
    2번이 실패할 때만 옛 방식(배치 저장 → Hwp() → 복원)으로 넘어간다. 그 경우엔
    창이 한 번 깜빡이므로, 왜 그랬는지 app.log 에 남는다.
    """
    global hwp
    err = _connection_error(hwp)
    if err is None:
        _diag("connect: 기존 연결 재사용")
        return hwp                  # ← 평소엔 여기서 끝. 창을 건드리지 않는다.

    if hwp is not None:
        applog.warn(f"connect: 연결이 끊어져 새로 연결 — {type(err).__name__}: {err}")

    attached = _attach_without_resize()
    if attached is not None:
        hwp = attached
        _diag("connect: 창 보존 연결 성공")
        return hwp

    _diag("connect: 재연결 직전")
    try:
        import win32gui
        saved = [(h, win32gui.GetWindowPlacement(h)) for h in _hwp_window_handles()]
    except Exception as e:
        applog.exc("창 배치 저장 실패 — 최대화가 풀릴 수 있음", e)
        saved = []

    hwp = Hwp()
    _diag("connect: Hwp() 생성 직후")

    for handle, placement in saved:
        try:
            win32gui.SetWindowPlacement(handle, placement)
        except Exception as e:
            applog.exc(f"창 배치 복원 실패 (handle={handle})", e)
    if not saved:
        # 실제로 겪은 버그: 클래스명 대소문자 오타로 창을 0개로 봐서
        # 복원 로직이 통째로 무동작이었는데 아무 소리도 안 났었다.
        applog.warn("connect: 복원할 한글 창을 찾지 못함 "
                    "(한글이 새로 실행된 경우면 정상)")
    _diag(f"connect: 복원 시도 후 (저장했던 창 {len(saved)}개)")
    return hwp


# ── 문서/선택 ─────────────────────────────────────────
def new_document():
    hwp.HAction.Run("FileNew")


def open_document(path):
    hwp.open(path)


def save_document():
    hwp.save()


def has_selection():
    try:
        return hwp.SelectionMode != 0
    except Exception as e:
        applog.exc("선택 상태 조회 실패", e)
        return False


def copy_selection():
    hwp.HAction.Run("Copy")


def read_selection_text(retries=10, delay=0.08):
    """선택 영역을 Copy 후 윈도우 클립보드에서 직접 읽는다.

    Tk 클립보드(clipboard_get)는 한글의 Copy 완료와 타이밍이 어긋나
    빈 값을 돌려주는 일이 잦다(실측 2026-07-15) — win32clipboard가 안정적.
    """
    import win32clipboard        # 플랫폼 의존 — 없을 수 있어 지역 import
    copy_selection()
    last_error = None
    for _ in range(retries):
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(
                        win32clipboard.CF_UNICODETEXT):
                    text = win32clipboard.GetClipboardData(
                        win32clipboard.CF_UNICODETEXT)
                    if text:
                        return text
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            last_error = e          # 클립보드는 다른 앱이 잠깐 점유하면 실패한다
        time.sleep(delay)
    if last_error is not None:
        applog.exc(f"클립보드 읽기 {retries}회 모두 실패", last_error)
    return ""


def delete_selection():
    hwp.HAction.Run("Delete")


def cancel_selection():
    hwp.HAction.Run("Cancel")


def current_pos():
    """현재 커서 위치 (list, para, pos). 못 읽으면 None."""
    try:
        return hwp.GetPos()
    except Exception as e:
        applog.exc("현재 위치 조회 실패", e)
        return None


def in_table():
    """커서가 표(각주 등 본문 아닌 리스트) 안에 있는가.

    GetPos()[0] 은 리스트 번호이고 본문이 0 이다. 표 안에서는 셀마다 리스트가
    따로라, 여러 셀에 걸친 선택을 '한 덩어리 글'로 다루면 셀 경계가 사라진다.
    """
    try:
        return hwp.GetPos()[0] != 0
    except Exception as e:
        applog.exc("표 안 여부 확인 실패 — 본문으로 간주", e)
        return False


def doc_end_para():
    """문서 마지막 문단 번호.

    주의: 커서를 문서 끝으로 옮긴다. 호출부가 위치를 복원해야 한다.
    """
    hwp.MoveDocEnd()
    return hwp.GetPos()[1]


# ── 텍스트/글꼴 ───────────────────────────────────────
def set_char_shape(font, size_pt):
    act = hwp.HAction
    ps = hwp.HParameterSet
    act.GetDefault("CharShape", ps.HCharShape.HSet)
    ps.HCharShape.FaceNameHangul = font
    ps.HCharShape.FaceNameLatin  = font
    ps.HCharShape.Height = hwp.PointToHwpUnit(size_pt)
    act.Execute("CharShape", ps.HCharShape.HSet)


def _maybe_apply_font():
    f = S.get("font", {})
    if f.get("apply"):
        set_char_shape(f.get("name", "함초롬바탕"), f.get("size_pt", 10))


def _text(s):
    """생성 문항용 텍스트 삽입 — 글꼴 강제 적용 옵션을 반영한다."""
    _maybe_apply_font()
    hwp.insert_text(s)


def insert_plain(text):
    """서식/원문자 버튼용 단순 삽입 — 글꼴 강제 적용 안 함(현재 문서 서식 유지)."""
    act = hwp.HAction
    ps = hwp.HParameterSet
    act.GetDefault("InsertText", ps.HInsertText.HSet)
    ps.HInsertText.Text = text
    act.Execute("InsertText", ps.HInsertText.HSet)


def insert_picture_to_cell(img_path):
    """현재 커서가 있는 셀에 사진 삽입 — 셀 너비 맞춤(비율 유지) + 중앙 정렬"""
    act = hwp.HAction
    try:
        act.Run("ParagraphShapeAlignCenter")
    except Exception as e:
        applog.exc("사진 삽입 전 가운데 정렬 실패 — 정렬 없이 계속 진행", e)
    hwp.insert_picture(str(img_path))


# ── 표/박스 공통 헬퍼 ─────────────────────────────────
def _mm(v):
    return hwp.MiliToHwpUnit(v)


def _col_width_mm():
    return S["layout"]["column_width_mm"]


def _set_cell_border(act, ps, top, bottom, left, right):
    act.GetDefault("CellBorderFill", ps.HCellBorderFill.HSet)
    ps.HCellBorderFill.BorderTypeTop    = hwp.HwpLineType(top)
    ps.HCellBorderFill.BorderTypeBottom = hwp.HwpLineType(bottom)
    ps.HCellBorderFill.BorderTypeLeft   = hwp.HwpLineType(left)
    ps.HCellBorderFill.BorderTypeRight  = hwp.HwpLineType(right)
    act.Execute("CellBorderFill", ps.HCellBorderFill.HSet)


# 표/구역 탈출 시 반복 한도 — 표가 이만큼 깊게 중첩되는 문서는 없다고 본다
_MAX_NEST_DEPTH = 8


def _exit_table(act):
    """표 편집 상태에서 확실히 본문으로 빠져나온다.

    주의: 셀 병합(TableMergeCell) 직후처럼 '셀 선택' 상태에서 CloseEx는 표 밖으로
    나가지 않고 선택만 해제한다(실측 2026-07-05 — 이때 다음 표가 셀 안에 중첩되던
    버그의 원인). Cancel로 선택을 먼저 풀고, 본문(list 0)에 도달할 때까지 CloseEx.
    """
    act.Run("Cancel")               # 셀 선택 상태 해제
    for _ in range(_MAX_NEST_DEPTH):
        try:
            if hwp.GetPos()[0] == 0:   # list 0 = 본문
                break
        except Exception as e:
            applog.exc("표 탈출 중 위치 조회 실패 — 탈출 중단", e)
            break
        act.Run("CloseEx")
    # 본문 도달 시 커서는 표 앵커 앞 — MoveDown은 표 '첫 셀로 들어가는' 키라
    # 쓰면 안 되고(실측), MoveRight로 앵커 글자를 건너뛰어 표 뒤로 나온다.
    act.Run("MoveRight")


# 표 생성 시 열마다 붙는 셀 좌우 안여백(1.8mm×2) — 실측 보정값(2026-07-05)
_CELL_SIDE_MARGIN_MM = 3.6


def _create_table(rows, cols, total_mm, row_heights_mm):
    """rows×cols 표 생성. 완성된 표의 전체 폭이 total_mm가 되도록 열을 균등 분할.

    실측(2026-07-05):
    - WidthType: 0=단에 맞춤, 1=문단에 맞춤 → 지정 너비 무시. 2=임의 값이어야 반영.
    - ColWidth는 셀 '내용' 폭 기준이라, 완성 폭 = Σ(ColWidth + 3.6mm). 열마다
      셀 좌우 안여백만큼 빼서 지정해야 전체 폭이 total_mm에 맞는다.
    - RowHeight는 '최소 높이' — 내용·줄간격·셀 여백이 크면 그만큼 늘어난다.
    """
    act = hwp.HAction
    ps  = hwp.HParameterSet
    act.GetDefault("TableCreate", ps.HTableCreation.HSet)
    ps.HTableCreation.Rows       = rows
    ps.HTableCreation.Cols       = cols
    ps.HTableCreation.WidthType  = 2
    ps.HTableCreation.HeightType = 1
    ps.HTableCreation.WidthValue = _mm(total_mm)
    ps.HTableCreation.CreateItemArray("ColWidth", cols)
    # 열 내용 폭 = 전체 폭/열 수 - 셀 좌우 여백 (반올림 오차는 마지막 칸에서 흡수)
    content_total = total_mm - cols * _CELL_SIDE_MARGIN_MM
    each = max(content_total / cols, 1.0)
    acc = 0.0
    for i in range(cols):
        w = max(content_total - acc, 1.0) if i == cols - 1 else each
        ps.HTableCreation.ColWidth.SetItem(i, _mm(w))
        acc += each
    ps.HTableCreation.CreateItemArray("RowHeight", rows)
    for i in range(rows):
        ps.HTableCreation.RowHeight.SetItem(i, _mm(row_heights_mm[i]))
    act.Execute("TableCreate", ps.HTableCreation.HSet)


def create_table_autofit(rows, cols):
    r"""rows×cols 표를 '단에 맞춤'으로 만든다 (\표3x3\ 변환용, 2026-07-25).

    _create_table 과 달리 폭을 계산하지 않는다. WidthType=0 이면 한글이
    **커서가 있는 단의 폭**에 맞춰 주기 때문이다 — 2단 시험지의 한 단에 넣으면
    그 단 폭, 본문이면 본문 폭. "들어가는 곳의 칸을 알아서 인식"이 이것이다.
    (WidthType 값의 뜻은 _create_table 주석 참고: 0=단에 맞춤, 2=임의 값)

    높이는 지정하지 않는다(HeightType=0) — 내용에 따라 늘어나게 둔다.
    """
    act = hwp.HAction
    ps  = hwp.HParameterSet
    act.GetDefault("TableCreate", ps.HTableCreation.HSet)
    ps.HTableCreation.Rows       = rows
    ps.HTableCreation.Cols       = cols
    ps.HTableCreation.WidthType  = 0      # 단에 맞춤
    ps.HTableCreation.HeightType = 0      # 자동 높이
    act.Execute("TableCreate", ps.HTableCreation.HSet)


def exit_table():
    """표 편집 상태에서 본문으로 빠져나온다 (_exit_table 의 공개 이름)."""
    _exit_table(hwp.HAction)


# ── 찾기 ──────────────────────────────────────────────
def find_text(query, direction="Forward"):
    r"""문서에서 문자열을 찾아 선택한다. 없으면 False.

    pyhwpx의 hwp.find()를 쓰지 않는 이유 (실측 2026-07-16):
      1) 내부에서 HAction.Execute("FindDlg", ...) 로 '찾기 대화상자'를 실제 실행함.
      2) SetMessageBoxMode(0x2FFF1) 로 바꾼 뒤 finally에서 원래값이 아니라
         0xFFFFF 를 강제 세팅해, 한글의 대화상자 처리 모드가 0x0 → 0xFFFFF 로
         영구히 바뀜 (변환할 때 '창 모드가 변하는' 증상의 원인).
    RepeatFind 만 쓰면 대화상자도 안 뜨고 모드도 그대로다(0x0 유지 실측 확인).
    """
    act = hwp.HAction
    pset = hwp.HParameterSet.HFindReplace
    act.GetDefault("RepeatFind", pset.HSet)
    pset.MatchCase = 1
    pset.SeveralWords = 0
    pset.UseWildCards = 0
    pset.WholeWordOnly = 0
    pset.AutoSpell = 1
    pset.Direction = hwp.FindDir(direction)
    pset.FindString = query
    pset.IgnoreMessage = 1
    pset.HanjaFromHangul = 1
    pset.AllWordForms = 0
    pset.FindJaso = 0
    pset.FindRegExp = 0
    pset.FindType = 1
    r = bool(act.Execute("RepeatFind", pset.HSet))
    _diag("find_text 후")
    return r
