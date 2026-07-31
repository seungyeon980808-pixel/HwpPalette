# -*- coding: utf-8 -*-
r"""릴리즈 자산 두 벌 만들기 — 투 트랙 (사용자 결정 2026-07-31).

    python build_release.py

만드는 것 (전부 dist\ 안):
    1. HwpPalette-<버전>-portable.zip   비설치형 — 풀어서 바로 실행
    2. HwpPalette-Setup-<버전>.exe      설치형 — Inno Setup 이 있어야 만든다

둘 다 GitHub Releases 에 올린다:
    gh release create v<버전> dist\HwpPalette-*-portable.zip dist\HwpPalette-Setup-*.exe

Inno Setup 이 없으면 zip 만 만들고, 설치형은 만드는 법을 안내한다 —
zip 트랙이 막히면 안 되므로 설치형 실패로 전체를 죽이지 않는다.
"""

import pathlib
import shutil
import subprocess
import sys
import zipfile

# build_exe 와 같은 이유 — 파이프로 넘길 때 cp949 로 죽지 않게
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_exe                                    # noqa: E402
from hwp_palette.core import appinfo                # noqa: E402

DIST = HERE / "dist"
ISS = HERE / "installer" / "hwp_palette.iss"

# ISCC(Inno Setup 컴파일러)를 찾는 자리 — PATH 에 없어도 기본 설치 자리를 본다
_ISCC_CANDIDATES = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def _find_iscc():
    hit = shutil.which("iscc")
    if hit:
        return hit
    for c in _ISCC_CANDIDATES:
        if pathlib.Path(c).exists():
            return c
    return None


def make_portable_zip(exe):
    """비설치형 zip — exe 하나만 담는다. '내 물감' 폴더는 첫 실행이 만든다."""
    out = DIST / f"HwpPalette-{appinfo.VERSION}-portable.zip"
    tmp = out.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe, exe.name)
    tmp.replace(out)                    # 원자적 — 반쪽짜리 zip 이 남지 않게
    return out


def make_installer():
    """설치형 Setup exe. Inno Setup 이 없으면 None — 안내만 하고 넘어간다."""
    iscc = _find_iscc()
    if iscc is None:
        print("\n[설치형 건너뜀] Inno Setup 6 이 없습니다. 만들려면:")
        print("    winget install JRSoftware.InnoSetup")
        print("  설치 후 이 스크립트를 다시 실행하세요.")
        return None
    print("\nInno Setup 실행 —", iscc)
    r = subprocess.run([iscc, f"/DAppVersion={appinfo.VERSION}", str(ISS)],
                       cwd=str(HERE))
    if r.returncode != 0:
        print("설치형 빌드 실패 — 위 오류를 확인하세요 (zip 은 이미 만들어졌습니다)")
        return None
    return DIST / f"HwpPalette-Setup-{appinfo.VERSION}.exe"


def main():
    rc = build_exe.main()               # exe 부터 — 검사·안내는 build_exe 가 한다
    if rc:
        return rc
    exe = DIST / "hwp_palette.exe"

    z = make_portable_zip(exe)
    print(f"\n비설치형: {z.name}  ({z.stat().st_size / 1024 / 1024:.1f} MB)")

    setup = make_installer()
    if setup and setup.exists():
        print(f"설치형:   {setup.name}  ({setup.stat().st_size / 1024 / 1024:.1f} MB)")

    print("\n릴리즈에 올리기 (버전 태그는 사용자가 정한 시점에):")
    print(f"    gh release create v{appinfo.VERSION} "
          f'dist\\{z.name}' + (f" dist\\{setup.name}" if setup else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
