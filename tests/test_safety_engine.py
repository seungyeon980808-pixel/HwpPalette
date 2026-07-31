# -*- coding: utf-8 -*-
r"""안전 감사(2026-07-31) 회귀 테스트 — 엔진·클립보드의 '남의 글 보호' 규칙.

막으려는 사고들:
  · 낡은 클립보드 내용이 '선택'으로 둔갑해 진짜 선택을 덮어쓴다
    → Copy 는 **클립보드 순번이 움직였을 때만** 성공으로 본다
  · 다른 탭/사용자 손글에 Undo 를 퍼붓는다
    → undo_to 는 누르기 전에 거절 검사부터 한다 (거절 행렬)
  · 지문 읽기 실패("")가 빈 문서("")와 헷갈린다
    → doc_fingerprint_strict 는 실패를 None 으로 준다
  · win32 가 잠깐 실패했다고 Tk 클립보드로 물러나 세션 내내 잠긴다
    → Tk 는 win32 모듈이 **아예 없을 때만** 쓴다
"""

import pathlib
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import clipboard            # noqa: E402
from hwp_palette.hwp import hwp_engine            # noqa: E402


# ── 엔티티 되돌리기 ───────────────────────────────────
class EntityDecodeTest(unittest.TestCase):

    def test_십진_엔티티(self):
        self.assertEqual(hwp_engine._unescape_entities("붙임 &#8212; 1부"),
                         "붙임 — 1부")

    def test_십육진_엔티티_대소문자(self):
        self.assertEqual(hwp_engine._unescape_entities("&#x2014;&#X2014;"),
                         "——")

    def test_이름_엔티티(self):
        self.assertEqual(
            hwp_engine._unescape_entities("&lt;표&gt; &quot;안&quot; &apos;초&apos;"),
            "<표> \"안\" '초'")

    def test_amp는_맨_마지막에_푼다(self):
        # &amp;lt; 는 '&lt; 라는 글자'다 — < 까지 두 번 풀리면 안 된다
        self.assertEqual(hwp_engine._unescape_entities("&amp;lt;"), "&lt;")
        self.assertEqual(hwp_engine._unescape_entities("A &amp; B"), "A & B")

    def test_범위_밖_숫자는_원문_그대로(self):
        self.assertEqual(hwp_engine._unescape_entities("&#99999999999;"),
                         "&#99999999999;")

    def test_앰퍼샌드가_없으면_그대로(self):
        self.assertEqual(hwp_engine._unescape_entities("50% <표>"), "50% <표>")


# ── 순번 관문 — 선택 읽기의 클립보드 경유 길 ─────────
class FakeHwp:
    """선택 관련만 흉내 낸 한글 (test_selection_read 와 같은 모양)."""

    def __init__(self, block=None, mode=0):
        self._block = block
        self.SelectionMode = mode
        self.copied = 0
        engine = self

        class _Action:
            @staticmethod
            def Run(name):
                if name == "Copy":
                    engine.copied += 1
        self.HAction = _Action()

    def GetTextFile(self, fmt, arg):
        if arg == "saveblock":
            return self._block
        return ""


class SequenceGatedReadTest(unittest.TestCase):

    def tearDown(self):
        hwp_engine.hwp = None

    def _use(self, fake):
        hwp_engine.hwp = fake

    def test_순번이_안_움직이면_클립보드를_읽지_않는다(self):
        """핵심 — Copy 가 헛손질이면 낡은 내용이 선택으로 둔갑하면 안 된다."""
        self._use(FakeHwp(block="", mode=1))
        with mock.patch.object(clipboard, "sequence_number",
                               return_value=10), \
                mock.patch.object(clipboard, "get_text",
                                  side_effect=AssertionError("낡은 내용을 읽었다")), \
                mock.patch("hwp_palette.hwp.hwp_engine.time.sleep"), \
                mock.patch("hwp_palette.hwp.hwp_engine.applog.warn"):
            self.assertEqual(hwp_engine.read_selection_text(), "")
        self.assertEqual(hwp_engine.hwp.copied, 1)   # Copy 는 시도했다

    def test_순번을_못_읽으면_Copy조차_하지_않는다(self):
        self._use(FakeHwp(block="", mode=1))
        with mock.patch.object(clipboard, "sequence_number",
                               return_value=None), \
                mock.patch.object(clipboard, "get_text",
                                  side_effect=AssertionError("읽으면 안 된다")), \
                mock.patch("hwp_palette.hwp.hwp_engine.applog.warn"):
            self.assertEqual(hwp_engine.read_selection_text(), "")
        self.assertEqual(hwp_engine.hwp.copied, 0)

    def test_순번이_움직였을_때만_클립보드를_믿는다(self):
        self._use(FakeHwp(block="", mode=1))
        with mock.patch.object(clipboard, "sequence_number",
                               side_effect=[10, 10, 11]), \
                mock.patch.object(clipboard, "get_text",
                                  return_value="복사된 표 내용"), \
                mock.patch("hwp_palette.hwp.hwp_engine.time.sleep"), \
                mock.patch("hwp_palette.hwp.hwp_engine.applog.warn"):
            self.assertEqual(hwp_engine.read_selection_text(), "복사된 표 내용")
        self.assertEqual(hwp_engine.hwp.copied, 1)


# ── 되돌리기 거절 행렬 ────────────────────────────────
class FakeDoc:
    """test_undo_to 의 FakeDoc 과 같은 모양 — 문서 식별까지 흉내."""

    def __init__(self, states, index=None, doc_id=7,
                 full_name=r"C:\문서\시험지.hwp"):
        self.states = states
        self.index = len(states) - 1 if index is None else index
        self.log = []
        doc = self

        class _Action:
            @staticmethod
            def Run(name):
                doc.run(name)
        self.HAction = _Action()
        active = types.SimpleNamespace(FullName=full_name, DocumentID=doc_id)
        self.hwp = types.SimpleNamespace(
            XHwpDocuments=types.SimpleNamespace(Active_XHwpDocument=active))

    def run(self, name):
        self.log.append(name)
        if name == "Undo" and self.index > 0:
            self.index -= 1
        elif name == "Redo" and self.index < len(self.states) - 1:
            self.index += 1

    def GetTextFile(self, _kind, _opt):
        return self.states[self.index]


class UndoRefusalMatrixTest(unittest.TestCase):
    """거절할 때는 **Undo 를 한 번도 누르지 않는다** — 전부 log 로 확인한다."""

    def setUp(self):
        self._saved = hwp_engine.hwp

    def tearDown(self):
        hwp_engine.hwp = self._saved

    def _sealed_token(self, doc):
        hwp_engine.hwp = doc
        return {"doc": hwp_engine.doc_identity(),
                "before": doc.states[0],
                "after": doc.states[doc.index]}

    def test_no_token(self):
        doc = FakeDoc(["A", "AB"])
        hwp_engine.hwp = doc
        for bad in (None, {}, {"doc": "x"}, {"before": "x"}):
            ok, steps, reason = hwp_engine.undo_to(bad)
            self.assertEqual((ok, steps, reason), (False, 0, "no_token"))
        self.assertEqual(doc.log, [])

    def test_unsealed(self):
        doc = FakeDoc(["A", "AB"])
        token = self._sealed_token(doc)
        token["after"] = None                   # seal 실패 상태
        ok, steps, reason = hwp_engine.undo_to(token)
        self.assertEqual((ok, steps, reason), (False, 0, "unsealed"))
        token2 = hwp_engine.record_undo_point()  # seal 을 아예 안 부른 상태
        ok, steps, reason = hwp_engine.undo_to(token2)
        self.assertEqual((ok, steps, reason), (False, 0, "unsealed"))
        self.assertEqual(doc.log, [])

    def test_other_doc(self):
        doc = FakeDoc(["A", "AB"])
        token = self._sealed_token(doc)
        # 사용자가 다른 탭으로 넘어갔다 — 식별자가 달라진다
        doc.hwp.XHwpDocuments.Active_XHwpDocument.DocumentID = 99
        ok, steps, reason = hwp_engine.undo_to(token)
        self.assertEqual((ok, steps, reason), (False, 0, "other_doc"))
        self.assertEqual(doc.log, [])

    def test_빈_문서_탭도_ID로_갈린다(self):
        """저장 안 한 탭 둘(FullName 둘 다 "")을 헷갈리면 안 된다."""
        doc = FakeDoc(["A", "AB"], doc_id=1, full_name="")
        token = self._sealed_token(doc)
        doc.hwp.XHwpDocuments.Active_XHwpDocument.DocumentID = 2
        ok, _steps, reason = hwp_engine.undo_to(token)
        self.assertFalse(ok)
        self.assertEqual(reason, "other_doc")
        self.assertEqual(doc.log, [])

    def test_edited_after(self):
        doc = FakeDoc(["A", "AB"])
        token = self._sealed_token(doc)
        doc.states[doc.index] = "AB그리고 손으로 쓴 글"    # 작업 뒤 사용자가 고침
        ok, steps, reason = hwp_engine.undo_to(token)
        self.assertEqual((ok, steps, reason), (False, 0, "edited_after"))
        self.assertEqual(doc.log, [])

    def test_fp_failed(self):
        doc = FakeDoc(["A", "AB"])
        token = self._sealed_token(doc)
        doc.GetTextFile = mock.Mock(side_effect=RuntimeError("COM 끊김"))
        with mock.patch("hwp_palette.hwp.hwp_engine.applog.exc"):
            ok, steps, reason = hwp_engine.undo_to(token)
        self.assertEqual((ok, steps, reason), (False, 0, "fp_failed"))
        self.assertEqual(doc.log, [])

    def test_redo_broken은_정직하게_알린다(self):
        """되감기 도중 Redo 가 터지면 — 반쯤 되돌아간 사실을 숨기지 않는다."""
        doc = FakeDoc(["A", "AB", "ABC"])
        token = self._sealed_token(doc)
        token["before"] = "이 문서에 없는 지문"
        original_run = doc.run

        def breaking_run(name):
            if name == "Redo":
                raise RuntimeError("Redo 실패")
            original_run(name)
        doc.run = breaking_run
        with mock.patch("hwp_palette.hwp.hwp_engine.applog.exc"):
            ok, steps, reason = hwp_engine.undo_to(token, cap=2)
        self.assertFalse(ok)
        self.assertEqual(reason, "redo_broken")
        self.assertEqual(steps, 2)              # 얼마나 눌렀는지는 알려 준다


# ── record / seal / 문서 식별 ─────────────────────────
class RecordSealTest(unittest.TestCase):

    def setUp(self):
        self._saved = hwp_engine.hwp

    def tearDown(self):
        hwp_engine.hwp = self._saved

    def test_record는_식별자와_직전_지문을_찍는다(self):
        hwp_engine.hwp = FakeDoc(["처음"], doc_id=3)
        token = hwp_engine.record_undo_point()
        self.assertEqual(token["before"], "처음")
        self.assertIn("3", token["doc"])

    def test_식별자를_못_얻으면_record는_None(self):
        hwp_engine.hwp = None
        self.assertIsNone(hwp_engine.record_undo_point())

    def test_지문을_못_읽으면_record는_None(self):
        doc = FakeDoc(["처음"])
        doc.GetTextFile = mock.Mock(side_effect=RuntimeError("COM 끊김"))
        hwp_engine.hwp = doc
        with mock.patch("hwp_palette.hwp.hwp_engine.applog.exc"):
            self.assertIsNone(hwp_engine.record_undo_point())

    def test_seal_실패는_토큰을_못_쓰게_만든다(self):
        doc = FakeDoc(["처음"])
        hwp_engine.hwp = doc
        token = hwp_engine.record_undo_point()
        doc.GetTextFile = mock.Mock(side_effect=RuntimeError("COM 끊김"))
        with mock.patch("hwp_palette.hwp.hwp_engine.applog.exc"):
            self.assertFalse(hwp_engine.seal_undo_point(token))
        self.assertIsNone(token["after"])

    def test_doc_identity_저장된_문서는_경로로도_된다(self):
        doc = FakeDoc(["x"], full_name=r"C:\수업\1학기.hwp")
        del doc.hwp.XHwpDocuments.Active_XHwpDocument.DocumentID
        hwp_engine.hwp = doc
        self.assertEqual(hwp_engine.doc_identity(), r"path|C:\수업\1학기.hwp")

    def test_doc_identity_ID없는_빈_문서는_None(self):
        """구분할 수 없으면 '같은 문서'라고 확신하지 않는다."""
        doc = FakeDoc(["x"], full_name="")
        del doc.hwp.XHwpDocuments.Active_XHwpDocument.DocumentID
        hwp_engine.hwp = doc
        self.assertIsNone(hwp_engine.doc_identity())


# ── 지문 — 실패(None)와 빈 문서("")의 구별 ────────────
class StrictFingerprintTest(unittest.TestCase):

    def tearDown(self):
        hwp_engine.hwp = None

    def test_예외면_None(self):
        broken = mock.Mock()
        broken.GetTextFile.side_effect = RuntimeError("COM 끊김")
        hwp_engine.hwp = broken
        with mock.patch("hwp_palette.hwp.hwp_engine.applog.exc"):
            self.assertIsNone(hwp_engine.doc_fingerprint_strict())

    def test_한글이_None을_줘도_None(self):
        fake = mock.Mock()
        fake.GetTextFile.return_value = None
        hwp_engine.hwp = fake
        self.assertIsNone(hwp_engine.doc_fingerprint_strict())

    def test_진짜_빈_문서만_빈_문자열(self):
        fake = mock.Mock()
        fake.GetTextFile.return_value = ""
        hwp_engine.hwp = fake
        self.assertEqual(hwp_engine.doc_fingerprint_strict(), "")

    def test_구식_doc_fingerprint는_예전_동작_그대로(self):
        """app.py 예전 배선 호환 — None 결과를 "" 로 뭉갠다 (strict 와 다름)."""
        fake = mock.Mock()
        fake.GetTextFile.return_value = None
        hwp_engine.hwp = fake
        self.assertEqual(hwp_engine.doc_fingerprint(), "")


# ── 클립보드 — Tk 후퇴 관문·복원·순번 ─────────────────
class ClipboardSafetyTest(unittest.TestCase):

    def test_win32가_있는데_실패하면_Tk로_물러나지_않는다(self):
        """핵심 — Tk 로 담는 순간 우리가 주인이 되어 세션 내내 잠긴다."""
        win = mock.Mock()
        win.OpenClipboard.side_effect = OSError("다른 앱이 잠금")
        widget = mock.Mock()
        with mock.patch.object(clipboard, "_win32", return_value=win), \
                mock.patch("hwp_palette.core.clipboard.time.sleep"), \
                mock.patch("hwp_palette.core.clipboard.applog.exc"):
            self.assertFalse(clipboard.set_text("예문", widget=widget))
        widget.clipboard_append.assert_not_called()
        widget.clipboard_clear.assert_not_called()

    def test_담기가_끝내_실패하면_원래_내용을_되살려_본다(self):
        """EmptyClipboard 로 지워 놓기만 한 채 끝나면 안 된다."""
        win = mock.Mock()
        win.GetClipboardData.return_value = "원래 있던 글"
        put = []

        def set_data(_fmt, val):
            put.append(val)
            if val == "새 값":
                raise OSError("잠김")
        win.SetClipboardData.side_effect = set_data
        with mock.patch.object(clipboard, "_win32", return_value=win), \
                mock.patch("hwp_palette.core.clipboard.time.sleep"), \
                mock.patch("hwp_palette.core.clipboard.applog.exc"):
            self.assertFalse(clipboard.set_text("새 값"))
        self.assertEqual(put[-1], "원래 있던 글")   # 마지막 시도는 복원이다

    def test_win32가_아예_없을_때만_Tk를_쓴다(self):
        widget = mock.Mock()
        with mock.patch.object(clipboard, "_win32", return_value=None):
            self.assertTrue(clipboard.set_text("예문", widget=widget))
        widget.clipboard_append.assert_called_once_with("예문")

    def test_순번은_OpenClipboard_없이_읽는다(self):
        win = mock.Mock()
        win.GetClipboardSequenceNumber.return_value = 42
        with mock.patch.object(clipboard, "_win32", return_value=win):
            self.assertEqual(clipboard.sequence_number(), 42)
        win.OpenClipboard.assert_not_called()

    def test_순번_모듈이_없으면_None(self):
        with mock.patch.object(clipboard, "_win32", return_value=None):
            self.assertIsNone(clipboard.sequence_number())

    def test_순번_조회가_터지면_None(self):
        win = mock.Mock()
        win.GetClipboardSequenceNumber.side_effect = OSError("실패")
        with mock.patch.object(clipboard, "_win32", return_value=win), \
                mock.patch("hwp_palette.core.clipboard.applog.exc"):
            self.assertIsNone(clipboard.sequence_number())


# ── 표 탈출 — 실패 시 한 발 더 걷지 않는다 ────────────
class ExitTableTest(unittest.TestCase):

    def tearDown(self):
        hwp_engine.hwp = None

    def _act(self, log):
        class _Action:
            @staticmethod
            def Run(name):
                log.append(name)
        return _Action()

    def test_본문에_도달하면_MoveRight까지_하고_True(self):
        log = []
        fake = mock.Mock()
        fake.GetPos.side_effect = [(3, 0, 0), (1, 0, 0), (0, 0, 0)]
        hwp_engine.hwp = fake
        self.assertTrue(hwp_engine._exit_table(self._act(log)))
        self.assertEqual(log, ["Cancel", "CloseEx", "CloseEx", "MoveRight"])

    def test_위치를_못_읽으면_MoveRight를_누르지_않는다(self):
        """셀 안에서 MoveRight 는 다음 문항을 표 속에 밀어 넣는다."""
        log = []
        fake = mock.Mock()
        fake.GetPos.side_effect = RuntimeError("COM 끊김")
        hwp_engine.hwp = fake
        with mock.patch("hwp_palette.hwp.hwp_engine.applog.exc"):
            self.assertFalse(hwp_engine._exit_table(self._act(log)))
        self.assertNotIn("MoveRight", log)

    def test_중첩_한도를_다_써도_본문이_아니면_False(self):
        log = []
        fake = mock.Mock()
        fake.GetPos.return_value = (5, 0, 0)     # 영영 본문(list 0)이 아니다
        hwp_engine.hwp = fake
        with mock.patch("hwp_palette.hwp.hwp_engine.applog.warn") as warned:
            self.assertFalse(hwp_engine._exit_table(self._act(log)))
        self.assertNotIn("MoveRight", log)
        self.assertTrue(warned.called)


if __name__ == "__main__":
    unittest.main()
