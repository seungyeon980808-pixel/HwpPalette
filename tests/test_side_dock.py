# -*- coding: utf-8 -*-
r"""세로 띠 도킹에서 **되돌리면 안 되는 것들**을 검사로 못박는다 (2026-07-29).

배경: 2026-07-29 에 임베드(SetParent)를 실측으로 다시 검토했다
(`docs/EMBED_검토.md`). 붙이는 것 자체는 잘 됐지만 —

  · 부모 창(우리 판)을 파괴하면 한글이 **저장을 묻지도 않고** 죽었고
  · 우리 프로세스를 강제 종료하면 문서 창 없는 **유령 프로세스**가 남았다.

그래서 도킹은 창 둘을 남남으로 두고 자리만 맞추는 방식으로 갔다. 나중에
"한 창처럼 보이게 하려면 SetParent 가 깔끔한데"라는 유혹이 다시 올 것이라,
그 길로 되돌아가면 검사가 먼저 막도록 여기에 적어 둔다.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import srcpath                                     # noqa: E402


def _read(module):
    return srcpath.src(module).read_text(encoding="utf-8")


class SideDockRules(unittest.TestCase):

    def test_부모자식으로_묶지_않는다(self):
        """SetParent 금지 — 문서 소실 경로를 새로 만드는 일이다."""
        code = _read("side_dock")
        # 주석에서는 이야기해도 된다(왜 안 쓰는지를 적어 둔 곳이라). 실제
        # 호출만 막는다.
        calls = [ln for ln in code.splitlines()
                 if "SetParent(" in ln and not ln.strip().startswith("#")]
        self.assertEqual(calls, [], f"SetParent 를 부르고 있다: {calls}")

    def test_왜_안_쓰는지가_적혀_있다(self):
        """근거 없는 금지는 다음 사람이 그냥 지운다."""
        code = _read("side_dock")
        self.assertIn("EMBED_검토", code)

    def test_최대화_판정은_GetWindowPlacement(self):
        r"""`win32gui.IsZoomed` 는 이 pywin32 에 없다 (실측 2026-07-29).

        있는 줄 알고 쓰면 매 틱 AttributeError 가 나는데, tick 이 예외를
        삼키고 "ok" 를 돌려주므로 **띠가 조용히 안 따라올 뿐** 아무도 모른다.
        """
        code = _read("side_dock")
        self.assertNotIn("win32gui.IsZoomed(", code)   # 이야기는 되고 호출은 안 된다
        self.assertIn("SW_SHOWMAXIMIZED", code)


class StripRules(unittest.TestCase):

    def test_띠에는_닫기_단추가_없다(self):
        r"""✕ 금지 (사용자 결정 2026-07-29).

        도구 띠의 ✕ 는 '한글을 닫는다'로 읽힌다. 원고를 닫는 일을 도구가
        대신해서는 안 된다 — 떼기(◱)만 둔다.
        """
        code = _read("dock_strip")
        head = code.split("# ── 팔레트 고르개")[0]
        # 주석에서는 '왜 안 두는지'를 이야기한다 — 실제 화면에 그리는 줄만 본다
        drawn = [ln for ln in head.splitlines()
                 if not ln.strip().startswith("#")]
        self.assertNotIn("✕", "\n".join(drawn))
        self.assertIn("◱", "\n".join(drawn))


class AppRules(unittest.TestCase):

    def test_닫을_때_먼저_뗀다(self):
        r"""도킹 중에 창을 닫으면 띠 좌표가 저장돼 다음 실행이 엉킨다.

        _remember_pos 가 위치를 저장하기 **전에** _exit_dock 을 부르는지 본다.
        """
        code = _read("app")
        body = code.split("def _remember_pos")[1].split("\ndef ")[0]
        self.assertIn("_exit_dock()", body)
        self.assertLess(body.index("_exit_dock()"), body.index("set_window_pos"))

    def test_도킹은_문서를_먼저_고르게_한다(self):
        """새 문서 / 파일 불러오기 — 사용자 결정 2026-07-29."""
        code = _read("app")
        body = code.split("def fn_dock_hwp")[1].split("\ndef ")[0]
        self.assertIn("새 문서로 시작", body)
        self.assertIn("파일 불러오기", body)
        self.assertIn("askopenfilename", body)


if __name__ == "__main__":
    unittest.main()
