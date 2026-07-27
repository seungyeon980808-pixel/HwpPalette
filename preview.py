# -*- coding: utf-8 -*-
r"""물감 미리보기 — hwp 파일에 한글이 넣어둔 그림을 꺼낸다.

왜 이 방법인가 (2026-07-27 검토):
    "물감이 실제로 어떻게 생겼는지"를 보여주려면 hwp 를 다시 그려야 하는데,
    그건 무겁다(pyhwp+렌더러 4.6MB, 근사 렌더) 거나 느리다(한글을 켜서 열기).
    그런데 **한글이 저장할 때 이미 첫 페이지 그림을 파일 안에 넣어 둔다** —
    HWP 5.0 규격의 `PrvImage` 스트림(PNG). 파일 탐색기가 hwp 아이콘에
    문서 모양을 보여주는 것도 이걸 읽는 것이다.

    그래서 여기서 하는 일은 "그리기"가 아니라 "꺼내기"뿐이다. 한글도,
    렌더러도 필요 없고 결과는 한글 화면 그 자체다.
    실측: fragments/ 의 물감 조각 26개 전부 PrvImage 를 갖고 있었다.

한계:
  · 해상도가 **페이지 기준**이라 작은 조각은 작게 나온다(3보기 = 292x80).
    타일·펼침 미리보기 크기로는 충분하지만 크게 확대하면 흐리다.
  · 첫 페이지만 있다. 물감은 다 한 페이지 미만이라 문제되지 않는다.
  · 한글이 저장한 파일에만 들어 있다. 없으면 None 을 돌려주므로
    호출한 쪽이 글자 미리보기로 대체하면 된다.
"""

import io
import os

import olefile
from PIL import Image, ImageChops

import applog
import paths

_PRV = "PrvImage"

# (경로, 수정시각) → 잘라낸 Image. 같은 물감을 여러 번 그려도 파일은 한 번만 읽는다.
_cache = {}
_CACHE_MAX = 60


def _trim(im):
    """흰 여백을 잘라낸다 — 페이지 전체가 아니라 물감 자체만 보이게."""
    bg = Image.new(im.mode, im.size, (255, 255, 255))
    box = ImageChops.difference(im, bg).getbbox()
    if not box:
        return None                     # 전부 흰색 = 보여줄 것이 없다
    # 잘라낸 자리에 숨 쉴 틈을 조금 둔다 (테두리가 화면 끝에 붙지 않게)
    pad = 4
    left, top, right, bottom = box
    return im.crop((max(left - pad, 0), max(top - pad, 0),
                    min(right + pad, im.width), min(bottom + pad, im.height)))


def cache_dir():
    d = paths.data_dir() / "미리보기"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cached_path(item_id):
    r"""자리표시(\)를 걷어낸 미리보기 그림의 자리.

    hwp 안의 PrvImage 는 **저장된 그대로**라 빈칸 표시 `\` 가 그림에 찍혀 있다.
    그건 인쇄물에 안 나오는 표시인데 미리보기에 보이면 물감이 지저분해 보인다
    (사용자 지적 2026-07-27). 표시를 지운 사본을 한 번 떠서 png 로 남겨 두고,
    있으면 그걸 우선 쓴다.
    """
    return cache_dir() / f"{item_id}.png"


def image_of_item(item, fragment_path):
    """물감 하나의 미리보기 — 다듬어 둔 그림이 있으면 그것, 없으면 파일 안의 것."""
    png = cached_path(item.get("id"))
    if png.exists():
        try:
            return Image.open(png).convert("RGB")
        except Exception as e:
            applog.exc(f"다듬은 미리보기 읽기 실패 — {png.name}", e)
    return image_of(fragment_path)


def tk_photo_for_item(item, fragment_path, max_w, max_h):
    im = image_of_item(item, fragment_path)
    if im is None:
        return None
    scale = min(max_w / im.width, max_h / im.height, 1.0)
    if scale < 1.0:
        im = im.resize((max(int(im.width * scale), 1),
                        max(int(im.height * scale), 1)), Image.LANCZOS)
    from PIL import ImageTk
    return ImageTk.PhotoImage(im)


def save_cache(item_id, src_hwp):
    """자리표시를 지운 hwp 에서 그림을 떠 캐시에 넣는다. 성공 여부."""
    im = image_of(src_hwp)
    if im is None:
        return False
    try:
        im.save(cached_path(item_id))
        return True
    except OSError as e:
        applog.exc(f"미리보기 저장 실패 — {item_id}", e)
        return False


def image_of(path):
    """hwp 파일의 미리보기 그림(PIL Image). 없거나 못 읽으면 None."""
    # PrvImage 는 .hwp(OLE 복합문서)에만 있다. .hwpx(zip)에 대고 열면 실패만
    # 하고 로그가 쌓이므로 아예 시도하지 않는다.
    if str(path).lower().endswith(".hwpx"):
        return None
    try:
        key = (str(path), os.stat(path).st_mtime)
    except OSError:
        return None
    if key in _cache:
        return _cache[key]
    im = None
    try:
        ole = olefile.OleFileIO(str(path))
        try:
            if ole.exists(_PRV):
                raw = ole.openstream(_PRV).read()
                im = _trim(Image.open(io.BytesIO(raw)).convert("RGB"))
        finally:
            ole.close()
    except Exception as e:
        applog.exc(f"미리보기 그림 읽기 실패 — {path}", e)
        im = None
    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[key] = im
    return im


def thumbnail(path, max_w, max_h):
    """정해진 상자에 맞춰 줄인 미리보기. 원본보다 크게 늘리지는 않는다."""
    im = image_of(path)
    if im is None:
        return None
    scale = min(max_w / im.width, max_h / im.height, 1.0)
    if scale >= 1.0:
        return im
    return im.resize((max(int(im.width * scale), 1),
                      max(int(im.height * scale), 1)), Image.LANCZOS)


def tk_photo(path, max_w, max_h):
    """Tk 위젯에 바로 붙일 수 있는 PhotoImage. 없으면 None.

    ⚠ 돌려받은 것을 **위젯 어딘가에 붙들어 둬야 한다**(예: label.image = photo).
    Tk 는 PhotoImage 참조를 안 붙들면 가비지 컬렉션돼 그림이 빈칸으로 나온다.
    """
    im = thumbnail(path, max_w, max_h)
    if im is None:
        return None
    from PIL import ImageTk          # Tk 없는 환경(테스트)에서도 이 모듈을 쓰게
    return ImageTk.PhotoImage(im)
