# -*- coding: utf-8 -*-
r"""모니터 범위 — 여러 대를 쓸 때 창이 엉뚱한 화면으로 튀지 않게 (2026-07-26).

무엇이 문제였나 (실측):
    Tk 의 winfo_screenwidth/height 는 **주 모니터 하나**의 크기만 말한다.
    이 PC 는 주 모니터가 1080x1920(세로)이고 4K 모니터가 **왼쪽**에 있어서,
    왼쪽 모니터의 x 좌표는 -3840 부터 시작한다.
    그래서 "화면 밖으로 나가지 않게" 하려고 x 를 0..screenwidth 로 자르면,
    왼쪽 모니터에 떠 있는 창의 팝업 메뉴가 **주 모니터로 순간이동**한다 —
    사용자 눈에는 "눌러도 아무 반응이 없다"로 보인다 (2026-07-26 버그).

여기서는 **모든 모니터를 합친 바탕 화면** 범위를 돌려준다. ctypes 로 묻는
값은 이 프로세스의 DPI 인식 수준을 따르므로 Tk 좌표와 같은 자로 잰 값이다.
"""

import applog

# GetSystemMetrics 인덱스 (winuser.h)
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79


def desktop_bounds(widget):
    """모든 모니터를 합친 범위 (x, y, width, height).

    못 물어보면 주 모니터 크기로 물러선다 (윈도우가 아닌 환경·테스트 대비).
    """
    try:
        import ctypes
        gsm = ctypes.windll.user32.GetSystemMetrics
        x, y = gsm(_SM_XVIRTUALSCREEN), gsm(_SM_YVIRTUALSCREEN)
        w, h = gsm(_SM_CXVIRTUALSCREEN), gsm(_SM_CYVIRTUALSCREEN)
        if w > 0 and h > 0:
            return x, y, w, h
    except Exception as e:
        applog.exc("모니터 범위 조회 실패 — 주 모니터 기준으로 동작", e)
    return 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight()


def clamp_window(widget, x, y, w, h):
    """(x, y) 를 바탕 화면 안으로 밀어 넣는다. 모니터를 가로질러도 안전하다."""
    dx, dy, dw, dh = desktop_bounds(widget)
    x = max(dx, min(int(x), dx + dw - int(w)))
    y = max(dy, min(int(y), dy + dh - int(h)))
    return x, y


def fits_below(widget, y, h):
    """그 자리에 높이 h 짜리가 아래로 다 들어가는가 (아니면 위로 펼쳐야 한다)."""
    _dx, dy, _dw, dh = desktop_bounds(widget)
    return y + h <= dy + dh


def is_on_desktop(widget, x, y, margin=100):
    """그 위치가 지금 붙어 있는 모니터들 안인가 (모니터를 뺐을 때 창 실종 방지)."""
    dx, dy, dw, dh = desktop_bounds(widget)
    return (dx - 50 <= x <= dx + dw - margin
            and dy - 20 <= y <= dy + dh - 80)
