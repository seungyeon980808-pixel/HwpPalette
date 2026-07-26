# -*- coding: utf-8 -*-
r"""라이브러리·팔레트 실행 엔진 — 캡처/적용, 블럭 실행, \라벨\ 변환.

hwp_engine(코어)이 '한글을 어떻게 조작하는가'를 맡는다면, 이 모듈은
'등록해 둔 것을 어떻게 꺼내 쓰는가'를 맡는다 (개선안 19 — 2026-07-18 분할).

  · 서식(부분 델타) 캡처/적용
  · 템플릿(조각 .hwp) 캡처/삽입, 양식(파일 통째) 열기
  · 팔레트 블럭 실행 (문자/기능/템플릿/양식)
  · 마크다운 \라벨\ 변환 계획 실행

한글 조작은 전부 hwp_engine 의 것을 그대로 쓴다(연결 인스턴스를 공유하기 위함).
"""

import time

import applog
import hwp_engine
import parser as md_parser          # MultiLine(한 칸에 여러 줄) 판별용
from hwp_engine import (
    delete_selection, find_text, has_selection, insert_plain,
)


def _h():
    """현재 연결된 한글 인스턴스. 재연결로 바뀌므로 매번 모듈에서 읽는다."""
    return hwp_engine.hwp


# ── 라이브러리: 서식(부분 델타) 캡처/적용 ───────────────
# 친화적 이름 : CharShape 딕셔너리 키. 값 단위는 저장소(library.py)에도 그대로
# 노출되므로, 여기 바뀌면 저장된 항목의 의미도 바뀐다는 점 주의.
CHARSHAPE_FIELD_LABELS = ["굵게", "기울임", "밑줄", "글자색", "자간", "글꼴", "크기"]

# 양식 안에 적어 두는 '본문 시작 자리' 표시 (2026-07-24).
#
# 양식은 문서 전체를 여는 것이라, 뒤따라오는 내용(문제 등)을 어디에 넣을지
# 정해 줘야 한다. 문서 끝에 붙이면 머리말·2단 구성·페이지번호가 있는 양식에서
# 엉뚱한 자리로 간다. 그래서 양식 파일 안에 이 표시를 한 번 적어 두면, 변환이
# 그 자리를 찾아 거기서부터 이어 쓴다. 표시가 없으면 문서 끝에서 이어 쓴다.
#
# 주의: 이 표시는 역슬래시를 2개 포함한다. fill_slots 는 빈칸(\)을 찾아 채우므로
# **빈칸 채우기 전에 반드시 다른 마커로 치환**해야 한다 — 안 그러면 본문 표시가
# 빈칸으로 잡아먹힌다. execute_library_plan 이 그 순서를 지킨다.
BODY_ANCHOR = "\\본문\\"


def _charshape_get(cs, label):
    if label == "굵게":
        return bool(cs.get("Bold"))
    if label == "기울임":
        return bool(cs.get("Italic"))
    if label == "밑줄":
        return int(cs.get("UnderlineType") or 0) != 0
    if label == "글자색":
        return cs.get("TextColor")
    if label == "자간":
        return cs.get("SpacingHangul")
    if label == "글꼴":
        return cs.get("FaceNameHangul")
    if label == "크기":
        h = cs.get("Height") or 0
        return round(h / 100, 1)
    return None


def capture_charshape(selected_labels):
    """현재 커서/선택 위치의 글자 서식에서, 체크된 항목만 델타로 캡처한다."""
    hwp = _h()
    act = hwp.HAction
    ps = hwp.HParameterSet
    act.GetDefault("CharShape", ps.HCharShape.HSet)
    cs = hwp.get_charshape_as_dict()
    delta = {}
    for label in selected_labels:
        v = _charshape_get(cs, label)
        if v is not None:
            delta[label] = v
    return delta


def apply_charshape_delta(delta):
    """델타에 있는 항목만 현재 선택/커서 위치에 적용한다(그 외 서식은 그대로 유지).

    GetDefault로 대상의 '현재' 서식을 먼저 불러온 뒤, 델타에 있는 필드만
    덮어써서 Execute 한다 — 이 방식이라야 부분 적용(굵기만 바꾸고 글꼴은
    유지 등)이 보장된다.
    """
    hwp = _h()
    act = hwp.HAction
    ps = hwp.HParameterSet
    act.GetDefault("CharShape", ps.HCharShape.HSet)
    if "굵게" in delta:
        ps.HCharShape.Bold = 1 if delta["굵게"] else 0
    if "기울임" in delta:
        ps.HCharShape.Italic = 1 if delta["기울임"] else 0
    if "밑줄" in delta:
        ps.HCharShape.UnderlineType = 1 if delta["밑줄"] else 0
    if "글자색" in delta:
        ps.HCharShape.TextColor = delta["글자색"]
    if "자간" in delta:
        ps.HCharShape.SpacingHangul = delta["자간"]
        ps.HCharShape.SpacingLatin = delta["자간"]
    if "글꼴" in delta:
        ps.HCharShape.FaceNameHangul = delta["글꼴"]
        ps.HCharShape.FaceNameLatin = delta["글꼴"]
    if "크기" in delta:
        ps.HCharShape.Height = hwp.PointToHwpUnit(delta["크기"])
    act.Execute("CharShape", ps.HCharShape.HSet)


# ── 라이브러리: 템플릿(통째 캡처) ───────────────────────
def auto_select_table_if_inside():
    """커서가 표 안이면(선택 없이 클릭만 한 상태) 그 표를 개체로 선택한다.

    예전 방식(Cancel+CloseEx 로 본문에 나온 뒤 MoveSelRight)은 복잡한 문서에서
    커서가 앵커 옆이 아닌 곳에 떨어져 **줄바꿈만 선택**되는 일이 있었다
    (실측 2026-07-19: CloseEx 후 위치가 앵커와 무관한 (0,1,8), 양옆 선택 모두
    '\\r\\n'). 커서가 속한 컨트롤을 ParentCtrl 로 직접 얻어 select_ctrl 로
    선택하는 것이 위치 계산 없이 정확하다.
    반환: 선택 성공 여부.
    """
    hwp = _h()
    try:
        if hwp.GetPos()[0] == 0:
            return False        # 본문에 있음 — 표 안이 아님
    except Exception as e:
        applog.exc("표 안 여부 확인 실패", e)
        return False
    try:
        ctrl = hwp.ParentCtrl
        if ctrl is None:
            return False
        hwp.select_ctrl(ctrl)
    except Exception as e:
        applog.exc("표 선택 실패", e)
        return False
    return has_selection()


def capture_fragment(dest_path):
    r"""현재 선택 영역을 통째로 조각 .hwp 파일로 저장한다(병합·서식 그대로).

    방식: 복사 → 새 탭에 붙여넣기 → 그 문서를 통째로 저장 → 탭 닫기.

    save_block_as(FileSaveBlock_S)를 쓰지 않는 이유 (실측 2026-07-19):
      표를 **개체로 선택**한 상태(SelectionMode 4 — 표 테두리 클릭 등)에서
      FileSaveBlock_S 는 선택만 저장하지 않고 **문서 전체를 저장**한다.
      복잡한 문서에서 표 하나를 캡처했는데 다른 내용까지 다 들어가고,
      그 비대한 조각을 삽입하면 한글이 멈추던 버그의 원인.
      복사→붙여넣기는 선택 종류(글자 선택 1 / 개체 선택 4)와 무관하게
      선택한 것만 정확히 담는다 (두 모드 모두 실측 확인).

    부작용: 사용자의 클립보드가 캡처 내용으로 바뀐다 — 캡처 흐름에서는
    read_selection_text 가 이미 Copy 를 쓰고 있어 추가 손해는 없다.

    반환: 조각의 본문 글자 (미리보기용, UI 제안 7). 실패하면 빈 문자열.
      **여기서 뽑는 이유** — 이 순간이 조각 내용을 글로 읽을 수 있는 유일한
      때다. .hwp 는 이진 형식이라 나중에 파일만 보고는 못 읽고, 다시 읽으려면
      한글을 켜서 파일을 열어야 한다. 지금은 이미 임시 탭에 펼쳐져 있다.
    """
    hwp = _h()
    if not has_selection():
        raise RuntimeError("캡처할 선택 영역이 없습니다")
    hwp.HAction.Run("Copy")
    saved = hwp.XHwpDocuments.Count
    preview = ""
    try:
        hwp.XHwpDocuments.Add(1)          # 1 = 새 탭
        hwp.HAction.Run("Paste")
        hwp.save_as(str(dest_path), format="HWP")
        try:
            preview = hwp.GetTextFile("TEXT", "") or ""
        except Exception as e:
            applog.exc("조각 미리보기 글자 추출 실패 — 미리보기 없이 등록", e)
    finally:
        try:
            if hwp.XHwpDocuments.Count > saved:
                hwp.XHwpDocuments.Active_XHwpDocument.Close(isDirty=False)
        except Exception as e:
            applog.exc("캡처용 임시 탭 닫기 실패 — 탭이 남아 있을 수 있음", e)
    return preview


def insert_photo(path):
    r"""사진 파일을 커서 자리에 글자처럼 삽입 (물감 설정 '사진' 탭의 삽입).

    옵션은 마크다운 변환의 \사진이름\ 삽입(insert_rich_line)과 같다 —
    embedded=True 로 문서에 포함, sizeoption=3 으로 셀 안이면 셀에 맞춤.
    삽입 직후 한글이 그림 개체를 선택한 채로 두므로 선택을 풀어 준다.
    """
    hwp = _h()
    hwp.insert_picture(str(path), treat_as_char=True, embedded=True,
                       sizeoption=3)
    try:
        hwp.HAction.Run("Cancel")
    except Exception as e:
        applog.exc("사진 삽입 후 개체 선택 해제 실패 (무해)", e)


def insert_fragment(path):
    r"""조각 .hwp 파일을 커서 위치에 그대로 삽입한다.

    keep_section=0 필수 — 조각에는 저장 당시의 구역(secd) 정의가 같이 담기는데,
    이를 유지(1)하면 구역 나눔이 일어나 표가 '다음 페이지'에 생성된다(실측 2026-07-15).

    나머지 keep_* 는 pyhwpx 기본값이 전부 1이라 지금까지 암묵적으로 1이었다
    (2026-07-18 pyhwpx 소스 확인 — 개선안 6). 무엇이 딸려오는지 코드에 드러나도록
    명시해 둔다. 값 자체는 바꾸지 않았다:
      keep_charshape / keep_parashape = 1
        조각의 글자·문단 서식 유지. 표가 원본대로 재현되려면 반드시 1이어야 한다.
      keep_style = 1
        조각에 딸린 '스타일 정의'까지 대상 문서로 들여온다. 같은 이름의 스타일이
        대상 문서에 있으면 덮어쓸 여지가 있다. 0으로 바꾸면 그 부작용은 사라지지만
        조각 모양이 달라질 수 있어, 실제 피해 사례가 관측되기 전까지는 유지한다.
    """
    hwp_engine._diag("insert_fragment: insert_file 직전")
    _h().insert_file(str(path), keep_section=0, keep_charshape=1,
                     keep_parashape=1, keep_style=1)
    hwp_engine._diag("insert_fragment: insert_file 직후  <<< 여기서 바뀌면 insert_file 범인")


def insert_table(rows, cols, grid):
    r"""커서 자리에 rows×cols 표를 만들고 셀을 채운다 (\표3x3\ 변환용, 2026-07-25).

    셀 이동은 TableRightCell 하나로 한다 — 행 끝에서 **다음 행 첫 칸**으로
    넘어간다(exam_engine 이 2행2열 표를 같은 방식으로 채운다).

    grid 가 모자라도 된다. 없는 자리는 건너뛰어 빈 칸으로 남긴다 — 표는 이미
    만들어졌으니 사용자가 한글에서 마저 채우면 된다. 변환을 통째로 실패시키는
    것보다 낫다.
    """
    hwp_engine.create_table_autofit(rows, cols)
    act = _h().HAction
    for r in range(rows):
        row = grid[r] if r < len(grid) else []
        for c in range(cols):
            if r or c:                      # 첫 칸은 이미 커서가 있다
                act.Run("TableRightCell")
            value = row[c] if c < len(row) else None
            if value is None:
                continue                    # '-' 이거나 값이 없는 칸
            if isinstance(value, list):
                insert_rich_line(value)     # 사진·서식이 섞인 칸
            else:
                insert_plain(value)
    hwp_engine.exit_table()


# ── 빈칸(\) 처리 ──────────────────────────────────────
# 한 번의 청소에서 훑을 빈칸 개수 상한 — 무한 루프 방지용 안전장치
_MAX_SLOT_SCAN = 200


def measure_insert_span(anchor_pos, insert_fn):
    r"""anchor_pos에 insert_fn()으로 삽입한 내용의 '마지막 문단 번호'를 돌려준다.

    insert_file 직후 커서가 삽입물 뒤로 이동하지 않아(실측) 끝 위치를 커서로는
    알 수 없다. 그래서 삽입 전후의 '문서 마지막 문단 번호' 차이로 삽입물이
    차지한 문단 수를 역산한다.

    **커서가 표 안이면 None 을 돌려준다.** doc_end_para() 는 본문(list 0) 기준
    번호인데 anchor_pos[1] 은 셀 안에서 다시 센 번호라, 둘을 더하면 뜻이 없는
    수가 나온다. 그 수로 범위를 재면 빈칸이 하나도 안 채워지고 `\` 가 문서에
    그대로 남는다. 범위를 모를 땐 개수 상한(max_delete)에 맡기는 게 맞다.
    """
    hwp = _h()
    if anchor_pos[0] != 0:
        insert_fn()
        hwp.SetPos(*anchor_pos)
        return None
    before = hwp_engine.doc_end_para()
    hwp.SetPos(*anchor_pos)
    insert_fn()
    after = hwp_engine.doc_end_para()
    hwp.SetPos(*anchor_pos)
    return anchor_pos[1] + max(after - before, 0)


def _beyond(end_para):
    r"""현재 커서가 삽입 범위를 벗어났는가.

    한계 (그래서 개수 상한을 함께 쓴다):
      GetPos() 는 (list, para, pos) 인데 **para 는 list 안에서의 번호**다.
      표 안에 들어가면 list 가 바뀌면서 para 가 셀 기준으로 다시 세어지므로
      (본문 300번째 문단의 표 안이어도 para 가 0 일 수 있다), 본문 기준으로
      계산한 end_para 와 곧바로 비교할 수 없다. 즉 이 검사만으로는
      "삽입 범위 아래에 있는 사용자의 표 속 \" 를 걸러내지 못한다.
      → strip_slot_markers/fill_slots 의 max_delete(빈칸 개수 상한)가 그 구멍을 막는다.
    """
    if end_para is None:
        return False
    try:
        list_id, para, _ = _h().GetPos()
    except Exception as e:
        # 위치를 모르면 '벗어났다'고 본다 — 남의 문서를 지우느니 빈칸을 남긴다
        applog.exc("빈칸 범위 확인 실패 — 안전하게 청소 중단", e)
        return True
    if list_id != 0:
        return False        # 표/각주 등 — para 비교가 무의미. 개수 상한에 맡긴다
    return para > end_para


def _before_anchor(anchor_pos):
    r"""커서가 삽입 지점보다 **앞**에 있는가 (되돌아간 것으로 본다).

    find_text 는 RepeatFind 인데, 문서 끝에 닿았을 때 맨 앞으로 되돌아가
    다시 찾는지 확인하지 못했다. 만약 되돌아간다면 앞쪽에 있는 사용자의 `\`
    가 '범위 안'으로 보여(문단 번호가 end_para 보다 작으므로) 지워져 버린다.
    삽입 지점보다 앞은 무슨 일이 있어도 우리 것이 아니므로 여기서 멈춘다.
    """
    try:
        list_id, para, pos = _h().GetPos()
    except Exception:
        return True         # 모르면 멈춘다
    if list_id != anchor_pos[0]:
        return False        # 다른 리스트 — 앞뒤를 따질 수 없다
    return (para, pos) < (anchor_pos[1], anchor_pos[2])


def strip_slot_markers(anchor_pos, end_para=None, max_delete=None):
    r"""anchor_pos부터 end_para 문단까지 남은 빈칸 표시(\)를 제거한다.

    빈칸 표시는 '여기에 내용이 들어간다'는 안내일 뿐이라, 채워지지 않고 남으면
    출력물에 그대로 보인다 → 삽입/변환 후 이 함수로 청소한다.

    end_para 를 반드시 넘겨야 하는 이유 (개선안 5):
      예전에는 anchor 부터 **문서 끝까지** 무조건 지웠다. 그래서 삽입한 템플릿
      아래에 사용자가 직접 써 둔 \ 까지 같이 사라졌다. 조용히 일어나고 인쇄물을
      보기 전에는 알 수 없는 훼손이라 위험도가 높았다.
      end_para=None 은 '문서 전체가 대상'인 경우(양식을 새 문서로 연 직후)에만
      의도적으로 쓴다.

    max_delete: 지울 빈칸 개수 상한. 템플릿이 선언한 빈칸 수를 넘겨 받는다.
      end_para 만으로는 표 안을 걸러내지 못하기 때문에(_beyond 설명 참고)
      반드시 함께 써야 한다 — "이 템플릿엔 빈칸이 3개다"가 가장 확실한 경계다.
      None 이면 개수 제한 없음(양식 전체 청소).
    """
    hwp = _h()
    act = hwp.HAction
    hwp.SetPos(*anchor_pos)
    limit = _MAX_SLOT_SCAN if max_delete is None else min(max_delete, _MAX_SLOT_SCAN)
    for _ in range(limit):
        if not find_text("\\"):
            break
        if _before_anchor(anchor_pos) or _beyond(end_para):
            break                   # 삽입 범위 밖 — 사용자가 쓴 \ 이므로 건드리지 않는다
        act.Run("Delete")


def fill_slots(anchor, fills, end_para=None, slot_count=None):
    r"""anchor 이후의 빈칸(\)을 fills 로 위에서부터 채우고, 남은 건 청소.

    반환: 실제로 채운 개수.

    반환: (채운 개수, 채우려던 개수). 두 값이 다르면 중간에 멈춘 것이다 —
    호출부가 그 사실을 사용자에게 알려야 한다. 조용히 넘기면 인쇄물을 보고서야
    빈칸이 남은 걸 알게 된다.

    end_para 는 삽입 직후 기준의 범위다. 채워 넣는 값이 문단을 늘리지는 않지만
    (한 줄짜리 텍스트만 들어온다), 혹시 어긋나더라도 실패 방향은 '빈칸이 남는다'
    쪽이지 '남의 글자를 지운다' 쪽이 아니다.
    """
    hwp = _h()
    act = hwp.HAction
    filled = 0
    used = 0
    want = sum(1 for v in fills if v is not None)
    hwp.SetPos(*anchor)
    for value in fills:
        if not find_text("\\"):
            # 빈칸을 못 찾으면 남은 값은 갈 곳이 없다. 예전에는 조용히 멈춰서
            # 사용자가 인쇄물을 보고서야 알았다 → 기록을 남긴다.
            applog.warn(f"빈칸을 더 찾지 못해 채우기를 멈춥니다 "
                        f"({filled}/{want}개 채움)")
            break
        if _before_anchor(anchor) or _beyond(end_para):
            applog.warn(f"빈칸이 삽입 범위를 벗어나 채우기를 멈춥니다 "
                        f"({filled}/{want}개 채움)")
            break
        used += 1
        if value is None:
            act.Run("Delete")               # '-' → 그 빈칸은 비움
        elif isinstance(value, md_parser.MultiLine):
            # { … } 로 묶은 덩어리 — 이 빈칸 하나에 여러 줄을 넣는다.
            # 표 셀 안이면 BreakPara 가 셀 안에서 문단을 나눈다(칸이 세로로 늘어남).
            delete_selection()              # 빈칸 표시(\)를 먼저 지운다
            for n, line_value in enumerate(value.lines):
                if n:
                    act.Run("BreakPara")
                if isinstance(line_value, md_parser.Table):
                    # 덩어리 안의 \표3*3\ — 글과 표가 한 빈칸에 같이 들어간다
                    insert_table(line_value.rows, line_value.cols,
                                 line_value.grid)
                elif isinstance(line_value, list):
                    insert_rich_line(line_value)
                else:
                    insert_plain(line_value)
            filled += 1
        elif isinstance(value, list):
            # 사진·서식이 섞인 빈칸 (parser._slot_value 가 조각 목록으로 준다).
            # insert_picture 는 선택을 대신 지워 주지 않으므로 빈칸 표시를 먼저 지운다
            # — 안 그러면 사진 옆에 \ 가 그대로 남는다.
            delete_selection()
            insert_rich_line(value)
            filled += 1
        else:
            insert_plain(value)             # 글자만 — InsertText 가 선택을 대체한다
            filled += 1
    # 남은 빈칸만 청소한다. slot_count 를 알면 "이 템플릿에 남은 개수"가 정확한
    # 상한이 된다 — 그만큼만 지우므로 아래쪽 사용자 문서는 절대 안 건드린다.
    remaining = None if slot_count is None else max(int(slot_count) - used, 0)
    strip_slot_markers(anchor, end_para, max_delete=remaining)
    return filled, want


def count_slots_in_file(path):
    r"""hwp 파일 안의 빈칸(\) 개수를 센다 (양식 등록 시 안내용).

    현재 열려 있는 문서를 건드리지 않으려고 별도 창에서 열었다 닫는다.
    """
    hwp = _h()
    saved = hwp.XHwpDocuments.Count
    try:
        hwp.XHwpDocuments.Add(1)          # 1 = 새 탭으로 열기
        hwp.open(str(path))
        text = hwp.GetTextFile("TEXT", "") or ""
        # 본문 시작 표시(\본문\)는 채울 빈칸이 아니다 — 세기 전에 걷어낸다.
        # 안 그러면 역슬래시 2개가 빈칸으로 계산돼 개수가 부풀려진다.
        return text.replace(BODY_ANCHOR, "").count("\\")
    finally:
        try:
            if hwp.XHwpDocuments.Count > saved:
                hwp.XHwpDocuments.Active_XHwpDocument.Close(isDirty=False)
        except Exception as e:
            applog.exc("빈칸 세기용 임시 문서 닫기 실패 — 창이 남아 있을 수 있음", e)


def close_stale_temp_docs():
    r"""한글에 열린 채 남아 있는 _tmp_*.hwp 문서를 닫는다.

    구버전의 실패한 캡처가 한글에 임시 문서를 열어둔 채 남겼다(실측 2026-07-19).
    한글이 문서로 붙들고 있는 동안은 디스크에서 지울 수 없으므로, 먼저 그 문서를
    닫아 준다. 그러면 다음에 cleanup_temp_fragments 가 파일을 지울 수 있다.
    반환: 닫은 문서 수.
    """
    hwp = _h()
    closed = 0
    try:
        docs = hwp.XHwpDocuments
        # 닫으면 인덱스가 밀리므로 뒤에서 앞으로 훑는다
        for i in range(docs.Count - 1, -1, -1):
            try:
                name = docs.Item(i).FullName or ""
            except Exception:
                continue
            if "_tmp_" in name and name.lower().endswith(".hwp"):
                try:
                    docs.Item(i).Close(isDirty=False)
                    closed += 1
                except Exception as e:
                    applog.exc(f"임시 문서 닫기 실패 — {name}", e)
    except Exception as e:
        applog.exc("임시 문서 정리 중 오류", e)
    return closed


def export_as_hwpx(src_path, dst_path):
    """.hwp/.hwpx 를 HWPX 로 저장한다. 반환: 성공 여부.

    HWPX 여야 빈칸을 안전하게 채울 수 있다 — .hwp(바이너리)는 문단 레코드를
    직접 고치기 어렵지만, HWPX 는 zip+XML 이라 글자만 갈아끼울 수 있다
    (실측 2026-07-19). form_fill 모듈이 그 일을 한다.

    지금 열려 있는 문서를 건드리지 않으려고 별도 탭에서 열었다 닫는다
    (count_slots_in_file 과 같은 방식).
    """
    hwp = _h()
    saved = hwp.XHwpDocuments.Count
    try:
        hwp.XHwpDocuments.Add(1)          # 1 = 새 탭으로 열기
        hwp.open(str(src_path))
        return bool(hwp.save_as(str(dst_path), format="HWPX"))
    finally:
        try:
            if hwp.XHwpDocuments.Count > saved:
                hwp.XHwpDocuments.Active_XHwpDocument.Close(isDirty=False)
        except Exception as e:
            applog.exc("HWPX 변환용 임시 문서 닫기 실패 — 창이 남아 있을 수 있음", e)


# 고치는 동안 문서 맨 위에 붙는 안내문의 표시 (2026-07-26).
# 저장할 때 이 표시가 있는 줄들을 걷어내므로, 사용자가 절대 쓸 일 없는
# 문자열이어야 한다.
EDIT_NOTE_MARK = "※※ [고치는 중] "


def _insert_edit_note(lines):
    r"""문서 맨 위에 안내문을 넣는다. 각 줄 앞에 EDIT_NOTE_MARK 를 붙인다.

    왜 문서 안에 넣나 (사용자 결정 2026-07-26): 고치는 동안 사용자가 보는
    것은 **한글 창**이지 이 프로그램이 아니다. 무엇을 어떻게 고쳐야 하는지는
    고치는 화면 위에 같이 있어야 읽힌다.
    """
    hwp = _h()
    hwp.MoveDocBegin()
    for ln in lines:
        hwp_engine.insert_plain(EDIT_NOTE_MARK + ln)
        hwp.HAction.Run("BreakPara")
    hwp_engine.insert_plain("")          # 안내와 본문 사이 빈 줄
    hwp.HAction.Run("BreakPara")


def strip_edit_note():
    r"""안내문 줄들을 지운다 (저장 직전). 지운 줄 수를 돌려준다.

    문단 단위로 지운다 — 표 안이 아니라 문서 맨 위 문단들이므로 안전하다.
    """
    hwp = _h()
    removed = 0
    for _ in range(20):                  # 안내가 20줄을 넘을 일은 없다
        hwp.MoveDocBegin()
        if not hwp_engine.find_text(EDIT_NOTE_MARK):
            break
        try:
            hwp.HAction.Run("MoveSelLineEnd")   # 그 줄 끝까지 선택
            hwp.HAction.Run("Delete")
            hwp.HAction.Run("DeleteBack")       # 남은 빈 문단도 지운다
            removed += 1
        except Exception as e:
            applog.exc("안내문 줄 삭제 실패 — 저장물에 안내가 남을 수 있음", e)
            break
    return removed


def open_template_copy(path, note_lines=None):
    r"""템플릿 조각을 **새 탭**에 펼친다 — '꺼내서 고치기'용 (2026-07-25).

    파일을 직접 열지 않고 빈 새 탭에 insert 한다. 직접 열면 한글이 조각
    파일을 잠가(한 번 연 파일은 안 놓는다 — WinError 32 계보) 덮어쓰기
    저장이 막히기 때문이다. 새 탭은 제목 없는 문서라 원본과 무관하다.

    note_lines 를 주면 문서 맨 위에 안내문을 붙인다 (저장할 때 자동으로 빠진다).
    """
    hwp = _h()
    hwp.XHwpDocuments.Add(1)          # 1 = 새 탭
    hwp.insert_file(str(path), keep_section=0, keep_charshape=1,
                    keep_parashape=1, keep_style=1)
    if note_lines:
        _insert_edit_note(note_lines)
        hwp.MoveDocBegin()


def select_all():
    """지금 문서 전체 선택 — '꺼내서 고치기'의 덮어쓰기 캡처가 쓴다."""
    _h().HAction.Run("SelectAll")


def read_file_structure(path):
    r"""파일을 새 탭에서 읽어 (HWPML2X XML, 순수 텍스트) 를 돌려준다.

    양식→AI 프롬프트 변환용. XML 은 표 구조까지 담고 있어 마크다운 표로
    풀 수 있다. XML 추출이 실패하면 (None, 텍스트) — 호출부가 표 없이
    텍스트로만 만든다. 현재 문서는 건드리지 않는다 (count_slots_in_file 방식).
    """
    hwp = _h()
    saved = hwp.XHwpDocuments.Count
    xml = text = ""
    try:
        hwp.XHwpDocuments.Add(1)
        hwp.open(str(path))
        try:
            xml = hwp.GetTextFile("HWPML2X", "") or ""
        except Exception as e:
            applog.exc("HWPML2X 추출 실패 — 표 없이 텍스트로만 변환", e)
        text = hwp.GetTextFile("TEXT", "") or ""
    finally:
        try:
            if hwp.XHwpDocuments.Count > saved:
                hwp.XHwpDocuments.Active_XHwpDocument.Close(isDirty=False)
        except Exception as e:
            applog.exc("구조 읽기용 임시 문서 닫기 실패 — 창이 남아 있을 수 있음", e)
    return (xml or None), text


def open_form(path):
    r"""양식 파일을 새 문서로 연다 (용지·여백·머리말까지 원본 그대로).

    템플릿(insert_fragment)은 문서 '일부'를 커서 위치에 꽂는 것이라 페이지 설정이
    안 따라온다. 표지·통신문처럼 "이 양식으로 새로 시작"하려면 파일 전체를 열어야
    한다. 실측(2026-07-16): 여백 45/40 보존, 창 최대화도 유지됨.
    """
    hwp = _h()
    hwp.FileNew()
    hwp.open(str(path))


# ── 팔레트: 기능 블럭 실행 (여러 기능 병렬) ─────────────
_TOGGLE_ACTION = {
    "굵게": "CharShapeBold",
    "기울임": "CharShapeItalic",
    "밑줄": "CharShapeUnderline",
}
_PARA_ACTION = {
    "가운데정렬": "ParagraphShapeAlignCenter",
    "왼쪽정렬": "ParagraphShapeAlignLeft",
    "양쪽정렬": "ParagraphShapeAlignJustify",
}


def execute_function_block(actions):
    """기능 블럭 실행 — actions: [{"func":이름, "value":값}, ...] 를 병렬 적용.

    값 있는 글자서식(글씨체·크기·자간·색)은 한 번의 CharShape로 묶어 적용하고,
    토글(굵게 등)과 문단정렬은 개별 Run, 줄간격은 ParagraphShape로 적용한다.
    선택 영역이 있어야 의미가 있다(호출부에서 보장).
    """
    hwp = _h()
    act = hwp.HAction
    ps = hwp.HParameterSet

    char_fields = {}   # CharShape에 묶어 넣을 값들
    para_fields = {}   # ParagraphShape에 묶어 넣을 값들
    toggles = []       # Run 액션들
    para_aligns = []

    for a in actions:
        func = a.get("func")
        val = a.get("value")
        if func in _TOGGLE_ACTION:
            toggles.append(_TOGGLE_ACTION[func])
        elif func in _PARA_ACTION:
            para_aligns.append(_PARA_ACTION[func])
        elif func == "글씨체":
            char_fields["face"] = val
        elif func == "글씨크기":
            char_fields["height"] = float(val)
        elif func == "자간":
            char_fields["spacing"] = int(val)
        elif func == "글자색":
            char_fields["color"] = val
        elif func == "줄간격":
            para_fields["line_spacing"] = int(val)
        # 들여쓰기/내어쓰기는 같은 필드(Indentation)의 부호 차이 (실측 2026-07-15)
        #   양수 = 첫 줄을 안으로, 음수 = 첫 줄을 밖으로. 단위는 pt(=100 HwpUnit).
        elif func == "들여쓰기":
            para_fields["indent_pt"] = abs(float(val))
        elif func == "내어쓰기":
            para_fields["indent_pt"] = -abs(float(val))
        elif func == "왼쪽여백":
            para_fields["left_mm"] = float(val)
        elif func == "오른쪽여백":
            para_fields["right_mm"] = float(val)
        # 한글 줄나눔 단위 (실측 2026-07-16): BreakNonLatinWord
        #   1 = 글자 단위(기본, 단어 중간에서 잘림) / 0 = 어절 단위
        elif func == "어절단위 줄바꿈":
            para_fields["break_nonlatin"] = 0
        elif func == "자간 자동조절":
            para_fields["condense"] = int(val)

    # 1) 값 있는 글자서식 묶어서 한 번에
    if char_fields:
        act.GetDefault("CharShape", ps.HCharShape.HSet)
        if "face" in char_fields:
            ps.HCharShape.FaceNameHangul = char_fields["face"]
            ps.HCharShape.FaceNameLatin = char_fields["face"]
        if "height" in char_fields:
            ps.HCharShape.Height = hwp.PointToHwpUnit(char_fields["height"])
        if "spacing" in char_fields:
            ps.HCharShape.SpacingHangul = char_fields["spacing"]
            ps.HCharShape.SpacingLatin = char_fields["spacing"]
        if "color" in char_fields:
            ps.HCharShape.TextColor = char_fields["color"]
        act.Execute("CharShape", ps.HCharShape.HSet)

    # 2) 토글 기능
    for action_id in toggles:
        act.Run(action_id)

    # 3) 문단 정렬
    for action_id in para_aligns:
        act.Run(action_id)

    # 4) 값 있는 문단서식(줄간격·들여쓰기/내어쓰기·좌우여백) 묶어서 한 번에
    if para_fields:
        act.GetDefault("ParagraphShape", ps.HParaShape.HSet)
        if "line_spacing" in para_fields:
            ps.HParaShape.LineSpacing = para_fields["line_spacing"]
            ps.HParaShape.LineSpacingType = 0
        if "indent_pt" in para_fields:
            ps.HParaShape.Indentation = hwp.PointToHwpUnit(para_fields["indent_pt"])
        if "left_mm" in para_fields:
            ps.HParaShape.LeftMargin = hwp.MiliToHwpUnit(para_fields["left_mm"])
        if "right_mm" in para_fields:
            ps.HParaShape.RightMargin = hwp.MiliToHwpUnit(para_fields["right_mm"])
        if "break_nonlatin" in para_fields:
            ps.HParaShape.BreakNonLatinWord = para_fields["break_nonlatin"]
        if "condense" in para_fields:
            ps.HParaShape.Condense = para_fields["condense"]
        act.Execute("ParagraphShape", ps.HParaShape.HSet)


# ── 팔레트: 블럭 실행 ──────────────────────────────────
def run_block(block, template_path_fn=None, form_path_fn=None,
              slot_count_fn=None):
    r"""팔레트 블럭 하나를 실행한다. 종류에 따라 삽입/적용 분기.

    template_path_fn: 블럭 → 템플릿 조각 경로 (커서 위치에 삽입)
    form_path_fn:     블럭 → 양식 파일 경로 (새 문서로 열기)
    slot_count_fn:    블럭 → 그 템플릿의 빈칸(\) 개수. 빈칸 청소 범위를 개수로
                      제한하는 데 쓴다(없으면 문단 범위로만 제한).
    반환: (성공여부, 상태메시지)
    """
    btype = block.get("type")
    if btype == "char":
        insert_plain(block.get("value", ""))
        return True, "삽입"
    if btype == "function":
        if not has_selection():
            return False, "기능은 글자를 선택한 뒤 눌러주세요"
        execute_function_block(block.get("actions", []))
        return True, "기능 적용"
    if btype == "template":
        if template_path_fn is None:
            return False, "템플릿 경로를 찾을 수 없습니다"
        path = template_path_fn(block)
        if not path:
            return False, (f"템플릿을 찾을 수 없습니다: {block.get('template', '?')}"
                           " (라이브러리에서 삭제된 것 같습니다)")
        anchor = _h().GetPos()
        # 팔레트로 넣을 땐 채울 내용이 없으므로, 삽입한 범위 안의 빈칸만 청소한다.
        # slot_count 를 알면 그 개수만큼만 지운다 (모르면 문단 범위로만 제한).
        end_para = measure_insert_span(anchor, lambda: insert_fragment(path))
        strip_slot_markers(anchor, end_para,
                           max_delete=slot_count_fn(block) if slot_count_fn else None)
        return True, "템플릿 삽입"
    if btype == "form":
        if form_path_fn is None:
            return False, "양식 경로를 찾을 수 없습니다"
        path = form_path_fn(block)
        if not path:
            return False, (f"양식을 찾을 수 없습니다: {block.get('form', '?')}"
                           " (라이브러리에서 삭제된 것 같습니다)")
        open_form(path)
        # 새 문서로 연 것이므로 빈칸은 남겨둔다 — 사용자가 채우거나
        # \라벨\ 변환으로 채운다.
        return True, "양식 열기"
    return False, f"알 수 없는 블럭: {btype}"


def apply_default_format(fmt, text=None):
    """선택 영역을 기본 서식으로 초기화(글자모양+문단모양). text 주면 교체 삽입.

    fmt: palette.get_default_format() 결과.
    """
    hwp = _h()
    act = hwp.HAction
    ps = hwp.HParameterSet
    if text is not None:
        delete_selection()
    act.Run("StyleClearCharShape")

    act.GetDefault("CharShape", ps.HCharShape.HSet)
    ps.HCharShape.FaceNameHangul = fmt.get("font", "함초롬바탕")
    ps.HCharShape.FaceNameLatin = fmt.get("font", "함초롬바탕")
    ps.HCharShape.Height = hwp.PointToHwpUnit(fmt.get("size_pt", 10.0))
    ps.HCharShape.SpacingHangul = fmt.get("spacing", 0)
    ps.HCharShape.SpacingLatin = fmt.get("spacing", 0)
    # StyleClearCharShape만으로는 굵게/기울임/밑줄이 남을 수 있어 명시적으로 끔
    ps.HCharShape.Bold = 0
    ps.HCharShape.Italic = 0
    ps.HCharShape.UnderlineType = 0
    ps.HCharShape.TextColor = hwp.rgb_color(0, 0, 0)
    act.Execute("CharShape", ps.HCharShape.HSet)

    act.GetDefault("ParagraphShape", ps.HParaShape.HSet)
    ps.HParaShape.LineSpacing = fmt.get("line_spacing", 160)
    ps.HParaShape.LineSpacingType = 0
    ps.HParaShape.Indentation = 0
    ps.HParaShape.LeftMargin = 0
    ps.HParaShape.RightMargin = 0
    ps.HParaShape.PrevSpacing = 0
    ps.HParaShape.NextSpacing = 0
    ps.HParaShape.AlignType = fmt.get("align", 0)
    ps.HParaShape.BreakNonLatinWord = 1   # 한글 기본값(글자 단위)으로 복귀
    ps.HParaShape.Condense = 0            # 자간 자동조절 해제
    act.Execute("ParagraphShape", ps.HParaShape.HSet)

    if text is not None:
        insert_plain(text)


def insert_rich_line(segments):
    r"""서식 구간이 섞인 한 줄을 삽입한다 (개선안 27 — \굵게{내용}).

    구간마다 [삽입 전 위치 기록 → 삽입 → 그 구간만 다시 선택 → 서식 적용]을
    반복한다. 선택을 걸면 커서가 구간 앞쪽으로 갈 수 있으므로, 다음 구간을
    이어 쓰기 전에 **반드시 끝 위치로 되돌려 놓는다** — 안 그러면 두 번째
    구간부터 글자가 앞에 끼어 들어간다.

    **감싸지 않은 구간에도 서식을 적용한다** — 줄 시작 시점의 서식을 미리
    떠 두었다가 그대로 되입힌다. 한글은 새로 넣는 글자에 '앞 글자의 서식'을
    물려주기 때문에, 그냥 두면 `\굵게{중요} 나머지` 에서 '나머지'까지 굵게
    나온다. 물려받은 서식을 매번 원래대로 되돌려야 감싼 부분만 굵어진다.

    서식 적용에 실패해도 글자는 이미 들어가 있다. 그 경우 서식만 포기하고
    계속 진행한다 — 변환 전체를 되돌리는 것보다 낫다.
    """
    hwp = _h()
    # 줄 시작 시점의 서식 = 감싸지 않은 구간이 유지해야 할 모습
    base = None
    if any(s.get("style") for s in segments):
        try:
            base = capture_charshape(CHARSHAPE_FIELD_LABELS)
        except Exception as e:
            applog.exc("서식 감싸기: 원래 서식을 못 읽음 — 감싼 뒤 서식이 번질 수 있음", e)

    for seg in segments:
        image = seg.get("image")
        if image:
            # \사진이름\ — 사진 폴더의 그림을 글자처럼 삽입.
            # embedded=True 라 문서에 포함된다(원본 폴더를 지워도 그림은 남음).
            # sizeoption=3 = 셀 안이면 셀 크기에 맞춰 비율 유지(셀 밖이면 원본 크기).
            pos = None
            try:
                pos = hwp.GetPos()
            except Exception as e:
                applog.exc("사진 삽입 전 위치 기록 실패 — 삽입 후 커서를 못 되돌린다", e)
            try:
                hwp.insert_picture(str(image), treat_as_char=True, embedded=True,
                                   sizeoption=3)
            except Exception as e:
                applog.exc(f"사진 삽입 실패 ({image}) — 자리 표시 텍스트로 대체", e)
                insert_plain(f"[사진 실패: {image}]")
                continue
            # ⚠ 그림을 넣으면 한글이 그 '그림 개체'를 선택한 채로 둔다.
            # 개체가 선택돼 있으면 뒤이은 찾기(RepeatFind)가 글자를 못 찾는다 →
            # fill_slots 가 다음 빈칸을 못 찾고 통째로 멈췄다
            # ("사진 전까지는 잘 들어가는데 그 뒤로 안 들어간다"의 원인).
            # 개체 선택을 풀고, 글자처럼취급된 그림(= 글자 한 칸) 바로 뒤로 커서를 옮긴다.
            try:
                hwp.HAction.Run("Cancel")
                if pos:
                    hwp.SetPos(pos[0], pos[1], pos[2] + 1)
            except Exception as e:
                applog.exc("사진 삽입 후 커서 복귀 실패 — 뒤따르는 내용이 밀릴 수 있음", e)
            continue
        text = seg.get("text") or ""
        if not text:
            continue
        start = hwp.GetPos()
        insert_plain(text)
        end = hwp.GetPos()
        delta = seg.get("style") or base
        if not delta:
            continue
        try:
            if hwp.select_text_by_get_pos(start, end):
                apply_charshape_delta(delta)
            else:
                applog.warn(f"서식 감싸기: 구간 선택 실패 — 서식 없이 삽입됨 ({text[:20]!r})")
        except Exception as e:
            applog.exc(f"서식 감싸기 적용 실패 ({text[:20]!r}) — 글자는 삽입됨", e)
        finally:
            hwp.HAction.Run("Cancel")       # 선택 해제
            hwp.SetPos(*end)                # 다음 구간은 이 줄 끝에서 이어 쓴다


def _unit_changes(unit, ops):
    """이 조각이 변환으로 실제로 달라지는가.

    안 달라지면 문서를 아예 건드리지 않는다 — 라벨이 없는 셀까지 지웠다 다시
    넣으면 서식이 흔들리고, 찾기가 어긋났을 때 멀쩡한 글을 망칠 위험만 커진다.
    """
    if len(ops) != 1:
        return True
    if ops[0][0] == "rich_line":
        return True                 # 서식·사진이 섞였다 = 반드시 다시 그려야 한다
    return ops[0][1] != unit


def convert_units_in_place(units, plan_fn, anchor=None):
    r"""조각들을 **있던 자리에서** 변환한다 (표의 셀 경계를 지키려고).

    왜 따로 있나:
      execute_library_plan 은 '선택을 통째로 지우고 커서 한 곳에 다시 쓰는' 방식이다.
      본문에서는 맞지만 표에서는 셀 경계가 사라진다 — 여러 셀을 선택해 변환하면
      모든 셀의 내용이 커서가 남은 한 셀에 줄바꿈으로 쌓였다(사진이 한 칸에
      몰리던 버그). 셀 안 내용은 옮길 필요가 없으므로, 옮기지 않고 제자리에서
      찾아 바꾼다. 그러면 find_text 가 알아서 해당 셀로 들어가므로 셀 이동을
      직접 다룰 필요도 없다.

    앞뒤로 찾는 이유:
      선택을 풀면(Cancel) 커서가 선택의 **끝**에 남을 수 있다(드래그 방향에 달렸다).
      그러면 조각들이 전부 커서 뒤쪽에 있어 앞으로 찾기만 해서는 하나도 못 찾는다.
      그래서 앞으로 찾아 실패하면 뒤로 한 번 더 찾는다. 첫 조각을 뒤에서 찾고
      나면 커서가 그 자리로 오므로, 나머지는 자연히 앞으로 찾기로 이어진다.

    안전 원칙 — 실패 방향은 '원문이 그대로 남는다' 쪽이다:
      · 바뀔 게 없는 조각은 건드리지 않는다 (라벨 없는 셀은 그대로 둔다)
      · 찾지 못한 조각은 경고만 남기고 건너뛴다 (지우지 않는다)
      · 바꾸는 대상은 사용자가 **선택한 글자와 완전히 같은 줄**뿐이다. 문서
        다른 곳의 같은 라벨이 함께 바뀔 수는 있어도, 그것도 사용자가 변환하려던
        라벨이므로 훼손이 아니다.

    plan_fn: 조각 한 개(=한 줄) → (ops, warnings). 경고는 여기서 쓰지 않는다.
      호출부가 이미 선택 전체에 대해 같은 경고를 사용자에게 보여줬기 때문이다.
    반환: 실제로 바꾼 조각 수.
    """
    hwp = _h()
    act = hwp.HAction
    if anchor is not None:
        try:
            hwp.SetPos(*anchor)
        except Exception as e:
            applog.exc("변환 시작 위치 복원 실패 — 커서가 있는 곳부터 찾습니다", e)
    changed = 0
    for unit in units:
        ops, _ = plan_fn(unit)
        if not _unit_changes(unit, ops):
            continue
        if not (find_text(unit) or find_text(unit, direction="Backward")):
            applog.warn(f"바꿀 자리를 찾지 못해 건너뜀: {unit[:30]!r}")
            continue
        delete_selection()
        for idx, op in enumerate(ops):
            if idx:
                act.Run("BreakPara")
            if op[0] == "line":
                if op[1]:
                    insert_plain(op[1])
            elif op[0] == "rich_line":
                insert_rich_line(op[1])
        changed += 1
    return changed


# ── 라이브러리: 마크다운(\라벨\) 변환 실행 ───────────────
def execute_library_plan(ops, template_path_fn, form_path_fn=None):
    r"""parser.build_library_plan()의 실행 계획을 문서에 반영한다.

    호출 전에 선택 영역은 삭제돼 있어야 한다(커서 = 삽입 지점).

    2단계 방식: ① 텍스트 줄과 '템플릿 자리표시 마커'를 순서대로 삽입 →
    ② 마커를 찾아 조각으로 바꾸고, 이어서 빈칸(\)을 아랫줄 내용으로 채움.
    한 번에 삽입하지 않는 이유: insert_file 직후 커서가 조각 뒤로 이동하지
    않아(실측) 순차 삽입 순서가 꼬이기 때문 — 마커 방식이 순서를 보장한다.

    양식('form')은 성격이 달라 **먼저** 처리한다 — 문서 전체를 여는 것이라
    마커를 심어둔 문서가 사라지기 때문이다. 양식을 연 뒤 본문 자리(BODY_ANCHOR)로
    커서를 옮기고, 나머지 계획을 그 문서에서 이어서 실행한다 (2026-07-24).
    예전에는 양식이 있으면 그것만 처리하고 나머지를 버렸다 — 시험지처럼
    "양식 + 문제들"을 한 번에 변환할 수가 없었다.
    """
    hwp = _h()
    act = hwp.HAction

    marker_base = "◈LIB%d_" % (int(time.time() * 1000) % 10**9)

    forms_done = 0
    form_filled = 0
    form_wanted = 0

    # ── 양식이 있으면: 그 문서를 열고 커서를 본문 자리에 놓는다 ──
    form_op = next((o for o in ops if o[0] == "form"), None)
    if form_op is not None:
        _, item, fills = form_op
        path = form_path_fn(item) if form_path_fn else None
        if not path:
            return {"templates": 0, "slots_filled": 0, "forms": 0,
                    "error": f"양식 파일을 찾을 수 없습니다: {item.get('name', '?')}"}
        open_form(path)

        # ① 본문 표시를 고유 마커로 먼저 치환한다.
        #    \본문\ 은 역슬래시 2개라, 그냥 두면 ②의 fill_slots 가 이걸
        #    빈칸으로 보고 내용을 채워 넣어 버린다.
        body_marker = marker_base + "BODY◈"
        hwp.MoveDocBegin()
        has_anchor = find_text(BODY_ANCHOR)
        if has_anchor:
            delete_selection()
            insert_plain(body_marker)

        # ② 양식이 가진 빈칸(\)을 양식 라벨 아랫줄들로 채운다.
        #    새로 연 양식 문서 전체가 대상이므로 범위 제한을 두지 않는다
        #    (사용자가 쓴 다른 내용이 섞여 있을 수 없는, 유일하게 안전한 경우)
        hwp.MoveDocBegin()
        form_filled, form_wanted = fill_slots(
            hwp.GetPos(), fills, end_para=None,
            slot_count=item.get("slot_count"))
        forms_done = 1

        # ③ 본문 자리로 커서 이동. 표시가 없는 양식이면 문서 끝에서 이어 쓴다.
        hwp.MoveDocBegin()
        if has_anchor and find_text(body_marker):
            delete_selection()
        else:
            hwp.MoveDocEnd()
            if not has_anchor:
                applog.warn(
                    f"양식 '{item.get('name', '?')}' 에 본문 표시({BODY_ANCHOR})가 "
                    f"없어 문서 끝에 이어 씁니다")

        # ④ 나머지 계획을 이 문서에서 이어서 실행한다.
        ops = [o for o in ops if o[0] != "form"]
        if not ops:
            return {"templates": 0, "slots_filled": form_filled,
                    "slots_wanted": form_wanted, "forms": 1}

    # ① 텍스트/마커 순차 삽입
    templates = []
    first = True
    for op in ops:
        if not first:
            act.Run("BreakPara")
        first = False
        if op[0] == "line":
            if op[1]:
                insert_plain(op[1])
        elif op[0] == "rich_line":
            insert_rich_line(op[1])
        elif op[0] == "table":
            insert_table(op[1], op[2], op[3])
        else:                               # ('template', item, fills)
            insert_plain(marker_base + str(len(templates)) + "◈")
            templates.append(op)

    # ② 마커 → 조각 치환 + 빈칸(\) 순서대로 채움
    filled = 0
    wanted = 0
    for idx, (_, item, fills) in enumerate(templates):
        marker = marker_base + str(idx) + "◈"
        hwp.MoveDocBegin()
        if not find_text(marker):
            applog.warn(f"마커 유실로 템플릿을 건너뜀: {item.get('name', '?')}")
            continue
        delete_selection()
        anchor = hwp.GetPos()
        path = template_path_fn(item)
        end_para = measure_insert_span(anchor, lambda p=path: insert_fragment(p))
        got, want = fill_slots(anchor, fills, end_para,
                               slot_count=item.get("slot_count"))
        filled += got
        wanted += want
    # 양식을 먼저 처리했다면 그 빈칸 개수도 합쳐서 보고한다 — 사용자에겐
    # "이번 변환에서 빈칸 몇 개를 채웠나"가 하나의 숫자여야 한다.
    return {"templates": len(templates), "slots_filled": filled + form_filled,
            "slots_wanted": wanted + form_wanted, "forms": forms_done}
