# -*- coding: utf-8 -*-
r"""고치기 세션의 '엉뚱한 문서 보호' 안전장치 (2026-07-31 안전 수리).

편집 세션에서 사용자의 진짜 문서(시험지)가 다치는 길이 세 갈래 있었다:

  ① activate() 가 False 를 줘도(편집 탭이 닫혔거나 한글이 바쁨) 저장 흐름이
     그대로 진행돼, 안내문 걷기·전체 저장이 **사용자가 보고 있던 문서**를
     상대로 실행됐다.
  ② normalize_marks_to_pairs 의 다섯 단계 replace_all 은 결과를 하나도
     확인하지 않았다 — 중간에 실패하면 피신 글자(⟪이름:…⟫)가 문서에 남고,
     save_active_as 는 그 실패를 삼킨 채 저장을 계속해 **피신 글자가 저장물에
     구워졌다.**
  ③ 양식 사본 경로가 `편집중_{원본이름}` 으로 고정이라, 같은 양식을 두 번
     열면 사본이 서로 덮어쓰고 한쪽 cleanup() 이 다른 쪽이 아직 고치는
     파일을 지웠다.

여기서 지키려는 것:
  · activate 실패 → 문서에 손대기 **전에** 통째로 멈춘다
  · 정리 실패 → 저장하지 않고, 실패가 사용자에게 보인다
  · 세션마다 사본 이름이 다르고, cleanup 은 자기 것만 지운다

2026-07-31 후속 수리(리뷰 지적): ① 의 activate 방어가 들어오자, open 이 새
탭을 쓰지 않은 예비 경로(open_form_copy 가 doc=None 세션을 돌려주던 곳)는
activate 가 **항상** 실패해 그 세션의 저장이 영영 막혔다 — "다시 시도해
주세요" 안내가 거짓이 된다. 그때의 활성 문서는 방금 open 한 사본이므로
세션에 담아 저장은 살리고, own_tab=False 로 **닫기만** 막는다. 문서 객체가
정말 없으면(활성 문서 읽기까지 실패) 재시도 안내 대신 정직하게 알린다.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.hwp import engine_library        # noqa: E402
from hwp_palette.ui import library_ui             # noqa: E402
from tests.test_edit_session import (                   # noqa: E402
    FakeDocs, FakeHwp, _install)


class FakeSession:
    """activate 결과를 골라 흉내 내는 편집 세션."""

    def __init__(self, activate_ok=True, doc="문서있음"):
        self._ok = activate_ok
        self.doc = doc
        self.temp_path = None

    def activate(self):
        return self._ok


class ActivateGuardTest(unittest.TestCase):
    r"""① activate 실패면 문서에 손대기 전에 멈춘다."""

    def setUp(self):
        mock.patch.object(library_ui, "_ensure_hwp",
                          return_value=True).start()
        self.err = mock.patch.object(library_ui.messagebox,
                                     "showerror").start()
        self.strip = mock.patch.object(library_ui.engine_library,
                                       "strip_edit_note").start()
        self.replace = mock.patch.object(library_ui.library,
                                         "replace_template_fragment",
                                         return_value=True).start()
        mock.patch.object(library_ui.engine_library, "finish_edit_session",
                          return_value=(True, True)).start()
        mock.patch("hwp_palette.hwp.preview.cached_path",
                   return_value=pathlib.Path(__file__).with_name(
                       "_없는_미리보기.png")).start()

    def tearDown(self):
        mock.patch.stopall()

    def test_활성화_실패면_아무것도_저장하지_않는다(self):
        r"""핵심 회귀 테스트 — 실패해도 계속 가면 사용자의 시험지를 덮는다."""
        ok, closed = library_ui.overwrite_content(
            FakeSession(activate_ok=False), "템플릿", {"id": "t1"}, None)
        self.assertFalse(ok)
        self.assertFalse(closed)
        self.strip.assert_not_called()
        self.replace.assert_not_called()

    def test_활성화_실패는_오류창으로_알린다(self):
        library_ui.overwrite_content(
            FakeSession(activate_ok=False), "템플릿", {"id": "t1"}, None)
        self.err.assert_called_once()
        msg = self.err.call_args.args[1]
        self.assertIn("편집 탭", msg, "무엇을 확인하라는지 알려줘야 한다")

    def test_활성화_성공이면_저장_흐름이_그대로_돈다(self):
        ok, _closed = library_ui.overwrite_content(
            FakeSession(activate_ok=True), "템플릿", {"id": "t1"}, None)
        self.assertTrue(ok)
        self.strip.assert_called_once()
        self.replace.assert_called_once()

    def test_문서를_놓친_세션은_재시도_안내_대신_정직하게_알린다(self):
        r"""doc=None 세션은 다시 시도해도 똑같이 실패한다 — 재시도 안내가 거짓."""
        ok, closed = library_ui.overwrite_content(
            FakeSession(doc=None), "양식", {"id": "f1"}, None)
        self.assertFalse(ok)
        self.assertFalse(closed)
        self.strip.assert_not_called()
        self.replace.assert_not_called()
        self.err.assert_called_once()
        msg = self.err.call_args.args[1]
        self.assertNotIn("다시 시도", msg, "성공할 수 없는 재시도를 안내했다")
        self.assertIn("내용 고치기", msg, "편집을 다시 여는 길을 알려줘야 한다")


class NormalizeFailureTest(unittest.TestCase):
    r"""② 정리 다섯 단계 — 결과를 확인하고, 실패하면 되돌린 뒤 멈춘다."""

    def tearDown(self):
        mock.patch.stopall()

    def _fake(self, body):
        fake = FakeHwp()
        fake.body = body
        _install(fake)
        return fake

    def test_중간_실패면_예외를_던지고_피신을_되돌린다(self):
        r"""핵심 회귀 테스트 — 여태 다섯 단계 전부 결과를 안 봤다."""
        self._fake("이름 \\학년\\ 과 홑 \\ 하나")
        calls = []

        def fake_replace(find, repl):
            calls.append((find, repl))
            return find != "\\"          # 홑 \ 불리기 단계만 실패
        mock.patch.object(engine_library.hwp_engine, "replace_all",
                          side_effect=fake_replace).start()
        with self.assertRaises(RuntimeError) as ctx:
            engine_library.normalize_marks_to_pairs()
        self.assertIn("되돌렸", str(ctx.exception))
        self.assertIn(("⟪이름:학년⟫", "\\학년\\"), calls,
                      "피신시킨 이름표를 제자리로 되돌리지 않았다")

    def test_되돌리기까지_실패하면_남았다고_알린다(self):
        self._fake("이름 \\학년\\ 과 홑 \\ 하나")
        # 피신(이름표 → ⟪이름:…⟫)만 성공하고 나머지는 전부 실패 —
        # 되돌리기까지 실패하니 피신 글자가 문서에 남는 최악의 경우다
        mock.patch.object(engine_library.hwp_engine, "replace_all",
                          side_effect=lambda find, repl:
                          find == "\\학년\\").start()
        with self.assertRaises(RuntimeError) as ctx:
            engine_library.normalize_marks_to_pairs()
        self.assertIn("⟪", str(ctx.exception),
                      "문서에 무엇이 남았는지 알려줘야 사용자가 지울 수 있다")

    def test_전부_성공이면_정리한_개수를_돌려준다(self):
        self._fake("쌍 \\\\ 과 홑 \\ 하나")
        mock.patch.object(engine_library.hwp_engine, "replace_all",
                          return_value=True).start()
        self.assertEqual(engine_library.normalize_marks_to_pairs(), 1)

    def test_홑이_없으면_바꾸기를_아예_안_한다(self):
        self._fake("쌍 \\\\ 뿐인 문서")
        spy = mock.patch.object(engine_library.hwp_engine,
                                "replace_all").start()
        self.assertEqual(engine_library.normalize_marks_to_pairs(), 0)
        spy.assert_not_called()


class SaveAbortsOnNormalizeFailureTest(unittest.TestCase):
    r"""② 정리가 실패하면 save_as 를 부르지 않는다 — 성공한 척 금지."""

    def tearDown(self):
        mock.patch.stopall()

    def test_정리_실패면_저장하지_않는다(self):
        r"""핵심 회귀 테스트 — 여태 예외를 삼키고 저장을 계속했다."""
        fake = FakeHwp()
        fake.body = "양식 내용"
        _install(fake)
        mock.patch.object(
            engine_library, "normalize_marks_to_pairs",
            side_effect=RuntimeError("정리 실패")).start()
        with self.assertRaises(RuntimeError):
            engine_library.save_active_as("결과.hwp")
        self.assertEqual(fake.saved, [], "정리가 실패했는데 저장이 실행됐다")

    def test_실패가_호출부의_오류창까지_닿는다(self):
        r"""overwrite_content 의 except 가 받아 오류창을 띄우는 경로."""
        mock.patch.object(library_ui, "_ensure_hwp",
                          return_value=True).start()
        err = mock.patch.object(library_ui.messagebox, "showerror").start()
        mock.patch.object(library_ui.engine_library,
                          "strip_edit_note").start()
        mock.patch.object(
            library_ui.library, "replace_template_fragment",
            side_effect=RuntimeError("자리 표시 정리에 실패")).start()
        ok, closed = library_ui.overwrite_content(
            FakeSession(activate_ok=True), "양식", {"id": "f1"}, None)
        self.assertFalse(ok)
        self.assertFalse(closed)
        err.assert_called_once()
        self.assertIn("자리 표시 정리에 실패", err.call_args.args[1])


class UniqueWorkingCopyTest(unittest.TestCase):
    r"""③ 같은 양식을 두 번 열어도 사본이 서로를 덮지 않는다."""

    def setUp(self):
        self.src = pathlib.Path(__file__).with_name("_safety_form.hwp")
        self.src.write_bytes(b"fake form")
        self.work = pathlib.Path(__file__).with_name("_safety_work")
        mock.patch.object(engine_library.paths, "data_dir",
                          lambda: self.work).start()

    def tearDown(self):
        mock.patch.stopall()
        self.src.unlink(missing_ok=True)
        if self.work.exists():
            for p in sorted(self.work.rglob("*"), reverse=True):
                if p.is_file():
                    p.unlink(missing_ok=True)

    def _open_two(self):
        _install(FakeHwp())
        s1 = engine_library.open_form_copy(self.src, None)
        s2 = engine_library.open_form_copy(self.src, None)
        return s1, s2

    def test_사본_이름이_세션마다_다르다(self):
        r"""핵심 회귀 테스트 — 고정 이름이면 두 번째가 첫 번째를 덮어쓴다."""
        s1, s2 = self._open_two()
        self.assertNotEqual(str(s1.temp_path), str(s2.temp_path))
        self.assertTrue(pathlib.Path(s1.temp_path).exists())
        self.assertTrue(pathlib.Path(s2.temp_path).exists())

    def test_cleanup_은_자기_사본만_지운다(self):
        s1, s2 = self._open_two()
        s1.cleanup()
        self.assertFalse(pathlib.Path(s1.temp_path).exists())
        self.assertTrue(pathlib.Path(s2.temp_path).exists(),
                        "다른 세션이 아직 고치는 파일을 지웠다")

    def test_cleanup_실패는_예외를_밖으로_던지지_않는다(self):
        s1, _s2 = self._open_two()
        s1.temp_path = 12345            # unlink 가 TypeError 를 던지는 값
        s1.cleanup()                    # 예외가 새면 이 줄에서 터진다


class FallbackSessionTest(unittest.TestCase):
    r"""open 이 새 탭을 안 쓴 예비 경로 — 저장은 살리고, 닫기만 막는다.

    2026-07-31 후속 수리(리뷰 지적): 이 경로가 doc=None 세션을 돌려주면
    activate 방어(①)에 걸려 저장이 **영영** 막혔다. 지금 활성 문서는 방금
    open 한 사본이므로 그것을 세션에 담고, own_tab=False 로 닫기만 금지한다.
    """

    def setUp(self):
        self.src = pathlib.Path(__file__).with_name("_fallback_form.hwp")
        self.src.write_bytes(b"fake form")
        self.work = pathlib.Path(__file__).with_name("_fallback_work")
        mock.patch.object(engine_library.paths, "data_dir",
                          lambda: self.work).start()

    def tearDown(self):
        mock.patch.stopall()
        self.src.unlink(missing_ok=True)
        if self.work.exists():
            for p in sorted(self.work.rglob("*"), reverse=True):
                if p.is_file():
                    p.unlink(missing_ok=True)

    def _open_fallback(self):
        """open 이 새 탭을 늘리지 못한 상황을 흉내 내 세션을 연다."""
        fake = FakeHwp()

        class NoGrowDocs(FakeDocs):
            def Add(self, _kind):
                doc = super().Add(_kind)
                self.Count -= 1          # 새 탭이 안 생긴 상황을 흉내
                return doc
        fake.XHwpDocuments = NoGrowDocs()
        _install(fake)
        return fake, engine_library.open_form_copy(self.src, None)

    def test_예비_세션도_활성화가_된다(self):
        r"""핵심 회귀 테스트 — doc=None 이면 저장 전 activate 가 항상 실패했다."""
        _fake, session = self._open_fallback()
        self.assertIsNotNone(session.doc)
        self.assertTrue(session.activate(), "예비 세션의 저장이 영영 막힌다")

    def test_예비_세션은_사용자_탭일_수_있는_문서를_닫지_않는다(self):
        _fake, session = self._open_fallback()
        self.assertFalse(session.own_tab)
        self.assertFalse(session.close())
        self.assertFalse(session.doc.closed, "사용자 탭일 수 있는 문서를 닫았다")

    def test_마무리는_탭을_안_닫아도_사본은_지운다(self):
        _fake, session = self._open_fallback()
        with mock.patch.object(engine_library, "strip_marks", lambda *a: 0), \
             mock.patch.object(engine_library.preview, "save_cache",
                               return_value=True):
            _ok, closed = engine_library.finish_edit_session(session, "fb1")
        self.assertFalse(closed, "탭을 닫지 않았다고 알려야 한다")
        self.assertFalse(session.doc.closed, "닫으면 안 되는 탭을 닫았다")
        self.assertFalse(pathlib.Path(session.temp_path).exists(),
                         "편집중_*.hwp 사본이 남았다")

    def test_문서_객체가_정말_없으면_activate_는_조용히_False(self):
        r"""AttributeError 를 삼키는 우회가 아니라 명시적 False 여야 한다."""
        self.assertFalse(engine_library.EditSession(None).activate())


class CursorRestoreTest(unittest.TestCase):
    r"""④ 삽입이 터져도 커서는 문서 끝에 남지 않는다 (doc_end_para 복원쌍)."""

    def tearDown(self):
        mock.patch.stopall()

    def test_삽입_중_예외에도_커서를_제자리로_되돌린다(self):
        fake = FakeHwp()
        set_calls = []
        fake.SetPos = lambda *pos: set_calls.append(pos)
        _install(fake)
        mock.patch.object(engine_library.hwp_engine, "doc_end_para",
                          return_value=7).start()

        def boom():
            raise RuntimeError("삽입 실패")
        with self.assertRaises(RuntimeError):
            engine_library.measure_insert_span((0, 3, 0), boom)
        self.assertEqual(set_calls[-1], (0, 3, 0),
                         "커서가 문서 끝에 남았다 — 마지막 복원이 빠졌다")

    def test_정상_경로_계산은_그대로다(self):
        fake = FakeHwp()
        fake.SetPos = lambda *pos: None
        _install(fake)
        mock.patch.object(engine_library.hwp_engine, "doc_end_para",
                          side_effect=[1, 3]).start()
        end = engine_library.measure_insert_span((0, 0, 0), lambda: None)
        self.assertEqual(end, 2)         # 0 + (3-1)


if __name__ == "__main__":
    unittest.main()
