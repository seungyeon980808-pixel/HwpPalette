r"""마크다운 파일 → 한글 조판 CLI (ExamMaker 파이프라인의 마지막 구간).

    python -m hwp_palette.cli --markdown-file 세트.md [--append]

ExamPool 이 내보낸 세트 마크다운(\템플릿\ + 빈칸 줄 문법)을 통째로 받아,
한글을 열고(없으면 실행) 새 문서에 전체를 조판한다. GUI 의 Ctrl+Alt+T 와
같은 엔진(build_library_plan → execute_library_plan)을 쓰되, '선택 영역'
대신 파일이 입력이라는 점만 다르다.

**저장은 하지 않는다** — 조판 결과를 사용자가 한글에서 확인하고 직접 저장한다
(5E 의 "저장은 사용자 손으로" 원칙과 같다).
"""
import argparse
import pathlib
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="python -m hwp_palette.cli",
        description="마크다운 파일을 한글 새 문서에 조판한다 (저장은 사용자가).")
    ap.add_argument("--markdown-file", required=True,
                    help="조판할 마크다운 파일 경로 (UTF-8)")
    ap.add_argument("--append", action="store_true",
                    help="새 문서를 만들지 않고 지금 활성 문서의 커서 위치에 조판")
    args = ap.parse_args(argv)

    src = pathlib.Path(args.markdown_file)
    if not src.is_file():
        print(f"파일이 없습니다: {src}", file=sys.stderr)
        return 2
    text = src.read_text(encoding="utf-8")
    if not text.strip():
        print("파일이 비어 있습니다.", file=sys.stderr)
        return 2

    # 무거운 것(COM·라이브러리)은 인자 검증이 끝난 뒤에야 불러온다 —
    # --help 만 치는 사람이 한글 연결을 기다리게 하지 않는다.
    from hwp_palette.core import applog
    from hwp_palette.model import library
    from hwp_palette.model import parser as md_parser
    from hwp_palette.hwp import engine_library, hwp_engine

    if not md_parser.has_library_tokens(text):
        print("라이브러리 문법(\\라벨\\)이 없습니다 — ExamPool 의 세트 export 결과를 "
              "넣어 주세요. 시험문제 문법(번호:/발문: …)은 GUI 의 Ctrl+Alt+T 로.",
              file=sys.stderr)
        return 2

    lookup = library.label_lookup()
    ops, warns = md_parser.build_library_plan(text, lookup)
    # '양식'(form)은 스스로 새 문서를 여는 블럭이라 순차 조판과 섞이지 않는다 —
    # GUI 도 같은 이유로 막는다(_form_plan_conflict). 여기서도 지우기 전에 막는다.
    if any(op[0] == "form" for op in ops):
        print("양식(\\양식라벨\\)은 CLI 로 조판할 수 없습니다 — GUI 에서 따로 변환해 주세요.",
              file=sys.stderr)
        return 2

    try:
        hwp_engine.connect()
    except Exception as e:
        applog.exc("CLI: 한글 연결 실패", e)
        print(f"한글에 연결하지 못했습니다: {e}", file=sys.stderr)
        return 1

    if not args.append:
        hwp_engine.new_document()

    result = engine_library.execute_library_plan(
        ops, library.template_path, form_path_fn=library.template_path)
    if result.get("error"):
        print(f"조판 실패: {result['error']}", file=sys.stderr)
        return 1

    n_tpl = sum(1 for op in ops if op[0] == "template")
    n_line = len(ops) - n_tpl
    print(f"조판 완료: 템플릿 {n_tpl}개 + 줄 {n_line}개 ({src.name})")
    for w in warns:
        print(f"  주의: {w}")
    print("한글에서 결과를 확인하고 직접 저장하세요 — CLI 는 저장하지 않습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
