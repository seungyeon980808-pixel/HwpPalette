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


class BarRules(unittest.TestCase):

    def test_이름을_자르지_않는다(self):
        r"""칩 이름 자르기 금지 (사용자 지적 2026-07-29: "짤리는 느낌").

        폭이 모자라면 **아랫줄로 넘긴다** — 그래서 _reflow 가 있다.
        """
        code = _read("dock_bar")
        self.assertIn("def _reflow", code)
        self.assertNotIn("…", _fn_body(code, "_chip"))

    def test_도구줄에는_닫기_단추가_없다(self):
        r"""✕ 금지 (사용자 결정 2026-07-29).

        도구줄의 ✕ 는 '한글을 닫는다'로 읽힌다. 원고를 닫는 일을 도구가
        대신해서는 안 된다 — 떼기(◱)만 둔다.
        """
        drawn = [ln for ln in _read("dock_bar").splitlines()
                 if not ln.strip().startswith("#")]
        self.assertNotIn("✕", "\n".join(drawn))
        self.assertIn("◱", "\n".join(drawn))


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
