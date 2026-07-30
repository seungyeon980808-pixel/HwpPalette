# -*- coding: utf-8 -*-
r"""프로그램 기능 아이콘 —  python assets/make_block_icons.py

**프로그램이 제공하는 기능에만** 그림을 붙인다 (사용자 결정 2026-07-29).
개인 팔레트의 블럭은 사용자가 만드는 것이라 프로그램이 무슨 그림을 그려야
할지 알 수 없다.

대상은 블럭 도구 일곱만이 아니다 (사용자 지적 2026-07-29: "더 다른 기능이
많은데"). 지금 화면에서 기호 한 글자로 버티고 있는 자리가 여럿이다 —
툴바의 ⚙ ? ↺ ⇧, 물감 분류, 팔레트 나누기(↗) 같은 것들. 겹치는 것을 걷어내면
스무 개다. 겹치는 것: 특수기호 블럭 = 물감 '문자' 분류(같은 창을 연다),
통합 찾기 블럭 = 툴바 ⌕, 라이브러리 블럭 = 물감 창고.

make_icons.py 와 무엇이 다른가:
    저쪽은 **프로그램 아이콘**(작업표시줄·exe·폴더)이라 한 벌뿐이고 크게 쓰인다.
    이쪽은 **버튼 안에 들어가는 그림**이라 스무 개이고 16~32px 로 쓰인다.

이어받은 원칙 (make_icons.py · CLAUDE.md):
  · AI티 금지 — 그라데이션·그림자 없이 납작하게
  · 8배로 그린 뒤 LANCZOS 로 줄인다 (계단 없애기)

이 파일만의 원칙:
  · 획 굵기를 상자 크기의 **비율**로 잡는다. px 로 박으면 16px 에서 사라지고
    48px 에서 실처럼 가늘어진다
  · 한 도형에 요소 셋 이상 넣지 않는다 — 16px 에서 뭉개진다
  · 툴바 넷은 **회색 한 색**이다. 그 자리는 도구가 아니라 창의 테두리라,
    색을 주면 아래 블럭과 같은 무게로 읽혀 어느 쪽이 본론인지 흐려진다

  · 글자는 원칙적으로 안 넣는다 — 작은 크기에서 얼룩이 된다.
    **예외 둘**: 마크다운 변환(사용자 결정 2026-07-29 — '!@#$ → 가나다')과
    특수기호(π). 둘 다 '글자 자체'가 그 기능의 뜻이라 그림으로 바꿀 수가 없다.
    π 는 선으로 직접 긋고, 변환은 글꼴로 찍되 **PNG 로 구워 두므로** 사용자
    PC 에 그 글꼴이 없어도 상관없다 (여기서 만들 때만 필요하다).

  python assets/make_block_icons.py
      → assets/icons/<key>-<크기>.png          (16·20·24·32·48)
      → assets/icons/_candidates/…             고르는 중인 후보
      → docs/mockups/icons/                    같은 파일 (미리보기 페이지가 읽는다)
"""

import math
import pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "icons"
PREVIEW = HERE.parent / "docs" / "mockups" / "icons"

N = 512                     # 그리는 크기 (실제의 8~32배)
SIZES = (16, 20, 24, 32, 48)

# ── 색 ─────────────────────────────────────────────────
# 채도·밝기를 한 줄에 맞춰 둔 한 벌. 하나만 튀면 그 기능이 더 중요해 보인다.
BLUE    = (9, 105, 218)     # 시그니처 메인
TEAL    = (14, 116, 144)    # 시그니처 서브
PURPLE  = (109, 84, 190)
MAGENTA = (166, 62, 130)
GREEN   = (26, 122, 78)
OCHRE   = (146, 100, 42)
CORAL   = (192, 80, 62)
INDIGO  = (66, 76, 170)
GRAY    = (86, 96, 108)     # 툴바 — 창의 테두리이지 도구가 아니다
# 툴바 포인트 색 (사용자 결정 2026-07-30, 시안 2 — docs/mockups/toolbar-color.html).
#
# 원래 규칙은 "툴바는 회색 한 색"이었다. 그 규칙이 막으려던 것은 **줄 전체가
# 파래져 아래 물감 블럭과 무게가 같아지는 것**이라, 획은 회색으로 두고
# **안쪽 요소 하나만** 색을 준다 — 색 면적은 아이콘의 5분의 1 안쪽이다.
# 값은 앱의 강조색(#0071e3)과 같게 둔다: 켜짐 상태의 옅은 파란 바탕과 한 식구다.
ACCENT  = (0, 113, 227)
ACCENT_SOFT = ACCENT + (38,)        # 렌즈 안쪽·판 채움처럼 '면'에 쓰는 옅은 판

# ── 획 (2026-07-29 다시 잡음) ───────────────────────────
# 0.10 은 굵었다 (사용자 지적: "선은 더 얇고"). 요즘 아이콘 한 벌들은
# 24px 상자에 2px — 0.083 이다. 여기는 그보다 한 단계 더 얇게 간다.
#
# 대신 **얇을수록 작은 크기를 잃는다.** 0.075 는 16px 에서 1.2px 이라
# 줄이는 과정(LANCZOS)에서 회색으로 번진다. 20px 이상에서 쓰는 것을 전제로 한다.
W = int(N * 0.075)
R = int(N * 0.09)           # 모서리 반경 — 획이 얇아진 만큼 모서리는 넉넉하게

# 안전 영역 — 모든 그림을 이 안에 담는다.
# 어떤 그림은 0.06 부터, 어떤 그림은 0.16 부터 시작하면 격자에 늘어놓았을 때
# 크기가 들쭉날쭉해 보인다. 한 벌로 보이려면 **차지하는 면적**이 같아야 한다.
SAFE = (0.13, 0.87)


def _canvas():
    return Image.new("RGBA", (N, N), (0, 0, 0, 0))


def _p(*xs):
    """0~1 비율 → 픽셀. 도형을 비율로 적어야 크기를 바꿔도 안 무너진다."""
    return [int(x * N) for x in xs]


def _poly(d, c, *xs):
    d.polygon(list(zip(*[iter(_p(*xs))] * 2)), fill=c)


def _stroke(d, c, *xs, w=None, closed=False):
    r"""**끝이 둥근** 선 — 이 파일의 기본 그리기 수단.

    Pillow 에는 line cap 이 없어 선 끝이 뭉툭하게 잘린다. 획이 굵을 땐 티가 안
    나지만 얇아지면 끝이 각져서 **깎다 만 것처럼** 보인다. 끝마다 지름이 획
    굵기인 원을 찍어 둥근 끝을 흉내낸다 — 꺾이는 자리에도 찍어야 각이 안 진다.
    """
    w = w or W
    pts = _p(*xs)
    xy = [(pts[i], pts[i + 1]) for i in range(0, len(pts), 2)]
    if closed:
        xy.append(xy[0])
    d.line([v for p in xy for v in p], fill=c, width=w, joint="curve")
    r = w // 2
    for x, y in xy:
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)


def _chevron(d, c, x, y, size, dx=1, dy=0, w=None):
    r"""꺾쇠 화살촉 (> 모양) — 채운 삼각형 대신 쓴다.

    채운 삼각형은 선 굵기와 무게가 달라, 얇은 선 끝에 **덩어리**가 매달린 것처럼
    보인다. 꺾쇠는 몸통과 같은 굵기라 획 하나가 이어지는 것으로 읽힌다.
    dx·dy 는 화살표가 향하는 쪽 (오른쪽=1,0 / 아래=0,1 …).
    """
    # 날개는 **뾰족한 끝의 반대쪽**으로 뻗는다. 부호를 헷갈려 뒤집었더니
    # 나누기 아이콘이 Y 자가 됐다 (실측 2026-07-29) — 화살표는 방향이 전부라
    # 반대로 가면 그림이 아니라 오해가 된다.
    s = size
    if dx:                                  # 좌우 (dx=1 이면 오른쪽을 가리킨다)
        _stroke(d, c, x - s * dx, y - s, x, y, x - s * dx, y + s, w=w)
    else:                                   # 위아래 (dy=1 이면 아래를 가리킨다)
        _stroke(d, c, x - s, y - s * dy, x, y, x + s, y - s * dy, w=w)


def _arrow_r(d, c, x1, x2, y, h=0.10):
    """오른쪽 화살표 — 여러 그림이 같은 화살표를 쓴다."""
    _stroke(d, c, x1, y, x2, y)
    _chevron(d, c, x2, y, h)


def _font_at(px, bold=False):
    """한글이 되는 글꼴. 없으면 None 을 돌려 그림 쪽에서 건너뛴다."""
    names = (["malgunbd.ttf", "malgun.ttf"] if bold
             else ["malgun.ttf", "malgunbd.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, px)
        except OSError:
            continue
    return None


def _text_mid(d, c, s, cx, cy, px, bold=True):
    f = _font_at(px, bold)
    if f is None:
        return
    d.text((cx, cy), s, font=f, fill=c, anchor="mm")


# ══ 블럭 도구 ══════════════════════════════════════════
def draw_convert(d, c):
    r"""마크다운 변환 — 기호가 한글이 된다 (사용자 결정 2026-07-29).

    화살표·종이로 그려 봤지만 '변환'은 그릴 물건이 없어 16px 에서 늘 다른
    것으로 읽혔다(문·로그인·그냥 문서). 그래서 **뜻을 글자로 직접 보인다**.

    역슬래시(\)는 쓰지 않는다 — 이 프로그램의 문법 기호이긴 하지만, 한글
    글꼴은 같은 자리(U+005C)를 **₩ 원화 기호**로 그린다 (실측 2026-07-29).
    글자는 **굵게 찍지 않는다**: 선을 얇게 간 판이라 글자만 굵으면 혼자 뜬다.
    """
    _text_mid(d, c, "#*", N // 2, int(N * 0.26), int(N * 0.34), bold=False)
    _arrow_r(d, c, 0.38, 0.58, 0.50, h=0.075)
    _text_mid(d, c, "가나", N // 2, int(N * 0.76), int(N * 0.32), bold=False)


def draw_reset_format(d, c):
    """기본 서식 — 문단 줄 위로 도는 되돌림 화살표."""
    for y, x2 in ((0.66, 0.87), (0.84, 0.62)):
        _stroke(d, c, 0.13, y, x2, y)
    d.arc(_p(0.20, 0.10, 0.84, 0.52), start=178, end=25, fill=c, width=W)
    _chevron(d, c, 0.20, 0.315, 0.10, dx=0, dy=1)


def draw_photo(d, c):
    """사진 — 액자 + 산 + 해 (사용자 확정 2026-07-29).

    구도는 그대로 두고 획만 얇게 했다. 산은 채우지 않고 **능선 두 개**로 —
    채운 삼각형은 이 한 벌에서 혼자 무겁다.
    """
    d.rounded_rectangle(_p(0.13, 0.19, 0.87, 0.81), radius=R, outline=c, width=W)
    sx, sy = _p(0.68, 0.35)
    r = int(N * 0.045)
    d.ellipse([sx - r, sy - r, sx + r, sy + r], outline=c, width=W)
    _stroke(d, c, 0.17, 0.72, 0.36, 0.49, 0.55, 0.72)
    _stroke(d, c, 0.47, 0.72, 0.60, 0.58, 0.83, 0.72)


def draw_special(d, c):
    """특수기호 — 로마자 파이 π (사용자 결정 2026-07-29).

    글꼴로 찍지 않고 **선 셋을 직접 긋는다.** 글꼴마다 π 의 다리 모양과 굵기가
    달라, 찍어 두면 이 PC 에서 만든 것과 다음에 만든 것이 서로 달라진다.
    다리를 살짝 벌리는 것이 진짜 π 다 — 수직으로 세우면 'ㅠ' 로 보인다.
    """
    _stroke(d, c, 0.13, 0.29, 0.87, 0.29)
    _stroke(d, c, 0.37, 0.29, 0.32, 0.85)
    _stroke(d, c, 0.66, 0.29, 0.71, 0.85)


def draw_form_fill(d, c):
    """양식 채우기 — 줄 그은 종이 + 체크 (후보 가)."""
    d.rounded_rectangle(_p(0.13, 0.13, 0.68, 0.87), radius=R, outline=c, width=W)
    for y in (0.33, 0.48):
        _stroke(d, c, 0.25, y, 0.56, y)
    _stroke(d, c, 0.52, 0.68, 0.63, 0.79, 0.88, 0.50)


def draw_library(d, c):
    """라이브러리(물감 창고) — 책 세 권, 하나는 기울임.

    막대 셋을 나란히 세우면 16px 에서 **막대그래프**로 읽힌다 (실측 2026-07-29).
    기운 것 하나가 '이건 책이다'를 단번에 말한다.
    """
    for box in (_p(0.13, 0.30, 0.31, 0.87), _p(0.37, 0.19, 0.55, 0.87)):
        d.rounded_rectangle(box, radius=int(R * 0.6), outline=c, width=W)
    _stroke(d, c, 0.65, 0.36, 0.81, 0.31, 0.90, 0.85, 0.74, 0.89, closed=True)


def draw_search(d, c):
    """통합 찾기 — 돋보기. 렌즈 **안쪽만** 옅은 포인트색 (시안 2)."""
    d.ellipse(_p(0.13, 0.13, 0.66, 0.66), fill=ACCENT_SOFT)
    d.ellipse(_p(0.13, 0.13, 0.66, 0.66), outline=c, width=W)
    _stroke(d, c, 0.62, 0.62, 0.87, 0.87)


# ══ 툴바 (회색 획 + 포인트 한 점) ═══════════════════════
def draw_settings(d, c):
    """설정 — 톱니. 가운데 원만 포인트색으로 채운다."""
    cx = cy = N / 2
    ri, ro = N * 0.30, N * 0.415
    d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], outline=c, width=W)
    r2 = N * 0.115
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=ACCENT + (255,))
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        _stroke(d, c,
                (cx + ri * math.cos(a)) / N, (cy + ri * math.sin(a)) / N,
                (cx + ro * math.cos(a)) / N, (cy + ro * math.sin(a)) / N)


def draw_help(d, c):
    """도움말 — 동그라미는 회색, **물음표만** 포인트색."""
    d.ellipse(_p(0.13, 0.13, 0.87, 0.87), outline=c, width=W)
    _text_mid(d, ACCENT + (255,), "?", N // 2, int(N * 0.47), int(N * 0.50),
              bold=False)


def draw_undo(d, c):
    """되돌리기 — 호는 회색, **화살촉만** 포인트색.

    원을 한 바퀴 가깝게 그렸더니 16px 에서 그냥 동그라미가 됐다 (실측
    2026-07-29). 호를 짧게 자르고 그 자리를 화살촉에 준다.
    """
    d.arc(_p(0.15, 0.20, 0.85, 0.90), start=185, end=55, fill=c, width=W)
    _chevron(d, ACCENT + (255,), 0.15, 0.55, 0.115, dx=0, dy=1)


def draw_pin(d, c):
    r"""항상 위 — **층 세 장, 맨 위 장만 포인트색** (사용자 결정 2026-07-30, 시안 라).

    압정은 '고정'이지 '가장 위'가 아니라는 지적이었다 (사용자 지시: "압정 말고
    가장 위에 있다는 느낌의 그림으로"). 층을 셋 쌓고 맨 위 한 장만 파랗게 두면
    **다른 것들 위에 있다**가 그림 그대로 읽힌다.

    획 셋은 이 한 벌에서 가장 많다 — 16px 에서 살아남게 층 간격을 0.17 로
    벌리고(획 굵기의 두 배 이상) 맨 위 장은 면으로 채워 덩어리를 만든다.
    """
    top = (0.50, 0.10, 0.87, 0.29, 0.50, 0.48, 0.13, 0.29)
    d.polygon(list(zip(*[iter(_p(*top))] * 2)), fill=ACCENT_SOFT)
    _stroke(d, ACCENT + (255,), *top, closed=True)
    _stroke(d, c, 0.13, 0.46, 0.50, 0.65, 0.87, 0.46)
    _stroke(d, c, 0.13, 0.63, 0.50, 0.82, 0.87, 0.63)


def draw_dock(d, c):
    """한글과 도킹 — 창 안에 도구줄과 문서가 든 모습 (시안 '가').

    우리 프로그램이 하는 일 그대로다: 위에 도구줄 한 줄, 그 아래 왼쪽은 우리
    자리(옅은 포인트색으로 채운다), 오른쪽은 한글 문서.
    """
    d.rounded_rectangle(_p(0.10, 0.17, 0.90, 0.83), radius=R, outline=c, width=W)
    d.rectangle(_p(0.10, 0.38, 0.38, 0.83), fill=ACCENT_SOFT)
    _stroke(d, c, 0.10, 0.38, 0.90, 0.38)
    _stroke(d, c, 0.38, 0.38, 0.38, 0.83)


# ══ 물감 분류 ═══════════════════════════════════════════
def draw_style(d, c):
    """물감 '서식' — 물감 한 방울.

    붓으로 그렸더니 16px 에서 **번개**로 읽혔다 (실측 2026-07-29). 자루와
    붓끝이 비스듬한 두 덩어리라 그렇다. 방울은 윤곽이 하나뿐이라 안 뭉갠다.
    이 프로그램에서 서식은 곧 물감이니 뜻도 이쪽이 곧다.
    """
    d.arc(_p(0.18, 0.36, 0.82, 0.90), start=0, end=180, fill=c, width=W)
    _stroke(d, c, 0.50, 0.13, 0.18, 0.63)
    _stroke(d, c, 0.50, 0.13, 0.82, 0.63)


def draw_template(d, c):
    """물감 '템플릿' — 종이에 **빈칸이 뚫린** 모양. 그 빈칸을 채우는 것이 템플릿이다."""
    d.rounded_rectangle(_p(0.17, 0.13, 0.83, 0.87), radius=R, outline=c, width=W)
    for y1, y2 in ((0.28, 0.41), (0.50, 0.63)):
        d.rounded_rectangle(_p(0.28, y1, 0.72, y2), radius=int(R * 0.45),
                            outline=c, width=int(W * 0.85))
    _stroke(d, c, 0.28, 0.76, 0.56, 0.76, w=int(W * 0.85))


def draw_form(d, c):
    """물감 '양식' — 줄 그은 종이 한 장. 통째로 여는 '종이'다."""
    d.rounded_rectangle(_p(0.20, 0.13, 0.80, 0.87), radius=R, outline=c, width=W)
    for y, x2 in ((0.31, 0.69), (0.45, 0.69), (0.59, 0.69), (0.73, 0.55)):
        _stroke(d, c, 0.31, y, x2, y, w=int(W * 0.85))


# ══ 그 밖 ══════════════════════════════════════════════
def draw_palette(d, c):
    """물감·팔레트 설정 — 팔레트 판. 프로그램 아이콘과 같은 어휘다.

    판을 통째로 채웠더니 이 한 벌에서 혼자 덩어리였다. 테두리만 남기고 물감
    자리는 **작고 채운 점**으로 — 점은 작아서 무게를 안 만들고, 오히려 얇은
    고리 안에서 '물감'이라는 뜻을 혼자 짊어진다.
    """
    d.ellipse(_p(0.13, 0.15, 0.87, 0.85), outline=c, width=W)
    for x, y in ((0.32, 0.36), (0.55, 0.29), (0.73, 0.46), (0.46, 0.66)):
        r = int(N * 0.052)
        cx, cy = _p(x, y)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)


def draw_share(d, c):
    """나누기 — 상자에서 위로 나가는 화살표. 지금 쓰는 ↗ 의 그림판이다."""
    _stroke(d, c, 0.50, 0.13, 0.50, 0.60)
    _chevron(d, c, 0.50, 0.13, 0.115, dx=0, dy=-1)
    _stroke(d, c, 0.15, 0.46, 0.15, 0.87, 0.85, 0.87, 0.85, 0.46)


def draw_tutorial(d, c):
    """튜토리얼 — 깃발.

    발자국 두 개로 그렸더니 16px 에서 **덩어리 넷**으로만 보였다 (실측
    2026-07-29). 작은 도형을 여러 개 늘어놓는 그림은 이 크기에서 안 된다.
    깃발은 윤곽이 하나고, '여기서 시작한다'는 뜻이 발자국만큼 곧다.
    """
    _stroke(d, c, 0.26, 0.13, 0.26, 0.87)
    _stroke(d, c, 0.26, 0.17, 0.84, 0.31, 0.26, 0.51, closed=True)


def draw_table(d, c):
    """표 만들기 — 격자. 머리줄만 있어 '표'와 '창 나누기'가 갈린다."""
    d.rounded_rectangle(_p(0.13, 0.18, 0.87, 0.82), radius=int(R * 0.6),
                        outline=c, width=W)
    _stroke(d, c, 0.13, 0.39, 0.87, 0.39)
    _stroke(d, c, 0.50, 0.18, 0.50, 0.82)


def draw_add(d, c):
    """추가 — 더하기. 빈 자리에 무언가를 새로 만드는 모든 곳에 쓴다."""
    _stroke(d, c, 0.50, 0.15, 0.50, 0.85)
    _stroke(d, c, 0.15, 0.50, 0.85, 0.50)


def draw_excel(d, c):
    """문항 엑셀 — 표 + 체크. 표를 채워 문항이 된다 (feature/excel 브랜치용)."""
    d.rounded_rectangle(_p(0.13, 0.16, 0.72, 0.84), radius=int(R * 0.6),
                        outline=c, width=W)
    _stroke(d, c, 0.13, 0.36, 0.72, 0.36, w=int(W * 0.85))
    _stroke(d, c, 0.42, 0.16, 0.42, 0.84, w=int(W * 0.85))
    _stroke(d, c, 0.58, 0.70, 0.68, 0.80, 0.90, 0.52)


# ── 목록 ────────────────────────────────────────────────
# (그룹, 표시 이름, 색, 그리는 함수) — 미리보기 페이지가 이 차례로 읽는다.
ICONS = {
    "convert":      ("블럭 도구", "마크다운 변환", BLUE,    draw_convert),
    "reset_format": ("블럭 도구", "기본 서식",     TEAL,    draw_reset_format),
    "photo":        ("블럭 도구", "사진",          PURPLE,  draw_photo),
    "special":      ("블럭 도구", "특수기호",      MAGENTA, draw_special),
    "form_fill":    ("블럭 도구", "양식 채우기",   GREEN,   draw_form_fill),
    "library":      ("블럭 도구", "라이브러리",    OCHRE,   draw_library),
    "search":       ("블럭 도구", "통합 찾기",     GRAY,    draw_search),

    "settings":     ("툴바", "설정",       GRAY, draw_settings),
    "help":         ("툴바", "도움말",     GRAY, draw_help),
    "undo":         ("툴바", "되돌리기",   GRAY, draw_undo),
    "pin":          ("툴바", "항상 위",    GRAY, draw_pin),
    "dock":         ("툴바", "한글과 도킹", GRAY, draw_dock),

    "style":        ("물감 분류", "서식",   TEAL,    draw_style),
    "template":     ("물감 분류", "템플릿", BLUE,    draw_template),
    "form":         ("물감 분류", "양식",   GREEN,   draw_form),

    "palette":      ("그 밖", "물감·팔레트 설정", CORAL,  draw_palette),
    "share":        ("그 밖", "나누기",           INDIGO, draw_share),
    "tutorial":     ("그 밖", "튜토리얼",         CORAL,  draw_tutorial),
    "table":        ("그 밖", "표 만들기",        INDIGO, draw_table),
    "add":          ("그 밖", "추가",             GRAY,   draw_add),
    "excel":        ("그 밖", "문항 엑셀",        GREEN,  draw_excel),
}


# ══ 고르는 중인 후보 ════════════════════════════════════
def draw_form_fill_b(d, c):
    """양식 채우기 후보 나 — **빈칸에 펜이 쓰고 있다.**

    가(종이+체크)는 '다 됐다'를 말한다. 이 기능은 다 된 것이 아니라 **지금
    채우는** 일이라, 펜이 빈칸 위에 있는 편이 뜻에 가깝다.
    """
    d.rounded_rectangle(_p(0.06, 0.10, 0.62, 0.94), radius=R, outline=c, width=W)
    for y in (0.32, 0.50, 0.68):
        x1, ly, x2, _ = _p(0.18, y, 0.50, 0)
        d.line([x1, ly, x2, ly], fill=c, width=int(W * 0.7))
    # 펜을 종이 위에 겹쳤더니 펜촉과 종이 모서리가 붙어 **체크 표시로** 보였다
    # (실측 2026-07-29) — 후보 가와 구별이 안 됐다. 종이 바깥으로 빼고 자루를
    # 길게 뽑아, 비스듬한 막대 하나가 따로 서 있게 한다.
    d.line(_p(0.98, 0.12, 0.72, 0.66), fill=c, width=int(W * 1.15))  # 펜대
    _poly(d, c, 0.74, 0.60, 0.86, 0.66, 0.70, 0.96)                  # 펜촉


def draw_form_fill_c(d, c):
    """양식 채우기 후보 다 — **빈칸 두 개, 위는 비고 아래는 찼다.**

    종이도 펜도 안 그린다. 이 기능의 알맹이는 '빈칸이 채워진다' 하나뿐이다.
    요소가 가장 적어 16px 에서 가장 안전하다.
    """
    d.rounded_rectangle(_p(0.08, 0.16, 0.92, 0.42), radius=int(R * 0.7),
                        outline=c, width=W)
    d.rounded_rectangle(_p(0.08, 0.58, 0.92, 0.84), radius=int(R * 0.7),
                        outline=c, width=W)
    d.rounded_rectangle(_p(0.16, 0.65, 0.74, 0.77), radius=int(R * 0.4), fill=c)


def draw_form_fill_d(d, c):
    """양식 채우기 후보 라 — 종이에 **화살표가 내려앉는다.** 값이 들어간다는 뜻."""
    d.rounded_rectangle(_p(0.10, 0.30, 0.90, 0.94), radius=R, outline=c, width=W)
    for y in (0.60, 0.78):
        x1, ly, x2, _ = _p(0.24, y, 0.62, 0)
        d.line([x1, ly, x2, ly], fill=c, width=int(W * 0.7))
    d.line(_p(0.72, 0.04, 0.72, 0.44), fill=c, width=W)
    h = int(N * 0.13)
    mx, my = _p(0.72, 0.50)
    d.polygon([(mx, my + h // 2), (mx - h, my - h), (mx + h, my - h)], fill=c)


def draw_convert_b(d, c):
    """변환 후보 나 — 기호 하나, 한글 하나. 글자 수를 줄여 작은 크기를 산다."""
    _text_mid(d, c, "#", int(N * 0.24), int(N * 0.50), int(N * 0.52))
    _arrow_r(d, c, 0.44, 0.60, 0.50, h=0.10)
    _text_mid(d, c, "가", int(N * 0.79), int(N * 0.50), int(N * 0.46))


def draw_convert_c(d, c):
    """변환 후보 다 — 사용자가 말한 그대로 `!@#$` 위, `가나다` 아래."""
    _text_mid(d, c, "!@#$", N // 2, int(N * 0.28), int(N * 0.28))
    _text_mid(d, c, "가나다", N // 2, int(N * 0.74), int(N * 0.28))


CANDIDATES = {
    "convert-가":   ("마크다운 변환", "#*\\ → 가나 (지금 것)",        BLUE,  draw_convert),
    "convert-나":   ("마크다운 변환", "# → 가  (글자 수를 줄임)",     BLUE,  draw_convert_b),
    "convert-다":   ("마크다운 변환", "!@#$ / 가나다  (말씀대로)",    BLUE,  draw_convert_c),
    "form_fill-가": ("양식 채우기", "종이 + 체크 (지금 것)",          GREEN, draw_form_fill),
    "form_fill-나": ("양식 채우기", "빈칸에 펜이 쓰는 중",            GREEN, draw_form_fill_b),
    "form_fill-다": ("양식 채우기", "빈칸 둘 — 위는 비고 아래는 참",  GREEN, draw_form_fill_c),
    "form_fill-라": ("양식 채우기", "종이로 내려앉는 화살표",         GREEN, draw_form_fill_d),
}


def build(fn, color):
    img = _canvas()
    fn(ImageDraw.Draw(img), color + (255,))
    return img


def _emit(fn, color, name, folders):
    for s in SIZES:
        small = build(fn, color).resize((s, s), Image.LANCZOS)
        for folder in folders:
            small.save(folder / f"{name}-{s}.png")


def main():
    cand = OUT / "_candidates", PREVIEW / "_candidates"
    for folder in (OUT, PREVIEW, *cand):
        folder.mkdir(parents=True, exist_ok=True)
    for key, (_g, _label, color, fn) in ICONS.items():
        _emit(fn, color, key, (OUT, PREVIEW))
    for name, (_g, _label, color, fn) in CANDIDATES.items():
        _emit(fn, color, name, cand)
    if _font_at(20) is None:
        print("⚠ 맑은 고딕을 못 찾았습니다 — 변환 아이콘의 글자가 빠집니다")
    print(f"기능 {len(ICONS)}개 · 후보 {len(CANDIDATES)}개 × {len(SIZES)}크기 "
          f"= {(len(ICONS) + len(CANDIDATES)) * len(SIZES)}장")
    print(f"  {OUT}")
    print(f"  {PREVIEW}  (미리보기용 사본)")


if __name__ == "__main__":
    main()
