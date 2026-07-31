# -*- coding: utf-8 -*-
r"""고치기 세션 — 열었던 그 탭만 닫고, 탭 개폐를 한 번으로 (2026-07-27).

사용자 지적 두 가지:
  ① "템플릿을 수정하고 나면 빈 한글 창이 남는다"
  ② "저장할 때 창이 여러 개 닫히는 듯한 모션이 보인다"

실측으로 확인한 원인:
  ① `open_form_copy` 가 쓰던 `hwp.FileNew()` 는 이름과 달리 새 **탭**이 아니라
     새 **문서 창**을 여는 명령이다(pyhwpx 문서). 편집이 끝나 그 창의 하나뿐인
     문서를 닫으면 창 자체는 남아 빈 한글 창이 됐다.
  ② 저장 한 번에 한글 탭이 다섯 번 열리고 닫혔다 — 캡처용 임시 탭,
     미리보기용 임시 탭, 그리고 편집 탭. 편집 탭이 이미 저장할 내용
     그대로인데도 굳이 새 탭에 복사-붙여넣기를 하고 있었다.

여기서 지키려는 것:
  · 양식 편집은 새 **탭**에서 열린다 (새 창이 아니다)
  · 저장 때 닫히는 것은 **고치던 탭 하나뿐**이다
  · 닫는 대상은 '지금 활성 문서'가 아니라 **펼칠 때 받아 둔 그 문서**다
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.hwp import engine_library        # noqa: E402


class FakeDoc:
    def __init__(self, tag):
        self.tag = tag
        self.FullName = ""
        self.closed = False
        self.activated = 0

    def SetActive_XHwpDocument(self):
        self.activated += 1

    def Close(self, isDirty=False):
        self.closed = True


class FakeDocs:
    """탭 목록 — 몇 번 열고 닫았는지 센다."""

    def __init__(self):
        self.Count = 1
        self.opened = 0
        self.docs = []
        self.Active_XHwpDocument = FakeDoc("사용자문서")

    def Add(self, _kind):
        self.opened += 1
        self.Count += 1
        doc = FakeDoc(f"탭{self.opened}")
        self.docs.append(doc)
        self.Active_XHwpDocument = doc
        return doc

    def closed_count(self):
        return sum(1 for d in self.docs if d.closed)


class FakeHwp:
    def __init__(self):
        self.XHwpDocuments = FakeDocs()
        self.opened_files = []
        self.saved = []
        self.body = "내용 있음"
        self.ctrls = ["secd", "cold", "tbl"]
        self.ran = []

    def open(self, path):
        self.opened_files.append(path)
        return True

    def save_as(self, path, format=None):
        self.saved.append(path)
        pathlib.Path(path).write_bytes(b"fake")
        return True

    def GetTextFile(self, *_a, **_kw):
        return self.body

    @property
    def HeadCtrl(self):
        class _C:
            def __init__(self, cid, nxt):
                self.CtrlID, self.Next = cid, nxt
        head = None
        for cid in reversed(self.ctrls):
            head = _C(cid, head)
        return head

    def MoveDocBegin(self):
        self._end = False

    def MoveDocEnd(self):
        self._end = True

    def GetPos(self):
        # 실측값 흉내: 빈 문서는 처음과 끝이 둘 다 (0,0,16) 이고,
        # 내용이 있으면 끝이 (0,0,24) 로 달라진다.
        has_content = bool(self.body) or set(self.ctrls) - {"secd", "cold"}
        if getattr(self, "_end", False) and has_content:
            return (0, 0, 24)
        return (0, 0, 16)

    def FileNew(self):
        raise AssertionError("FileNew 는 새 '창'을 연다 — 써서는 안 된다")

    @property
    def HAction(self):
        outer = self

        class _A:
            def Run(self, name):
                outer.ran.append(name)

            def GetDefault(self, *_a):
                pass

            def Execute(self, *_a):
                return True
        return _A()

    @property
    def HParameterSet(self):
        if not hasattr(self, "_ps"):
            class _I:
                HSet = None
                Text = ""

            class _P:
                HInsertText = _I()
            self._ps = _P()
        return self._ps


def _install(fake):
    mock.patch.object(engine_library, "_h", lambda: fake).start()
    mock.patch.object(engine_library.hwp_engine, "hwp", fake).start()


class OpenFormCopyTest(unittest.TestCase):
    """양식 편집은 새 창이 아니라 새 탭에서 열려야 한다."""

    def setUp(self):
        self.src = pathlib.Path(__file__).with_name("_form_test.hwp")
        self.src.write_bytes(b"fake form")
        self.work = pathlib.Path(__file__).with_name("_workdir")
        mock.patch.object(engine_library.paths, "data_dir",
                          lambda: self.work).start()

    def tearDown(self):
        mock.patch.stopall()
        self.src.unlink(missing_ok=True)
        for p in self.work.rglob("*"):
            if p.is_file():
                p.unlink(missing_ok=True)

    def test_FileNew_를_쓰지_않는다(self):
        r"""핵심 회귀 테스트 — FileNew 는 새 '창'이라 빈 창이 남았다."""
        fake = FakeHwp()
        _install(fake)
        engine_library.open_form_copy(self.src, None)   # FileNew 면 AssertionError
        self.assertEqual(fake.XHwpDocuments.opened, 1, "새 탭을 열지 않았다")

    def test_사본을_열고_세션에_사본_경로를_담는다(self):
        fake = FakeHwp()
        _install(fake)
        session = engine_library.open_form_copy(self.src, None)
        self.assertTrue(fake.opened_files, "사본을 열지 않았다")
        self.assertIn("편집중_", fake.opened_files[0])
        self.assertTrue(pathlib.Path(session.temp_path).name.startswith("편집중_"))

    def test_양식_파일이_없으면_예외(self):
        fake = FakeHwp()
        _install(fake)
        with self.assertRaises(FileNotFoundError):
            engine_library.open_form_copy(self.src.with_name("_없음.hwp"), None)

    def test_탭이_늘지_않으면_자동_닫기를_포기한다(self):
        r"""open 이 사용자 문서를 갈아치웠을 수 있다 — 그때 닫으면 남의 문서를 닫는다.

        단, 지금 활성 문서는 방금 open 한 사본이므로 세션에 담아 둔다
        (2026-07-31) — doc=None 이면 저장 전 activate() 가 항상 실패해
        이 세션은 영영 저장할 수 없었다. 닫기만 own_tab=False 로 막는다.
        """
        fake = FakeHwp()

        class NoGrowDocs(FakeDocs):
            def Add(self, _kind):
                doc = super().Add(_kind)
                self.Count -= 1          # 새 탭이 안 생긴 상황을 흉내
                return doc
        fake.XHwpDocuments = NoGrowDocs()
        _install(fake)
        session = engine_library.open_form_copy(self.src, None)
        self.assertIsNotNone(session.doc,
                             "활성 문서를 담아 둬야 저장(activate)이 된다")
        self.assertFalse(session.own_tab, "우리가 연 탭이 아니라고 표시해야 한다")
        self.assertFalse(session.close(), "닫으면 안 되는 탭을 닫으려 했다")
        self.assertFalse(session.doc.closed, "사용자 탭일 수 있는 문서를 닫았다")


class FinishEditSessionTest(unittest.TestCase):
    """저장 마무리 — 탭 하나만 닫히고, 임시 사본은 지워진다."""

    def setUp(self):
        self.work = pathlib.Path(__file__).with_name("_workdir2")
        mock.patch.object(engine_library.paths, "data_dir",
                          lambda: self.work).start()
        mock.patch.object(engine_library, "strip_marks", lambda *a: 0).start()

    def tearDown(self):
        mock.patch.stopall()
        if self.work.exists():
            for p in sorted(self.work.rglob("*"), reverse=True):
                if p.is_file():
                    p.unlink(missing_ok=True)

    def test_고치던_탭만_닫는다(self):
        fake = FakeHwp()
        _install(fake)
        mine = FakeDoc("고치던탭")
        others = FakeDoc("사용자문서")
        fake.XHwpDocuments.Active_XHwpDocument = others
        session = engine_library.EditSession(mine)
        with mock.patch.object(engine_library.preview, "save_cache",
                               return_value=True):
            engine_library.finish_edit_session(session, "id1")
        self.assertTrue(mine.closed, "고치던 탭이 안 닫혔다")
        self.assertFalse(others.closed, "엉뚱한 문서를 닫았다")

    def test_저장할_때_새_탭을_열지_않는다(self):
        r"""핵심 회귀 테스트 — 미리보기용 임시 탭이 '여러 창 닫힘' 모션의 절반이었다."""
        fake = FakeHwp()
        _install(fake)
        session = engine_library.EditSession(FakeDoc("고치던탭"))
        with mock.patch.object(engine_library.preview, "save_cache",
                               return_value=True):
            engine_library.finish_edit_session(session, "id2")
        self.assertEqual(fake.XHwpDocuments.opened, 0,
                         "미리보기를 뽑느라 임시 탭을 또 열었다")

    def test_양식_사본을_지운다(self):
        fake = FakeHwp()
        _install(fake)
        self.work.mkdir(parents=True, exist_ok=True)
        copy = self.work / "편집중_양식.hwp"
        copy.write_bytes(b"fake")
        session = engine_library.EditSession(FakeDoc("탭"), temp_path=copy)
        with mock.patch.object(engine_library.preview, "save_cache",
                               return_value=True):
            engine_library.finish_edit_session(session, "id3")
        self.assertFalse(copy.exists(), "편집중_*.hwp 사본이 남았다")

    def test_탭은_임시파일을_읽기_전에_닫힌다(self):
        r"""한글이 붙들고 있는 파일은 지울 수 없다 (WinError 32 계보)."""
        fake = FakeHwp()
        _install(fake)
        order = []
        doc = FakeDoc("탭")
        real_close = doc.Close

        def spy_close(isDirty=False):
            order.append("close")
            real_close(isDirty=isDirty)
        doc.Close = spy_close
        session = engine_library.EditSession(doc)
        with mock.patch.object(engine_library.preview, "save_cache",
                               side_effect=lambda *a: order.append("cache") or True):
            engine_library.finish_edit_session(session, "id4")
        self.assertEqual(order, ["close", "cache"],
                         "탭을 닫기 전에 임시 파일을 읽었다")

    def test_미리보기가_실패해도_탭은_닫는다(self):
        fake = FakeHwp()
        fake.save_as = mock.Mock(side_effect=RuntimeError("저장 실패"))
        _install(fake)
        doc = FakeDoc("탭")
        engine_library.finish_edit_session(engine_library.EditSession(doc), "id5")
        self.assertTrue(doc.closed, "미리보기 실패가 탭 닫기를 막았다")


class HideWindowIfIdleTest(unittest.TestCase):
    r"""고치기가 끝난 뒤 빈 한글 창을 남기지 않는다 (2026-07-27).

    사용자 지적: "수정하고 닫은 다음에 빈 문서 하나가 여전히 남아 있다."
    실측: 편집 탭은 정상적으로 닫히지만 그 인스턴스의 **바탕 문서**가 남는다.
    한글은 문서를 0개로 만들 수 없어 마지막 문서는 Close 해도 안 없어진다
    (실측: Close 뒤에도 Count 가 1). 남는 길은 창을 숨기는 것뿐이다.

    다만 **사용자 문서가 하나라도 있으면 절대 숨기지 않는다** — 쓰던 창이
    사라지는 것이 빈 창이 남는 것보다 훨씬 나쁘다.
    """

    def tearDown(self):
        mock.patch.stopall()

    def _hwp(self, docs):
        """docs: [(FullName, 글자)] — 열려 있는 문서 목록."""
        fake = FakeHwp()

        class Docs:
            Count = len(docs)

            def Item(_s, i):
                d = FakeDoc(docs[i][0])
                d.FullName = docs[i][0]

                def activate(_name=docs[i][0], _text=docs[i][1]):
                    fake.body = _text
                    fake.ctrls = ["secd", "cold"]
                d.SetActive_XHwpDocument = activate
                return d
        fake.XHwpDocuments = Docs()
        _install(fake)
        return fake

    def test_빈_무제_문서_하나뿐이면_창을_숨긴다(self):
        self._hwp([("", "")])
        hid = mock.patch.object(engine_library.hwp_engine, "set_window_visible",
                                return_value=True).start()
        self.assertTrue(engine_library.hide_window_if_idle())
        hid.assert_called_once_with(False)

    def test_문서가_둘_이상이면_숨기지_않는다(self):
        self._hwp([("", ""), ("", "사용자 글")])
        spy = mock.patch.object(engine_library.hwp_engine,
                                "set_window_visible").start()
        self.assertFalse(engine_library.hide_window_if_idle())
        spy.assert_not_called()

    def test_파일이_열려_있으면_숨기지_않는다(self):
        r"""사용자가 쓰던 문서다 — 창이 사라지면 안 된다."""
        self._hwp([(r"C:\수업\시험지.hwp", "")])
        spy = mock.patch.object(engine_library.hwp_engine,
                                "set_window_visible").start()
        self.assertFalse(engine_library.hide_window_if_idle())
        spy.assert_not_called()

    def test_내용이_있으면_숨기지_않는다(self):
        self._hwp([("", "사용자가 쓰던 글")])
        spy = mock.patch.object(engine_library.hwp_engine,
                                "set_window_visible").start()
        self.assertFalse(engine_library.hide_window_if_idle())
        spy.assert_not_called()


class HideWindowIfOursTest(unittest.TestCase):
    r"""우리가 띄운 창만 되돌린다 (2026-07-27).

    사용자 지적: "한글 창이 원래 없던 상태에서도 빈 창이 안 사라진다."
    실측 원인: '연결된 창이 보이는가'로 판단했더니, 한글이 아예 없을 때
    connect() 가 **새로 띄운** 창이 처음부터 보이는 상태라 '원래 있던 창'으로
    오인돼 정리에서 빠졌다. 고치기 **전에** 잰 창 핸들 목록과 비교해야 한다.
    """

    def tearDown(self):
        mock.patch.stopall()

    def _arrange(self, hwnd):
        mock.patch.object(engine_library.hwp_engine, "connected_hwnd",
                          return_value=hwnd).start()
        return mock.patch.object(engine_library, "hide_window_if_idle",
                                 return_value=True).start()

    def test_한글이_아예_없던_경우_되돌린다(self):
        """핵심 회귀 — 고치기 전 보이는 창이 하나도 없었다."""
        spy = self._arrange(1234)
        self.assertTrue(engine_library.hide_window_if_ours(set()))
        spy.assert_called_once()

    def test_숨어_있던_경우_되돌린다(self):
        spy = self._arrange(1234)
        self.assertTrue(engine_library.hide_window_if_ours(set()))
        spy.assert_called_once()

    def test_고치기_전부터_보이던_창은_건드리지_않는다(self):
        spy = self._arrange(1234)
        self.assertFalse(engine_library.hide_window_if_ours({1234, 5678}))
        spy.assert_not_called()

    def test_다른_한글_창만_보였다면_우리_창은_되돌린다(self):
        """사용자의 다른 한글은 그대로 두고, 우리가 켠 것만 정리한다."""
        spy = self._arrange(1234)
        self.assertTrue(engine_library.hide_window_if_ours({5678}))
        spy.assert_called_once()

    def test_핸들을_모르면_판단은_내용에_맡긴다(self):
        spy = self._arrange(None)
        engine_library.hide_window_if_ours({5678})
        spy.assert_called_once()


class EditSessionTest(unittest.TestCase):

    def test_사용자가_이미_닫았어도_오류로_보지_않는다(self):
        class Gone:
            def Close(self, isDirty=False):
                raise RuntimeError("이미 닫힘")
        self.assertFalse(engine_library.EditSession(Gone()).close())

    def test_활성화_실패는_False(self):
        class Gone:
            def SetActive_XHwpDocument(self):
                raise RuntimeError("이미 닫힘")
        self.assertFalse(engine_library.EditSession(Gone()).activate())


if __name__ == "__main__":
    unittest.main()
