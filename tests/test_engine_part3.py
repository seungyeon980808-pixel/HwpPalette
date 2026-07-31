# -*- coding: utf-8 -*-
r"""파트 3 — 누르면 무슨 일이 일어나는가 (033·034·040, 2026-08-01).

셋 다 한글 엔진 언저리의 규칙이라, 여기서는 **되돌리면 그 버그가 돌아오는
코드 모양**만 못박는다. 실기 동작은 spikes/cell_spacing_spike.py ·
cell_fit_verify.py · hidden_slot_spike.py 가 한글을 띄워 실측했다.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import srcpath                                     # noqa: E402


def _read(module):
    return srcpath.src(module).read_text(encoding="utf-8")


class SpacingFitInCells(unittest.TestCase):
    r"""034 — 자간 맞춤이 표 안에서도 돈다.

    막던 것은 문 하나였다: `_selected_para_range` 가 본문(list 0)만 통과시키고,
    배관 전체가 `SetPos(0, …)` 로 list 0 을 박아 썼다. 실측(3건)으로 셀 안
    이동·문단모양·자간 적용이 본문과 같게 노는 것을 확인하고 list_id 를 꿴다.
    """

    def test_범위_판정이_list_를_함께_돌려준다(self):
        body = _read("engine_library").split("def _selected_para_range")[1] \
                                      .split("\ndef ")[0]
        # 양끝 list 가 **같으면** 통과 — 0 강요가 돌아오면 표가 다시 막힌다
        self.assertIn("int(got[1]) == int(got[4])", body)
        self.assertNotIn("== 0 and", body)

    def test_배관에_list_0_이_박혀_있지_않다(self):
        r"""`SetPos(0, ` 가 자간 배관에 남으면 셀 좌표가 본문으로 새서
        **남의 문단**을 고치게 된다."""
        code = _read("engine_library")
        for name in ("_line_bounds", "_set_break_by_word", "_read_spacing",
                     "_apply_spacing", "_pull_up", "_tighten_para"):
            body = code.split(f"def {name}")[1].split("\ndef ")[0]
            self.assertNotIn("SetPos(0,", body,
                             f"{name} 이 list 0 을 박아 쓴다")
            self.assertIn("list_id", body, f"{name} 에 list_id 가 안 꿰였다")

    def test_줄_끝_이동이_다음_셀로_새는_것을_막는다(self):
        """표에서는 줄 끝 MoveRight 가 다음 셀로 넘어갈 수 있다 —
        문단 번호만 보면 그 셀의 0번 문단이 '같은 문단'으로 읽힌다."""
        body = _read("engine_library").split("def _tighten_para")[1] \
                                      .split("\ndef ")[0]
        self.assertIn("int(nxt[0]) != list_id", body)

    def test_선택_확인은_돌려주는_값을_믿지_않는다(self):
        r"""실측(2026-08-01): 셀 안에서 SelectText 는 **True 를 돌려주면서
        아무것도 선택하지 않는다.** 예외로만 가르면 셀에서 조용히 실패한다."""
        code = _read("engine_library")
        self.assertIn("def _select_run", code)
        body = code.split("def _select_run")[1].split("\ndef ")[0]
        self.assertIn("GetSelectedPos", body)
        # _apply_spacing 은 선택이 실제로 잡혔을 때만 서식을 건다
        apply_body = code.split("def _apply_spacing")[1].split("\ndef ")[0]
        self.assertIn("_select_run", apply_body)

    def test_안내_문구가_새_현실을_말한다(self):
        """'표 안은 제외됩니다'가 알림으로 남아 있으면 이제 거짓말이다."""
        lines = [ln for ln in _read("app").splitlines()
                 if "표 안은 제외" in ln and not ln.strip().startswith("#")]
        self.assertEqual(lines, [])
        self.assertIn("셀 하나씩 선택해 주세요", _read("app"))


class ChoiceOnClick(unittest.TestCase):
    r"""040 (안 A) — 빈칸이 있는 물감은 누르면 **옵션을 고른다**.

    예전에는 물감마다 달랐다(이름 없는 템플릿=즉시, 이름 있는 템플릿·양식=표).
    "누르기 전에 무엇이 일어날지 알 수 없다"가 사용자가 물은 혼란의 정체다.
    """

    def test_옵션_팝오버가_있다(self):
        body = _read("app").split("def _run_palette_block")[1].split("\ndef ")[0]
        self.assertIn("빈칸인 채로 꽂기", body)
        self.assertIn("채워 넣고 꽂기", body)

    def test_빈칸이_없으면_즉시_꽂는다(self):
        """고를 것이 없는 물감에까지 팝오버를 띄우면 클릭 수만 는다."""
        body = _read("app").split("def _run_palette_block")[1].split("\ndef ")[0]
        self.assertIn("_insert_block_now(block)", body)

    def test_이름_없는_자리만_있어도_표로_갈_수_있다(self):
        r"""잔결정: 이름 있는 자리는 표, 이름 없는 `\` 만이면 순서대로 입력 —
        갈래는 팝오버 **뒤**에 정해지므로 사용자는 신경 쓸 필요가 없다.
        예전의 '이름이 하나라도 있으면'(any) 조건이 돌아오면 이 길이 막힌다."""
        body = _read("app").split("def _fill_table_fn")[1].split("\ndef ")[0]
        self.assertNotIn("any(", body)
        self.assertIn('it.get("slot_names")', body)

    def test_팝오버_콜백은_제_잠금을_챙긴다(self):
        """run_palette_block 의 잠금은 팝오버가 뜨는 순간 이미 풀려 있다."""
        code = _read("app")
        self.assertIn("def _insert_block_guarded", code)
        body = code.split("def _insert_block_guarded")[1].split("\ndef ")[0]
        self.assertIn("_op_busy", body)


class HiddenRunsReadable(unittest.TestCase):
    r"""033-a — 자식 태그가 든 조각도 읽고 채운다 (모양 검사).

    동작 검사는 tests/test_safety_content.py 의 RunWithAttributesTest 에 있다.
    여기서는 정규식이 옛 모양(`[^<]*` — 자식 태그에서 통째로 건너뜀)으로
    돌아오는 것만 막는다.
    """

    def test_run_판이_자식_태그를_건너뛰지_않는다(self):
        code = _read("form_fill")
        line = [ln for ln in code.splitlines() if ln.startswith("RUN_RE = ")][0]
        self.assertNotIn("[^<]*", line,
                         "옛 판이 돌아오면 수능양식의 둘째 빈칸이 다시 사라진다")
        self.assertIn(".*?", line)


if __name__ == "__main__":
    unittest.main()
