# -*- coding: utf-8 -*-
r"""아이콘 만들기 —  python assets/make_icons.py

두 벌을 뽑는다 (사용자 결정 2026-07-27):
  · icon.ico / icon-96.png  — 프로그램(exe·창) 아이콘 = **팔레트**
  · folder.ico              — '내 물감' 데이터 폴더 아이콘 = **물감**

왜 다시 그리나: 예전 아이콘은 팔레트 + 붓 + 글자(h·w·P)까지 들어 있어
16px 로 줄이면 뭉개져 아무것도 안 읽혔다(assets/icon-candidates/_16px-test.png
에서 확인). 작업표시줄·바탕화면에서 실제로 보이는 크기는 16~32px 다.

원칙 (CLAUDE.md 디자인):
  · AI티 금지 — 그라데이션·큰 그림자·과한 장식 없이 납작하게
  · 시그니처 색을 쓴다 — 메인 #0969da, 서브 #0e7490
  · **글자를 넣지 않는다** — 작은 크기에서 글자는 얼룩이 된다

그리는 법: 실제 크기의 8배로 그린 뒤 LANCZOS 로 줄인다(계단 없애기).
"""

import pathlib

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
S = 8                                   # 오버샘플 배수
BASE = 256                              # 기준 크기
N = BASE * S

NAVY = (13, 27, 42, 255)                # 바탕 — 짙은 남색
CREAM = (246, 248, 250, 255)            # 팔레트 판
BLUE = (9, 105, 218, 255)               # 시그니처 메인
TEAL = (14, 116, 144, 255)              # 시그니처 서브
CORAL = (214, 90, 74, 255)              # 물감 하나는 따뜻한 색이어야 '물감'이다
SUNNY = (232, 176, 40, 255)


def _canvas():
    return Image.new("RGBA", (N, N), (0, 0, 0, 0))


def _round_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def app_icon():
    r"""프로그램 아이콘 — 짙은 바탕 위 **팔레트 한 장**.

    팔레트 판을 크게 두고 물감 네 방울만 얹는다. 붓·글자를 뺀 자리를 판이
    채우므로 16px 에서도 '둥근 판에 색점' 이라는 형태가 남는다.
    """
    img = _canvas()
    d = ImageDraw.Draw(img)
    _round_rect(d, (0, 0, N - 1, N - 1), radius=int(N * 0.22), fill=NAVY)

    # 팔레트 판 — 살짝 기운 타원 (손잡이 쪽이 넓은 진짜 팔레트 모양)
    pad = int(N * 0.14)
    d.ellipse((pad, int(N * 0.20), N - pad, int(N * 0.86)), fill=CREAM)

    # 엄지 구멍 — 판을 팔레트로 읽히게 하는 유일한 단서라 큼직하게
    hx, hy, hr = int(N * 0.63), int(N * 0.63), int(N * 0.105)
    d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=NAVY)

    # 물감 네 방울 — 판 위쪽을 따라 호를 그리며 놓는다
    r = int(N * 0.082)
    for (cx, cy), color in (
            ((0.34, 0.40), BLUE),
            ((0.50, 0.335), TEAL),
            ((0.665, 0.395), CORAL),
            ((0.35, 0.60), SUNNY)):
        x, y = int(N * cx), int(N * cy)
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)
    return img


def folder_icon():
    r"""'내 물감' 폴더 아이콘 — **물감 세 방울**.

    폴더 모양을 그대로 두고 색점만 얹으면 탐색기의 기본 폴더와 헷갈린다.
    그래서 폴더 실루엣을 시그니처 색으로 칠하고, 그 위에 물감을 얹는다.
    """
    img = _canvas()
    d = ImageDraw.Draw(img)

    # 폴더 뒷장 (탭이 있는 쪽)
    top = int(N * 0.20)
    d.rounded_rectangle((int(N * 0.06), top, int(N * 0.50), top + int(N * 0.10)),
                        radius=int(N * 0.035), fill=TEAL)
    d.rounded_rectangle((int(N * 0.06), top + int(N * 0.04),
                         int(N * 0.94), int(N * 0.84)),
                        radius=int(N * 0.05), fill=TEAL)
    # 앞장 — 한 단 밝게 해서 열린 폴더처럼
    d.rounded_rectangle((int(N * 0.06), int(N * 0.34),
                         int(N * 0.94), int(N * 0.86)),
                        radius=int(N * 0.05), fill=BLUE)

    # 물감 세 방울
    r = int(N * 0.088)
    for (cx, cy), color in (((0.30, 0.60), CREAM),
                            ((0.50, 0.60), SUNNY),
                            ((0.70, 0.60), CORAL)):
        x, y = int(N * cx), int(N * cy)
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)
    return img


def save_ico(img, path, sizes=(16, 24, 32, 48, 64, 128, 256)):
    small = img.resize((256, 256), Image.LANCZOS)
    small.save(path, format="ICO",
               sizes=[(s, s) for s in sizes])
    return path


def main():
    app = app_icon()
    save_ico(app, HERE / "icon.ico")
    app.resize((96, 96), Image.LANCZOS).save(HERE / "icon-96.png")

    folder = folder_icon()
    save_ico(folder, HERE / "folder.ico", sizes=(16, 32, 48, 256))

    # 눈으로 확인할 작은 판 — 실제로 보이는 크기로 나란히
    strip = Image.new("RGBA", (16 + 32 + 48 + 40, 48), (255, 255, 255, 0))
    x = 0
    for size in (16, 32, 48):
        strip.paste(app.resize((size, size), Image.LANCZOS), (x, 48 - size))
        x += size + 10
    strip.save(HERE / "icon-candidates" / "_preview-app.png")

    strip2 = Image.new("RGBA", (16 + 32 + 48 + 40, 48), (255, 255, 255, 0))
    x = 0
    for size in (16, 32, 48):
        strip2.paste(folder.resize((size, size), Image.LANCZOS), (x, 48 - size))
        x += size + 10
    strip2.save(HERE / "icon-candidates" / "_preview-folder.png")
    print("만들었습니다: icon.ico · icon-96.png · folder.ico")


if __name__ == "__main__":
    main()
