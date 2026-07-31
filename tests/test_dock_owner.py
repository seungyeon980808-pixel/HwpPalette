# -*- coding: utf-8 -*-
r"""도킹의 **주인은 하나** — 소유권 대장과 창 순서 규칙 (2026-08-01).

피드백 031·032·035·036·038-b 한 라운드에서 못박은 것들이다.

무엇이 문제였나: `Dock` 인스턴스가 둘(메인 도킹 · 양식 수정) 살아 있을 수
있었고, 둘이 같은 한글 hwnd 를 각자 제 판 자리로 밀어 한글이 두 자리를
왕복했다 — 사용자가 말한 "두 상황을 왕복하면서 버벅거리는" 그것이다.
겹치면 **더 구체적인 작업이 이긴다**: 양식 수정 > 메인 도킹.

여기 있는 검사들은 되돌리면 그 버그가 그대로 돌아오는 것들만 담는다.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import srcpath                                     # noqa: E402

from hwp_palette.hwp import hwp_dock               # noqa: E402


def _read(module):
    return srcpath.src(module).read_text(encoding="utf-8")


class _FakeDock:
    """대장이 시키는 일만 받아 적는 가짜 Dock."""

    def __init__(self, hwnd=1):
        self.hwnd = hwnd
        self.log = []

    def stop_follow(self):
        self.log.append("pause")

    def start(self):
        self.log.append("resume")
        return True

    def keep_order(self, force=False):
        self.log.append(f"order:{force}")


class _AliveWin32:
    """모든 창이 살아 있다고 답하는 win32gui 대역."""

    @staticmethod
    def IsWindow(hwnd):
        return bool(hwnd)


class OwnerLedger(unittest.TestCase):

    def setUp(self):
        hwp_dock._reset_owners_for_test()
        p = mock.patch.object(hwp_dock, "win32gui", _AliveWin32)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(hwp_dock._reset_owners_for_test)

    def test_편집이_메인보다_세다(self):
        """양식 수정이 오면 메인 도킹은 잠든다 — 창 복원은 하지 않는다."""
        main, edit = _FakeDock(), _FakeDock()
        self.assertTrue(hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN))
        self.assertTrue(hwp_dock.claim(edit, hwp_dock.PRIORITY_EDIT))
        self.assertEqual(main.log, ["pause"])
        self.assertIs(hwp_dock.owner(), edit)

    def test_편집이_끝나면_메인이_저절로_돌아온다(self):
        r"""사용자가 기대하는 것: 저장하면 메인 도킹이 알아서 제자리로.

        스택이라 이전 주인을 기억한다 — 호출부가 서로를 몰라도 된다.
        """
        main, edit = _FakeDock(), _FakeDock()
        hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN)
        hwp_dock.claim(edit, hwp_dock.PRIORITY_EDIT)
        hwp_dock.release(edit)
        self.assertEqual(main.log, ["pause", "resume"])
        self.assertIs(hwp_dock.owner(), main)

    def test_되살릴_때_호출부의_준비를_먼저_부른다(self):
        """한글이 그새 숨겨졌을 수 있다 — ensure_visible 이 start 보다 먼저."""
        order = []
        main = _FakeDock()
        main.start = lambda: order.append("start") or True
        hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN,
                       on_resume=lambda: order.append("ensure"))
        edit = _FakeDock()
        hwp_dock.claim(edit, hwp_dock.PRIORITY_EDIT)
        hwp_dock.release(edit)
        self.assertEqual(order, ["ensure", "start"])

    def test_낮은_쪽은_뺏지_못한다(self):
        r"""양식 수정 중에 메인 ◫ 를 눌러도 **뺏지 않는다** (사용자 결정).

        뺏으면 한글이 다시 두 자리를 오간다 — 고치려던 그 버그다.
        """
        edit, main = _FakeDock(), _FakeDock()
        hwp_dock.claim(edit, hwp_dock.PRIORITY_EDIT)
        self.assertFalse(hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN))
        self.assertIs(hwp_dock.owner(), edit)
        self.assertEqual(edit.log, [])              # 잠들지도 않았다

    def test_이중_release_는_안전하다(self):
        main = _FakeDock()
        hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN)
        hwp_dock.release(main)
        hwp_dock.release(main)                      # 두 번째는 아무 일도 없다
        self.assertIsNone(hwp_dock.owner())

    def test_주인이_아닌_release_는_무시한다(self):
        """남의 자리를 실수로 내려놓게 두면 대장이 무너진다."""
        main, stranger = _FakeDock(), _FakeDock()
        hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN)
        hwp_dock.release(stranger)
        self.assertIs(hwp_dock.owner(), main)

    def test_한글이_죽었으면_되살리지_않는다(self):
        """편집이 끝났는데 한글이 닫혀 있으면 조용히 정리한다."""
        main, edit = _FakeDock(hwnd=0), _FakeDock()
        hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN)
        hwp_dock.claim(edit, hwp_dock.PRIORITY_EDIT)
        hwp_dock.release(edit)
        self.assertEqual(main.log, ["pause"])       # resume 이 없다
        self.assertIsNone(hwp_dock.owner())

    def test_판이_열리면_순서를_다시_잡는다(self):
        """팝오버가 뜰 때 부르는 갈고리 — 주인이 없으면 아무 일도 없다."""
        hwp_dock.reorder_now()                      # 주인 없음 — 조용히 지나간다
        main = _FakeDock()
        hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN)
        hwp_dock.reorder_now()
        self.assertEqual(main.log, ["order:True"])


class HoleNamesExist(unittest.TestCase):
    r"""구멍 뚫기가 쓰는 이름이 **정의돼 있는가** (2026-08-01 회귀).

    e84cc46(제목줄 잘라내기 철회)이 `dpi_scale` 과 `_RGN_DIFF` 의 **정의만**
    지우고 호출부는 남겼다. 그 뒤로 `_punch_hole` 은 매번 NameError 로
    실패했고(except 가 삼켜 로그에만 남았다), 구멍이 없으니 도킹 화면은
    keep_order 의 z 순서 하나에만 기대게 됐다 — 순서가 흔들리는 순간
    판이 하얗게 비던 035·036 증상의 바닥이다.
    """

    def test_이름이_살아_있다(self):
        self.assertTrue(callable(hwp_dock.dpi_scale))
        self.assertEqual(hwp_dock._RGN_DIFF, 4)

    def test_구멍_코드가_부르는_이름이_전부_모듈에_있다(self):
        code = _read("hwp_dock")
        for name in ("dpi_scale", "_RGN_DIFF"):
            self.assertIn(f"{name} =" if name.startswith("_") else f"def {name}",
                          code, f"{name} 의 정의가 없다 — 호출부만 남으면 조용히 죽는다")


class ZOrderOwner(unittest.TestCase):
    r"""도킹 중 **창 순서의 주인은 keep_order 하나**여야 한다 (035·036)."""

    def test_우리_편_판정이_소유_사슬까지_본다(self):
        r"""팝오버·대화상자는 자체 hwnd 를 가진 창이다.

        핸들 둘하고만 비교하면 그것들이 활성일 때 '남의 프로그램'으로 읽혀
        keep_order 가 그냥 돌아갔다 — 순서를 다시 잡아 줄 사람이 없어
        도킹 판이 하얗게 비었다 (035).
        """
        code = _read("hwp_dock")
        self.assertIn("GA_ROOTOWNER", code)
        body = code.split("def keep_order")[1].split("\n    def ")[0]
        self.assertIn("_is_ours", body)

    def test_도킹_중에는_항상_위를_바꿀_수_없다(self):
        r"""PageUp 은 단독키로 '항상 위' 토글이다 (2026-07-31 결정).

        우리 창이 최상위 띠로 올라가면 그 아래에 평범한 창(한글)을 넣을 수
        없어, keep_order 의 두 줄이 매 틱 이길 수 없는 싸움을 반복한다 —
        도킹 판이 하얗게 비는 036 의 정체다. 버튼(⇧)과 키(PageUp)가 같은
        길(_toggle_top)로 들어오므로 거기 한 곳만 막으면 된다.
        """
        code = _read("app")
        body = code.split("def _toggle_top")[1].split("\ndef ")[0]
        self.assertIn("_is_docked()", body)
        self.assertLess(body.index("_is_docked()"), body.index("set_config_value"),
                        "도킹 확인이 값 저장보다 뒤면 상태만 어긋난 채 남는다")

    def test_도킹에_들어가며_끈_항상_위를_되돌린다(self):
        """끄기만 하고 안 되돌리면 도킹을 뗀 뒤 창이 뒤로 숨는다."""
        code = _read("app")
        self.assertIn('_dock["was_topmost"]', code)
        body = code.split("def _restore_normal_layout")[1].split("\ndef ")[0]
        self.assertIn("was_topmost", body)

    def test_판이_열릴_때_순서를_다시_잡는_갈고리가_걸려_있다(self):
        code = _read("app")
        self.assertIn("popover_mod.on_shown(hwp_dock.reorder_now)", code)


class PopoverPassThrough(unittest.TestCase):
    r"""팝오버는 **첫 클릭을 먹지 않는다** (038-b).

    예전에는 `grab_set()` 으로 마우스를 잡고 창 밖 클릭까지 제 이벤트로 받아
    닫는 데 썼다 — 그 클릭은 목적지(창의 ✕·다른 버튼)로 가지 않았다.
    사용자에게는 "눌러도 안 꺼진다"로 보였다.
    """

    def test_잡기를_쓰지_않는다(self):
        # 주석은 뺀다 — 왜 안 쓰는지가 거기 적혀 있다
        lines = [ln for ln in _read("popover").splitlines()
                 if not ln.strip().startswith("#")]
        calls = [ln for ln in lines if "grab_set(" in ln]
        self.assertEqual(calls, [], f"잡기가 돌아오면 첫 클릭을 다시 먹는다: {calls}")

    def test_바깥_클릭은_엿듣기로_감지한다(self):
        code = _read("popover")
        self.assertIn('bind_all("<ButtonPress-1>"', code)
        self.assertIn("def _outside_click", code)

    def test_하위_메뉴가_열린_동안은_부모가_안_닫힌다(self):
        """계단식 메뉴(⋯)를 누르면 부모 판은 그대로 남아야 한다."""
        code = _read("popover")
        self.assertIn("_muted", code)
        self.assertIn("def suspend_grab", code)
        self.assertIn("def resume_grab", code)


class FitWindowSettle(unittest.TestCase):
    r"""양식 수정이 끝나면 창이 커진 채 굳던 문제 (031-a).

    `_fit_window` 는 "호출부가 전부 after_idle 로 미룬다"를 전제로 스스로
    update_idletasks 를 하지 않는다. 그런데 판을 통째로 접었다 펴는 두
    자리(도킹 진입·이탈)는 다음 줄이 바로 창 크기에 기대므로 미룰 수가 없다 —
    그 전제가 거기서만 깨져 있었고, 편집 때의 큰 높이가 minsize 에 박혔다.
    """

    def test_접었다_펴는_자리는_settle_로_부른다(self):
        code = _read("palette_ui")
        for name in ("_collapse_for_edit", "_exit_dock_layout"):
            body = code.split(f"def {name}")[1].split("\n    def ")[0]
            self.assertIn("_fit_window(settle=True)", body,
                          f"{name} 이 접기 전 크기로 창을 잰다 — minsize 가 굳는다")

    def test_settle_은_이른_반환을_건너뛴다(self):
        """요청 크기가 우연히 같아도 minsize 는 반드시 다시 잡아야 한다."""
        body = _read("palette_ui").split("def _fit_window")[1].split("\n    def ")[0]
        self.assertIn("if settle:", body)
        self.assertIn("and not settle", body)


class OwnerWiring(unittest.TestCase):
    """호출부 둘이 실제로 대장을 거치는가 — 안 거치면 대장은 장식이다."""

    def test_메인_도킹은_10_으로_잡는다(self):
        body = _read("app").split("def _enter_dock_risky")[1].split("\ndef ")[0]
        self.assertIn("hwp_dock.claim(dock, hwp_dock.PRIORITY_MAIN", body)
        exit_body = _read("app").split("def _exit_dock(")[1].split("\ndef ")[0]
        self.assertIn("hwp_dock.release(dock)", exit_body)

    def test_양식_수정은_100_으로_잡는다(self):
        code = _read("palette_ui")
        body = code.split("def _start_dock")[1].split("\n    def ")[0]
        self.assertIn("hwp_dock.claim(dock, hwp_dock.PRIORITY_EDIT", body)
        exit_body = code.split("def _exit_dock_layout")[1].split("\n    def ")[0]
        self.assertIn("hwp_dock.release", exit_body)

    def test_되돌린_뒤에_내려놓는다(self):
        r"""순서가 뒤집히면 깨어난 메인 도킹과 우리 restore 가 같은 창을 다툰다."""
        body = _read("palette_ui").split("def _exit_dock_layout")[1] \
                                  .split("\n    def ")[0]
        self.assertLess(body.index(".restore()"), body.index("hwp_dock.release"))


if __name__ == "__main__":
    unittest.main()
