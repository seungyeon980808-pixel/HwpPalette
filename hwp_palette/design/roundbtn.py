# -*- coding: utf-8 -*-
r"""둥근 모서리 버튼 (애플 디자인 A안, 2026-07-25).

tk.Button 은 모서리를 못 깎는다 — 곡률을 내려면 Canvas 에 둥근 사각형을
직접 그리는 수밖에 없다. 이 부품이 그 일을 하고, 겉으로는 버튼처럼 군다:

    RoundButton(parent, text="사진", command=..., bg="#eef4ff", radius=8)

들어 있는 것:
  · 곡률       — smooth polygon (모서리 12점 + smooth=True. Tk 의 표준 기법)
  · 호버 보간  — ui_fx 와 같은 4단계 색 전환
  · 누름 피드백 — 색 진해짐 + **글자 1px 침하** (tk.Button 으론 못 하던 것)
  · 키보드     — Tab 초점(파란 테두리) + Enter/Space 실행. 기존 블럭 버튼의
                 highlightcolor=ACCENT 초점 표시를 잃지 않기 위함
  · 줄바꿈     — 이름의 \n 그대로 (블럭 이름 줄바꿈 기능과 이어진다)

명령은 <ButtonRelease> 에서, 커서가 버튼 위일 때만 실행한다 — 실수로 누르고
밖으로 빼서 취소하는 표준 버튼 동작 그대로다.
"""

import tkinter as tk

from hwp_palette.design import ui_fx

# 아이콘 줄과 이름 줄 사이 틈(px). 0 이면 두 줄이 붙어 한 글자처럼 뭉치고,
# 3 이상이면 좁은 칸(42px)에서 아래 이름이 잘린다.
ICON_GAP = 1

# ── 글꼴 재기 캐시 (2026-07-31, 성능) ───────────────────
# fit()·_text_metrics() 가 부를 때마다 tkfont.Font 를 새로 만들었다 —
# Font 생성은 Tcl 에 이름 있는 폰트를 등록하는 일이라 호출당 ~1ms 씩 들었고
# (실측: fit 1.15ms), 블럭 수십 개를 그릴 때 그대로 쌓였다. 같은 스펙이면
# 같은 Font 를 돌려 쓴다.
#
# 열쇠는 스펙 문자열뿐이라 Tk 루트가 여럿일 때(테스트가 루트를 만들었다
# 부수는 경우) 죽은 루트에 묶인 Font 가 남을 수 있다. 그래서 쓰기 전에
# 싼 호출 한 번으로 살아 있는지 확인하고, 죽었으면 통째로 버리고 다시 만든다.
_font_cache = {}


def _shared_font(spec):
    """spec(글꼴 튜플·문자열·None) → 공유 tkfont.Font."""
    import tkinter.font as tkfont
    key = str(spec)
    f = _font_cache.get(key)
    if f is not None:
        try:
            f.metrics("linespace")      # 루트 생존 확인 — Font 생성보다 훨씬 싸다
            return f
        except tk.TclError:
            _font_cache.clear()         # 그 루트의 Font 는 전부 죽었다
    f = tkfont.Font(font=spec) if spec else tkfont.Font()
    _font_cache[key] = f
    return f


class RoundButton(tk.Canvas):

    def __init__(self, parent, text="", command=None, bg="#ffffff",
                 fg="#1d1d1f", radius=8, font=None, outline="",
                 focus_color="#0071e3", zone_bg=None, justify="center",
                 trailing=None, pad_in=10, align="center", image=None,
                 icon=None, icon_font=None, icon_fg=None, icon_image=None):
        # zone_bg = 모서리 '바깥'에 비칠 색. 안 주면 부모 배경을 따른다.
        super().__init__(parent, highlightthickness=0, bd=0,
                         bg=zone_bg or parent.cget("bg"),
                         cursor="hand2", takefocus=1)
        self.command = command
        self._text = text
        self._font = font
        self._fg = fg
        self._radius = radius
        self._outline = outline
        self._focus_color = focus_color
        self._justify = justify
        # trailing = 오른쪽 끝에 **따로** 그리는 짧은 기호 (▾ 같은 것).
        #
        # 왜 글자에 붙여 쓰지 않나 (사용자 지적 2026-07-28: "드롭다운이 좌측으로
        # 정렬되고 표시가 오른쪽 끝에 있어야 한다"): "수능  ▾" 처럼 한 덩어리로
        # 가운데 정렬하면, 이름 길이에 따라 ▾ 가 좌우로 떠다닌다. 폭을 가장 긴
        # 이름으로 고정해 둔 버튼에서는 짧은 이름일수록 ▾ 가 안쪽으로 들어와
        # '오른쪽 끝의 펼침 표시'라는 관습이 깨진다. 이름은 왼쪽 고정,
        # ▾ 는 오른쪽 고정 — 둘을 따로 그려야 성립한다.
        self._trailing = trailing
        self._pad_in = pad_in
        # align="left" — 글자를 칸 왼쪽에 붙인다 (사용자 결정 2026-07-28).
        #
        # 팔레트 블럭 이름은 길이가 제각각인데(변환·글씨체·합답형2사진3선지)
        # 가운데 정렬이면 이름마다 글머리가 다른 자리에서 시작해, 블럭이 격자로
        # 줄 맞춰 서 있어도 **글자는 줄이 안 맞는다.** 왼쪽에 붙이면 세로로
        # 글머리가 한 줄에 서고, 두 줄 이름도 첫 글자가 어긋나지 않는다.
        self._align = align
        # image 와 icon 은 **다른 것**이다 (2026-07-30 합칠 때 정리).
        #   image = PNG 그림 하나를 칸 가운데 (툴바의 ⚙·↺·… — 글자가 없다)
        #   icon  = 이름 **위**에 한 줄로 그리는 기호 글자 (블럭 카드)
        # 한 버튼이 둘을 함께 쓰는 자리는 없다.
        #
        # image 참조를 여기 붙들어 둔다: Tk 는 PhotoImage 를 안 붙들면 가비지
        # 컬렉션돼 그림이 빈칸으로 나온다.
        self._image = image
        # icon = 이름 **위에** 한 줄로 그리는 기호 (H안, 2026-07-29).
        #
        # trailing 과 다른 자리다: trailing 은 같은 줄의 오른쪽 끝(▾ 같은 것),
        # icon 은 윗줄 가운데다. 종류를 배경색 대신 아이콘으로 말하기로 하면서
        # 생겼다 — 배경이 전부 흰 카드라 색으로는 더 이상 구별이 안 된다.
        #
        # 아이콘이 있으면 글자 자리는 **자동으로 가운데**가 된다: 아이콘만
        # 가운데이고 이름은 왼쪽에 붙으면 둘이 한 덩어리로 안 읽히고 계단처럼
        # 어긋나 보인다.
        self._icon = icon
        # icon_image = 이름 위 한 줄에 **그림**을 얹는다(사진 등, 2026-07-30) —
        # icon(글자 기호) 과 같은 자리를 쓰되 폰트 대신 실제 아이콘 PNG 다.
        # 글자로는 그릴 수 없는 그림(액자+산+해 등)에 쓴다. icon 과 동시에
        # 주지 않는다 — 자리가 하나뿐이다.
        self._icon_image = icon_image
        self._icon_font = icon_font or font
        # 아이콘은 이름보다 **흐리게** 그린다. 같은 색이면 아이콘이 이름과 같은
        # 무게로 읽혀 둘이 서로 경쟁하고, 격자로 늘어놓으면 기호가 먼저 눈에
        # 들어와 정작 무엇을 누르는지 늦게 안다. 아이콘은 '거들 뿐'이다.
        self._icon_fg = icon_fg or fg
        self._base = bg
        self._hover = ui_fx.darken(bg, ui_fx.HOVER_FACTOR)
        self._press = ui_fx.darken(bg, ui_fx.PRESS_FACTOR)
        self._fill = bg
        self._job = None          # 진행 중인 보간 after id
        self._focused = False
        self._pressed = False
        self._metrics = None      # 글꼴 높이 캐시 (_text_metrics)
        self._drawn_size = None   # 마지막으로 그린 (폭, 높이) — _on_configure 가 본다
        self._ribbon = None       # 오른쪽 세로 띠 (text, bg, fg) — 037

        self.bind("<Configure>", self._on_configure)
        self.bind("<Enter>", lambda e: self._to(self._hover))
        self.bind("<Leave>", lambda e: self._to(self._base))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<FocusIn>", lambda e: self._set_focus(True))
        self.bind("<FocusOut>", lambda e: self._set_focus(False))
        self.bind("<Return>", lambda e: self._invoke())
        self.bind("<space>", lambda e: self._invoke())

    # ── 크기 ────────────────────────────────────────
    def fit(self, pad_x=12, pad_y=6, min_w=0):
        r"""글자에 맞춰 캔버스 크기를 정한다.

        Canvas 는 기본 크기(378×265)가 있어 그냥 두면 버튼이 터무니없이 커진다.
        tk.Button 을 바꿔 끼울 때마다 크기를 손으로 재는 대신 여기서 잰다.
        줄바꿈이 있으면 가장 긴 줄을 재고 줄 수만큼 높이를 잡는다.
        """
        try:
            f = _shared_font(self._font)    # 매번 새 Font 를 만들지 않는다
            lines = (self._text or " ").split("\n")
            w = max((f.measure(ln) for ln in lines), default=0) + pad_x * 2
            if self._trailing:      # 오른쪽 기호가 글자를 침범하지 않게
                w += f.measure(self._trailing) + pad_x
            h = f.metrics("linespace") * len(lines) + pad_y * 2
            if self._icon or self._icon_image:  # 아이콘 줄만큼 키를 더 준다
                icon_h, _ = self._text_metrics()
                h += icon_h + ICON_GAP
            self.config(width=max(w, min_w), height=h)
        except Exception:
            self.config(width=max(80, min_w), height=28)
        return self

    # ── 아이콘 세로 배치 ────────────────────────────
    def _text_metrics(self):
        """(아이콘 줄 높이, 이름 줄 높이 합).

        글꼴 잴 때마다 Font 객체를 새로 만들면 누를 때마다 그 값이 다시 계산된다
        — 값이 바뀌는 일이 거의 없으므로(글꼴·줄 수가 그대로면 같다) 한 번 재서
        들고 있는다. set_text·retint 가 무효로 만든다.
        """
        # 열쇠에 PhotoImage **객체**를 넣지 않는다 (2026-07-31, 성능): 객체
        # 정체성이 열쇠에 섞이면 그림이 같아도 캐시가 어긋나 매번 다시 쟀다.
        # 그림의 유무만 적는다 — 그림 높이는 버튼이 사는 동안 안 바뀐다
        # (아이콘 그림을 갈아끼우는 경로가 없고, set_text 는 _metrics 를 비운다).
        key = (str(self._font), str(self._icon_font), self._icon,
               self._icon_image is not None, (self._text or "").count("\n"))
        if self._metrics and self._metrics[0] == key:
            return self._metrics[1]
        try:
            lf = _shared_font(self._font)
            label_h = (lf.metrics("linespace")
                       * len((self._text or " ").split("\n")))
            icon_h = 0
            if self._icon_image is not None:
                icon_h = self._icon_image.height()
            elif self._icon:
                icon_h = _shared_font(self._icon_font).metrics("linespace")
        except Exception:
            return 0, 0
        self._metrics = (key, (icon_h, label_h))
        return icon_h, label_h

    def _stack_y(self, h):
        """(이름 줄 중심 y, 아이콘 중심 y).

        아이콘과 이름을 **한 덩어리로 묶어** 그 덩어리를 칸 한가운데에 놓는다.
        각각을 따로 가운데 맞추면(아이콘 1/3, 이름 2/3 식) 이름이 한 줄일 때와
        두 줄일 때 덩어리 위치가 달라져, 격자로 늘어놓았을 때 아이콘 줄이 들쭉
        날쭉해진다.
        """
        if not self._icon and self._icon_image is None:
            return h // 2, 0
        icon_h, label_h = self._text_metrics()
        if not icon_h or not label_h:
            return h // 2, h // 2
        total = icon_h + ICON_GAP + label_h
        top = (h - total) / 2.0
        return (int(top + icon_h + ICON_GAP + label_h / 2.0),
                int(top + icon_h / 2.0))

    # ── 그리기 ──────────────────────────────────────
    def _on_configure(self, _e):
        """<Configure> — 크기가 그대로면(자리만 옮긴 이벤트) 다시 그리지 않는다.

        격자 재배치 때 버튼마다 자리 이동 Configure 가 쏟아지는데, 그림 좌표는
        캔버스 안 상대값이라 자리만 바뀌면 그릴 것이 없다 (2026-07-31, 성능).
        누름·초점처럼 **내용**이 바뀌는 갱신은 _redraw 를 직접 부르므로 안 걸린다.
        """
        if (self.winfo_width(), self.winfo_height()) == self._drawn_size:
            return
        self._redraw()

    @staticmethod
    def _round_points(x1, y1, x2, y2, r):
        """둥근 사각형의 꼭짓점 목록 — smooth=True 로 그리면 모서리가 깎인다."""
        return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
                x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
                x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]

    def _redraw(self):
        r"""도형을 **한 번만 만들고 그다음엔 값만 고친다**.

        예전에는 매번 delete("all") 후 다시 그렸는데, 지운 순간과 다시 그린
        순간 사이에 빈 캔버스가 한 프레임 비쳐 **깜빡였다** — 창 크기가 바뀌거나
        누를 때마다 오류처럼 번쩍이던 원인이다 (2026-07-25).
        지금은 coords/itemconfig 로 갱신하므로 빈 프레임이 없다.
        """
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            return
        self._drawn_size = (w, h)           # _on_configure 의 건너뛰기 기준
        r = min(self._radius, w // 2, h // 2)
        pts = self._round_points(1, 1, w - 2, h - 2, r)
        edge = (self._focus_color if self._focused else self._outline)
        dy = 1 if self._pressed else 0      # 누르면 글자가 1px 가라앉는다

        # 글자 자리 — trailing 이 있거나 align="left" 면 왼쪽 붙임.
        # 단 아이콘이 있으면 무조건 가운데다 (아이콘과 이름이 한 덩어리로 서야 한다).
        if self._icon or self._icon_image is not None:
            lx, lanchor = w // 2, "center"
        elif self._trailing or self._align == "left":
            lx, lanchor = self._pad_in, "w"
        else:
            lx, lanchor = w // 2, "center"
        ly, iy = self._stack_y(h)

        if not self.find_withtag("body"):
            self.create_polygon(pts, smooth=True, fill=self._fill,
                                outline=edge or "",
                                width=2 if self._focused else 1, tags="body")
            if self._image is not None:
                # 그림 버튼은 글자가 없다 — 여기서 끝낸다 (태그도 따로 둔다:
                # 아래 icon 은 기호 '글자'라 같은 이름을 쓰면 서로 지운다)
                self.create_image(w // 2, h // 2 + dy, image=self._image,
                                  tags="img")
                return
            if self._icon_image is not None:
                # 사진처럼 글자로 못 그리는 아이콘 — 실제 PNG (2026-07-30).
                # "icon" 태그를 그대로 쓰면 텍스트 아이콘과 겹쳐 서로 지우므로
                # "iconimg" 로 따로 둔다.
                self.create_image(w // 2, iy + dy, image=self._icon_image,
                                  tags="iconimg")
            elif self._icon:
                self.create_text(w // 2, iy + dy, text=self._icon,
                                 anchor="center", font=self._icon_font,
                                 fill=self._icon_fg, tags="icon")
            self.create_text(lx, ly + dy, text=self._text, anchor=lanchor,
                             font=self._font, fill=self._fg,
                             justify=self._justify, tags="label")
            if self._trailing:
                self.create_text(w - self._pad_in, h // 2 + dy,
                                 text=self._trailing, anchor="e",
                                 font=self._font, fill=self._fg, tags="trail")
            self._draw_ribbon(w, h)
            return

        self.coords("body", *pts)
        self.itemconfig("body", fill=self._fill, outline=edge or "",
                        width=2 if self._focused else 1)
        if self._image is not None:
            self.coords("img", w // 2, h // 2 + dy)
            return
        if self._icon_image is not None and self.find_withtag("iconimg"):
            self.coords("iconimg", w // 2, iy + dy)
            self.itemconfig("iconimg", image=self._icon_image)
        elif self._icon and self.find_withtag("icon"):
            self.coords("icon", w // 2, iy + dy)
            self.itemconfig("icon", text=self._icon, fill=self._icon_fg,
                            font=self._icon_font)
        self.coords("label", lx, ly + dy)
        self.itemconfig("label", text=self._text, fill=self._fg,
                        font=self._font, anchor=lanchor)
        self._draw_ribbon(w, h)
        if self._trailing:
            self.coords("trail", w - self._pad_in, h // 2 + dy)
            self.itemconfig("trail", text=self._trailing, fill=self._fg,
                            font=self._font)

    # ── 색 전환 (ui_fx 와 같은 리듬) ────────────────
    def _cancel(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _to(self, color):
        """지금 색에서 color 로 이징 곡선을 따라 옮긴다."""
        self._cancel()
        if self._fill == color:
            return                          # 이미 그 색 — 헛돌지 않는다
        self._step(self._fill, color, 1)

    def _step(self, start, color, step):
        # 시작색을 붙잡아 둔다 — 매 단계 '현재 색'에서 다시 보간하면 목표에
        # 점점 느리게 다가가기만 해 끝이 흐지부지되고 색이 튄다 (ui_fx 참고).
        self._job = None
        try:
            if not self.winfo_exists():
                return
            self._fill = ui_fx.lerp(start, color,
                                    ui_fx.ease_out(step / ui_fx.STEPS))
            self.itemconfig("body", fill=self._fill)
            if step < ui_fx.STEPS:
                self._job = self.after(
                    ui_fx.INTERVAL_MS,
                    lambda: self._step(start, color, step + 1))
        except Exception:
            pass                            # 파괴 직전 경합 — 조용히 끝낸다

    # ── 동작 ────────────────────────────────────────
    def _on_press(self, _e):
        self._cancel()
        self._pressed = True
        self._fill = self._press            # 누름은 즉시 — 눌린 맛
        self._redraw()
        self._flush()

    def _on_release(self, e):
        self._pressed = False
        inside = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        self._fill = self._hover if inside else self._base
        self._redraw()
        self._flush()
        if inside:
            self._invoke()

    def _flush(self):
        r"""바뀐 색을 **지금 화면에 내보낸다**.

        Tk 는 itemconfig 로 바뀐 그림을 곧바로 그리지 않고 '한가할 때' 그린다.
        그런데 버튼 명령(한글 COM 조작)은 눌린 직후 몇 초씩 붙잡고 있어서,
        그 사이 한가한 순간이 오지 않는다 — 눌러도 아무 반응이 없다가 일이
        다 끝난 뒤에야 화면이 바뀌었다 (사용자 지적 2026-07-26).
        명령을 부르기 전에 한 번 밀어내면 '눌렀다'가 즉시 보인다.
        """
        try:
            self.update_idletasks()
        except Exception:
            pass                            # 파괴 직전 경합 — 조용히 넘어간다

    def _invoke(self):
        if self.command:
            self.command()

    def _set_focus(self, on):
        self._focused = on
        self._redraw()

    # ── 겉모습 갱신 (탭 활성 전환 등) ───────────────
    def set_text(self, text, pad_x=12, pad_y=6):
        """글자를 바꾸고 **폭도 다시 잰다** — 팔레트 고르개처럼 이름이 바뀌는 버튼용.

        itemconfig 만 하면 캔버스 크기는 예전 글자에 맞춰져 있어, 이름이 길어지면
        잘리고 짧아지면 오른쪽이 텅 빈다.
        """
        self._text = text
        self._metrics = None      # 줄 수가 달라졌을 수 있다
        self.fit(pad_x=pad_x, pad_y=pad_y)
        self._redraw()

    def retint(self, bg=None, fg=None, icon_fg=None):
        if bg:
            self._base = bg
            self._hover = ui_fx.darken(bg, ui_fx.HOVER_FACTOR)
            self._press = ui_fx.darken(bg, ui_fx.PRESS_FACTOR)
            self._fill = bg
        if fg:
            self._fg = fg
        if icon_fg:
            self._icon_fg = icon_fg
        self._redraw()

    # ── 오른쪽 세로 띠 (2026-08-01, 피드백 037) ─────────────
    def set_ribbon(self, text, bg, fg):
        r"""칸 오른쪽에 세로 띠를 단다 (겹친 칸의 개수 · 꾸러미의 MIX).

        **칸 높이·폭은 불변**(2026-07-31 결정) — 띠는 칸 안쪽으로만 들어간다.
        None 을 주면 뗀다. 캔버스라 place() 로 라벨을 못 얹으므로 도형으로
        직접 그린다 — 세 화면이 같은 물감을 같은 표시로 보이게 하는 통로다.
        """
        self._ribbon = (str(text), bg, fg) if text else None
        if self._drawn_size:
            self._draw_ribbon(*self._drawn_size)

    def _draw_ribbon(self, w, h):
        if not self._ribbon:
            self.delete("ribbon", "ribbontxt")
            return
        text, bg, fg = self._ribbon
        f = self._font or ("TkDefaultFont", 9)
        if isinstance(f, (list, tuple)) and len(f) > 1:
            size = max(6, int(f[1]) - 2)
        else:
            size = 7
        rw = size + 6                       # 글자 한 자 폭 + 숨쉴 틈
        r = min(self._radius, rw // 2, (h - 2) // 2)
        pts = self._round_points(w - 1 - rw, 1, w - 2, h - 2, r)
        vtext = "\n".join(text)             # 세로쓰기
        if not self.find_withtag("ribbon"):
            self.create_polygon(pts, smooth=True, fill=bg, outline="",
                                tags="ribbon")
            self.create_text(w - 1 - rw // 2, h // 2, text=vtext,
                             font=(f[0], size, "bold"), fill=fg,
                             justify="center", tags="ribbontxt")
        else:
            self.coords("ribbon", *pts)
            self.itemconfig("ribbon", fill=bg)
            self.coords("ribbontxt", w - 1 - rw // 2, h // 2)
            self.itemconfig("ribbontxt", text=vtext, fill=fg,
                            font=(f[0], size, "bold"))
        # 띠가 이름을 덮지 않게 늘 맨 위로, 그리고 클릭은 버튼이 받게
        self.tag_raise("ribbon")
        self.tag_raise("ribbontxt")


class RoundTile(tk.Canvas):
    r"""모서리가 둥근 **판때기** — 버튼이 아니라 무언가를 담는 타일용.

    왜 필요한가 (사용자 지적 2026-07-28: "메인 위젯의 곡률과 팔레트 설정
    위젯의 곡률이 다릅니다"): 메인 창의 블럭은 RoundButton 이라 모서리가
    깎여 있는데, 팔레트 설정의 격자 블럭과 창고 카드는 tk.Frame 이라
    직각이었다. 같은 물건(블럭·물감)이 화면마다 다른 모양이면 **다른 물건으로
    읽힌다.** 곡률은 메인 쪽(RADIUS["ctl"])으로 맞춘다.

    핵심 설계: **configure 를 가로챈다.**
        기존 코드는 타일 테두리를 `highlightbackground`·`highlightthickness`
        로 바꾼다(선택 표시·놓기 강조·창고 색칠). 그 호출들을 한 줄도 안
        고치고 그대로 쓰려고, 여기서 그 두 옵션을 받아 **폴리곤 외곽선**으로
        옮긴다. Canvas 는 원래 그 옵션들을 다른 뜻으로 갖고 있으므로
        가로채지 않으면 둘레에 엉뚱한 네모 테두리가 하나 더 생긴다.
    """

    def __init__(self, parent, bg, radius=None, zone_bg=None, **kw):
        self._tile_bg = bg
        self._radius = 8 if radius is None else radius
        # 만들 때 준 테두리 옵션도 configure 와 **같은 규칙**으로 받는다 —
        # 안 그러면 Canvas 가 자기 뜻(둘레의 초점 테두리)으로 해석해 충돌한다.
        self._edge = kw.pop("highlightbackground", "")
        self._edge_w = max(1, int(kw.pop("highlightthickness", 1)))
        kw.pop("highlightcolor", None)
        super().__init__(parent, highlightthickness=0, bd=0,
                         bg=zone_bg or parent.cget("bg"), **kw)
        self._drawn_size = None
        self.bind("<Configure>", self._on_configure, add="+")

    def _on_configure(self, _e):
        # 크기가 그대로면 자리만 옮긴 이벤트 — 그릴 것이 없다 (RoundButton 과
        # 같은 이유). 색 갱신(configure)은 _redraw 를 직접 부르므로 안 걸린다.
        if (self.winfo_width(), self.winfo_height()) == self._drawn_size:
            return
        self._redraw()

    def _redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            return
        self._drawn_size = (w, h)
        r = min(self._radius, w // 2, h // 2)
        pts = RoundButton._round_points(1, 1, w - 2, h - 2, r)
        if not self.find_withtag("body"):
            self.create_polygon(pts, smooth=True, fill=self._tile_bg,
                                outline=self._edge or "", width=self._edge_w,
                                tags="body")
            self.tag_lower("body")      # 안에 놓인 자식·글자보다 뒤로
            return
        self.coords("body", *pts)
        self.itemconfig("body", fill=self._tile_bg, outline=self._edge or "",
                        width=self._edge_w)

    def configure(self, cnf=None, **kw):
        opts = dict(cnf or {})
        opts.update(kw)
        redraw = False
        if "highlightbackground" in opts:
            self._edge = opts.pop("highlightbackground")
            redraw = True
        opts.pop("highlightcolor", None)        # 초점 테두리는 쓰지 않는다
        if "highlightthickness" in opts:
            self._edge_w = max(1, int(opts.pop("highlightthickness")))
            redraw = True
        for key in ("bg", "background"):
            if key in opts:
                self._tile_bg = opts.pop(key)
                redraw = True
        if opts:
            super().configure(**opts)
        if redraw:
            self._redraw()

    config = configure

    def cget(self, key):
        if key in ("bg", "background"):
            return self._tile_bg
        return super().cget(key)
