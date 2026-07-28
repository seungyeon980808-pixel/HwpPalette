# -*- coding: utf-8 -*-
r"""'내용 고치기'로 펼칠 때·저장할 때의 안전장치 테스트 (2026-07-27).

증상 (사용자 지적): **템플릿을 수정할 때 내용이 가끔 출력되지 않는다.**

실측으로 확인한 원인:
  pyhwpx 의 insert_file 은 `HAction.Execute` 를 그대로 돌려준다 — 실패해도
  예외를 던지지 않고 **False 만** 준다. 여태 그 값을 안 봐서, 조각 파일이
  사라졌거나 잠겨 있으면 빈 탭에 안내문만 붙은 채 "고치세요"가 떴다.
  app.log 에 아무것도 안 남던 이유이기도 하다.

그 상태에서 [이 내용으로 덮어쓰기]를 누르면 **원본 조각이 빈 내용으로
교체된다.** 표시 버그가 데이터 손실로 번지는 길이라, 여기서 지키려는 것은
하나다:

  **빈 문서는 절대 저장물이 되지 않는다.**
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.hwp import engine_library        # noqa: E402


class FakeDoc:
    """XHwpDocuments.Add(1) 이 돌려주는 문서 객체 흉내."""

    def __init__(self):
        self.closed = False
        self.activated = 0

    def SetActive_XHwpDocument(self):
        self.activated += 1

    def Close(self, isDirty=False):
        self.closed = True


class FakeDocs:
    def __init__(self):
        self.Count = 1
        self.made = []

    def Add(self, _kind):
        self.Count += 1
        doc = FakeDoc()
        self.made.append(doc)
        return doc


class FakeCtrl:
    """HeadCtrl 사슬의 한 마디. CtrlID 는 'secd'/'cold'/'tbl' 등."""

    def __init__(self, ctrl_id, nxt=None):
        self.CtrlID = ctrl_id
        self.Next = nxt


def _ctrl_chain(ids):
    head = None
    for cid in reversed(ids):
        head = FakeCtrl(cid, head)
    return head


class FakeHwp:
    r"""삽입 성공/실패를 골라 흉내 내는 가짜 한글.

    실측값을 그대로 흉내 낸다 (2026-07-27):
      · 빈 새 탭도 MoveDocEnd 뒤 GetPos 가 (0,0,16) — (0,0,0) 이 아니다
      · 어떤 문서에나 secd·cold 컨트롤이 있고, 표가 있으면 tbl 이 더 붙는다

    insert_results: insert_file 이 차례로 돌려줄 값들 (True/False).
    body_after: 삽입이 '성공'했을 때 문서에 생기는 글자.
    ctrls_after: 삽입이 '성공'했을 때 생기는 컨트롤 목록.
    """

    _EMPTY_POS = (0, 0, 16)          # 실측: 빈 문서의 처음이자 끝
    _END_POS = (0, 0, 24)            # 실측: 표가 하나 있는 문서의 끝

    def __init__(self, insert_results=(True,), body_after="표 내용",
                 ctrls_after=("secd", "cold")):
        self._insert_results = list(insert_results)
        self._body_after = body_after
        self._ctrls_after = list(ctrls_after)
        self.body = ""
        self.ctrls = ["secd", "cold"]
        self.inserted = 0
        self.ran = []
        self.saved_to = None
        self.XHwpDocuments = FakeDocs()

    # ── 문서 내용 ──
    def insert_file(self, path, **kw):
        self.inserted += 1
        ok = bool(self._insert_results.pop(0)) if self._insert_results else False
        if ok:
            self.body = self._body_after
            self.ctrls = list(self._ctrls_after)
        return ok

    def GetTextFile(self, *_a, **_kw):
        return self.body

    @property
    def HeadCtrl(self):
        return _ctrl_chain(self.ctrls)

    def MoveDocEnd(self):
        self._at_end = True

    def MoveDocBegin(self):
        self._at_end = False

    def GetPos(self):
        has_content = bool(self.body) or set(self.ctrls) - {"secd", "cold"}
        if getattr(self, "_at_end", False) and has_content:
            return self._END_POS
        return self._EMPTY_POS

    def save_as(self, path, format=None):
        self.saved_to = path
        return True

    # ── HAction / HParameterSet (안내문 삽입이 쓴다) ──
    @property
    def HAction(self):
        outer = self

        class _A:
            def Run(self, name):
                outer.ran.append(name)
                if name == "Delete":
                    outer.body = ""
                if name == "Paste":
                    outer.body = outer._paste_value()

            def GetDefault(self, *_a):
                pass

            def Execute(self, name, *_a):
                if name == "InsertText":
                    outer.body += outer.HParameterSet.HInsertText.Text
                return True
        return _A()

    @property
    def HParameterSet(self):
        if not hasattr(self, "_ps"):
            class _Insert:
                HSet = None
                Text = ""

            class _PS:
                HInsertText = _Insert()
            self._ps = _PS()
        return self._ps

    def _paste_value(self):
        return self.body


def _install(fake):
    """engine_library 가 쓰는 한글을 가짜로 갈아끼운다.

    hwp_engine.hwp 도 함께 꽂는다 — 안내문 삽입(_insert_edit_note)이
    hwp_engine.insert_plain 을 거쳐 그 전역을 읽기 때문이다.
    """
    mock.patch.object(engine_library, "_h", lambda: fake).start()
    mock.patch.object(engine_library.hwp_engine, "hwp", fake).start()


class DocIsEmptyTest(unittest.TestCase):
    """빈 문서 판정 — 글자·컨트롤·커서 세 신호로 본다."""

    def tearDown(self):
        mock.patch.stopall()

    def test_글자가_있으면_비지_않았다(self):
        fake = FakeHwp()
        fake.body = "안녕"
        _install(fake)
        self.assertFalse(engine_library.doc_is_empty())

    def test_표만_있고_글자가_없어도_비지_않았다(self):
        r"""그림·표만 든 조각을 '빈 문서'로 오판하면 정상 열기가 막힌다."""
        fake = FakeHwp()
        fake.body = ""
        fake.ctrls = ["secd", "cold", "tbl"]
        _install(fake)
        self.assertFalse(engine_library.doc_is_empty())

    def test_글자도_표도_없으면_빈_문서(self):
        fake = FakeHwp()
        fake.body = ""
        fake.ctrls = ["secd", "cold"]
        _install(fake)
        self.assertTrue(engine_library.doc_is_empty())

    def test_커서를_절대값_0으로_비교하지_않는다(self):
        r"""핵심 회귀 테스트 (실측 2026-07-27).

        빈 새 탭에서도 MoveDocEnd 뒤 GetPos 는 **(0,0,16)** 이지 (0,0,0) 이
        아니다. 예전 판정은 (0,0,0) 과 비교해서 **영영 참이 되지 않았고**,
        안전장치가 통째로 무동작이었다. 처음과 끝을 서로 비교해야 한다.
        """
        fake = FakeHwp()
        fake.body = ""
        fake.ctrls = ["secd", "cold"]
        _install(fake)
        self.assertNotEqual(fake._EMPTY_POS, (0, 0, 0),
                            "실측값을 흉내 내지 않으면 이 테스트는 의미가 없다")
        self.assertTrue(engine_library.doc_is_empty())


class OpenTemplateCopyTest(unittest.TestCase):
    """조각 펼치기 — 실패를 성공처럼 보이게 두지 않는다."""

    def setUp(self):
        self.tmp = pathlib.Path(__file__).with_name("_frag_test.hwp")
        self.tmp.write_bytes(b"fake hwp")

    def tearDown(self):
        mock.patch.stopall()
        self.tmp.unlink(missing_ok=True)

    def test_조각_파일이_없으면_예외(self):
        r"""스테일 경로(덮어쓰기로 이미 지워진 옛 파일명)를 조용히 통과시키지 않는다."""
        fake = FakeHwp()
        _install(fake)
        missing = self.tmp.with_name("_없는파일.hwp")
        with self.assertRaises(FileNotFoundError):
            engine_library.open_template_copy(missing, ["안내"])
        self.assertEqual(fake.inserted, 0, "없는 파일인데 삽입을 시도했다")

    def test_삽입_성공이면_안내문이_붙는다(self):
        fake = FakeHwp(insert_results=(True,))
        _install(fake)
        engine_library.open_template_copy(self.tmp, ["첫 줄", "둘째 줄"])
        self.assertEqual(fake.inserted, 1)
        self.assertIn(engine_library.EDIT_NOTE_MARK, fake.body)

    def test_첫_삽입이_비면_한_번_다시_시도한다(self):
        fake = FakeHwp(insert_results=(False, True))
        _install(fake)
        engine_library.open_template_copy(self.tmp, ["안내"])
        self.assertEqual(fake.inserted, 2, "재시도를 하지 않았다")
        self.assertIn("SelectAll", fake.ran,
                      "재시도 전에 탭을 비우지 않으면 내용이 두 번 들어간다")

    def test_두_번_다_실패하면_예외를_던지고_빈_탭을_닫는다(self):
        fake = FakeHwp(insert_results=(False, False))
        _install(fake)
        with self.assertRaises(RuntimeError):
            engine_library.open_template_copy(self.tmp, ["안내"])
        self.assertTrue(fake.XHwpDocuments.made[0].closed,
                        "실패한 빈 탭이 한글에 남았다")

    def test_실패하면_안내문을_붙이지_않는다(self):
        r"""핵심 회귀 테스트 — '빈 탭 + 고치세요 안내'가 데이터 손실의 입구였다."""
        fake = FakeHwp(insert_results=(False, False))
        _install(fake)
        with self.assertRaises(RuntimeError):
            engine_library.open_template_copy(self.tmp, ["다 고쳤으면 덮어쓰기"])
        self.assertNotIn(engine_library.EDIT_NOTE_MARK, fake.body)


class SaveGuardTest(unittest.TestCase):
    """저장 쪽 마지막 방어선 — 빈 문서는 원본을 덮어쓰지 못한다."""

    def tearDown(self):
        mock.patch.stopall()

    def test_빈_문서는_저장하지_않는다(self):
        fake = FakeHwp()
        fake.body = ""
        _install(fake)
        with self.assertRaises(RuntimeError):
            engine_library.save_active_as("아무데나.hwp")
        self.assertIsNone(fake.saved_to, "빈 문서인데 저장이 실행됐다")

    def test_내용이_있으면_저장한다(self):
        fake = FakeHwp()
        fake.body = "양식 내용"
        _install(fake)
        with mock.patch.object(engine_library, "normalize_marks_to_pairs",
                               return_value=0):
            engine_library.save_active_as("결과.hwp")
        self.assertEqual(fake.saved_to, "결과.hwp")


class CaptureFragmentTest(unittest.TestCase):
    r"""캡처 — 클립보드 경합으로 빈 조각이 저장되는 것을 막는다."""

    def tearDown(self):
        mock.patch.stopall()

    def _fake(self, paste_value):
        fake = FakeHwp()
        fake._paste_value = lambda: paste_value
        return fake

    def test_붙여넣기가_비면_저장하지_않는다(self):
        fake = self._fake("")
        _install(fake)
        mock.patch.object(engine_library, "has_selection",
                          return_value=True).start()
        with self.assertRaises(RuntimeError):
            engine_library.capture_fragment("조각.hwp")
        self.assertIsNone(fake.saved_to, "빈 내용인데 조각을 저장했다")

    def test_붙여넣기가_되면_저장한다(self):
        fake = self._fake("표 내용")
        _install(fake)
        mock.patch.object(engine_library, "has_selection",
                          return_value=True).start()
        mock.patch.object(engine_library, "normalize_marks_to_pairs",
                          return_value=0).start()
        engine_library.capture_fragment("조각.hwp")
        self.assertEqual(fake.saved_to, "조각.hwp")


if __name__ == "__main__":
    unittest.main()
