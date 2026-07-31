# -*- coding: utf-8 -*-
r"""버튼 손맛 — 호버 색 보간과 누름 피드백 (애플 디자인 A안, 2026-07-25).

무엇이 문제였나:
    기존 tk.Button 은 마우스를 올려도 아무 변화가 없다가 누르는 순간
    activebackground 로 **탁** 바뀌었다. 중간 단계가 없어서 '버벅인다'고
    느껴진다 — 애플 UI 의 부드러움은 대부분 이 **전환 구간**에서 나온다.

어떻게 하나:
    <Enter>/<Leave> 에서 배경색을 ease-out cubic 곡선을 따라 보간한다.
    걸리는 시간은 theme.MOTION["hover_ms"] 가 정하고(지금 128ms), 여기서는
    60fps 프레임 주기(16ms)로 나눠 단계 수만 역산한다.
    누르면 즉시 진해진다 (전환 없이 — 누름은 **즉각** 반응해야 눌린 맛이 난다).

주의:
    팔레트 블럭은 탭 전환 때 파괴된다. 파괴된 위젯에 늦게 도착한 after 콜백이
    닿으면 TclError 가 나므로 winfo_exists() 로 매번 확인한다.
"""

from hwp_palette.core import applog
from hwp_palette.design import theme

# 단계 간격 — 60fps 화면이 새로 그려지는 주기. 이보다 촘촘히 잡아 봐야
# 중간 색은 그려지지 않고 버려진다.
INTERVAL_MS = 16
# 보간 단계 수는 **토큰에서 역산한다**. 여기에 8 이라고 적어 두면 theme.MOTION
# 의 값과 갈라져도 아무도 모른다 (실제로 128 vs 130 으로 갈라져 있었다).
# 이제 호버 시간을 바꾸려면 theme.MOTION 한 곳만 고치면 된다.
STEPS = max(1, round(theme.MOTION["hover_ms"] / INTERVAL_MS))


def ease_out(t):
    """ease-out cubic — 빠르게 시작해 부드럽게 멈춘다.

    선형 보간은 끝에서 **뚝 멈춰** 기계적으로 느껴진다. 애플 UI 의 부드러움은
    대부분 이 감속 곡선에서 온다 (2026-07-25).
    """
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


# ── 색 계산 (순수 함수 — 테스트 대상) ──────────────────
def hex_to_rgb(color):
    """'#rrggbb' → (r, g, b). '#abc' 축약형도 받는다."""
    h = (color or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"색이 아닙니다: {color!r}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def lerp(color_a, color_b, t):
    """두 색 사이 t(0~1) 지점의 색."""
    a, b = hex_to_rgb(color_a), hex_to_rgb(color_b)
    return rgb_to_hex(tuple(av + (bv - av) * t for av, bv in zip(a, b)))


def darken(color, factor=0.94):
    """살짝 어둡게 — 호버(0.94)·누름(0.86)용.

    애플식 피드백은 '다른 색'이 아니라 **같은 색이 진해지는 것**이다.
    그래서 고정 색 대신 어느 배경에서든 통하는 배율을 쓴다 — 사용자가
    블럭 색을 직접 골라도(빨강·남색…) 그 색의 진한 판이 나온다.
    """
    return rgb_to_hex(tuple(v * factor for v in hex_to_rgb(color)))


HOVER_FACTOR = 0.94
PRESS_FACTOR = 0.86


# ── 창 투명도 전환 (2026-07-28) ────────────────────────
# 왜 필요한가: 창을 destroy 하거나 판을 접었다 펴면 Tk 는 그 사이 **다시 그리는
# 과정을 그대로 보여준다** — 판이 사라졌다가 다른 크기로 나타나는 한두 프레임이
# 사람 눈에는 '깜빡임'으로 읽힌다 (사용자 지적 2026-07-28).
#
# 애플이 쓰는 방법은 그 구간을 **안 보이게 덮는 것**이다: 불투명도를 잠깐
# 내렸다가, 배치가 다 끝난 뒤 올린다. 옮기는 동안 창 자체가 반투명이라
# 무엇이 어떻게 재배치되는지가 눈에 띄지 않는다.
#
# 창 알파는 윈도우 합성기가 처리하므로(Tk 위젯 재그리기와 무관) 이 전환은
# 레이아웃을 한 번도 건드리지 않는다 — 그래서 그 자체로는 절대 안 깜빡인다.
FADE_STEPS = 7
FADE_INTERVAL_MS = 14


def _set_alpha(win, value):
    try:
        win.attributes("-alpha", max(0.0, min(1.0, value)))
        return True
    except Exception:
        return False            # -alpha 를 못 쓰는 환경 — 전환 없이 즉시 처리


def fade(win, to, ms=None, on_done=None, ease=True):
    """창 불투명도를 지금 값에서 to(0~1)로 옮긴다. 끝나면 on_done.

    -alpha 를 지원하지 않으면 곧바로 on_done 을 부른다 — 전환은 장식이므로
    없다고 해서 동작이 막히면 안 된다.
    """
    try:
        start = float(win.attributes("-alpha"))
    except Exception:
        if on_done:
            on_done()
        return
    steps = FADE_STEPS
    interval = FADE_INTERVAL_MS if ms is None else max(1, int(ms / steps))
    if abs(to - start) < 0.02:
        _set_alpha(win, to)
        if on_done:
            on_done()
        return

    def step(k):
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return
        t = ease_out(k / steps) if ease else (k / steps)
        _set_alpha(win, start + (to - start) * t)
        if k < steps:
            try:
                win.after(interval, lambda: step(k + 1))
            except Exception:
                pass
        elif on_done:
            on_done()

    step(1)


def fade_close(win, ms=120):
    """창을 흐려지며 닫는다 — 뚝 사라지는 대신.

    파괴는 **전환이 끝난 뒤** 한 번만 한다. 중간에 destroy 되면 남은 after
    콜백이 죽은 창을 잡으므로 winfo_exists 로 막는다 (fade 안에서 확인).
    """
    def done():
        try:
            win.destroy()
        except Exception:
            pass
    fade(win, 0.0, ms=ms, on_done=done)


def reveal(win, place=None, ms=120):
    r"""숨긴 창을 애플식 '빠르게 떠서 부드럽게 정착'으로 보여준다.

    창이 '탁' 나타나는 대신 0.12초 ease-out 페이드다. withdraw 된 Toplevel 을
    (1) place() 로 먼저 자리 잡고 (2) 알파 0 으로 내린 채 deiconify + lift,
    (3) fade 로 1.0 까지 올린다 — 자리 잡는 재배치 과정이 화면에 안 보인다.
    -alpha 를 못 쓰는 환경이면 전환 없이 그냥 deiconify 한다 (전환은 장식이라
    없다고 동작이 막히면 안 된다 — fade 와 같은 원칙).

    이미 보이는 창에 불러도 안전하다: 알파를 0 으로 떨어뜨리지 않고 앞으로
    올리기만 한다 — 멀쩡히 떠 있는 창이 깜빡이면 그게 또 '탁'이다.
    """
    try:
        if place is not None:
            place()                     # 알파를 내리기 전에 — 자리부터 잡는다
    except Exception as e:
        applog.exc("reveal: 자리 잡기 실패 — 지금 자리에서 띄운다", e)
    try:
        shown = win.state() == "normal"
    except Exception:
        shown = False
    if not shown and not _set_alpha(win, 0.0):
        # -alpha 미지원 (TclError) — 전환 없이 즉시 보여준다
        try:
            win.deiconify()
            win.lift()
        except Exception:
            pass
        return
    try:
        win.deiconify()
        win.lift()
    except Exception:
        pass
    # 이미 알파 1.0 이면 fade 는 곧바로 끝난다 (멱등) — 반투명으로 남아
    # 있었다면 마저 올린다.
    fade(win, 1.0, ms=ms)


def veil(win, work, dim=0.0, out_ms=110, in_ms=160):
    r"""**옮기는 동안 가린다** — 흐려짐 → work() → 다시 진해짐.

    판을 접었다 펴거나 창 크기를 크게 바꾸는 일(양식 수정 종료 등)에 쓴다.
    work 는 흐려진 뒤에 불리므로, 그 안에서 창 크기·배치를 마음껏 바꿔도
    재배치 과정이 화면에 안 보인다.

    work 가 예외를 던져도 **반드시 다시 진해진다** — 안 그러면 창이 투명한
    채로 남아 프로그램이 사라진 것처럼 보인다.
    """
    def after_dim():
        try:
            work()
        finally:
            try:
                win.update_idletasks()      # 새 배치를 알파 복귀 전에 확정
            except Exception:
                pass
            fade(win, 1.0, ms=in_ms)

    fade(win, dim, ms=out_ms, on_done=after_dim)


# ── Tk 위젯에 붙이기 ───────────────────────────────────
def rebase(widget, base):
    """attach 로 붙인 위젯의 **기준색**을 바꾼다 (탭 활성/비활성 전환 등).

    다시 attach 하면 바인딩이 겹쳐 쌓이므로(add="+"), 기준색만 갈아끼운다.
    """
    setter = getattr(widget, "_fx_rebase", None)
    if setter:
        setter(base)


def attach_all(container):
    r"""창 안의 **모든 tk.Button** 을 훑어 호버 보간을 단다 (2026-07-25).

    라이브러리·환경설정처럼 버튼이 수십 개인 창에 하나하나 attach 를 부르는
    대신, 창을 다 만든 뒤(또는 목록을 다시 그린 뒤) 이걸 한 번 부른다.
    기준색은 그 버튼의 **지금 배경색** — 파랑 버튼은 파랑답게, 회색은 회색답게.
    이미 붙인 버튼(_fx_rebase 표식)은 건너뛰므로 여러 번 불러도 겹치지 않는다.
    """
    import tkinter as tk
    stack = [container]
    while stack:
        w = stack.pop()
        try:
            stack.extend(w.winfo_children())
            if isinstance(w, tk.Button) and not hasattr(w, "_fx_rebase"):
                attach(w, w.cget("bg"))
        except Exception:
            continue        # 파괴 중인 위젯 — 건너뛴다


def attach(widget, base, hover=None, press=None):
    r"""tk.Button/Label 에 호버 보간 + 누름 피드백을 단다.

    hover/press 를 안 주면 base 를 어둡게 만들어 쓴다.
    기존 <Enter>/<Leave> 바인딩(툴팁)과 공존한다 — add="+" 로 붙인다.
    """
    state = {"job": None,
             "base": base,
             "hover": hover or darken(base, HOVER_FACTOR),
             "press": press or darken(base, PRESS_FACTOR)}

    def _rebase(new_base):
        state["base"] = new_base
        state["hover"] = darken(new_base, HOVER_FACTOR)
        state["press"] = darken(new_base, PRESS_FACTOR)

    widget._fx_rebase = _rebase             # rebase() 가 찾아 쓴다

    def _cancel():
        if state["job"] is not None:
            try:
                widget.after_cancel(state["job"])
            except Exception:
                pass
            state["job"] = None

    def _animate(start, to_color, step=1):
        """start → to_color 로 이징 곡선을 따라 옮긴다.

        **시작색을 붙잡아 두는 것**이 중요하다. 매 단계 '현재 색'에서 다시
        보간하면 목표에 점점 느리게 다가가기만 해서(제논의 역설) 끝이
        흐지부지되고, 중간에 방향이 바뀌면 색이 튄다 — 그게 '깜빡이는' 느낌의
        원인이었다 (2026-07-25).
        """
        state["job"] = None
        try:
            if not widget.winfo_exists():
                return                      # 탭 전환 등으로 이미 파괴됨
            widget.config(bg=lerp(start, to_color, ease_out(step / STEPS)))
            if step < STEPS:
                state["job"] = widget.after(
                    INTERVAL_MS, lambda: _animate(start, to_color, step + 1))
        except Exception as e:              # 파괴 직전 경합 — 조용히 끝낸다
            applog.exc("호버 전환 중단 (무해)", e, detail=False)

    def _start(to_color):
        _cancel()
        try:
            here = widget.cget("bg")
        except Exception:
            return
        if here == to_color:
            return                          # 이미 그 색 — 헛돌지 않는다
        _animate(here, to_color)

    def _on_enter(_e):
        _start(state["hover"])

    def _on_leave(_e):
        _start(state["base"])

    def _on_press(_e):
        _cancel()
        try:
            widget.config(bg=state["press"])  # 누름은 전환 없이 즉시 — 눌린 맛
        except Exception:
            pass

    def _on_release(_e):
        _start(state["hover"])              # 커서는 아직 위에 있다

    widget.bind("<Enter>", _on_enter, add="+")
    widget.bind("<Leave>", _on_leave, add="+")
    widget.bind("<ButtonPress-1>", _on_press, add="+")
    widget.bind("<ButtonRelease-1>", _on_release, add="+")
