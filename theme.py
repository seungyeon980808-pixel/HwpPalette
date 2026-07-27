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

import settings

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
RADIUS = {"ctl": 6, "card": 10, "pane": 12}

# 주고받기 기호 — 팔레트 나누기와 물감 나누기가 **같은 글자**를 쓴다
# (사용자 결정 2026-07-28). 여기 한 곳에 두는 이유: 두 화면에 각각 적어 두면
# 한쪽만 바뀌어 "다른 기능"처럼 보이게 되고, 글꼴이 없는 PC 에서 대체 글자로
# 갈아끼울 때도 한 줄만 고치면 된다.
# ⤴·⇪ 같은 것은 맑은 고딕에 없는 PC 가 있어 네모(두부)로 뜬다 — ↗ 는 어디에나 있다.
SHARE_GLYPH = "↗"

# 글자 위계 — 자리마다 고르지 않고 **역할**로 정한다.
# fs() 를 거치기 전의 논리 크기다: fs(FS["body"]) 처럼 쓴다.
FS = {"title": 12, "head": 10, "body": 9, "sub": 8, "caption": 7}

# 모션 — 늘리는 게 아니라 금지를 명문화한 값이다 (docs/DESIGN_개편.md).
#   블럭 클릭처럼 하루 수백 번 하는 일에는 **애니메이션을 넣지 않는다**.
#   호버는 ui_fx 가 130ms ease-out 으로 보간하고, 누름은 0ms 즉시 반응한다.
MOTION = {"hover_ms": 130, "press_ms": 0, "enter_ms": 0}

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

# 블럭 종류별 배경 — 밝은 쪽은 옅은 파스텔, 어두운 쪽은 같은 색상의 어두운 판.
# 색상(파랑=템플릿, 주황=서식조합, 초록=양식)은 두 모드에서 같아야 한다.
# 2026-07-27: 채도를 한 단계 낮췄다 — 강조색(변환)만 화면에서 튀어야 한다.
BLOCK_LIGHT = {"char": "#ffffff", "template": "#eef4fb",
               "function": "#f1efe9", "form": "#eef7ef",
               "builtin": "#f3eefb"}      # 프로그램 기능 (사진·특수문자 등)
BLOCK_DARK = {"char": "#2c2c2e", "template": "#1e2b3f",
              "function": "#3a2f1c", "form": "#18321f",
              "builtin": "#2b2740"}

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
def get_mode():
    """"light" 또는 "dark". 저장된 값이 깨져 있으면 밝게."""
    v = settings.get_config_value(MODE_KEY, "light")
    return "dark" if v == "dark" else "light"


def set_mode(mode):
    settings.set_config_value(MODE_KEY, "dark" if mode == "dark" else "light")


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
