# -*- coding: utf-8 -*-
r"""'도구' 블럭 (프로그램 기능) — 한글·창 없이 검증 (2026-07-25).

사진·특수문자·양식 채우기는 예전에 메인 화면에 코드로 박혀 있었다. 이제 블럭이
되어 사용자가 빼거나 옮길 수 있는데, 그 이관에 두 가지 함정이 있다:
  · 첫 실행에 안 깔면 → 쓰던 기능이 사라진다
  · 매번 깔면       → 사용자가 지운 것이 계속 되살아난다
그래서 '딱 한 번' 깔리는지를 여기서 못박는다.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import builtin_actions        # noqa: E402
import palette                # noqa: E402


class CatalogTest(unittest.TestCase):

    def test_키는_중복되지_않는다(self):
        keys = [a["key"] for a in builtin_actions.BUILTIN_ACTIONS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_기본_도구는_모두_카탈로그에_있다(self):
        for key in builtin_actions.DEFAULT_MAIN_KEYS:
            self.assertIn(key, builtin_actions.ACTION_BY_KEY, key)

    def test_모르는_키는_키를_그대로_보여준다(self):
        # 옛 config 에 사라진 키가 남아 있어도 화면이 깨지지 않아야 한다
        self.assertEqual(builtin_actions.name_of("없는키"), "없는키")
        self.assertEqual(builtin_actions.hint_of("없는키"), "")

    def test_이름과_설명이_비어_있지_않다(self):
        for a in builtin_actions.BUILTIN_ACTIONS:
            self.assertTrue(a["name"].strip(), a["key"])
            self.assertTrue(a["hint"].strip(), a["key"])


class SeedMainToolsTest(unittest.TestCase):
    """첫 실행에 '메인' 탭으로 기본 도구를 옮기는 이관."""

    def _run(self, tabs, already_seeded=False):
        store = {palette.MAIN_TOOLS_SEEDED_KEY: already_seeded}
        with mock.patch.object(palette.settings, "get_config_value",
                               side_effect=lambda k, d=None: store.get(k, d)), \
             mock.patch.object(palette.settings, "set_config_value",
                               side_effect=lambda k, v: store.update({k: v})):
            changed = palette._seed_main_tools(tabs)
        return changed, store

    def _main(self, blocks=None):
        return [{"name": palette.MAIN_TAB, "cols": 8,
                 "blocks": list(blocks or [])}]

    def test_빈_메인탭에_기본_도구를_깐다(self):
        tabs = self._main()
        changed, store = self._run(tabs)
        self.assertTrue(changed)
        keys = [b["key"] for b in tabs[0]["blocks"]]
        self.assertEqual(keys, list(builtin_actions.DEFAULT_MAIN_KEYS))
        self.assertTrue(store[palette.MAIN_TOOLS_SEEDED_KEY])

    def test_이미_블럭이_있어도_기존_것을_지우지_않는다(self):
        # 여기서 건너뛰면 쓰던 기능이 사라진다 (실제로 한 번 그랬다)
        mine = {"type": "function", "name": "글씨체", "span": 2,
                "row": 0, "col": 0}
        tabs = self._main([mine])
        self._run(tabs)
        blocks = tabs[0]["blocks"]
        self.assertIn(mine, blocks)                       # 내 블럭 그대로
        keys = [b.get("key") for b in blocks if b["type"] == "builtin"]
        self.assertEqual(keys, list(builtin_actions.DEFAULT_MAIN_KEYS))

    def test_깔린_도구는_서로_겹치지_않는다(self):
        tabs = self._main([{"type": "function", "name": "글씨체", "span": 2,
                            "rows": 1, "row": 0, "col": 0}])
        self._run(tabs)
        blocks = tabs[0]["blocks"]
        cells = palette.occupied_cells(blocks)
        total = sum(int(b.get("span", 1)) * int(b.get("rows", 1))
                    for b in blocks)
        self.assertEqual(len(cells), total)   # 겹치면 칸 수가 모자란다

    def test_이미_깔았으면_다시_안_깐다(self):
        # 사용자가 지운 도구가 다음 실행에 되살아나면 안 된다
        tabs = self._main()
        changed, _ = self._run(tabs, already_seeded=True)
        self.assertFalse(changed)
        self.assertEqual(tabs[0]["blocks"], [])

    def test_메인탭이_없으면_아무_일도_안_한다(self):
        tabs = [{"name": "수능", "cols": 15, "blocks": []}]
        changed, _ = self._run(tabs)
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
