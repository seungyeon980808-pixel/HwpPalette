# -*- coding: utf-8 -*-
r"""내장 문자 — 등록 없이 바로 쓰는 규칙적인 기호들.

라이브러리(서식/문자/템플릿)와 달리 사용자가 등록하지 않아도 되는, 개수 많고
규칙적인 문자들을 코드에 내장한다. 마크다운 변환에서 \원1\ \로마3\ 처럼 호출하고,
물감 설정의 '특수기호' 탭에 내가 등록한 기호와 함께 격자로 보인다.

각 항목: (label, text, group)
  label = \label\ 로 부를 이름 (사용자 등록 항목과 이름이 겹치면 사용자 것이 우선)
  text  = 삽입될 실제 문자
  group = 검색·분류용 이름
"""

# 원문자 자모 순서 (㉠=ㄱ … ㉭=ㅎ)
_KR_CONSONANTS = list("ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ")


def _build():
    items = []

    # ── 원문자: 숫자 ①~⑳ ──
    for i in range(20):
        items.append((f"원{i+1}", chr(0x2460 + i), "원문자·숫자"))
    # ── 원문자: 알파벳 ⓐ~ⓩ ──
    for i in range(26):
        items.append((f"원{chr(ord('a')+i)}", chr(0x24D0 + i), "원문자·알파벳"))
    # ── 원문자: 한글 자모 ㉠~㉭ ──
    for i, c in enumerate(_KR_CONSONANTS):
        items.append((f"원{c}", chr(0x3260 + i), "원문자·한글"))

    # ── 로마 숫자 Ⅰ~Ⅻ ──
    for i in range(12):
        items.append((f"로마{i+1}", chr(0x2160 + i), "로마숫자"))

    # ── 낫표 (양쪽 방향 둘 다 = 쌍) + 방향별 ──
    items.append(("홑낫표", "「」", "낫표"))
    items.append(("겹낫표", "『』", "낫표"))
    items.append(("여는홑낫표", "「", "낫표"))
    items.append(("닫는홑낫표", "」", "낫표"))
    items.append(("여는겹낫표", "『", "낫표"))
    items.append(("닫는겹낫표", "』", "낫표"))

    return items


BUILTINS = _build()

# 라벨 → 텍스트 빠른 조회
BUILTIN_LOOKUP = {label: text for label, text, _ in BUILTINS}


def search(query):
    """query가 label/text/group 어디에든 들어가면 매치. 빈 query면 전체."""
    q = (query or "").strip().lower()
    if not q:
        return list(BUILTINS)
    out = []
    for label, text, group in BUILTINS:
        if q in label.lower() or q in text.lower() or q in group.lower():
            out.append((label, text, group))
    return out
