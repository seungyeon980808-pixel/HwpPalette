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

    def clear_topmost(self):
        self.log.append("unpin")

    def clear_owner(self):
        self.log.append("unown")

    def clear_hole(self):
        self.log.append("fill")

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
        self.assertEqual(main.log, ["pause", "unpin", "unown", "fill"])
        self.assertIs(hwp_dock.owner(), edit)

    def test_편집이_끝나면_메인이_저절로_돌아온다(self):
        r"""사용자가 기대하는 것: 저장하면 메인 도킹이 알아서 제자리로.

        스택이라 이전 주인을 기억한다 — 호출부가 서로를 몰라도 된다.
        """
        main, edit = _FakeDock(), _FakeDock()
        hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN)
        hwp_dock.claim(edit, hwp_dock.PRIORITY_EDIT)
        hwp_dock.release(edit)
        self.assertEqual(main.log, ["pause", "unpin", "unown", "fill", "resume"])
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
        self.assertEqual(main.log, ["pause", "unpin", "unown", "fill"])   # resume 이 없다
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


class HoleAlwaysFilled(unittest.TestCase):
    r"""오려 낸 판 자리는 **어느 길로 끝나든 메운다** (2026-08-01, 사용자 지적).

        "왜 잘려버리는거야 심지어 강제로 창 닫기도 안되네"

    `_punch_hole` 은 `SetWindowRgn` 으로 창의 그 자리를 **없앤다** — 그리지도
    눌리지도 않는다. 안 메우면 창이 잘린 채 남고, 제목줄 ✕ 가 그 안에 들면
    창을 닫을 수조차 없다.

    메인 도킹은 `Dock.stop()` 이 메우는데 **양식 수정 경로에만 빠져 있었다.**
    여태 안 드러난 이유는 구멍 뚫기 자체가 죽어 있어서다 (HoleNamesExist 참고)
    — 되살리는 순간 잠자던 이 버그가 났다.
    """

    def setUp(self):
        hwp_dock._reset_owners_for_test()
        p = mock.patch.object(hwp_dock, "win32gui", _AliveWin32)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(hwp_dock._reset_owners_for_test)

    def test_양식_수정을_끝내면_메운다(self):
        body = _read("palette_ui").split("def _exit_dock_layout")[1] \
                                  .split("\n    def ")[0]
        self.assertIn("clear_hole()", body,
                      "구멍을 안 메우면 창이 잘린 채 남아 ✕ 도 안 먹는다")
        self.assertLess(body.index("clear_hole()"), body.index(".restore()"),
                        "되돌리기 전에 메워야 잘린 창이 눈에 안 띈다")

    def test_메인_도킹을_떼면_메운다(self):
        body = _read("hwp_dock").split("def stop(")[1].split("\n    def ")[0]
        self.assertIn("clear_hole", body)

    def test_잠들_때도_메운다(self):
        """한글은 새 주인에게 갔다 — 잠든 창의 구멍에는 비칠 것이 없다."""
        main, edit = _FakeDock(), _FakeDock()
        hwp_dock.claim(main, hwp_dock.PRIORITY_MAIN)
        hwp_dock.claim(edit, hwp_dock.PRIORITY_EDIT)
        self.assertIn("fill", main.log)

    def test_시작에_실패하면_제_구멍을_메운다(self):
        """start() 는 구멍을 먼저 뚫는다 — 그 뒤 실패하면 잘린 창만 남는다."""
        body = _read("hwp_dock").split("def start(")[1].split("\n    def ")[0]
        self.assertIn("clear_hole()", body)


class OwnerHierarchy(unittest.TestCase):
    r"""도킹은 **소유자 위계**로 붙는다 (2026-08-02, 041 — 사용자 지적).

        "도킹을 할 때 뒷자리가 비는게 좀 신경쓰이는데 저렇게 구멍을 뚫지
         않고는 해결을 할 수 없나? 명확한 위계를 세우면 되는거잖아"

    맞는 말이었다. 윈도우에는 창 사이의 위계(소유자, GWLP_HWNDPARENT)가
    실제로 있고, 소유 창은 소유자보다 늘 위에 있도록 윈도우가 지켜 준다.

    실측 (spikes/dock_hierarchy_spike.py):
      · 소유자만 세우면 z 순서를 안 맞춰도 한글이 위
      · 우리 창이 '항상 위'여도 한글이 그 위에 남는다 → 036 금지를 풀 근거
    안전 실측 (spikes/owner_survival_spike.py):
      · 소유자를 세운 프로세스를 정리 없이 즉사시켜도 한글은 살아남고
        소유자 값은 저절로 0 으로 풀렸다 (임베드와 다른 결정적 차이)
    """

    def setUp(self):
        hwp_dock._reset_owners_for_test()
        self.addCleanup(hwp_dock._reset_owners_for_test)

    def test_구멍보다_위계를_먼저_시도한다(self):
        body = _read("hwp_dock").split("def start(")[1].split("\n    def ")[0]
        self.assertIn("_set_owner()", body)
        self.assertLess(body.index("_set_owner()"), body.index("_punch_hole()"),
                        "위계를 먼저 세워야 구멍을 안 뚫는다")

    def test_위계가_실패하면_구멍으로_후퇴한다(self):
        r"""다른 프로세스 창에 쓰는 API 라 어느 판에서 막힐지 모른다.

        후퇴 경로가 없으면 그런 판에서 도킹이 통째로 죽는다.
        """
        body = _read("hwp_dock").split("def start(")[1].split("\n    def ")[0]
        self.assertIn("if not self._set_owner():", body)
        self.assertIn("_punch_hole()", body)

    def test_뗄_때_위계를_푼다(self):
        """안 풀면 한글이 죽은 창을 소유자로 물고 따라다닌다."""
        for where, src in (("stop(", "hwp_dock"),):
            body = _read(src).split("def " + where)[1].split("\n    def ")[0]
            self.assertIn("clear_owner()", body)
        body = _read("palette_ui").split("def _exit_dock_layout")[1] \
                                  .split("\n    def ")[0]
        self.assertIn("clear_owner()", body)

    def test_시작에_실패해도_위계를_푼다(self):
        body = _read("hwp_dock").split("def start(")[1].split("\n    def ")[0]
        self.assertIn("clear_owner()", body)

    def test_원래_소유자로_되돌린다(self):
        """0 이 아니라 **원래 값**으로 — 남이 세워 둔 관계를 지우지 않는다."""
        body = _read("hwp_dock").split("def clear_owner")[1] \
                                .split("\n    def ")[0]
        self.assertIn("self._owner0", body)

    def test_위계로_붙었는지_밖에서_물어볼_수_있다(self):
        """'항상 위'를 풀어도 되는지 판정하는 유일한 근거."""
        self.assertFalse(hwp_dock.owner_has_hierarchy())    # 주인 없음
        d = _FakeDock()
        hwp_dock.claim(d, hwp_dock.PRIORITY_MAIN)
        self.assertFalse(hwp_dock.owner_has_hierarchy(),
                         "위계를 안 세운 주인은 False 여야 한다")
        d._owner_set = True
        self.assertTrue(hwp_dock.owner_has_hierarchy())

    def test_구멍은_위계가_섰으면_아예_안_뚫는다(self):
        r"""start 에서만 막으면 **따라가는 스레드가 곧바로 다시 뚫는다.**

        실측에서 그렇게 됐다 — 위계가 서 있는데도 창이 오려진 채였다
        (spikes/dock_e2e_verify.py 1차). 막는 자리는 _punch_hole 안이어야 한다.
        """
        body = _read("hwp_dock").split("def _punch_hole")[1] \
                                .split("\n    def ")[0]
        self.assertIn("if self._owner_set:", body)
        self.assertLess(body.index("if self._owner_set:"),
                        body.index("GetWindowRect"),
                        "좌표를 재기 전에 빠져나와야 한다")

    def test_한글을_우리와_같은_띠로_올린다(self):
        r"""소유 관계는 **같은 띠 안에서만** 위아래를 지켜 준다.

        우리 창만 '항상 위' 띠로 올라가면 한글은 아래 띠에 남아 가려진다 —
        실측에서 판이 우리 창으로 덮였다.
        """
        body = _read("hwp_dock").split("def keep_order")[1] \
                                .split("\n    def ")[0]
        self.assertIn("_root_is_topmost()", body)
        self.assertIn("HWND_TOPMOST", body)

    def test_뗄_때_한글을_띠에서_내린다(self):
        """우리가 올린 것만 내린다 — 원래 항상 위였으면 그대로 둔다."""
        body = _read("hwp_dock").split("def clear_topmost")[1] \
                                .split("\n    def ")[0]
        self.assertIn("_hwp_was_topmost", body)
        stop = _read("hwp_dock").split("def stop(")[1].split("\n    def ")[0]
        self.assertIn("clear_topmost()", stop)

    def test_항상_위를_켜면_순서를_다시_잡는다(self):
        """안 잡으면 한글이 아래 띠에 남아 판이 우리 창으로 덮인다."""
        body = _read("app").split("def _toggle_top")[1].split("\ndef ")[0]
        self.assertIn("reorder_now()", body)

    def test_도킹_중에도_항상_위를_쓸_수_있다(self):
        r"""036 의 금지를 푼다 — 다만 **위계로 붙었을 때만**.

        구멍 뚫기로 후퇴한 판에서는 옛 문제(판이 하얗게 빔)가 그대로다.
        """
        body = _read("app").split("def _toggle_top")[1].split("\ndef ")[0]
        self.assertIn("owner_has_hierarchy()", body)
        self.assertIn("_is_docked()", body)


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


class SettingsWindowFitsScreen(unittest.TestCase):
    r"""설정 창은 **화면보다 큰 최소 크기**를 갖지 않는다 (2026-08-02).

    전 화면 훑기(spikes/ui_sweep.py)에서 나왔다: 이 창의 내용 폭은 1151px 인데
    선생님 주모니터는 세로(1080×1920)다. 내용 크기를 그대로 minsize 로 박으면
    오른쪽 71px 이 화면 밖으로 나가고 **줄일 수조차 없다** — 하필 잘리는 쪽이
    미리보기 판의 [수정]·[양식 수정] 단추라 그 기능에 손이 아예 안 닿는다.

    못 줄이는 것보다 줄일 수 있는 편이 낫다.
    """

    def test_최소_크기를_화면_안으로_묶는다(self):
        code = _read("palette_ui")
        self.assertIn("def _capped_min", code)
        # minsize 를 그대로 박는 자리가 남아 있으면 안 된다 — 한 곳만 고치면
        # _fit_window 의 갱신이 곧바로 덮어쓴다
        raw = [ln for ln in code.splitlines()
               if "self.minsize(" in ln and "_capped_min" not in ln]
        self.assertEqual(raw, [],
                         f"화면 밖으로 나갈 수 있는 minsize 가 남아 있다: {raw}")

    def test_묶는_함수가_화면_크기를_본다(self):
        body = _read("palette_ui").split("def _capped_min")[1] \
                                  .split("\n    def ")[0]
        self.assertIn("winfo_screenwidth", body)
        self.assertIn("winfo_screenheight", body)
