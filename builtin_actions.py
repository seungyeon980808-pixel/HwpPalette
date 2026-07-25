# -*- coding: utf-8 -*-
r"""프로그램 기능 카탈로그 — 팔레트에 블럭으로 놓을 수 있는 '앱 자체 기능'.

왜 필요한가 (2026-07-25):
    사진 삽입·특수문자·양식 채우기 같은 것은 **코드에 박혀 있어** 사용자가 빼거나
    순서를 바꿀 수 없었다. 반면 문자·템플릿·서식 조합 블럭은 전부 사용자 것이다.
    "내가 만들어 넣은 기능도 추가·삭제할 수 있으면 좋겠다"는 요청이 이 간극을
    가리킨다 — 그래서 앱 기능도 **블럭 한 종류**로 만들어 같은 규칙에 태운다.

여기는 '무엇이 있는지'만 정의한다. 실제 실행은 main.py 가 키를 보고 자기
함수로 잇는다(BUILTIN_DISPATCH) — 이 모듈이 UI 를 임포트하지 않게 하려는 것이다.

func_catalog.py 와 헷갈리지 말 것:
    func_catalog = 선택 영역에 **한글 서식**을 먹이는 조작 목록('서식 조합' 블럭)
    builtin_actions = 이 **프로그램의 기능** 자체 (창 열기, 변환 실행 등)
"""

# key 는 config.json 에 저장되므로 **바꾸면 기존 블럭이 끊긴다.**
BUILTIN_ACTIONS = [
    {"key": "convert",      "name": "마크다운 변환",
     "hint": "선택한 마크다운을 한글 문서로 변환"},
    {"key": "reset_format", "name": "기본 서식",
     "hint": "선택 영역을 기본 글꼴·크기·줄간격으로 되돌림"},
    {"key": "photo",        "name": "사진",
     "hint": "그림 파일을 골라 커서 자리에 삽입"},
    {"key": "special",      "name": "특수문자",
     "hint": "내장 기호 목록 (\\원1\\ \\로마3\\ \\홑낫표\\ …)"},
    {"key": "form_fill",    "name": "양식 채우기",
     "hint": "양식의 빈칸을 뽑아 채운 뒤 새 문서로 열기"},
    {"key": "library",      "name": "라이브러리",
     "hint": "등록한 서식·문자·템플릿·양식 관리"},
    {"key": "search",       "name": "통합 찾기",
     "hint": "블럭과 라이브러리를 한 번에 검색"},
]

ACTION_BY_KEY = {a["key"]: a for a in BUILTIN_ACTIONS}

# 첫 실행 때 '메인' 탭에 깔아 둘 기본 도구. 예전에 코드로 박혀 있던 네 개를
# 그대로 옮겨 놓는다 — 처음 쓰는 사람이 빈 화면을 보지 않게 하려는 것이다.
# 그 뒤로는 사용자가 지우든 옮기든 자유이고, 다시 채워 넣지 않는다.
DEFAULT_MAIN_KEYS = ("reset_format", "photo", "special", "form_fill")


def name_of(key):
    """키 → 사람이 읽는 이름. 모르는 키면 키를 그대로 돌려준다."""
    action = ACTION_BY_KEY.get(key)
    return action["name"] if action else (key or "?")


def hint_of(key):
    action = ACTION_BY_KEY.get(key)
    return action["hint"] if action else ""
