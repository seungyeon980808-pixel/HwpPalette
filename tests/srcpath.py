# -*- coding: utf-8 -*-
r"""소스 파일의 자리를 **한 곳에서** 알려준다 (2026-07-28 폴더 개편).

왜 필요한가: 테스트 여섯 개가 소스를 글자로 읽어 검사한다 (단축키 표기와 실제
등록이 어긋나지 않는지, 대화상자에 tkinter 기본 창을 쓰지 않았는지 등).
그 여섯 개가 각자 `ROOT / "main.py"` 처럼 경로를 직접 적고 있으면, 파일을 한 번
옮길 때마다 여섯 군데를 고쳐야 하고 한 곳을 빠뜨리면 **테스트가 조용히 통과**한다
(파일을 못 읽어 검사 자체를 안 하게 되는 게 아니라 FileNotFoundError 로 터지는
편이 그나마 낫다).

여기 한 곳만 고치면 되게 모아 둔다.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "hwp_palette"

# 모듈 이름 → 실제 파일. hwp_palette/__init__.py 의 층 규칙과 같은 나눔이다.
_LAYERS = {
    "core":   ["appinfo", "applog", "paths", "settings", "backup",
               "clipboard", "screens", "hotkey"],
    "design": ["theme", "ui_fx", "roundbtn", "popover", "dialogs", "disclosure"],
    "model":  ["palette", "library", "chip", "parser", "form_fill",
               "builtin_actions", "builtin_chars", "func_catalog"],
    "hwp":    ["hwp_engine", "engine_library", "exam_engine", "preview",
               "hwp_dock", "form_markdown"],
    "ui":     ["palette_ui", "store_ui", "library_ui", "form_fill_ui",
               "form_table_ui", "help_ui", "help_content", "onboarding",
               "tutorial", "tutorials", "dock_bar", "char_source"],
}
_WHERE = {m: layer for layer, mods in _LAYERS.items() for m in mods}


def src(module):
    """모듈 이름 → 그 소스 파일 경로. 'app' 은 hwp_palette/app.py."""
    if module == "app":
        return PKG / "app.py"
    layer = _WHERE.get(module)
    if layer is None:
        raise KeyError(f"어느 층인지 모르는 모듈: {module}")
    return PKG / layer / f"{module}.py"


def rel(module):
    """뿌리 기준 상대 경로 문자열 (git check-ignore 등에 쓴다)."""
    return src(module).relative_to(ROOT).as_posix()
