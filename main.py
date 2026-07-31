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

시작 실패를 감싼다 (2026-07-31 안전 점검):
    app.py 는 임포트하는 순간 창을 조립한다. 그 도중 예외가 나면 창 없는
    exe(console=False)에서는 **아무 창도, 아무 기록도 없이** 그냥 죽었다.
    여기서 받아 app.log 에 남기고, 로그조차 못 쓰는 상황(경로 계산 실패 등)
    에도 보이도록 윈도우 기본 대화상자(MessageBoxW)로 알린다.
"""

try:
    import hwp_palette.app     # noqa: F401  — 임포트하는 순간 창이 뜨고 mainloop 로 간다
except Exception as e:                       # SystemExit(정상 종료)는 그대로 통과한다
    # 1) 기록 — applog 자체가 안 켜지는 상황일 수 있으니 따로 감싼다
    try:
        from hwp_palette.core import applog
        applog.exc("시작 실패 — 창을 띄우지 못했습니다", e, detail=True)
    except Exception:
        pass
    # 2) 알림 — ctypes 만 쓰므로 applog·paths 가 다 죽어도 뜬다
    try:
        import ctypes
        short = f"{type(e).__name__}: {e}"
        ctypes.windll.user32.MessageBoxW(
            0,
            "한글 팔레트가 시작하지 못했습니다.\n"
            "'내 물감' 폴더의 app.log 를 확인해 주세요.\n\n" + short,
            "한글 팔레트", 0x10)
    except Exception:
        pass
    raise                                    # 콘솔로 켰을 때는 스택도 보인다
