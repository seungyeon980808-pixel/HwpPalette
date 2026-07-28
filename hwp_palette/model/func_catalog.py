# -*- coding: utf-8 -*-
"""기능 카탈로그 — '기능' 블럭에 병렬로 담을 수 있는 한글 조작 목록.

각 기능의 실제 실행은 engine_library.execute_function_block()이 한다. 여기서는
UI가 "어떤 기능이 있고, 값을 어떻게 입력받는지"만 정의한다.

kind:
  toggle   값 없음. 켜기/끄기 토글 (굵게 등) — 선택 영역에 Run 액션
  number   숫자 입력 (자간, 크기, 줄간격)
  font     글꼴 이름 (드롭다운 + 직접 입력)
  color    색상 (팔레트)
  para     문단 정렬 등 값 없는 문단 액션
"""

FUNCTIONS = [
    {"key": "굵게",     "kind": "toggle", "hint": "선택 글자를 굵게 (토글)"},
    {"key": "기울임",   "kind": "toggle", "hint": "선택 글자를 기울임 (토글)"},
    {"key": "밑줄",     "kind": "toggle", "hint": "선택 글자에 밑줄 (토글)"},
    {"key": "글씨체",   "kind": "font",   "hint": "글꼴 변경"},
    {"key": "글씨크기", "kind": "number", "unit": "pt", "hint": "글자 크기(pt)"},
    {"key": "자간",     "kind": "number", "unit": "",   "hint": "글자 간격(음수=좁게)"},
    {"key": "글자색",   "kind": "color",  "hint": "글자 색"},
    {"key": "가운데정렬", "kind": "para", "hint": "문단 가운데 정렬"},
    {"key": "왼쪽정렬",   "kind": "para", "hint": "문단 왼쪽 정렬"},
    {"key": "양쪽정렬",   "kind": "para", "hint": "문단 양쪽 정렬"},
    {"key": "줄간격",   "kind": "number", "unit": "%",  "hint": "문단 줄간격(%)"},
    {"key": "들여쓰기", "kind": "number", "unit": "pt",
     "hint": "첫 줄만 안으로 (문단 첫 줄 들여쓰기)"},
    {"key": "내어쓰기", "kind": "number", "unit": "pt",
     "hint": "첫 줄만 밖으로 (둘째 줄부터 들여씀 — 발문·보기 번호용)"},
    {"key": "왼쪽여백", "kind": "number", "unit": "mm", "hint": "문단 전체를 오른쪽으로"},
    {"key": "오른쪽여백", "kind": "number", "unit": "mm", "hint": "문단 오른쪽 여백"},
    {"key": "어절단위 줄바꿈", "kind": "toggle",
     "hint": "한글이 글자 단위로 잘리지 않고 어절(띄어쓰기) 단위로 넘어감"},
    {"key": "자간 자동조절", "kind": "number", "unit": "%",
     "hint": "줄 끝을 맞추려 자간을 자동으로 좁힘 (0~50 권장)"},
]

# 소수점 입력을 허용할 기능 (나머지는 정수)
FLOAT_KEYS = {"글씨크기", "들여쓰기", "내어쓰기", "왼쪽여백", "오른쪽여백"}

FUNC_BY_KEY = {f["key"]: f for f in FUNCTIONS}

# 글꼴 드롭다운 후보 (직접 입력도 허용). 실측 fontsUsed 기반.
COMMON_FONTS = [
    "함초롬바탕", "함초롬돋움", "맑은 고딕", "굴림", "굴림체", "바탕", "돋움",
    "한컴산뜻돋움", "HY헤드라인M",
    "HY견고딕", "HY견명조", "HY신명조", "HY중고딕", "휴먼명조",
]
