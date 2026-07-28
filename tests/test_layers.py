# -*- coding: utf-8 -*-
r"""층 규칙을 지키는지 (2026-07-28 폴더 개편 4단계).

왜 이 테스트가 필요한가:
    폴더로 나눠 놓아도 **아무도 안 보면 한 달 만에 다시 섞인다.** 급할 때
    model/ 안에서 hwp_engine 을 한 줄 부르면 그 순간 층이 무너지는데, 화면에는
    아무 표시도 안 난다 — 몇 달 뒤 "이 파일 하나 고치려면 왜 열 개를 알아야
    하지" 로만 돌아온다.

    규칙을 글로만 적어 두면 규칙이 아니고, 검사해야 규칙이다.

규칙 (hwp_palette/__init__.py 와 같은 내용):

    core  →  (없음)
    design → core
    model  → core
    hwp    → core, design?, model      ← design 은 안 부르는 것이 맞다
    ui     → 전부
    app    → 전부

같은 층끼리는 서로 불러도 된다:
    library 와 palette 는 서로를 부른다(지운 물감을 가리키는 블럭 청소 ↔ 옛
    블럭의 ref 이전). 둘 다 model 이고, '물감'과 '그 물감을 놓는 자리'는
    같은 높이의 개념이라 한쪽이 다른 쪽 밑에 있다고 말할 수 없다.
    층을 넘는 순환만 사고다.
"""

import ast
import io
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

PKG = pathlib.Path(__file__).resolve().parent.parent / "hwp_palette"

# 그 층이 **부를 수 있는** 층 (자기 층은 언제나 허용)
ALLOWED = {
    "core":   set(),
    "design": {"core"},
    "model":  {"core"},
    "hwp":    {"core", "model"},
    "ui":     {"core", "design", "model", "hwp"},
    "":       {"core", "design", "model", "hwp", "ui"},   # app.py
}


# 알고 있는 예외 — **파일 하나 단위로만** 열어 준다.
#
# 예외를 층 규칙 자체로 넓히지 않는 이유: 'model 은 design 을 불러도 된다'로
# 풀어 버리면 그다음 사람이 model 어디서나 화면 부품을 부르기 시작한다.
# 여기 이름이 적혀 있으면 "이건 갚아야 할 빚"이라고 읽힌다.
EXCEPTIONS = {
    # palette 가 저장된 블럭 색을 12색 파스텔로 맞출 때 theme.PASTELS 를 본다.
    #
    # 진짜 원인은 theme.py 가 **색 데이터**(PASTELS·블럭 종류별 색)와
    # **화면 토큰**(SP·FS·RADIUS·FONT)을 한 파일에 갖고 있다는 것이다. 앞쪽은
    # model 것이고 뒤쪽은 design 것이다. 갈라 두면 이 예외가 없어진다.
    # 지금 안 가르는 이유: theme 를 부르는 곳이 14군데라, 폴더 개편과 같은
    # 커밋에 섞으면 무엇 때문에 깨졌는지 못 가린다.
    ("model/palette.py", "design"),
}


def _imports(path):
    """그 파일이 부르는 hwp_palette 하위 층 이름들."""
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    out = set()
    for node in ast.walk(tree):
        mod = None
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("hwp_palette"):
                    out.add(a.name.split(".")[1] if "." in a.name else "")
            continue
        if mod and mod.startswith("hwp_palette"):
            parts = mod.split(".")
            out.add(parts[1] if len(parts) > 1 else "")
    return out


class LayerTest(unittest.TestCase):

    def _files(self):
        for path in sorted(PKG.rglob("*.py")):
            if path.name == "__init__.py":
                continue
            layer = "" if path.parent == PKG else path.parent.name
            yield layer, path

    def test_층을_거슬러_부르지_않는다(self):
        for layer, path in self._files():
            allowed = ALLOWED[layer] | {layer}
            rel = path.relative_to(PKG).as_posix()
            for called in _imports(path):
                if (rel, called) in EXCEPTIONS:
                    continue
                self.assertIn(
                    called, allowed,
                    f"{path.relative_to(PKG.parent)} 가 '{called}' 층을 부릅니다. "
                    f"'{layer}' 층이 부를 수 있는 것: {sorted(allowed)}")

    def test_모든_모듈이_어느_층엔가_있다(self):
        for layer, path in self._files():
            self.assertIn(layer, ALLOWED,
                          f"{path.name} 이 알 수 없는 폴더에 있습니다: {layer}")

    def test_뿌리에_남은_소스는_진입점뿐(self):
        """main.py 말고 다른 .py 가 뿌리에 늘어나면 평면 구조로 되돌아간다."""
        root = PKG.parent
        stray = sorted(p.name for p in root.glob("*.py")
                       if p.name not in ("main.py", "build_exe.py"))
        self.assertEqual(stray, [], f"뿌리에 소스가 늘었습니다: {stray}")


if __name__ == "__main__":
    unittest.main()
