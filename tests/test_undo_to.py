# -*- coding: utf-8 -*-
r"""되돌리기(↺) 테스트 — **반쯤 되돌린 상태로 두지 않는다**.

왜 이 테스트가 필요한가:
    변환 한 번은 한글 입장에서 동작 수십 개다. 사용자가 Ctrl+Z 를 몇 번
    눌러야 하는지 알 수 없어서, 프로그램이 대신 눌러 주기로 했다
    (hwp_engine.undo_to). 그런데 이 기능은 **남의 글을 지울 수 있는 쪽**에
    있다 — 지문을 못 찾았는데도 계속 누르면 사용자가 손으로 쓴 글까지
    사라진다. 그래서 지키는 규칙:

      · 지문이 나오면 거기서 **즉시 멈춘다** (한 번도 더 누르지 않는다)
      · 한도 안에 못 찾으면 누른 만큼 Redo 로 **원상복구**하고 실패를 알린다
      · 이미 그 자리면 아무것도 누르지 않는다
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import hwp_engine        # noqa: E402


class FakeAction:
    def __init__(self, doc):
        self.doc = doc

    def Run(self, name):
        self.doc.run(name)


class FakeDoc:
    r"""되돌리기 스택 흉내 — 상태 목록을 인덱스로 오간다.

    states[0] 이 가장 오래된 상태이고 index 가 지금 자리다. Undo 는 하나
    뒤로, Redo 는 하나 앞으로. 실제 한글도 이렇게 움직인다.
    """

    def __init__(self, states, index=None):
        self.states = states
        self.index = len(states) - 1 if index is None else index
        self.log = []
        self.HAction = FakeAction(self)

    def run(self, name):
        self.log.append(name)
        if name == "Undo" and self.index > 0:
            self.index -= 1
        elif name == "Redo" and self.index < len(self.states) - 1:
            self.index += 1

    def GetTextFile(self, _kind, _opt):
        return self.states[self.index]


class UndoToTest(unittest.TestCase):

    def setUp(self):
        self._saved = hwp_engine.hwp

    def tearDown(self):
        hwp_engine.hwp = self._saved

    def use(self, doc):
        hwp_engine.hwp = doc
        return doc

    def test_찾으면_거기서_멈춘다(self):
        # 지문 'A' 로 돌아가려면 Undo 세 번이면 된다
        doc = self.use(FakeDoc(["A", "AB", "ABC", "ABCD"]))
        ok, pressed = hwp_engine.undo_to("A")
        self.assertTrue(ok)
        self.assertEqual(pressed, 3)
        self.assertEqual(doc.GetTextFile("TEXT", ""), "A")
        self.assertEqual(doc.log, ["Undo"] * 3)      # 한 번도 더 안 눌렀다

    def test_이미_그_자리면_안_누른다(self):
        doc = self.use(FakeDoc(["A", "AB"], index=0))
        ok, pressed = hwp_engine.undo_to("A")
        self.assertTrue(ok)
        self.assertEqual(pressed, 0)
        self.assertEqual(doc.log, [])

    def test_못_찾으면_원래대로_되감는다(self):
        # 'Z' 라는 지문은 이 문서 어디에도 없다 — 되돌린 만큼 도로 감아야 한다
        doc = self.use(FakeDoc(["A", "AB", "ABC"]))
        ok, pressed = hwp_engine.undo_to("Z")
        self.assertFalse(ok)
        self.assertEqual(pressed, 0)
        self.assertEqual(doc.GetTextFile("TEXT", ""), "ABC")   # 그대로다
        self.assertEqual(doc.log.count("Undo"), doc.log.count("Redo"))

    def test_한도를_넘겨_누르지_않는다(self):
        doc = self.use(FakeDoc([str(i) for i in range(200)]))
        ok, _pressed = hwp_engine.undo_to("0", cap=5)
        self.assertFalse(ok)
        self.assertEqual(doc.log.count("Undo"), 5)

    def test_지점이_없으면_아무것도_안_한다(self):
        doc = self.use(FakeDoc(["A", "AB"]))
        ok, pressed = hwp_engine.undo_to(None)
        self.assertFalse(ok)
        self.assertEqual(pressed, 0)
        self.assertEqual(doc.log, [])


if __name__ == "__main__":
    unittest.main()
