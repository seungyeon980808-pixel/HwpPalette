# -*- coding: utf-8 -*-
r"""파일 캐시 회귀 테스트 (2026-07-28, 버벅임 1단계).

여태 config.json/library.json 은 **매 호출마다** 읽고 파싱됐다 — 상호작용
한 번에 수십 번. mtime 캐시를 얹으면서 지켜야 할 약속 세 가지:

  ① 파일이 안 바뀌면 다시 읽지 않는다 (이게 목적)
  ② 파일이 바뀌면(다른 프로세스 포함) 다음 호출이 바로 알아챈다
  ③ 돌려준 값은 **사본**이다 — 호출부가 고쳐도 저장 없이는 아무 데도 안 샌다
     (캐시 공유로 "저장 안 했는데 반영되는" 새 버그가 생기면 안 된다)
"""

import json
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.model import library      # noqa: E402
from hwp_palette.model import palette      # noqa: E402
from hwp_palette.core import settings     # noqa: E402


def _touch_newer(path):
    """mtime 을 확실히 다르게 만든다 (같은 초 안에 두 번 쓰는 경우 대비)."""
    st = path.stat()
    import os
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))


class SettingsCacheTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = pathlib.Path(self.tmp.name) / "config.json"
        self.cfg.write_text(json.dumps({"a": 1, "tabs": [{"n": "x"}]}),
                            encoding="utf-8")
        mock.patch.object(settings, "CONFIG_PATH", self.cfg).start()
        settings._cfg_cache["tok"] = None       # 이전 테스트의 캐시 격리
        settings._cfg_cache["data"] = None

    def tearDown(self):
        mock.patch.stopall()
        settings._cfg_cache["tok"] = None
        settings._cfg_cache["data"] = None
        self.tmp.cleanup()

    def test_같은_파일이면_다시_읽지_않는다(self):
        settings.load_config()
        with mock.patch.object(settings.json, "loads",
                               side_effect=AssertionError("다시 파싱했다")):
            self.assertEqual(settings.load_config()["a"], 1)

    def test_파일이_바뀌면_바로_알아챈다(self):
        settings.load_config()
        self.cfg.write_text(json.dumps({"a": 2}), encoding="utf-8")
        _touch_newer(self.cfg)
        self.assertEqual(settings.load_config()["a"], 2)

    def test_save_config_가_캐시를_함께_갱신한다(self):
        settings.load_config()
        settings.save_config({"a": 3})
        with mock.patch.object(settings.json, "loads",
                               side_effect=AssertionError("다시 파싱했다")):
            self.assertEqual(settings.load_config()["a"], 3)

    def test_get_config_value_는_사본을_준다(self):
        got = settings.get_config_value("tabs")
        got[0]["n"] = "오염"
        self.assertEqual(settings.get_config_value("tabs")[0]["n"], "x",
                         "돌려준 값을 고쳤더니 캐시가 오염됐다")

    def test_set_config_value_왕복(self):
        settings.set_config_value("b", {"k": [1, 2]})
        self.assertEqual(settings.get_config_value("b"), {"k": [1, 2]})
        self.assertEqual(json.loads(self.cfg.read_text(encoding="utf-8"))["b"],
                         {"k": [1, 2]}, "파일에도 저장돼야 한다")


class PaletteTabsCacheTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = pathlib.Path(self.tmp.name) / "config.json"
        self.cfg.write_text("{}", encoding="utf-8")
        mock.patch.object(settings, "CONFIG_PATH", self.cfg).start()
        settings._cfg_cache["tok"] = None
        settings._cfg_cache["data"] = None
        palette._tabs_cache["tok"] = None
        palette._tabs_cache["tabs"] = None

    def tearDown(self):
        mock.patch.stopall()
        settings._cfg_cache["tok"] = None
        settings._cfg_cache["data"] = None
        palette._tabs_cache["tok"] = None
        palette._tabs_cache["tabs"] = None
        self.tmp.cleanup()

    def test_두_번째_호출은_캐시를_쓴다(self):
        palette.load_tabs()                      # 시드 생성 + 캐시
        with mock.patch.object(settings.json, "loads",
                               side_effect=AssertionError("다시 파싱했다")):
            tabs = palette.load_tabs()
        self.assertTrue(tabs)

    def test_돌려준_탭은_사본이다(self):
        r"""핵심 회귀 — 호출부가 고친 것이 저장 없이 다음 호출에 새면 안 된다."""
        tabs = palette.load_tabs()
        tabs[0]["name"] = "오염"
        tabs[0]["blocks"].append({"type": "char", "value": "!"})
        again = palette.load_tabs()
        self.assertNotEqual(again[0].get("name"), "오염")

    def test_save_tabs_뒤에는_새_값이_보인다(self):
        tabs = palette.load_tabs()
        tabs[0]["cols"] = 17
        palette.save_tabs(tabs, _record=False)
        self.assertEqual(palette.load_tabs()[0]["cols"], 17)


class LibraryCacheTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.lib = root / "library.json"
        self.lib.write_text(json.dumps(
            {"템플릿": [{"id": "aaa", "name": "표", "label": "표", "tags": [],
                        "file": "aaa.hwp", "slot_count": 0, "slot_names": []}]},
            ensure_ascii=False), encoding="utf-8")
        mock.patch.object(library, "LIBRARY_PATH", self.lib).start()
        mock.patch.object(library, "FRAGMENTS_DIR", root / "fragments").start()
        library._load_cache["tok"] = None
        library._load_cache["data"] = None

    def tearDown(self):
        mock.patch.stopall()
        library._load_cache["tok"] = None
        library._load_cache["data"] = None
        self.tmp.cleanup()

    def test_같은_파일이면_다시_읽지_않는다(self):
        library.load()
        with mock.patch.object(library.json, "loads",
                               side_effect=AssertionError("다시 파싱했다")):
            self.assertEqual(library.list_items("템플릿")[0]["name"], "표")

    def test_파일이_바뀌면_알아챈다(self):
        library.load()
        data = json.loads(self.lib.read_text(encoding="utf-8"))
        data["템플릿"][0]["name"] = "새이름"
        self.lib.write_text(json.dumps(data, ensure_ascii=False),
                            encoding="utf-8")
        _touch_newer(self.lib)
        self.assertEqual(library.list_items("템플릿")[0]["name"], "새이름")

    def test_돌려준_목록은_사본이다(self):
        library.list_items("템플릿")[0]["name"] = "오염"
        self.assertEqual(library.list_items("템플릿")[0]["name"], "표")

    def test_update_item_왕복(self):
        library.update_item("템플릿", "aaa", name="고침", label="고침", tags=[])
        self.assertEqual(library.find_by_id("템플릿", "aaa")["name"], "고침")
        on_disk = json.loads(self.lib.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["템플릿"][0]["name"], "고침")


if __name__ == "__main__":
    unittest.main()
