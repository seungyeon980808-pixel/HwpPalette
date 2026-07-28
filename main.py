# -*- coding: utf-8 -*-
r"""실행 진입점.

    python main.py

여기에는 **아무 내용도 두지 않는다.** 프로그램 본체는 hwp_palette/ 안에 층으로
나뉘어 있고(hwp_palette/__init__.py 의 층 규칙 참고), 창을 조립하는 일은
hwp_palette/app.py 가 한다.

이 파일을 남겨 둔 이유 (2026-07-28 폴더 개편):
    `python main.py` 로 켜는 손버릇, run.bat, PyInstaller 설정(hwp_palette.spec
    의 Analysis(["main.py"]))이 모두 이 이름에 걸려 있다. 얇은 파일 하나로
    그 셋을 그대로 두는 편이, 셋을 다 고치고 새 이름을 외우는 것보다 싸다.
"""

import hwp_palette.app     # noqa: F401  — 임포트하는 순간 창이 뜨고 mainloop 로 간다
