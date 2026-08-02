# -*- coding: utf-8 -*-
r"""ExamMaker 템플릿 조각 3종을 한글 COM 으로 만들어 등록한다 (1회용 도구).

    python tools/make_exam_fragments.py

만드는 것 (export_palette.py 의 갭 3종):
  학교합답0사진5선지  11칸: 번호·지문발문·점수 / ㄱㄴㄷ / 선지5 (실험 템플릿과 같은 순서)
  정답형1사진        10칸: 번호·발문·점수 / 사진 / 선지5(세로)
  서술형             3칸: 번호·발문·점수 / 답란 상자

빈칸은 홑 \ 로 심는다 — 조각 저장(save_active_as)이 normalize_marks_to_pairs 로
쌍(\\)으로 정리하고, 등록(add_template_from_capture)이 본문에서 자리 수를 다시 센다.
작업 탭은 닫지 않는다(수정된 문서 닫기 확인창이 COM 을 막는다) — 끝나면 사용자가 닫는다.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hwp_palette.hwp import engine_library, exam_engine, hwp_engine
from hwp_palette.model import library

BLANK = "\\"        # 홑 자리 표시 — 저장 시 쌍으로 정리된다


def _act():
    return hwp_engine.hwp.HAction


def _head_line():
    """`\. \ (\점)` — 번호·지문발문·점수 세 자리를 한 문단에."""
    hwp_engine._text(f"{BLANK}. {BLANK} ({BLANK}점)")
    _act().Run("BreakPara")


def build_school_habdap():
    _head_line()
    exam_engine.insert_bogi_box([BLANK, BLANK, BLANK])
    # 표 탈출(CloseEx) 뒤 커서가 표 '앞' 문단에 남아, 다음 표가 보기 위에
    # 끼어들었다(실측 2026-08-03: 선지 표가 〈보기〉 위로). 문서 끝으로 옮겨
    # 순서를 보장한다 — 빈 문서에서 조각을 빌드하는 이 도구에서만 안전한 수법.
    _act().Run("MoveDocEnd")
    exam_engine._insert_choices({"choices": [BLANK] * 5, "choices_type": "5"})
    _act().Run("MoveDocEnd")


def build_jungdap_photo():
    _head_line()
    _act().Run("ParagraphShapeAlignCenter")
    hwp_engine._text(BLANK)
    _act().Run("BreakPara")
    _act().Run("ParagraphShapeAlignLeft")
    exam_engine._insert_choices({"choices": [BLANK] * 5, "choices_type": "1"})


def build_school_habdap_photo():
    """사진 칸이 있는 합답형 — 발문을 조각에 박지 않는다.

    발문이 박힌 기존 합답형 조각은 부정발문("옳지 않은")을 표현할 수 없다.
    지문 칸에 발문을 함께 넣으면 발문이 두 번 찍히고, 안 넣으면 부정이 사라진다.
    """
    _head_line()
    _act().Run("ParagraphShapeAlignCenter")
    hwp_engine._text(BLANK)
    _act().Run("BreakPara")
    _act().Run("ParagraphShapeAlignLeft")
    exam_engine.insert_bogi_box([BLANK, BLANK, BLANK])
    _act().Run("MoveDocEnd")
    exam_engine._insert_choices({"choices": [BLANK] * 5, "choices_type": "5"})
    _act().Run("MoveDocEnd")


def build_essay():
    _head_line()
    hwp_engine._create_table(1, 1, hwp_engine._col_width_mm(), [45])
    hwp_engine._exit_table(_act())


PLAN = [
    ("학교합답0사진5선지", build_school_habdap, 11),
    ("학교합답1사진5선지", build_school_habdap_photo, 12),
    ("정답형1사진",       build_jungdap_photo, 9),
    ("서술형",            build_essay,          3),
]


def main():
    hwp_engine.connect()
    existing = {it["label"] for it in library.load()["템플릿"]}
    results = []
    for name, build, want in PLAN:
        if name in existing:
            results.append((name, "이미 등록됨 — 건너뜀", None))
            continue
        hwp_engine.new_document()
        build()
        # 캡처(복사→붙여넣기)는 표 두 개짜리 선택을 온전히 담지 못했다(실측
        # 2026-08-03: 선지 표만 저장됨). 빌드한 문서를 통째로 저장하는 쪽이
        # 정확하다 — 캡처도 결국 임시 문서를 통째로 저장하는 방식이므로
        # 조각 파일 형식은 같다.
        item_id = library.add_template_from_capture(
            name, lambda p: engine_library.save_active_as(p),
            label=name, subcat="시험출제")
        got = next(it["slot_count"] for it in library.load()["템플릿"]
                   if it["id"] == item_id)
        ok = "OK" if got == want else f"⚠ 자리 수 불일치 (기대 {want})"
        results.append((name, ok, got))
    print()
    for name, status, got in results:
        print(f"  {name}: {status}" + (f" — 자리 {got}칸" if got is not None else ""))
    print("\n작업 탭은 열어 두었습니다 — 한글에서 확인 후 저장 없이 닫으세요.")


if __name__ == "__main__":
    main()
