# -*- coding: utf-8 -*-
r"""윈도우 클립보드 — **Tk 클립보드를 쓰지 않는다** (실측 2026-07-26).

왜 따로 떼어 놓는가.

Tk 의 `clipboard_append` 는 클립보드에 값을 넣는 것이 아니라 **"내가 클립보드
주인이다, 필요하면 물어봐라"** 라고 등록만 한다(지연 렌더링). 그래서 그 뒤로
같은 프로세스에서 `win32clipboard.OpenClipboard()` 를 부르면
`(5, 'OpenClipboard', '액세스가 거부되었습니다')` 가 쏟아진다(실측).

이것이 튜토리얼에서 변환이 안 잡히던 원인이다:
  [복사] 버튼(Tk 클립보드) → 한글에 붙여넣기 → 드래그 선택 → [마크다운 변환]
  → 한글의 Copy 결과를 읽어야 하는데 클립보드가 잠겨 10회 재시도 모두 실패
  → 선택을 못 읽고 "선택 없음".

그래서 **담을 때도 읽을 때도 윈도우 API 로만** 다룬다. 우리가 클립보드 주인이
되지 않으므로 잠기지 않고, 한글이 Copy 로 넣은 값도 그대로 읽힌다.
win32clipboard 가 없는 환경(테스트·비윈도우)에서는 Tk 로 물러난다.
"""

import time

from hwp_palette.core import applog

_RETRIES = 10
_DELAY = 0.08


def _win32():
    """win32clipboard 모듈 (없으면 None) — 플랫폼 의존이라 지역 import."""
    try:
        import win32clipboard
        return win32clipboard
    except ImportError:
        return None


def set_text(text, widget=None):
    """클립보드에 글자를 담는다. 성공하면 True.

    widget 을 주면 윈도우 API 가 없는 환경에서만 Tk 로 물러난다
    (되도록 쓰이지 않아야 하는 길이다 — 위 설명 참조).
    """
    w = _win32()
    if w is not None:
        last = None
        for _ in range(_RETRIES):
            try:
                w.OpenClipboard()
                try:
                    w.EmptyClipboard()
                    w.SetClipboardData(w.CF_UNICODETEXT, str(text))
                finally:
                    w.CloseClipboard()
                return True
            except Exception as e:
                last = e            # 다른 앱이 잠깐 잡고 있으면 실패한다
                time.sleep(_DELAY)
        applog.exc(f"클립보드 담기 {_RETRIES}회 모두 실패", last)
    if widget is not None:
        try:
            widget.clipboard_clear()
            widget.clipboard_append(str(text))
            widget.update()
            return True
        except Exception as e:
            applog.exc("Tk 클립보드 담기도 실패", e)
    return False


def get_text(retries=_RETRIES, delay=_DELAY):
    """클립보드의 글자. 못 읽으면 빈 문자열."""
    w = _win32()
    if w is None:
        return ""
    last = None
    for _ in range(retries):
        try:
            w.OpenClipboard()
            try:
                if w.IsClipboardFormatAvailable(w.CF_UNICODETEXT):
                    text = w.GetClipboardData(w.CF_UNICODETEXT)
                    if text:
                        return text
            finally:
                w.CloseClipboard()
        except Exception as e:
            last = e
        time.sleep(delay)
    if last is not None:
        applog.exc(f"클립보드 읽기 {retries}회 모두 실패", last)
    return ""
