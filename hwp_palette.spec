# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 설정 (UI 제안 20).

빌드:  python build_exe.py       (또는  pyinstaller hwp_palette.spec)
결과:  dist/hwp_palette.exe      — 파이썬이 없는 PC 에서도 그대로 실행

onefile 인 이유
  받는 사람에게 "이 폴더 통째로 복사하세요"라고 설명할 필요 없이 파일 하나만
  건네면 된다. 대신 실행할 때마다 임시 폴더에 풀리므로 첫 실행이 몇 초 느리다.
  설정·라이브러리는 임시 폴더가 아니라 **exe 옆**에 저장된다(paths.py 참고) —
  임시 폴더는 프로그램이 끝나면 지워지기 때문이다.

console=False 인 이유
  GUI 프로그램이라 검은 콘솔 창이 같이 뜨면 지저분하다. 대신 오류를 볼 곳이
  없어지므로, 로그를 app.log 로 남기는 applog 가 유일한 단서가 된다.
"""

import pathlib

HERE = pathlib.Path(SPECPATH)

a = Analysis(
    ["main.py"],
    pathex=[str(HERE)],
    binaries=[],
    # 아이콘은 코드에서 파일로 읽으므로 같이 넣어야 한다 (paths.RESOURCE_DIR)
    datas=[("assets/icon-96.png", "assets")],
    # pyhwpx 는 한글 COM 타입라이브러리를 실행 중에 만들어 쓴다. PyInstaller 의
    # 정적 분석으로는 win32com.client 의 동적 생성 경로가 안 잡혀서, 명시하지
    # 않으면 exe 에서만 "한글을 찾을 수 없습니다"가 난다.
    hiddenimports=[
        "win32com", "win32com.client", "win32com.client.gencache",
        "win32com.client.dynamic", "win32timezone",
        "pythoncom", "pywintypes", "win32gui", "win32api", "win32con",
        # 클립보드는 clipboard.py 가 함수 안에서 import 한다 — 정적 분석이
        # 놓치면 exe 에서만 복사·붙여넣기가 조용히 실패한다
        "win32clipboard",
        "pyhwpx",
    ],
    hookspath=[],
    runtime_hooks=[],
    # excludes 를 함부로 건드리지 말 것 (실측 2026-07-19).
    #   처음엔 크기를 줄이려고 numpy·pandas·PIL 을 뺐다. 빌드는 성공했고 테스트도
    #   전부 통과했지만, **exe 를 실행하면 창이 뜨기도 전에 죽었다** —
    #   ModuleNotFoundError: No module named 'numpy'.
    #   pyhwpx/core.py 가 맨 위에서 numpy·pandas·pyperclip·PIL 을 무조건 import
    #   하기 때문이다. 우리가 그 기능을 안 써도 pyhwpx 를 부르는 순간 필요하다.
    #   → 크기(약 15MB → 60MB)보다 '실행된다'가 먼저다.
    # 여기 남은 것들은 아무도 import 하지 않는 것만 확인하고 넣은 것이다.
    excludes=["matplotlib", "pytest", "setuptools", "tkinter.test", "test"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="hwp_palette",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # UPX 압축은 백신이 자주 오탐한다 — 학교 PC 에서 위험
    runtime_tmpdir=None,
    console=False,
    icon=str(HERE / "assets" / "icon.ico"),
)
