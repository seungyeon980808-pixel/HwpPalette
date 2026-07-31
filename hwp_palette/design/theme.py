# -*- coding: utf-8 -*-
"""화면 색 한 곳 모음 (UI 제안 17·18).

여태 BG/CARD/TEXT... 같은 색 상수가 main·palette_ui·library_ui·form_fill_ui·
bogi_visual_ui 다섯 파일에 **똑같이 복사**돼 있었다. 다크 모드를 넣으려면
다섯 군데를 따로 고쳐야 하고, 한 곳을 빠뜨리면 창 하나만 하얗게 뜬다.
그래서 색을 여기로 모으고 각 파일은 읽어 쓰기만 한다.

밝게/어둡게 전환은 **다시 시작**으로 처리한다. Tk 위젯은 만든 뒤 색을 일괄로
못 바꾸고(위젯마다 config 를 다시 줘야 한다), 화면 크기 모드(ui_scale)가 이미
같은 방식이라 규칙을 하나로 맞추는 편이 낫다.
"""

from hwp_palette.core import settings

MODE_KEY = "ui_theme"

# 밝게 — 기존 색 그대로 (바뀌면 안 된다. 지금 쓰던 화면이다)
LIGHT = {
    "bg":     "#f5f5f7",
    "card":   "#ffffff",
    "accent": "#0071e3",
    "text":   "#1d1d1f",
    # 예전 #86868b 는 배경 대비가 3.3 뿐이라 WCAG 본문 기준(4.5)에 못 미쳤다.
    # 버전·저작자 표기처럼 작은 글자에 쓰이는 색이라 한 단계 어둡게 했다(4.7).
    "muted":  "#6e6e73",
    # muted 보다 한 단계 더 흐림 — 저작권처럼 '읽는 글'이 아니라 '있는 글'용.
    # 대비 기준(4.5)을 일부러 안 지킨다: 본문이 아니기 때문이다.
    "faint":  "#a8a8ad",
    "border": "#d2d2d7",
    # 강조색의 아주 옅은 판 — '지금 켜져 있음'을 색으로만 말하는 자리에 쓴다
    # (툴바 버튼이 눌려 열려 있을 때 등). accent 를 그대로 깔면 너무 세다.
    "accent_soft": "#e8f2fd",
    "subbg":  "#fafafa",
    "green":  "#0071e3",
    "yellow": "#e8e8ed",
}

# 어둡게 — 순검정(#000)은 쓰지 않는다. 밤에 흰 글자가 번져 보이고, 창 경계가
# 사라져 어디까지가 프로그램인지 알 수 없다. 회색 계단으로 층을 만든다.
DARK = {
    "bg":     "#1c1c1e",
    "card":   "#2c2c2e",
    "accent": "#0a84ff",     # 어두운 배경에선 #0071e3 가 가라앉아 한 단계 밝힌다
    "text":   "#f2f2f7",
    "muted":  "#98989d",     # #86868b 는 어두운 배경에서 대비가 모자란다
    "faint":  "#5c5c60",
    "border": "#48484a",
    "accent_soft": "#16324f",
    "subbg":  "#242426",
    "green":  "#0a84ff",
    "yellow": "#3a3a3c",
}

# ── 글꼴 (애플 디자인 A안, 2026-07-25) ─────────────────
# Pretendard: SF Pro 와 굵기·자간 체계가 호환되게 설계된 무료 한글 글꼴.
# 설치돼 있으면 쓰고, 없으면 맑은 고딕 그대로 — 어느 PC 에서든 동작해야 한다.
#
# 감지를 Tk(tkfont.families)가 아니라 **폰트 폴더**로 하는 이유: 이 모듈은
# Tk 창이 만들어지기 전에 임포트되고, 각 UI 파일이 로드 시점에 FONT 를 복사해
# 가므로(FONT = theme.FONT) 그 전에 값이 정해져 있어야 한다.
def _pick_font():
    import os
    import pathlib
    folders = [pathlib.Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    local = os.environ.get("LOCALAPPDATA")
    if local:   # 요즘 윈도우는 '사용자용 설치'가 기본이라 여기로 들어간다
        folders.append(pathlib.Path(local) / "Microsoft" / "Windows" / "Fonts")
    names = set()
    for folder in folders:
        try:
            for f in folder.iterdir():
                if f.name.lower().startswith("pretendard"):
                    names.add(f.stem.lower())
        except OSError:
            continue
    # Regular 는 맑은 고딕보다 획이 가늘어 작은 UI 글자에서 흐릿하다(실측
    # 2026-07-25). Medium 이 있으면 그쪽 — 애플도 작은 UI 글자엔 중간 굵기를 쓴다.
    if "pretendard-medium" in names:
        return "Pretendard Medium"
    if names:
        return "Pretendard"
    return "맑은 고딕"


FONT = _pick_font()

# Pretendard 는 같은 pt 에서 맑은 고딕보다 작게 보인다(자면 설계 차이).
# 크기를 일괄 1pt 올려 보정한다.
FONT_BOOST = 1 if FONT.startswith("Pretendard") else 0

# 전체 글자 배율 (사용자 결정 2026-07-25: "지금보다 25% 확대").
# 모든 창의 글자 크기가 이 함수를 거친다 — 개별 파일에 숫자를 곱해 두면
# 다음에 또 키울 때 수십 군데를 고쳐야 한다.
FONT_SCALE = 1.25


def fs(size):
    """UI 글자 크기 → 실제 pt (배율 + Pretendard 보정)."""
    return max(7, int(round(size * FONT_SCALE)) + FONT_BOOST)


# ── 디자인 토큰 (2026-07-27 개편) ──────────────────────
# 왜 필요한가: padx 가 6/8/10/12/14/16 으로 파일마다 제각각이었고 모서리도
# 6/7/8 이 섞여 있었다. 사람 눈은 이런 어긋남을 하나씩은 못 알아채도 **모아
# 놓으면 '손으로 대충 그린 것' 으로 읽는다**. 숫자를 몇 개로 못박아 두면
# 서른 개 화면이 한 손으로 그린 것처럼 보인다.
#
# 규칙: 간격은 4의 배수 다섯 개, 이 밖의 숫자는 쓰지 않는다.
SP = {"xs": 4, "s": 8, "m": 12, "l": 16, "xl": 24}

# 모서리 — 컨트롤(버튼·입력칸) / 카드(타일·대화상자) / 판(창 안 큰 구획)
#
# 셋은 **겹쳐 놓기 위한 값**이다: 판 안에 카드가 들어가고, 카드 안에 버튼이
# 들어간다. 이때 지켜야 하는 규칙이 `바깥 = 안쪽 + 여백` 이다. 이걸 어기면
# 안쪽 모서리가 바깥보다 덜 둥글어 보여서, 하나씩 볼 땐 몰라도 겹쳐 놓으면
# 어긋난 것이 눈에 띈다.
#
#   ctl 6 ──(+4)──> card 10 ──(+4)──> pane 14
#
# 세 단계 모두 여백이 SP["xs"](4) 다. pane 을 12 로 두면 카드와의 차가 2 가
# 되는데, 2 는 SP 에 없는 숫자다 — 간격 체계를 깨거나 모서리 체계를 깨거나
# 둘 중 하나를 골라야 했다 (감사 2026-07-30, docs/.reviews/feel-audit-round-1.md).
RADIUS = {"ctl": 6, "card": 10, "pane": 14}

# 주고받기 기호 — 팔레트 나누기와 물감 나누기가 **같은 글자**를 쓴다
# (사용자 결정 2026-07-28). 여기 한 곳에 두는 이유: 두 화면에 각각 적어 두면
# 한쪽만 바뀌어 "다른 기능"처럼 보이게 되고, 글꼴이 없는 PC 에서 대체 글자로
# 갈아끼울 때도 한 줄만 고치면 된다.
# ⤴·⇪ 같은 것은 맑은 고딕에 없는 PC 가 있어 네모(두부)로 뜬다 — ↗ 는 어디에나 있다.
SHARE_GLYPH = "↗"

# 글자 위계 — 자리마다 고르지 않고 **역할**로 정한다.
# fs() 를 거치기 전의 논리 크기다: fs(FS["body"]) 처럼 쓴다.
#
# 다섯 단계에서 **네 단계로 줄였다** (사용자 승인 2026-07-30).
# 예전 값은 12/10/9/8/7 이었는데, fs() 를 거치면 실제로는 16/13/12/11/10pt 가
# 되어 가운데 세 단계가 **1pt 간격**이었다. 사람 눈은 1pt 차이를 크기 차이로
# 안 읽는다 — 특히 body(12pt)와 sub(11pt)는 코드에서 가장 많이 쓰이는 두
# 단계라, 화면 글자의 절반이 사실상 같은 크기였다. 단계가 있으나 마나 하면
# 고르는 사람만 헷갈린다.
#
# 이제 논리값 간격이 2 씩이다: 13·11·9·7 → 실제 17·15·12·10pt.
# 어느 두 개를 나란히 놓아도 다르다는 것이 보인다.
#
# sub 는 **키만 남기고 body 와 같은 값**으로 합쳤다. 54곳에서 쓰이고 있어
# 한 번에 다 갈아끼우면 어느 자리가 왜 바뀌었는지 확인할 수 없다. 값이 같으니
# 화면은 이미 의도대로 나오고, 자리마다의 재분류(body 냐 caption 이냐)는
# 그 화면을 손볼 때 하나씩 하면 된다. 새 코드에서는 쓰지 않는다.
FS = {"title": 13, "head": 11, "body": 9, "sub": 9, "caption": 7}

# 모션 — 늘리는 게 아니라 금지를 명문화한 값이다 (docs/DESIGN_개편.md).
#   블럭 클릭처럼 하루 수백 번 하는 일에는 **애니메이션을 넣지 않는다**.
#   호버는 ui_fx 가 ease-out 으로 보간하고, 누름은 0ms 즉시 반응한다.
#
# 128 인 이유: ui_fx 는 16ms(=60fps 한 프레임) 간격으로 색을 옮긴다. 화면이
# 새로 그려지는 리듬에 맞춰야 중간 단계가 버려지지 않기 때문이다. 그래서
# 이 값은 **16의 배수여야 한다** — 8단계 × 16ms = 128ms.
# 예전에 130 으로 적혀 있었는데, 실제 코드는 128 로 돌고 있었다. 토큰과 코드가
# 갈라져 있으면 토큰이 없느니만 못하므로 실측값으로 맞추고, ui_fx 가 이 값을
# 읽어 가도록 바꿨다 (감사 2026-07-30).
MOTION = {"hover_ms": 128, "press_ms": 0, "enter_ms": 0}

# 블럭 사용자 색 — 자유 선택(colorchooser)을 대신하는 12색.
#
# 왜 좁히나: 자유 선택은 네온 초록(#00e050) 같은 원색을 허용해, 화면에서
# 제일 시끄러운 것이 **내용이 아니라 장식**이 됐다. 열두 개는 어느 조합으로
# 골라도 화면이 안 깨지도록 채도를 맞춰 둔 값이다.
PASTELS = [
    ("파랑", "#eef4fb"), ("초록", "#eef7ef"), ("주황", "#fdf3e7"),
    ("분홍", "#fbeef0"), ("보라", "#f3eefb"), ("청록", "#eff8f6"),
    ("노랑", "#f8f4e8"), ("모래", "#f1efe9"), ("회청", "#eff1f4"),
    ("살구", "#f6efe9"), ("하늘", "#edf6fb"), ("회색", "#f2f2f4"),
]
# 어두운 모드에서 같은 자리에 쓸 짝 (색상은 같고 명도만 뒤집는다)
PASTELS_DARK = [
    ("파랑", "#1e2b3f"), ("초록", "#18321f"), ("주황", "#3a2f1c"),
    ("분홍", "#3a1f28"), ("보라", "#2b2740"), ("청록", "#14332f"),
    ("노랑", "#3a3520"), ("모래", "#332f26"), ("회청", "#26292e"),
    ("살구", "#382b22"), ("하늘", "#1b2d3a"), ("회색", "#2c2c2e"),
]


def pastels():
    """지금 모드의 12색 [(이름, 색)]."""
    return list(PASTELS_DARK if is_dark() else PASTELS)


def _rgb_of(hex_color):
    h = (hex_color or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(hex_color)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def nearest_pastel(hex_color):
    r"""자유롭게 고른 색 → 가장 가까운 12색 중 하나.

    **색상(hue)으로 고른다.** RGB 거리로 재면 네온 초록(#00e050)이 모래색으로
    가 버린다 (실측 2026-07-27) — 파스텔은 전부 밝아서, 채도 높은 원색과는
    밝기 차이가 색상 차이를 덮어 버리기 때문이다. 사람은 "초록을 골랐으면
    옅은 초록" 을 기대하므로 색상을 먼저 맞추는 것이 옳다.

    채도가 거의 없는 색(회색·검정·흰색)은 색상이 뜻을 잃으므로 회색으로 보낸다.
    """
    import colorsys
    try:
        r, g, b = _rgb_of(hex_color)
    except ValueError:
        return None
    table = pastels()
    # 이미 12색 중 하나면 그대로 — 채도가 낮은 파스텔(초록 0.036)이 무채색
    # 판정에 걸려 회색으로 옮겨지던 버그를 여기서 원천 차단한다 (테스트가 잡음).
    for _name, cand in table:
        if cand.lower() == (hex_color or "").lower():
            return cand
    hue, sat, _val = colorsys.rgb_to_hsv(r, g, b)
    # 문턱 값의 근거 (실측 2026-07-27): 파스텔 채도는 0.008(회색)~0.087(주황).
    # 0.014 는 회색만 갈라내고 나머지 열하나는 모두 색상 짝으로 남긴다.
    # 예전에 0.06 으로 뒀더니 후보 대부분이 탈락해 전부 '노랑'이 됐다.
    GRAY_SAT = 0.014
    if sat < GRAY_SAT:
        return table[-1][1]                 # 회색 — 색상이 뜻을 잃는 구간
    best, best_d = None, None
    for _name, cand in table:
        cr, cg, cb = _rgb_of(cand)
        chue, csat, _cv = colorsys.rgb_to_hsv(cr, cg, cb)
        if csat < GRAY_SAT:
            continue                        # 회색 칸은 색상 짝으로 쓰지 않는다
        d = abs(hue - chue)
        d = min(d, 1.0 - d)                 # 색상환은 둥글다 (빨강 0 ≒ 1)
        if best_d is None or d < best_d:
            best, best_d = cand, d
    return best or table[-1][1]

# 블럭 배경 — **종류와 상관없이 한 가지 카드색** (H안, 사용자 결정 2026-07-29).
#
# 예전에는 종류마다 옅은 파스텔을 깔았다(파랑=템플릿, 주황=서식조합…).
# 그런데 블럭이 여덟 개만 돼도 화면에서 제일 먼저 보이는 것이 이름이 아니라
# **색 덩어리**였다. 종류는 이제 색이 아니라 **아이콘**(BLOCK_ICON)이 말한다 —
# 아이콘은 배경을 통째로 물들이지 않으므로 화면이 조용해진다.
#
# 키는 그대로 둔다: 종류별로 다른 색을 다시 주고 싶어지면 값만 바꾸면 된다.
BLOCK_LIGHT = {"char": "#ffffff", "template": "#ffffff",
               "function": "#ffffff", "form": "#ffffff",
               "builtin": "#ffffff"}      # 프로그램 기능 (사진·특수문자 등)
BLOCK_DARK = {"char": "#2c2c2e", "template": "#2c2c2e",
              "function": "#2c2c2e", "form": "#2c2c2e",
              "builtin": "#2c2c2e"}

# 카드 테두리 — 배경색이 하나뿐이라 **블럭의 경계는 선이 그린다**.
# 창 바탕(bg)과 카드(흰색)의 밝기 차가 작아서, 선이 없으면 블럭이 어디서
# 끝나는지 안 보인다. 일반 border 보다 한 단계 옅다 — 선이 이름보다 세면 안 된다.
BLOCK_EDGE_LIGHT = "#e2e6ec"
BLOCK_EDGE_DARK = "#3a3a3d"


def block_edge():
    """블럭 카드 테두리색 (지금 모드)."""
    return BLOCK_EDGE_DARK if is_dark() else BLOCK_EDGE_LIGHT


# ── 블럭 아이콘 (H안, 2026-07-29) ──────────────────────
#
# 2026-07-19 에 자동 아이콘(▦ ƒ 📄)을 뺐던 적이 있다. 그때는 **이름 옆에**
# 붙어서 이름을 밀어내고 글자 자리를 먹었다. 이번에는 **이름 위 한 줄**에
# 따로 서므로 이름을 침범하지 않는다. 배경색을 없앤 자리를 이것이 메운다.
#
# 글자 고르는 기준: 이모지를 쓰지 않는다. 윈도우에서 이모지는 **컬러로**
# 그려져서, 색을 아끼자고 배경을 흰색으로 바꾼 노력이 아이콘에서 도로 깨진다.
# 흑백으로 그려지는 기호 중에서도 KS X 1001(한글 완성형)에 든 것만 쓴다 —
# 맑은 고딕·Pretendard 어느 쪽에도 있어서 네모(두부)로 뜨지 않는다.
# ⌕ 는 이미 위쪽 도구줄에서 쓰고 있어 이 PC 에서 그려지는 것이 확인된 글자다.
BLOCK_ICON = {
    "convert":      "⇒",    # 마크다운 → 한글로 넘어간다
    # "가a" — 한글 한 자 + 라틴 소문자 한 자. 한글 워드프로세서·글자 모양
    # 대화상자가 흔히 쓰는 "폰트 견본" 표기(한/영 글꼴이 같이 걸린다는 뜻)를
    # 그대로 가져왔다. 처음엔 "가나"(두 음절)를 썼는데 **완전한 한글 두
    # 글자**라 한 글자 아이콘(⇒ ¶ ▨)의 거의 두 배 면적을 먹어 아이콘이
    # 아니라 작은 제목처럼 보였다(사용자 지적 2026-07-30, "너무 크잖아").
    # "a" 는 폭이 좁아 이 문제가 없다 (사용자 확정 2026-07-30).
    "reset_format": "가a",
    # "photo" 는 텍스트가 아니라 **그림**이다 — BLOCK_ICON_ASSET 참고.
    # 여기 값은 이미지를 못 불러올 때만 쓰는 대비책이다.
    "photo":        "▲",
    "special":      "※",    # 특수기호 그 자체
    "form_fill":    "▤",    # 줄 그은 종이 = 양식
    "library":      "▥",
    "search":       "⌕",
}

# 종류별 — 도구가 아닌 블럭(사용자가 만든 템플릿·양식·서식 조합)용.
# char(문자 삽입)는 **이름 자리에 이미 그 문자가 있다** — 아이콘을 또 얹으면
# 같은 것이 두 번 보이므로 넣지 않는다.
TYPE_ICON = {
    "template": "▦",
    "form":     "▤",
    "function": "가a",      # BLOCK_ICON["reset_format"] 과 같은 이유·같은 글자
    "builtin":  "◆",        # 카탈로그에 없는 새 도구가 생겼을 때의 기본값
}

# ── 글자로 못 그리는 아이콘 (2026-07-30) ────────────────
# assets/make_block_icons.py 가 이미 손으로 그려 assets/icons/ 에 구워 둔
# 진짜 벡터 그림이 있는 자리는 글자 대신 **그 PNG**를 쓴다. 사진은
# 2026-07-29 에 이미 확정된 그림(액자+산+해)이었는데, 그동안 프로그램은
# 이걸 안 쓰고 글자(▨)로 대신하고 있었다 — 그 연결을 여기서 잇는다.
#
# 값은 assets/icons/<값>-<크기>.png 파일 이름이다. 무채색(다른 아이콘과
# 같은 회색 톤) 버전을 쓰기로 했으므로 "_mono" 접미사가 붙은 별도 파일을
# 가리킨다 — 원본(물감 분류색) 파일과 나란히 있다 (make_block_icons.py 의
# MONO 목록 참고).
BLOCK_ICON_ASSET = {
    "photo": "photo_mono",
}


def block_icon_key(block):
    """이 블럭의 아이콘을 고를 **키**. 그림(BLOCK_ICON_ASSET)과 글자(BLOCK_ICON)가
    같은 키를 공유하므로, 어느 쪽으로 그릴지는 호출부가 BLOCK_ICON_ASSET 로 정한다.
    """
    if block.get("type") == "builtin":
        key = block.get("key")
        return key if key in BLOCK_ICON else None
    return block.get("type") if block.get("type") in TYPE_ICON else "builtin"


def block_icon_asset(block):
    """이 블럭 아이콘이 실제 그림 파일이면 그 파일 이름(크기 앞자리), 아니면 None."""
    return BLOCK_ICON_ASSET.get(block_icon_key(block))


def block_icon(block):
    """블럭 위에 얹을 기호. 없으면 None (문자 블럭 등)."""
    if block.get("type") == "builtin":
        return BLOCK_ICON.get(block.get("key")) or TYPE_ICON["builtin"]
    return TYPE_ICON.get(block.get("type"))

# 도구 중 **변환**만 진한 강조색 — 이 프로그램의 본체이고, 예전에 큰 파란
# 버튼이던 것이 블럭으로 옮겨왔다. 눈에 띄어야 찾기 쉽다 (2026-07-25).
# 사용자가 blk["color"] 로 직접 고르면 그쪽이 우선한다.
BUILTIN_ACCENT = {"convert": True}


def block_color(block):
    """블럭 배경색 — 사용자 지정 > 도구 강조 > 종류별 기본."""
    if block.get("color"):
        return block["color"]
    if (block.get("type") == "builtin"
            and BUILTIN_ACCENT.get(block.get("key"))):
        return colors()["accent"]
    return block_colors().get(block.get("type"), colors()["card"])

# 알림 색 (종류 → 글자색, 배경색)
NOTICE_LIGHT = {
    "ok":    ("#0a6b2e", "#e8f7ee"),
    "warn":  ("#8a5300", "#fff4e0"),
    "error": ("#9b1c1c", "#fdecec"),
    "info":  ("#6e6e73", "#f5f5f7"),
}
NOTICE_DARK = {
    "ok":    ("#7ee2a8", "#13301f"),
    "warn":  ("#f5c26b", "#3a2c14"),
    "error": ("#ff9b9b", "#3a1c1c"),
    "info":  ("#98989d", "#242426"),
}


# ── 지금 모드 ──────────────────────────────────────────
# 모드 캐시 (2026-07-31, 성능): colors()·block_colors()·block_edge() 가 전부
# 여기(get_mode)를 지나는데, settings.get_config_value 는 매번 설정 **전체를
# 깊은 복사**한다 — 블럭 하나 그릴 때 이 길을 세 번쯤 지나 약 2ms 가 들었다
# (실측). 모드는 config.json 이 안 바뀌면 안 바뀌므로, 파일의 세대 표식
# (settings.config_token: mtime+크기)을 열쇠로 값을 들고 있는다. 다른
# 프로세스가 파일을 고쳐도 표식이 달라져 다음 호출이 새로 읽는다.
_mode_cache = {"tok": None, "mode": None}


def _drop_mode_cache():
    """모드 캐시 무효화 — set_mode 와 테스트(설정을 목으로 갈아끼움)가 부른다."""
    _mode_cache["tok"] = None
    _mode_cache["mode"] = None


def get_mode():
    """"light" 또는 "dark". 저장된 값이 깨져 있으면 밝게."""
    tok = settings.config_token()
    if (tok is not None and _mode_cache["mode"] is not None
            and _mode_cache["tok"] == tok):
        return _mode_cache["mode"]
    v = settings.get_config_value(MODE_KEY, "light")
    mode = "dark" if v == "dark" else "light"
    if tok is not None:     # 파일이 없으면(첫 실행) 읽기가 원래 싸다 — 캐시 안 함
        _mode_cache["tok"] = tok
        _mode_cache["mode"] = mode
    return mode


def set_mode(mode):
    settings.set_config_value(MODE_KEY, "dark" if mode == "dark" else "light")
    # 저장이 실패했어도 무효화는 안전하다 — 다음 읽기가 파일을 다시 볼 뿐이다.
    _drop_mode_cache()


def is_dark():
    return get_mode() == "dark"


def colors():
    return dict(DARK if is_dark() else LIGHT)


def block_colors():
    return dict(BLOCK_DARK if is_dark() else BLOCK_LIGHT)


def notice_colors():
    return dict(NOTICE_DARK if is_dark() else NOTICE_LIGHT)


# ── 대비 (UI 제안 18) ──────────────────────────────────
def _luminance(hex_color):
    """0(검정)~1(흰색). WCAG 상대휘도 — 사람 눈은 초록에 가장 민감하다."""
    h = (hex_color or "").lstrip("#")
    if len(h) == 3:                       # #abc → #aabbcc
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return 1.0                        # 못 읽는 값이면 밝다고 보고 검은 글자
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return 1.0

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def text_on(bg_hex):
    """그 배경 위에서 읽히는 글자색.

    블럭 색은 사용자가 직접 고른다(빨강·남색 등). 글자색을 TEXT 로 고정하면
    어두운 색을 골랐을 때 검은 글자가 배경에 묻혀 안 보인다. 배경 밝기를 재서
    검정/흰색 중 대비가 큰 쪽을 준다.
    """
    return "#1d1d1f" if _luminance(bg_hex) > 0.45 else "#ffffff"


def contrast_ratio(fg_hex, bg_hex):
    """WCAG 명도 대비 (1~21). 본문 글자는 4.5 이상이어야 한다."""
    a, b = _luminance(fg_hex), _luminance(bg_hex)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)
