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
    "border": "#d2d2d7",
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
    "border": "#48484a",
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
# 크기를 일괄 1pt 올려 보정한다 — 각 창의 _font() 가 이 값을 더한다.
FONT_BOOST = 1 if FONT.startswith("Pretendard") else 0

# 블럭 종류별 배경 — 밝은 쪽은 옅은 파스텔, 어두운 쪽은 같은 색상의 어두운 판.
# 색상(파랑=템플릿, 주황=서식조합, 초록=양식)은 두 모드에서 같아야 한다.
BLOCK_LIGHT = {"char": "#ffffff", "template": "#eef4ff",
               "function": "#fff4e6", "form": "#eafaf1",
               "builtin": "#f0eefc"}      # 프로그램 기능 (사진·특수문자 등)
BLOCK_DARK = {"char": "#2c2c2e", "template": "#1e2b3f",
              "function": "#3a2f1c", "form": "#18321f",
              "builtin": "#2b2740"}

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
