# -*- coding: utf-8 -*-
"""개인 데이터가 커밋되지 않는지 (실제 사고 재발 방지).

백업 기능(backup.py)을 넣은 뒤로 config.json.bak1~3 이 **깃에 그대로 올라가고
있었다**. .gitignore 에 config.json 은 있었지만 config.json.bak1 은 없었기
때문이다. 개인 양식 설정이 공개 저장소에 올라간 상태였다.

이 파일은 그 종류의 실수를 다시 못 하게 막는다. backup.py 가 만드는 이름과
.gitignore 규칙이 어긋나는 순간 여기서 깨진다.
"""

import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import backup   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 절대 커밋되면 안 되는 것들 — 실제 파일이 없어도 규칙은 있어야 한다
MUST_IGNORE = [
    "config.json",
    "library.json",
    "app.log",
    "window_diag.log",
    "fragments/abc123.hwp",
]


def _git(*args):
    return subprocess.run(["git", *args], cwd=str(ROOT),
                          capture_output=True, text=True)


class IgnoreRuleTest(unittest.TestCase):

    def test_개인_파일이_무시된다(self):
        for name in MUST_IGNORE:
            r = _git("check-ignore", "-q", name)
            self.assertEqual(r.returncode, 0, f"{name} 이 커밋될 수 있습니다")

    def test_백업_파일이_전부_무시된다(self):
        # backup.py 가 실제로 만드는 이름을 그대로 물어본다 — KEEP 을 늘려도
        # 규칙이 따라가는지 여기서 드러난다.
        for base in ("config.json", "library.json"):
            for n in range(1, backup.KEEP + 1):
                name = f"{base}.bak{n}"
                r = _git("check-ignore", "-q", name)
                self.assertEqual(r.returncode, 0,
                                 f"{name} 이 커밋될 수 있습니다")

    def test_소스는_무시되지_않는다(self):
        # 규칙을 너무 넓게 잡아 코드까지 빠뜨리는 반대 방향 실수도 막는다
        # data/ 를 통째로 막은 뒤로는 **패키지 안의 소스**도 함께 확인한다 —
        # 규칙이 'hwp_palette' 같은 이름에 걸리면 본체가 통째로 사라진다.
        from tests.srcpath import rel                          # noqa: E402
        for name in ("main.py", "hwp_palette.spec", "README.md",
                     rel("theme"), rel("paths"), rel("backup"), rel("app")):
            r = _git("check-ignore", "-q", name)
            self.assertNotEqual(r.returncode, 0, f"{name} 이 무시되고 있습니다")


class TrackedFilesTest(unittest.TestCase):
    """지금 깃이 **실제로 들고 있는** 목록을 본다 — 규칙보다 이쪽이 진실이다."""

    def setUp(self):
        r = _git("ls-files")
        if r.returncode != 0:
            self.skipTest("깃 저장소가 아닙니다")
        self.tracked = r.stdout.splitlines()

    def test_추적_중인_개인_파일이_없다(self):
        bad = [f for f in self.tracked
               if f in ("config.json", "library.json", "app.log",
                        "window_diag.log")
               or f.startswith("fragments/")
               or ".bak" in f]
        self.assertEqual(bad, [], f"개인 데이터가 커밋돼 있습니다: {bad}")


if __name__ == "__main__":
    unittest.main()
