# -*- coding: utf-8 -*-
r"""특수기호 목록을 만드는 **규칙 한 곳** (2026-08-01, 피드백 028).

왜 생겼나 — 회귀의 내력:
    기호를 고르는 화면이 두 벌이었다. 물감 설정(창고)의 '문자' 탭에는
    **묶음 목록**(원문자·로마숫자·수학 …)과 **내가 등록한 기호**가 있었고,
    팔레트 빈칸에서 여는 창(`_CharDialog`)에는 검색칸 하나뿐이었다.
    022("에셋별로 만들기 창은 하나여야 한다")를 반영하면서 **기능이 적은
    쪽으로 합쳐 버렸고**, 사용자는 묶음 목록과 자기가 등록한 기호를 잃었다.

        "원래 특수기호가 종류별로 잘 정리가 되어있었는데 왜 구조가 자기
         마음대로 변경된 것인지? 종류별로 분류되어 있어야 합니다.
         내가 추가한 특수기호도 들어가야하는거고요"

    합치는 방향을 **반대로** 잡는다: 묶음이 있는 쪽이 기준이다. 다만 두 창은
    하는 일이 달라서(한쪽은 블럭 만들기, 한쪽은 물감 고르기) 화면을 통째로
    합치지는 않는다 — 대신 **목록을 만드는 규칙**을 여기 한 곳에 둔다.
    한쪽만 고쳐 다시 어긋나는 일이 이 회귀의 원인이었다.

여기는 화면을 그리지 않는다. 무엇이 목록에 들어가고 어떤 묶음이 있는지만 안다.
"""

from hwp_palette.model import builtin_chars
from hwp_palette.model import library

ALL_GROUP = "전체"
MY_GROUP = "내가 등록"


def groups():
    r"""묶음 목록 — `전체` · `내가 등록` · 내장 기호의 묶음들(나온 차례대로).

    하드코딩하지 않는다: 묶음은 `builtin_chars` 의 항목이 스스로 달고 있어서,
    기호를 더하면 묶음도 저절로 따라온다.
    """
    out = [ALL_GROUP, MY_GROUP]
    for _label, _text, g in builtin_chars.BUILTINS:
        if g not in out:
            out.append(g)
    return out


def _blob(item):
    """검색어를 맞춰 볼 글자 뭉치 (호출부가 제 것을 주면 그것을 쓴다)."""
    return " ".join(str(item.get(k) or "")
                    for k in ("name", "label", "text")).lower()


def entries(group=ALL_GROUP, query="", blob_fn=None):
    r"""그 묶음에서 보여줄 기호들 — **내가 등록한 것이 먼저**.

    반환 하나하나: `{kind, cat, item, text, label, group}`
      · kind "item"    = 내가 등록한 문자 물감 (item 이 진짜 물감 기록)
      · kind "builtin" = 내장 기호 (item 은 화면이 쓰기 좋게 지어낸 것)

    내가 등록한 것은 내장 기호의 묶음(원문자·수학 …)에 속하지 않는다 —
    묶음에서는 `내가 등록`으로만 걸리고, `전체`에는 함께 나온다.
    """
    ql = (query or "").lower()
    hit = blob_fn or _blob
    out = []
    if group in (ALL_GROUP, MY_GROUP):
        for it in library.list_items("문자"):
            if ql and ql not in hit(it):
                continue
            out.append({"kind": "item", "cat": "문자", "item": it,
                        "text": it.get("text", ""),
                        "label": it.get("label") or it["name"],
                        "group": MY_GROUP})
    if group != MY_GROUP:
        for label, text, g in builtin_chars.search(query):
            if group not in (ALL_GROUP, g):
                continue
            out.append({"kind": "builtin", "cat": "문자",
                        "item": {"name": label, "label": label,
                                 "text": text, "group": g},
                        "text": text, "label": label, "group": g})
    return out
