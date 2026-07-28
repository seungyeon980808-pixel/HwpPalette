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


class RoundButton(tk.Canvas):

    def __init__(self, parent, text="", command=None, bg="#ffffff",
                 fg="#1d1d1f", radius=8, font=None, outline="",
                 focus_color="#0071e3", zone_bg=None, justify="center",
                 trailing=None, pad_in=10, align="center"):
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
        self._base = bg
        self._hover = ui_fx.darken(bg, ui_fx.HOVER_FACTOR)
        self._press = ui_fx.darken(bg, ui_fx.PRESS_FACTOR)
        self._fill = bg
        self._job = None          # 진행 중인 보간 after id
        self._focused = False
        self._pressed = False

        self.bind("<Configure>", lambda e: self._redraw())
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
        import tkinter.font as tkfont
        try:
            f = tkfont.Font(font=self._font) if self._font else tkfont.Font()
            lines = (self._text or " ").split("\n")
            w = max((f.measure(ln) for ln in lines), default=0) + pad_x * 2
            if self._trailing:      # 오른쪽 기호가 글자를 침범하지 않게
                w += f.measure(self._trailing) + pad_x
            h = f.metrics("linespace") * len(lines) + pad_y * 2
            self.config(width=max(w, min_w), height=h)
        except Exception:
            self.config(width=max(80, min_w), height=28)
        return self

    # ── 그리기 ──────────────────────────────────────
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
        r = min(self._radius, w // 2, h // 2)
        pts = self._round_points(1, 1, w - 2, h - 2, r)
        edge = (self._focus_color if self._focused else self._outline)
        dy = 1 if self._pressed else 0      # 누르면 글자가 1px 가라앉는다

        # 글자 자리 — trailing 이 있거나 align="left" 면 왼쪽 붙임
        if self._trailing or self._align == "left":
            lx, lanchor = self._pad_in, "w"
        else:
            lx, lanchor = w // 2, "center"

        if not self.find_withtag("body"):
            self.create_polygon(pts, smooth=True, fill=self._fill,
                                outline=edge or "",
                                width=2 if self._focused else 1, tags="body")
            self.create_text(lx, h // 2 + dy, text=self._text, anchor=lanchor,
                             font=self._font, fill=self._fg,
                             justify=self._justify, tags="label")
            if self._trailing:
                self.create_text(w - self._pad_in, h // 2 + dy,
                                 text=self._trailing, anchor="e",
                                 font=self._font, fill=self._fg, tags="trail")
            return

        self.coords("body", *pts)
        self.itemconfig("body", fill=self._fill, outline=edge or "",
                        width=2 if self._focused else 1)
        self.coords("label", lx, h // 2 + dy)
        self.itemconfig("label", text=self._text, fill=self._fg,
                        font=self._font, anchor=lanchor)
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
        self.fit(pad_x=pad_x, pad_y=pad_y)
        self._redraw()

    def retint(self, bg=None, fg=None):
        if bg:
            self._base = bg
            self._hover = ui_fx.darken(bg, ui_fx.HOVER_FACTOR)
            self._press = ui_fx.darken(bg, ui_fx.PRESS_FACTOR)
            self._fill = bg
        if fg:
            self._fg = fg
        self._redraw()


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
        self.bind("<Configure>", lambda e: self._redraw(), add="+")

    def _redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            return
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
