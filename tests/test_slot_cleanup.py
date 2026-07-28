# -*- coding: utf-8 -*-
r"""빈칸(\) 청소 범위 테스트 (개선안 5).

한글을 띄울 수 없으므로 **가짜 한글**을 만들어 engine_library 에 꽂는다.
문서를 "문단 리스트"로 흉내 내고, find_text/Delete/GetPos/SetPos 만 구현하면
청소 로직의 경계 판단을 그대로 검증할 수 있다.

여기서 지키려는 것은 하나다:
  **삽입한 템플릿 범위 밖의 `\` 는 절대 지우지 않는다.**
사용자가 템플릿 아래에 써 둔 역슬래시가 조용히 사라지던 버그가 그것이었다.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.hwp import engine_library        # noqa: E402


class FakeHwp:
    r"""문단 배열로 흉내 낸 한글.

    paragraphs: [(list_id, 문자열), ...]
    커서는 (문단index, 문자offset). GetPos 는 (list_id, para, pos) 를 돌려주는데,
    실제 한글처럼 **para 는 list 안에서 다시 세어진다** — 표 안이면 0부터.
    """

    def __init__(self, paragraphs):
        self.paras = [[lid, list(text)] for lid, text in paragraphs]
        self.cur = (0, 0)
        self.deleted = 0

    # ── 실제 한글 API 흉내 ──
    def GetPos(self):
        pi, off = self.cur
        lid = self.paras[pi][0]
        para_in_list = sum(1 for p in self.paras[:pi] if p[0] == lid)
        return (lid, para_in_list, off)

    def SetPos(self, lid, para, pos):
        for i, p in enumerate(self.paras):
            if p[0] == lid and sum(1 for q in self.paras[:i] if q[0] == lid) == para:
                self.cur = (i, pos)
                return True
        return False

    def MoveDocEnd(self):
        self.cur = (len(self.paras) - 1, len(self.paras[-1][1]))

    def find_forward(self, ch):
        pi, off = self.cur
        while pi < len(self.paras):
            text = self.paras[pi][1]
            start = off if pi == self.cur[0] else 0
            for j in range(start, len(text)):
                if text[j] == ch:
                    self.cur = (pi, j + 1)      # 찾은 글자 뒤에 커서
                    return True
            pi += 1
            off = 0
        return False

    def delete_before_cursor(self):
        pi, off = self.cur
        del self.paras[pi][1][off - 1]
        self.cur = (pi, off - 1)
        self.deleted += 1

    def text(self):
        return "\n".join("".join(t) for _, t in self.paras)


class SlotCleanupTest(unittest.TestCase):

    def _install(self, fake):
        """engine_library 가 쓰는 한글 호출을 가짜로 갈아끼운다."""
        self.fake = fake
        patches = [
            mock.patch.object(engine_library, "_h", return_value=fake),
            mock.patch.object(engine_library, "find_text",
                              side_effect=lambda q, **kw: fake.find_forward(q)),
            mock.patch.object(engine_library, "insert_plain",
                              side_effect=lambda t: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        # act.Run("Delete") 만 쓰이므로 HAction 을 가짜로
        fake.HAction = mock.Mock()
        fake.HAction.Run.side_effect = lambda cmd: (
            fake.delete_before_cursor() if cmd == "Delete" else None)

    def test_범위_안의_빈칸만_지운다(self):
        # 0~1번 문단이 삽입된 템플릿, 2번 문단은 사용자가 쓴 글
        fake = FakeHwp([(0, "이름: \\"), (0, "날짜: \\"), (0, r"내 메모 \ 중요")])
        self._install(fake)
        engine_library.strip_slot_markers((0, 0, 0), end_para=1)
        self.assertEqual(fake.deleted, 2)
        self.assertIn(r"내 메모 \ 중요", fake.text())   # 사용자 글은 그대로

    def test_범위를_안_주면_문서_끝까지_지운다(self):
        """양식을 새 문서로 연 경우 — 문서 전체가 대상이라 이게 맞는 동작."""
        fake = FakeHwp([(0, "이름: \\"), (0, "메모 \\")])
        self._install(fake)
        engine_library.strip_slot_markers((0, 0, 0), end_para=None)
        self.assertEqual(fake.deleted, 2)

    def test_개수_상한을_넘겨_지우지_않는다(self):
        fake = FakeHwp([(0, "\\ \\ \\ \\")])
        self._install(fake)
        engine_library.strip_slot_markers((0, 0, 0), end_para=0, max_delete=2)
        self.assertEqual(fake.deleted, 2)

    def test_표_안의_사용자_빈칸을_개수_상한이_막는다(self):
        r"""핵심 회귀 테스트.

        표 안(list_id != 0)에서는 para 가 셀 기준으로 다시 세어져서 문단 범위
        검사가 통하지 않는다. 개수 상한이 없으면 아래쪽 표에 있는 사용자의 `\`
        까지 지워진다.
        """
        fake = FakeHwp([
            (0, "템플릿 빈칸 \\"),      # 삽입 범위 (본문 0번)
            (5, "사용자 표 안의 \\"),   # 아래쪽 표 — list_id 가 다름
        ])
        self._install(fake)
        # 템플릿이 선언한 빈칸은 1개뿐 → 1개만 지워야 한다
        engine_library.strip_slot_markers((0, 0, 0), end_para=0, max_delete=1)
        self.assertEqual(fake.deleted, 1)
        self.assertIn("사용자 표 안의 \\", fake.text())

    def test_상한이_없으면_표_안까지_지워진다(self):
        """위 테스트가 무엇을 막고 있는지 보여주는 대조군."""
        fake = FakeHwp([(0, "템플릿 빈칸 \\"), (5, "사용자 표 안의 \\")])
        self._install(fake)
        engine_library.strip_slot_markers((0, 0, 0), end_para=0, max_delete=None)
        self.assertEqual(fake.deleted, 2)          # 이것이 고치려던 상황

    def test_fill_slots_는_채운_만큼_상한을_줄인다(self):
        fake = FakeHwp([(0, "\\ \\ \\"), (0, r"사용자 \ 글")])
        self._install(fake)
        # 빈칸 3개짜리 템플릿에 2개만 채움 → 남은 1개만 지워야 한다
        filled, want = engine_library.fill_slots((0, 0, 0), ["가", "나"],
                                                 end_para=0, slot_count=3)
        self.assertEqual(filled, 2)
        self.assertEqual(want, 2)          # 넣으려던 값도 2개 = 끝까지 채웠다
        self.assertEqual(fake.deleted, 1)
        self.assertIn(r"사용자 \ 글", fake.text())

    def test_fill_slots_는_중간에_멈추면_못_채운_수를_알려준다(self):
        r"""빈칸이 하나뿐인데 값이 셋 → 둘은 갈 곳이 없다.

        예전에는 조용히 멈춰서 인쇄물을 보고서야 알았다. 이제 (채움, 채우려던 수)를
        돌려주므로 호출부가 사용자에게 알릴 수 있다.
        """
        fake = FakeHwp([(0, "빈칸 \\ 하나")])
        self._install(fake)
        filled, want = engine_library.fill_slots((0, 0, 0), ["가", "나", "다"],
                                                 end_para=0, slot_count=1)
        self.assertEqual(want, 3)
        self.assertLess(filled, want)      # 다 못 채웠다는 사실이 드러난다


    def test_삽입_지점보다_앞은_안_지운다(self):
        r"""find_text 가 문서 끝에서 맨 앞으로 되돌아가더라도, 앞쪽에 있는
        사용자의 `\` 는 문단 번호가 작아서 '범위 안'으로 보인다 → 앞쪽 방어."""
        fake = FakeHwp([(0, r"위쪽 사용자 \ 글"), (0, "템플릿 \\")])
        self._install(fake)
        # 앵커는 1번 문단 시작 — 0번 문단은 건드리면 안 된다
        engine_library.strip_slot_markers((0, 1, 0), end_para=1)
        self.assertEqual(fake.deleted, 1)
        self.assertIn(r"위쪽 사용자 \ 글", fake.text())

    def test_되돌아가면_멈춘다(self):
        """find 가 앞으로 되감긴 상황을 직접 흉내 낸다."""
        fake = FakeHwp([(0, r"앞쪽 \ 글"), (0, "템플릿 \\")])
        self._install(fake)
        calls = {"n": 0}

        def wrapping_find(ch, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return fake.find_forward(ch)        # 정상: 템플릿 빈칸
            fake.cur = (0, 0)                        # 되감김
            return fake.find_forward(ch)
        with mock.patch.object(engine_library, "find_text",
                               side_effect=wrapping_find):
            engine_library.strip_slot_markers((0, 1, 0), end_para=1)
        self.assertEqual(fake.deleted, 1)            # 되감긴 뒤엔 안 지움
        self.assertIn(r"앞쪽 \ 글", fake.text())


class MeasureInsertSpanTest(unittest.TestCase):
    r"""표 안에서는 문단 범위를 계산할 수 없으므로 None 을 줘야 한다."""

    def test_본문이면_문단_범위를_계산한다(self):
        fake = FakeHwp([(0, "가"), (0, "나")])
        with mock.patch.object(engine_library, "_h", return_value=fake), \
             mock.patch.object(engine_library.hwp_engine, "doc_end_para",
                               side_effect=[1, 3]):
            end = engine_library.measure_insert_span((0, 0, 0), lambda: None)
        self.assertEqual(end, 2)          # 0 + (3-1)

    def test_표_안이면_None(self):
        """본문 기준 번호와 셀 기준 번호를 더하면 뜻 없는 수가 나온다."""
        fake = FakeHwp([(0, "가"), (5, "나")])
        called = {"n": 0}
        with mock.patch.object(engine_library, "_h", return_value=fake):
            end = engine_library.measure_insert_span(
                (5, 0, 0), lambda: called.__setitem__("n", called["n"] + 1))
        self.assertIsNone(end)
        self.assertEqual(called["n"], 1)   # 삽입 자체는 반드시 일어나야 한다


if __name__ == "__main__":
    unittest.main()
