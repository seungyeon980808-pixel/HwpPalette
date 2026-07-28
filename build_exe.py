# -*- coding: utf-8 -*-
"""exe 만들기 (UI 제안 20).

    python build_exe.py

빌드 전에 확인할 것들을 먼저 짚고 나서 PyInstaller 를 부른다. 그냥
`pyinstaller hwp_palette.spec` 를 쳐도 되지만, 빠뜨리기 쉬운 것들(개인 데이터가
exe 에 섞여 들어가는 것 등)을 여기서 막는다.
"""

import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SPEC = HERE / "hwp_palette.spec"
DIST = HERE / "dist"

# 이것들은 **개인 데이터**다. exe 안에 섞여 들어가면 남에게 건넬 때 내 팔레트와
# 저장해둔 조각이 통째로 딸려 간다. spec 의 datas 에 없으니 지금은 안 들어가지만,
# 나중에 누가 datas 에 "." 을 넣는 실수를 하면 조용히 새어 나간다.
# 2026-07-28 폴더 개편 뒤로는 이것들이 전부 data/ 안에 있다. 폴더 이름 하나만
# 막으면 되지만, 옛 이름도 함께 둔다 — spec 을 손보다 실수로 되살릴 수 있다.
PRIVATE = ["data", "config.json", "library.json", "fragments", "app.log"]


def check():
    problems = []
    if not SPEC.exists():
        problems.append(f"{SPEC.name} 이 없습니다")
    if not (HERE / "assets" / "icon.ico").exists():
        problems.append("assets/icon.ico 가 없습니다 (exe 아이콘)")
    if not (HERE / "assets" / "icon-96.png").exists():
        problems.append("assets/icon-96.png 가 없습니다 (창 안 아이콘)")
    try:
        import PyInstaller                      # noqa: F401
    except ImportError:
        problems.append("PyInstaller 가 없습니다  →  pip install pyinstaller")

    spec_text = SPEC.read_text(encoding="utf-8") if SPEC.exists() else ""
    for name in PRIVATE:
        if f'"{name}"' in spec_text.split("datas=")[-1].split("]")[0]:
            problems.append(f"spec 의 datas 에 개인 데이터({name})가 들어 있습니다")
    return problems


def main():
    problems = check()
    if problems:
        print("빌드할 수 없습니다:")
        for p in problems:
            print("  -", p)
        return 1

    # 이전 exe 가 아직 떠 있으면 파일이 잠겨 빌드가 중간에 죽는다. PyInstaller 의
    # 오류 메시지(PermissionError [WinError 5])만 보면 원인을 알기 어려우므로
    # 여기서 먼저 걸러 알려준다. ignore_errors=True 로 삼키면 안 된다 —
    # 지운 줄 알았는데 안 지워진 채로 빌드에 들어가게 된다.
    if DIST.exists():
        try:
            shutil.rmtree(DIST)
        except PermissionError:
            print("dist 폴더를 지울 수 없습니다.")
            print("  이전에 만든 hwp_palette.exe 가 아직 실행 중인 것 같습니다.")
            print("  창을 닫고 다시 시도하세요.")
            print("  (작업 관리자에서 hwp_palette.exe 를 끝내도 됩니다)")
            return 1

    print("PyInstaller 실행 — 몇 분 걸립니다\n")
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                        str(SPEC)], cwd=str(HERE))
    if r.returncode != 0:
        print("\n빌드 실패 — 위 오류를 확인하세요")
        return r.returncode

    exe = DIST / "hwp_palette.exe"
    if not exe.exists():
        print("\n빌드는 끝났는데 exe 가 없습니다 — spec 의 name 을 확인하세요")
        return 1

    print(f"\n완성: {exe}  ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
    print("\n건네기 전에 확인할 것")
    print("  1. 파이썬이 없는 PC 에서 실행되는지 (다른 컴퓨터에서 한 번)")
    print("  2. 한글을 켜고 → 표시등이 파란지 → 변환이 되는지")
    print("  3. 껐다 켰을 때 팔레트가 남아 있는지 (exe 옆 '내 물감' 폴더 확인)")
    print("  4. 백신이 막지 않는지 — 서명이 없어 경고가 뜰 수 있습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
