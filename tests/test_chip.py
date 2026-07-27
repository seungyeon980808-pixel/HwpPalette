# -*- coding: utf-8 -*-
r"""칩 — 팔레트를 물감째 넘기기 (사용자 기획 2026-07-26, 구현 2026-07-27).

핵심 회귀: **받은 뒤에도 버튼이 물감을 제대로 가리키는가.**
물감은 받는 쪽에서 새 id 를 받는다(같은 id 가 두 개면 참조가 엉킨다).
그래서 블럭의 `ref` 를 새 id 로 갈아끼우지 않으면 버튼이 전부 죽는다.
"""

import json
import pathlib
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import chip                  # noqa: E402
import library               # noqa: E402
import palette               # noqa: E402


class ChipTestCase(unittest.TestCase):
    """A선생(보내는 쪽)과 B선생(받는 쪽)의 저장소를 갈아끼우며 쓴다."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self._use("A")

    def tearDown(self):
        self._stop()
        self._tmp.cleanup()

    def _stop(self):
        for p in getattr(self, "_patches", []):
            p.stop()
        self._patches = []

    def _use(self, who):
        """그 사람의 library.json / config.json 으로 갈아끼운다."""
        self._stop()
        home = self.root / who
        home.mkdir(parents=True, exist_ok=True)
        self._tabs = getattr(self, "_all_tabs", {}).setdefault(who, [])
        self._patches = [
            mock.patch.object(library, "LIBRARY_PATH", home / "library.json"),
            mock.patch.object(library, "FRAGMENTS_DIR", home / "fragments"),
            mock.patch.object(palette, "load_tabs",
                              side_effect=lambda: json.loads(
                                  json.dumps(self._tabs))),
            mock.patch.object(palette, "save_tabs",
                              side_effect=self._save_tabs),
        ]
        for p in self._patches:
            p.start()

    def _save_tabs(self, tabs, _record=True):
        self._tabs[:] = json.loads(json.dumps(tabs))

    _all_tabs = None

    def setUpTabs(self):
        pass

    def _make_template(self, name, body="표"):
        """조각 파일까지 갖춘 템플릿 하나를 등록한다."""
        def save_to(dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body.encode("utf-8"))
            return body
        return library.add_template_from_capture(name, save_to, slot_count=1)


class _Base(ChipTestCase):
    def setUp(self):
        self._all_tabs = {}
        super().setUp()


class ExportTest(_Base):

    def test_탭이_쓰는_물감만_담긴다(self):
        """고르게 하지 않는다 — ref 를 훑으면 필요한 것이 정해져 있다."""
        a = self._make_template("소1사진")
        self._make_template("안 쓰는 템플릿")
        tab = {"name": "수능", "cols": 8, "blocks": [
            {"type": "template", "ref": a, "template": "소1사진"},
            {"type": "char", "value": "√"},
        ]}
        pairs = chip.required_items(tab)
        self.assertEqual([it["name"] for _cat, it in pairs], ["소1사진"])

    def test_같은_물감을_두_번_써도_한_번만(self):
        a = self._make_template("소1사진")
        tab = {"name": "수능", "blocks": [
            {"type": "template", "ref": a, "template": "소1사진"},
            {"type": "template", "ref": a, "template": "소1사진"},
        ]}
        self.assertEqual(len(chip.required_items(tab)), 1)

    def test_없는_물감을_가리키면_알려준다(self):
        tab = {"name": "수능", "blocks": [
            {"type": "template", "ref": "없는id", "template": "사라진표"}]}
        self.assertEqual(chip.missing_refs(tab), ["사라진표"])

    def test_칩에_탭과_물감이_함께_들어간다(self):
        a = self._make_template("소1사진")
        tab = {"name": "수능", "cols": 8, "blocks": [
            {"type": "template", "ref": a, "template": "소1사진"}]}
        dest = self.root / f"수능{chip.CHIP_EXT}"
        chip.export_tab(tab, dest, note="설명", author="A선생")
        with zipfile.ZipFile(dest) as zf:
            names = zf.namelist()
        self.assertIn("chip.json", names)
        self.assertIn("tab.json", names)
        self.assertIn("library.json", names)
        self.assertTrue(any(n.startswith("fragments/") for n in names))

    def test_물감_꾸러미는_탭이_없다(self):
        """같은 형식, 입구만 둘 — tab.json 이 없으면 물감 꾸러미."""
        self._make_template("소1사진")
        dest = self.root / f"물감{chip.CHIP_EXT}"
        chip.export_items([("템플릿", library.list_items("템플릿")[0])],
                          dest, name="내 템플릿")
        with zipfile.ZipFile(dest) as zf:
            self.assertNotIn("tab.json", zf.namelist())


class InstallTest(_Base):

    def _make_chip(self):
        """A선생이 템플릿 2개 + 특수기호 블럭이 든 탭을 칩으로 만든다."""
        self._use("A")
        a = self._make_template("소1사진", body="소1")
        b = self._make_template("대1사진", body="대1")
        library.update_item("템플릿", a, tags="수능")     # 태그는 안 넘어가야 한다
        tab = {"name": "수능", "cols": 8, "blocks": [
            {"type": "template", "ref": a, "template": "소1사진",
             "row": 0, "col": 0, "span": 2},
            {"type": "template", "ref": b, "template": "대1사진",
             "row": 0, "col": 2, "span": 2},
            {"type": "char", "value": "√", "row": 1, "col": 0},
            {"type": "builtin", "key": "convert", "row": 1, "col": 1},
        ]}
        dest = self.root / f"수능{chip.CHIP_EXT}"
        chip.export_tab(tab, dest, author="A선생")
        return dest, tab

    def test_받은_버튼이_받은_물감을_가리킨다(self):
        """**핵심 회귀** — ref 재연결이 안 되면 버튼이 전부 죽는다."""
        dest, _tab = self._make_chip()
        self._use("B")
        out = chip.install(dest)

        self.assertEqual(out["tab_name"], "수능")
        self.assertEqual(out["lost"], 0)
        tab = palette.load_tabs()[0]
        got = {it["name"]: it["id"] for it in library.list_items("템플릿")}
        for block in tab["blocks"]:
            if block["type"] == "template":
                self.assertEqual(block["ref"], got[block["template"]],
                                 f"{block['template']} 의 ref 가 안 이어졌다")

    def test_물감을_가리키지_않는_블럭은_그대로(self):
        dest, _tab = self._make_chip()
        self._use("B")
        chip.install(dest)
        blocks = palette.load_tabs()[0]["blocks"]
        self.assertEqual([b for b in blocks if b["type"] == "char"],
                         [{"type": "char", "value": "√", "row": 1, "col": 0}])
        self.assertTrue(any(b["type"] == "builtin" for b in blocks))

    def test_배치가_그대로_따라온다(self):
        """배치가 곧 전달할 가치다 — 좌표가 틀어지면 보낸 뜻이 없다."""
        dest, tab = self._make_chip()
        self._use("B")
        chip.install(dest)
        got = palette.load_tabs()[0]
        self.assertEqual(got["cols"], tab["cols"])
        for before, after in zip(tab["blocks"], got["blocks"]):
            for key in ("row", "col", "span", "type"):
                self.assertEqual(before.get(key), after.get(key))

    def test_받은_물감은_태그_없이_출처만(self):
        dest, _tab = self._make_chip()
        self._use("B")
        chip.install(dest)
        for it in library.list_items("템플릿"):
            self.assertEqual(it["tags"], [])
            self.assertEqual(it["from_chip"], "수능")

    def test_내_것을_덮어쓰지_않는다(self):
        """B선생에게 이미 같은 이름·같은 탭 이름이 있어도 살아 있어야 한다."""
        dest, _tab = self._make_chip()
        self._use("B")
        mine = self._make_template("소1사진", body="내 것")
        self._save_tabs([{"name": "수능", "cols": 8, "blocks": []}])

        out = chip.install(dest)
        names = [it["name"] for it in library.list_items("템플릿")]
        self.assertIn("소1사진", names)              # 내 것 그대로
        self.assertEqual(len(names), 3)              # 받은 2개가 더해짐
        self.assertEqual(library.find_by_id("템플릿", mine)["name"], "소1사진")
        self.assertEqual(out["tab_name"], "수능 (2)")   # 내 탭도 그대로
        self.assertEqual([t["name"] for t in palette.load_tabs()],
                         ["수능", "수능 (2)"])

    def test_같은_칩을_두_번_받아도_물감은_한_벌(self):
        """탭만 하나 더 생기고, 그 탭은 먼저 받은 물감을 가리킨다."""
        dest, _tab = self._make_chip()
        self._use("B")
        chip.install(dest)
        first = {it["id"] for it in library.list_items("템플릿")}

        out = chip.install(dest)
        self.assertEqual(out["added"], 0)
        self.assertEqual(out["reused"], 2)
        self.assertEqual(len(library.list_items("템플릿")), 2)   # 안 늘어남
        for block in palette.load_tabs()[1]["blocks"]:
            if block["type"] == "template":
                self.assertIn(block["ref"], first)

    def test_물감_꾸러미는_탭을_만들지_않는다(self):
        self._use("A")
        self._make_template("소1사진")
        dest = self.root / f"물감{chip.CHIP_EXT}"
        chip.export_items([("템플릿", library.list_items("템플릿")[0])],
                          dest, name="내 템플릿")
        self._use("B")
        out = chip.install(dest)
        self.assertIsNone(out["tab_name"])
        self.assertEqual(out["added"], 1)
        self.assertEqual(palette.load_tabs(), [])


class PeekTest(_Base):
    """등록 **전에** 무엇이 들어오고 무엇과 겹치는지 보여줄 수 있는가."""

    def _chip(self):
        self._use("A")
        a = self._make_template("소1사진")
        tab = {"name": "수능", "cols": 8, "blocks": [
            {"type": "template", "ref": a, "template": "소1사진"}]}
        dest = self.root / f"수능{chip.CHIP_EXT}"
        chip.export_tab(tab, dest, note="수능형 문항용", author="A선생")
        return dest

    def test_아무것도_바꾸지_않는다(self):
        dest = self._chip()
        self._use("B")
        before = library.load()
        chip.peek(dest)
        self.assertEqual(library.load(), before)
        self.assertEqual(palette.load_tabs(), [])

    def test_표지를_읽는다(self):
        dest = self._chip()
        self._use("B")
        info = chip.peek(dest)
        self.assertEqual(info["name"], "수능")
        self.assertEqual(info["note"], "수능형 문항용")
        self.assertEqual(info["author"], "A선생")
        self.assertEqual(len(info["items"]), 1)
        self.assertEqual(info["tab"]["name"], "수능")

    def test_충돌을_미리_알려준다(self):
        dest = self._chip()
        self._use("B")
        self._make_template("소1사진")
        self._save_tabs([{"name": "수능", "cols": 8, "blocks": []}])
        c = chip.peek(dest)["conflicts"]
        self.assertEqual(c["names"], ["소1사진"])
        self.assertEqual(c["labels"], ["소1사진"])
        self.assertEqual(c["tab"], "수능")

    def test_이미_받은_칩이면_알려준다(self):
        dest = self._chip()
        self._use("B")
        chip.install(dest)
        self.assertEqual(chip.peek(dest)["known"], 1)


class ReportedCountTest(_Base):
    r"""내보낸 개수를 **실제로 담긴 수**로 보고하는가 (2026-07-27).

    조각 파일이 사라진 항목은 library 쪽에서 건너뛴다. 고른 개수를 그대로
    보고하면 "5개 보냈다"고 해 놓고 4개만 간 것을 아무도 모른다.
    """

    def test_조각이_사라진_항목은_개수에서_빠진다(self):
        a = self._make_template("멀쩡한표")
        b = self._make_template("조각잃은표")
        # 조각 파일만 지운다 (목록에는 남아 있는 상태)
        lost = library.find_by_id("템플릿", b)
        (library.FRAGMENTS_DIR / lost["file"]).unlink()

        dest = self.root / f"물감{chip.CHIP_EXT}"
        pairs = [("템플릿", library.find_by_id("템플릿", x)) for x in (a, b)]
        with mock.patch("library.applog.warn"):
            r = chip.export_items(pairs, dest, name="물감")
        self.assertEqual(r["items"], 1, "담긴 개수를 그대로 보고해야 한다")

    def test_팔레트도_실제로_담긴_수를_보고한다(self):
        a = self._make_template("멀쩡한표")
        b = self._make_template("조각잃은표")
        lost = library.find_by_id("템플릿", b)
        (library.FRAGMENTS_DIR / lost["file"]).unlink()
        tab = {"name": "수능", "cols": 8, "blocks": [
            {"type": "template", "ref": a, "template": "멀쩡한표"},
            {"type": "template", "ref": b, "template": "조각잃은표"}]}
        dest = self.root / f"수능{chip.CHIP_EXT}"
        with mock.patch("library.applog.warn"):
            r = chip.export_tab(tab, dest)
        self.assertEqual(r["items"], 1)
        self.assertEqual(r["blocks"], 2, "버튼 수는 배치 그대로다")


class MixedInstallTest(_Base):
    r"""물감 파일과 팔레트 파일을 **차례로** 받는 실제 상황 (2026-07-27).

    '물감 보내기'로 몇 개를 먼저 받고, 나중에 그 물감을 쓰는 '팔레트 보내기'
    파일을 받으면 — 물감이 두 벌 생기면 안 되고, 팔레트는 먼저 받은 물감을
    가리켜야 한다.
    """

    def test_먼저_받은_물감에_팔레트가_이어붙는다(self):
        self._use("A")
        a = self._make_template("소1사진", body="소1")
        b = self._make_template("대1사진", body="대1")
        tab = {"name": "수능", "cols": 8, "blocks": [
            {"type": "template", "ref": a, "template": "소1사진"},
            {"type": "template", "ref": b, "template": "대1사진"}]}
        paints = self.root / f"물감{chip.CHIP_EXT}"
        chip.export_items([("템플릿", library.find_by_id("템플릿", a))],
                          paints, name="물감 몇 개")
        pal = self.root / f"수능{chip.CHIP_EXT}"
        chip.export_tab(tab, pal)

        self._use("B")
        chip.install(paints)          # 소1사진만 먼저 받는다
        first = {it["name"]: it["id"] for it in library.list_items("템플릿")}
        self.assertEqual(list(first), ["소1사진"])

        out = chip.install(pal)       # 그 물감을 쓰는 팔레트를 받는다
        self.assertEqual(out["reused"], 1, "이미 있는 소1사진을 또 만들면 안 된다")
        self.assertEqual(out["added"], 1, "대1사진만 새로 들어와야 한다")
        self.assertEqual(len(library.list_items("템플릿")), 2)
        self.assertEqual(out["lost"], 0)

        got = {it["id"]: it["name"] for it in library.list_items("템플릿")}
        blocks = palette.load_tabs()[0]["blocks"]
        by_name = {b["template"]: b["ref"] for b in blocks}
        self.assertEqual(by_name["소1사진"], first["소1사진"],
                         "먼저 받아 둔 물감을 가리켜야 한다")
        self.assertEqual(got[by_name["대1사진"]], "대1사진")


class RelinkTest(unittest.TestCase):
    """ref 갈아끼우기 자체 — 칩 없이도 검사되는 순수 함수."""

    def test_대응표대로_바꾼다(self):
        blocks = [{"type": "template", "ref": "old"}]
        out, lost = chip.relink(blocks, {"old": "new"})
        self.assertEqual(out[0]["ref"], "new")
        self.assertEqual(lost, 0)

    def test_원본을_건드리지_않는다(self):
        blocks = [{"type": "template", "ref": "old"}]
        chip.relink(blocks, {"old": "new"})
        self.assertEqual(blocks[0]["ref"], "old")

    def test_못_이은_블럭은_버리지_않고_센다(self):
        """지우면 배치에 구멍이 생겨 무엇이 빠졌는지도 모른다."""
        blocks = [{"type": "template", "ref": "old", "template": "표"}]
        with mock.patch("chip.applog.warn"):
            out, lost = chip.relink(blocks, {})
        self.assertEqual(len(out), 1)
        self.assertEqual(lost, 1)

    def test_ref가_없는_블럭은_그대로(self):
        blocks = [{"type": "char", "value": "√"},
                  {"type": "builtin", "key": "convert"},
                  {"type": "function", "actions": [{"func": "굵게"}]}]
        out, lost = chip.relink(blocks, {})
        self.assertEqual(out, blocks)
        self.assertEqual(lost, 0)


if __name__ == "__main__":
    unittest.main()
