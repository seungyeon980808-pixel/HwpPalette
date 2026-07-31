# -*- coding: utf-8 -*-
r"""033-a 실측 — 수능양식의 둘째 `\` 는 HWPX 의 **어떤 요소 안**에 있나 (2026-08-01).

RUN_RE(<hp:t> 스캔)가 못 찾는 `\` 의 조상 태그 사슬을 추적한다.
글상자(hp:drawText)면 읽기를 넓힐 자리가 정해지고, **재주입(되쓰기)이 같은
경로로 안전한지**도 판단할 근거가 된다.

원본은 손대지 않는다 — 임시 폴더 사본으로 변환한다.
"""
import io
import pathlib
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.hwp import engine_library
from hwp_palette.hwp import hwp_engine
from hwp_palette.model import form_fill

FRAG = pathlib.Path("data/fragments/31354095e68c4693818afe912a52d84e.hwp")
OUT = pathlib.Path(__file__).with_suffix(".log")
out = []


def say(*a):
    out.append(" ".join(str(x) for x in a))


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="spike033_"))
    src = tmp / FRAG.name
    shutil.copy2(FRAG, src)
    dst = tmp / (FRAG.stem + ".hwpx")

    if not hwp_engine.connect():
        say("한글 연결 실패")
        return
    engine_library.export_as_hwpx(src, dst)
    say("변환:", dst, dst.exists())

    say("read_runs 가 본 빈칸:",
        sum(form_fill._count_tokens(t) for _, t in form_fill.read_runs(dst)))
    say("hidden_slot_count:", form_fill.hidden_slot_count(dst))

    with zipfile.ZipFile(dst) as zf:
        for name in zf.namelist():
            if not form_fill.SECTION_RE.search(name):
                continue
            xml = zf.read(name).decode("utf-8")
            # 네임스페이스를 무시하고 파싱하기 위해 지역 이름만 남긴다
            xml2 = re.sub(r"xmlns(:\w+)?=\"[^\"]*\"", "", xml)
            xml2 = re.sub(r"<(/?)\w+:", r"<\1", xml2)
            xml2 = re.sub(r"(\s)\w+:(\w+=)", r"\1\2", xml2)
            root = ET.fromstring(xml2)
            parent = {c: p for p in root.iter() for c in p}

            def chain(el):
                names = []
                cur = el
                while cur is not None:
                    names.append(cur.tag)
                    cur = parent.get(cur)
                return " < ".join(names)

            for el in root.iter("t"):
                text = "".join(el.itertext())
                n = form_fill._count_tokens(text)
                if n:
                    say(f"[{name}] 빈칸 {n}개 · 글자 {text!r}")
                    say("   조상:", chain(el))
    say("\n끝")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        say("예외:", traceback.format_exc())
    finally:
        io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
        print(f"[log] {OUT}")
