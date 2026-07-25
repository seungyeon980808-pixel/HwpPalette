# -*- coding: utf-8 -*-
r"""버튼 손맛 — 호버 색 보간과 누름 피드백 (애플 디자인 A안, 2026-07-25).

무엇이 문제였나:
    기존 tk.Button 은 마우스를 올려도 아무 변화가 없다가 누르는 순간
    activebackground 로 **탁** 바뀌었다. 중간 단계가 없어서 '버벅인다'고
    느껴진다 — 애플 UI 의 부드러움은 대부분 이 **전환 구간**에서 나온다.

어떻게 하나:
    <Enter>/<Leave> 에서 배경색을 4단계로 보간한다 (30ms 간격 ≈ 120ms).
    진짜 이징 곡선까진 필요 없다 — 사람 눈은 이 정도면 '부드럽다'로 읽는다.
    누르면 즉시 진해진다 (전환 없이 — 누름은 **즉각** 반응해야 눌린 맛이 난다).

주의:
    팔레트 블럭은 탭 전환 때 파괴된다. 파괴된 위젯에 늦게 도착한 after 콜백이
    닿으면 TclError 가 나므로 winfo_exists() 로 매번 확인한다.
"""

import applog

STEPS = 8          # 보간 단계 수
INTERVAL_MS = 16   # 단계 간격 — 8단계 × 16ms ≈ 130ms, 60fps 리듬


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


# ── Tk 위젯에 붙이기 ───────────────────────────────────
def rebase(widget, base):
    """attach 로 붙인 위젯의 **기준색**을 바꾼다 (탭 활성/비활성 전환 등).

    다시 attach 하면 바인딩이 겹쳐 쌓이므로(add="+"), 기준색만 갈아끼운다.
    """
    setter = getattr(widget, "_fx_rebase", None)
    if setter:
        setter(base)


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
