# -*- coding: utf-8 -*-
r"""안내문 걷어내기 — 접힌 줄의 꼬리를 남기지 않는다 (2026-07-27).

사용자 지적: **"들어가면 안 되는 단어(`다.`)가 템플릿에 남는다.
수정해서 지워도 계속 남아 있다."**

실측으로 확인한 원인:
    `strip_edit_note` 가 `MoveSelLineEnd` 로 "그 줄 끝까지" 지웠다. 그런데
    한글의 '줄'은 문단이 아니라 **화면에서 접힌 한 줄**이다. 안내 첫 문장
    "…여기서 고칩니다." 가 두 줄로 접히는 문서(글씨가 큰 조각)에서는 앞부분만
    지워지고 꼬리 `다.` 가 문단으로 남았다.

    더 나빴던 것: 그 꼬리가 **저장할 때마다 새로 하나씩 생겼다.** 손으로
    지워도 다음 저장에서 또 만들어지니 "지웠는데 계속 남는다"가 됐다.
    실측(지문박스) — 지금 코드: `다.` 2개, 고친 방식: 새로 안 생김.

    `DeleteBack` 도 문제였다. 커서 앞 글자를 지우는 명령이라 안내가 본문과
    같은 문단에 걸리면 **본문 글자를 먹었다** (실측: '진짜본문내용' →
    '진짜본문내').

여기서 지키려는 것:
    안내 문단은 **통째로** 걷히고, 본문은 한 글자도 다치지 않는다.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import engine_library        # noqa: E402

MARK = engine_library.EDIT_NOTE_MARK


class FakeParaHwp:
    r"""문단 배열로 흉내 낸 한글 — **줄 접힘**까지 흉내 낸다.

    wrap_at: 한 화면 줄에 들어가는 글자 수. 이보다 긴 문단은 접힌다.
    커서는 (문단 index, 글자 offset).
    """

    def __init__(self, paragraphs, wrap_at=40):
        self.paras = list(paragraphs)
        self.wrap_at = wrap_at
        self.cur = [0, 0]

    # ── 이동 ──
    def MoveDocBegin(self):
        self.cur = [0, 0]

    def MoveDocEnd(self):
        self.cur = [len(self.paras) - 1, len(self.paras[-1])]

    def GetTextFile(self, *_a, **_kw):
        return "\n".join(self.paras)

    def find(self, query):
        """찾으면 커서를 그 글자 **뒤**에 놓는다 (실제 find_text 와 같다)."""
        for i in range(len(self.paras)):
            j = self.paras[i].find(query)
            if j >= 0:
                self.cur = [i, j + len(query)]
                return True
        return False

    # ── HAction.Run 이 부르는 것들 ──
    def _line_end(self):
        """지금 커서가 있는 **화면 줄**의 끝 offset (접힘 반영)."""
        p, off = self.cur
        line_no = off // self.wrap_at
        return min((line_no + 1) * self.wrap_at, len(self.paras[p]))

    def run(self, cmd):
        p, off = self.cur
        if cmd == "MoveParaBegin":
            self.cur = [p, 0]
        elif cmd == "MoveSelParaEnd":
            self._sel = (p, off, p, len(self.paras[p]))
        elif cmd == "MoveSelLineEnd":
            self._sel = (p, off, p, self._line_end())
        elif cmd == "MoveSelNextParaBegin":
            self._sel = (p, off, p + 1, 0)
        elif cmd == "Delete":
            self._delete_selection()
        elif cmd == "DeleteBack":
            if off > 0:
                self.paras[p] = self.paras[p][:off - 1] + self.paras[p][off:]
                self.cur = [p, off - 1]
            elif p > 0:                      # 앞 문단과 합쳐진다
                prev = len(self.paras[p - 1])
                self.paras[p - 1] += self.paras[p]
                del self.paras[p]
                self.cur = [p - 1, prev]

    def _delete_selection(self):
        sel = getattr(self, "_sel", None)
        if not sel:
            return
        p0, o0, p1, o1 = sel
        if p0 == p1:
            self.paras[p0] = self.paras[p0][:o0] + self.paras[p0][o1:]
        else:
            head = self.paras[p0][:o0]
            tail = self.paras[p1][o1:] if p1 < len(self.paras) else ""
            self.paras[p0:p1 + 1] = [head + tail]
        self.cur = [p0, o0]
        self._sel = None

    @property
    def HAction(self):
        outer = self

        class _A:
            def Run(self, cmd):
                outer.run(cmd)
        return _A()


def _install(fake):
    mock.patch.object(engine_library, "_h", lambda: fake).start()
    mock.patch.object(engine_library.hwp_engine, "find_text",
                      lambda q, **kw: fake.find(q)).start()


# 실제 안내문 첫 줄과 같은 길이 — 접히는 것이 핵심이라 짧게 줄이면 안 된다
LONG_NOTE = MARK + "이 문서를 원하는 대로 고치세요 — 글자·표·빈칸 모두 여기서 고칩니다."
SHORT_NOTE = MARK + "(이 안내 줄들은 저장할 때 자동으로 빠집니다)"


class StripEditNoteTest(unittest.TestCase):

    def tearDown(self):
        mock.patch.stopall()

    def test_접힌_안내_문단의_꼬리를_남기지_않는다(self):
        r"""핵심 회귀 테스트 — 남던 그 `다.` 다."""
        fake = FakeParaHwp([LONG_NOTE, SHORT_NOTE, "", "진짜 본문"], wrap_at=40)
        _install(fake)
        engine_library.strip_edit_note()
        self.assertEqual(fake.paras, ["진짜 본문"],
                         f"안내 꼬리가 남았다: {fake.paras}")

    def test_짧아서_안_접히는_안내도_지운다(self):
        fake = FakeParaHwp([SHORT_NOTE, "", "진짜 본문"], wrap_at=200)
        _install(fake)
        engine_library.strip_edit_note()
        self.assertEqual(fake.paras, ["진짜 본문"])

    def test_본문_글자를_먹지_않는다(self):
        r"""DeleteBack 이 커서 앞 글자를 지워 본문을 갉던 문제."""
        fake = FakeParaHwp([LONG_NOTE, "본문 첫 줄", "본문 둘째 줄"], wrap_at=40)
        _install(fake)
        engine_library.strip_edit_note()
        self.assertIn("본문 첫 줄", fake.paras)
        self.assertIn("본문 둘째 줄", fake.paras)

    def test_안내가_없으면_아무것도_건드리지_않는다(self):
        fake = FakeParaHwp(["본문만 있다", "", "둘째 줄"], wrap_at=40)
        _install(fake)
        self.assertEqual(engine_library.strip_edit_note(), 0)
        self.assertEqual(fake.paras, ["본문만 있다", "", "둘째 줄"])

    def test_안내와_본문_사이_빈_줄을_하나만_걷는다(self):
        r"""_insert_edit_note 가 넣는 빈 줄은 하나 — 안 걷으면 저장할 때마다 쌓인다."""
        fake = FakeParaHwp([LONG_NOTE, "", "", "본문"], wrap_at=40)
        _install(fake)
        engine_library.strip_edit_note()
        # 우리가 넣은 빈 줄 하나만 걷고, 조각이 원래 갖던 빈 줄은 남긴다
        self.assertEqual(fake.paras, ["", "본문"])

    def test_저장을_여러_번_해도_쌓이지_않는다(self):
        r"""고치기→저장을 두 번 해도 문서가 그대로여야 한다."""
        body = ["본문", "둘째"]
        fake = FakeParaHwp(list(body), wrap_at=40)
        _install(fake)
        for _ in range(2):
            fake.paras = [LONG_NOTE, SHORT_NOTE, ""] + fake.paras   # 안내 붙이기
            engine_library.strip_edit_note()                        # 저장 직전
        self.assertEqual(fake.paras, body, f"쌓였다: {fake.paras}")


class WrapFakeSanityTest(unittest.TestCase):
    """가짜가 '줄 접힘'을 실제로 흉내 내는지 — 아니면 위 테스트가 무의미하다."""

    def tearDown(self):
        mock.patch.stopall()

    def test_옛_방식이라면_꼬리가_남는다(self):
        fake = FakeParaHwp([LONG_NOTE, "본문"], wrap_at=40)
        _install(fake)
        fake.find(MARK)
        fake.run("MoveSelLineEnd")
        fake.run("Delete")
        self.assertTrue(fake.paras[0], "가짜가 접힘을 흉내 내지 못한다 — 테스트 무효")
        self.assertNotIn("본문", fake.paras[0])


if __name__ == "__main__":
    unittest.main()
