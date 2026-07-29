# -*- coding: utf-8 -*-
r"""'한글과 도킹'에서 **되돌리면 안 되는 것들**을 검사로 못박는다.

두 번의 결정이 여기 들어 있다.

1) 2026-07-29 — 임베드(SetParent) 실측 (`docs/EMBED_검토.md`)
   붙이는 것 자체는 됐지만, 부모 창을 파괴하면 한글이 **저장을 묻지도 않고**
   죽었고 강제 종료 때는 문서 창 없는 유령 프로세스가 남았다. 그래서 창 둘은
   남남으로 두고 자리만 맞춘다.

2) 2026-07-29 — 세로 띠를 버리고 **감싸기**로 (사용자 지적)
   "엄청 버벅거린다 · 짤리는 느낌이 심하다. 차라리 감싸고 있어서
   버벅거리더라도 따라오는 느낌이 낫겠다."
   우리 창을 한글 옆으로 매 틱 옮기는 방식은 창 둘이 서로를 쫓는 것이 그대로
   보였다. 지금은 우리 창이 가만히 있고 한글이 판 자리로 따라 들어온다.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import srcpath                                     # noqa: E402


def _read(module):
    return srcpath.src(module).read_text(encoding="utf-8")


def _fn_body(code, name):
    return code.split(f"def {name}")[1].split("\ndef ")[0]


class WrapRules(unittest.TestCase):

    def test_부모자식으로_묶지_않는다(self):
        """SetParent 금지 — 문서 소실 경로를 새로 만드는 일이다."""
        for module in ("app", "hwp_dock", "dock_bar"):
            calls = [ln for ln in _read(module).splitlines()
                     if "SetParent(" in ln and not ln.strip().startswith("#")]
            self.assertEqual(calls, [], f"{module} 이 SetParent 를 부른다: {calls}")

    def test_왜_안_쓰는지가_적혀_있다(self):
        """근거 없는 금지는 다음 사람이 그냥 지운다."""
        self.assertIn("EMBED_검토", _read("hwp_dock") + _read("app"))

    def test_자리_추적은_한_곳에서만(self):
        r"""도킹 중 한글 좌표를 미는 곳은 hwp_dock 하나뿐이어야 한다.

        app 쪽에서도 창을 밀면 두 곳이 같은 창을 두고 다투어 첫 판(세로 띠)의
        버벅임이 그대로 돌아온다. app 의 감시 타이머는 **살아 있는지만** 본다.
        """
        body = _fn_body(_read("app"), "_dock_watch")
        self.assertNotIn("SetWindowPos", body)
        self.assertIn("connected_hwnd", body)

    def test_감시는_느리게(self):
        """0.5초쯤 — 40ms 로 돌리면 그 자체가 잰크가 된다 (첫 판의 교훈)."""
        code = _read("app")
        line = [ln for ln in code.splitlines()
                if ln.startswith("_DOCK_ALIVE_MS")][0]
        self.assertGreaterEqual(int(line.split("=")[1].split("#")[0].strip()),
                                250)

    def test_추적은_이벤트_훅이고_완화가_없다(self):
        r"""사용자 지시 2026-07-30: "버벅임을 최소화하라."

        실측(spikes/dock_lag_spike.py): 폴링 30ms + 완화 45% 는 끌기 중
        평균 34px 어긋나고 정착에 592ms 걸렸다. 이벤트 훅 + 즉시 스냅은
        0px / 2.5ms. 그러므로:
          · 추적은 SetWinEventHook 이벤트로 깨어난다 (잠들어 기다리지 않는다)
          · 스냅에는 완화(_EASE)를 섞지 않는다 — 완화가 곧 지연이다
        _EASE 는 restore() 의 되돌아가는 활강에만 남는다.
        """
        code = _read("hwp_dock")
        self.assertIn("SetWinEventHook", code)
        # _fn_body 는 모듈 함수용이라(들여쓴 def 를 못 자름) 직접 자른다
        snap = code.split("def _snap")[1].split("    def ")[0]
        self.assertNotIn("_EASE", snap,
                         "스냅에 완화를 섞으면 '미끄러지듯'이라는 이름의 지연이 돌아온다")


class CropRules(unittest.TestCase):
    r"""제목줄 감추기 — 스타일이 아니라 **잘라내기**로 (실측 2026-07-30).

    WS_CAPTION 을 떼는 방식으로 먼저 만들었는데 화면을 그림으로 떠 보니 제목줄이
    그대로 있었다 (spikes/dock_fix_spike.py). 한글의 제목줄은 OS 창틀이 아니라
    한글이 자기 그림 영역에 직접 그리는 것이라, 창 영역(SetWindowRgn)으로
    잘라내야 사라진다.
    """

    def test_스타일이_아니라_영역으로_자른다(self):
        code = _read("hwp_dock")
        self.assertIn("SetWindowRgn", code)
        self.assertNotIn("~win32con.WS_CAPTION", code)

    def test_영역은_창보다_크게_잡는다(self):
        r"""DPI 미인식 프로세스라 SetWindowRgn 과 SetWindowPos 의 배율이 다르다.

        창 크기를 그대로 넣으면 오른쪽·아래가 잘려 회색 여백이 남았다(실측).
        넉넉히 잡으면 배율 계산이 필요 없다 — 잘라낼 것은 위 한 줄뿐이다.
        """
        code = _read("hwp_dock")
        self.assertIn("1 << 15", code)

    def test_뗄_때_잘라내기를_되돌린다(self):
        """잘린 채 되돌리면 밖에 나간 한글 창이 반쪽으로 남는다."""
        code = _read("hwp_dock")
        self.assertIn("def clear_crop", code)
        body = code.split("def restore")[1].split("\n    def ")[0]
        self.assertIn("clear_crop", body)

    def test_한글이_영역을_지우면_다시_씌운다(self):
        """최대화·배율 변경 때 한글이 자기 영역을 다시 씌운다 — 안전망이 있다."""
        self.assertIn("def _crop_ok", _read("hwp_dock"))


class ZOrderRules(unittest.TestCase):

    def test_우리_창이_앞에_올_때_한글을_올린다(self):
        r"""사용자 지적 2026-07-30: "원래 멀쩡했던 양식수정쪽 도킹이 엉망이다".

        z 를 매 틱 밀어 올리던 것을 그만둔 뒤(클릭 가로채기 때문), 우리 창을 한 번
        누르면 우리 창이 한글 위로 올라와 판이 회색으로 덮였다. 활성화될 때
        한 번만 다시 올려 준다 — 자리다툼 없이 순서가 유지된다.
        """
        code = _read("hwp_dock")
        self.assertIn('bind("<FocusIn>"', code)
        self.assertIn("raise_above", code)


class BarRules(unittest.TestCase):

    def test_이름을_자르지_않는다(self):
        r"""칩 이름 자르기 금지 (사용자 지적 2026-07-29: "짤리는 느낌").

        폭이 모자라면 **아랫줄로 넘긴다** — 그래서 reflow 가 있다.
        (2026-07-30 좌우 분할로 _Zone.reflow 로 옮겼다 — 이름만 바뀌었다)
        """
        code = _read("dock_bar")
        self.assertIn("def reflow", code)
        self.assertNotIn("…", _fn_body(code, "_chip"))

    def test_공통과_개인이_좌우로_갈린다(self):
        r"""사용자 지적 2026-07-30: "위계적으로 전혀 구분이 안 갑니다."

        가운데를 경계로 **왼쪽 공통 / 오른쪽 개인**이고 사이에 구분선이 선다.
        두 구역에 같은 무게(uniform)를 줘야 경계가 한가운데에 선다 — 무게를
        빼면 칩이 많은 쪽이 경계를 밀어 다시 뒤죽박죽이 된다.
        """
        code = _read("dock_bar")
        self.assertIn('uniform="zone"', code)
        self.assertIn("공통", code)
        body = _fn_body(code, "render")
        # 공통(메인 탭)과 개인(고른 탭)을 **각각** 담는다 — 한 줄로 잇지 않는다
        self.assertIn("_common.set_chips", body)
        self.assertIn("_personal.set_chips", body)

    def test_창을_다루는_단추는_도구줄에_없다(self):
        r"""떼기·방식은 물감이 아니라 **창을 다루는 것** (사용자 지적 2026-07-30).

        "도킹 관련 버튼들은 개인 팔레트 쪽 위계가 아니라 설정·도움말 쪽 위계에
        있어야 합니다." → app.py 의 misc_row 가 들고 있다.
        ✕(한글 닫기)는 여전히 어디에도 두지 않는다 (사용자 결정 2026-07-29):
        원고를 닫는 일을 도구가 대신해서는 안 된다.
        """
        joined = "\n".join(ln for ln in _read("dock_bar").splitlines()
                           if not ln.strip().startswith("#"))
        self.assertNotIn("✕", joined)
        self.assertNotIn("◱", joined)          # 떼기는 위 도구줄로 갔다
        app_code = _read("app")
        self.assertIn("◱", app_code)
        self.assertIn("def _show_dock_buttons", app_code)

    def test_기본_두께는_세_줄(self):
        """사용자 결정 2026-07-30: "팔레트 기본 두께는 3줄짜리가 되어야 합니다"."""
        line = [ln for ln in _read("dock_bar").splitlines()
                if ln.startswith("MIN_ROWS")][0]
        self.assertEqual(int(line.split("=")[1].split("#")[0].strip()), 3)

    def test_고르개는_펼친다_순환하지_않는다(self):
        r"""사용자 지적 2026-07-30: "드롭다운이 안 되고 클릭할 때마다 바뀐다".

        ▾ 를 달아 놓고 순환시키는 것은 그 표시와 어긋난다 — 팝오버로 펼친다.
        """
        code = _read("dock_bar")
        self.assertNotIn("def _next_tab", code)
        self.assertIn("on_open_palettes", code)
        self.assertIn("def _dock_pal_menu", _read("app"))


class AppRules(unittest.TestCase):

    def test_위_도구줄은_남긴다(self):
        """사용자 결정 2026-07-29: '버튼은 싹 다 위쪽으로'."""
        body = _fn_body(_read("app"), "_enter_dock")
        self.assertIn("is not misc_row", body)

    def test_닫을_때_먼저_뗀다(self):
        """도킹 중 좌표를 저장하면 다음 실행에서 창이 엉킨다."""
        body = _fn_body(_read("app"), "_remember_pos")
        self.assertIn("_exit_dock()", body)
        self.assertLess(body.index("_exit_dock()"), body.index("set_window_pos"))

    def test_도킹은_문서를_먼저_고르게_한다(self):
        """새 문서 / 파일 불러오기 — 사용자 결정 2026-07-29."""
        body = _fn_body(_read("app"), "fn_dock_hwp")
        self.assertIn("새 문서로 시작", body)
        self.assertIn("파일 불러오기", body)
        self.assertIn("askopenfilename", body)


if __name__ == "__main__":
    unittest.main()
