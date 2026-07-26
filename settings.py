# -*- coding: utf-8 -*-
"""양식 프리셋 저장소.

- 표/박스/글꼴의 모든 스펙을 코드에 하드코딩하지 않고 여기서 관리한다.
- 이름별 프리셋(예: '대왕중 2단', '1단 모의고사')을 config.json에 저장하고
  드롭다운으로 전환한다. 프리셋은 JSON으로 내보내/가져와 다른 사람과 공유한다.
- config.json은 사용자 로컬 파일(.gitignore). 기본 프리셋은 이 파일의
  DEFAULT_SPEC/기본 프리셋으로 코드에 내장돼, 새 설치에서도 바로 쓸 수 있다.
"""

import copy
import applog
import backup
import json
import os
import pathlib
import paths

CONFIG_PATH = paths.DATA_DIR / "config.json"

# ── 기본 스펙 ──────────────────────────────────────────
# 모든 값의 단위: *_mm = 밀리미터, *_pt = 포인트,
# line_spacing = 퍼센트(%), spacing/indentation = 한글 내부 단위
DEFAULT_SPEC = {
    "layout": {
        "column_width_mm": 93.99,   # 전체 단 폭. 2단=93.99, 1단이면 ~155
    },
    "font": {
        "apply": False,             # True면 삽입 텍스트에 아래 글꼴 강제 적용
        "name": "함초롬바탕",
        "size_pt": 10.0,
    },
    "material_box": {               # 자료: (기본형 자료박스)
        "row1_height_mm": 45.0,     # 내용 칸
        "row2_height_mm": 5.0,      # 아래 여백 칸
    },
    "photo_box": {                  # 사진자료:
        "row1_height_mm": 45.0,
        "row2_height_mm": 7.0,
    },
    "experiment_box": {             # 실험자료:
        "height_mm": 80.0,
        "label": "[실험 과정]",
    },
    "bogi_box": {                   # 보기: 〈보 기〉 박스
        "title_height_mm": 3.0,     # 1행 (제목 위 칸)
        "gap_height_mm": 3.0,       # 2행 (제목 아래 칸)
        "content_height_mm": 20.0,  # 3행 (ㄱㄴㄷ 내용 칸)
        "title": "〈보 기〉",
        "line_spacing": 130,        # 내용 줄간격 %
        "cell_margin_left_mm": 2.0,
        "cell_margin_right_mm": 2.0,
        "cell_margin_top_mm": 0.5,
        "cell_margin_bottom_mm": 4.0,
    },
    "choices": {                    # 선지 표
        "row_height_mm": 6.0,
    },
    "stem": {                       # 발문
        "indentation": -399,        # 내어쓰기(음수, 한글 단위)
        "line_spacing": 150,
    },
    "question": {                   # 질문(들여쓴 질문 문단)
        "prev_spacing": 800,        # 위 간격
        "next_spacing": 400,        # 아래 간격
    },
    "border": {                     # 테두리 종류 (None/Solid/Dash/Double)
        "material_type": "None",    # 자료박스 (기본: 투명)
        "bogi_type": "Solid",       # 보기박스 바깥선
        "experiment_type": "Solid", # 실험박스
    },
}


def default_spec():
    return copy.deepcopy(DEFAULT_SPEC)


def _default_profiles():
    """새 설치에 심어줄 기본 프리셋 2종 (2단/1단)."""
    two = default_spec()
    one = default_spec()
    one["layout"]["column_width_mm"] = 155.0   # 1단은 폭만 넓힘
    return {"기본 (2단)": two, "기본 (1단)": one}


# ── deep merge (하위호환: 저장된 프리셋에 새 키를 기본값으로 채움) ──
def deep_merge(base, override):
    """base(기본값) 위에 override(저장값)를 덮되, base에만 있는 키는 유지."""
    result = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


# ── config.json 입출력 ─────────────────────────────────
def load_config():
    if not CONFIG_PATH.exists():
        return {}                      # 첫 실행 — 정상
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # 설정이 깨졌는데 조용히 {} 를 돌려주면 사용자의 팔레트가 통째로
        # 사라진 것처럼 보인다 → 반드시 기록을 남긴다.
        applog.exc(f"설정 파일을 읽지 못함 ({CONFIG_PATH.name}) — 기본값으로 시작", e)
        return {}


def save_config(cfg):
    try:
        backup.rotate(CONFIG_PATH)      # 저장 직전 상태를 .bak1 로 보관
        CONFIG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except (OSError, TypeError) as e:
        applog.exc(f"설정 저장 실패 ({CONFIG_PATH.name}) — 변경이 유실됨", e)
        return False


def _ensure_profiles(cfg):
    """cfg에 profiles/active_profile이 없으면 기본값으로 채우고 저장."""
    changed = False
    if not cfg.get("profiles"):
        cfg["profiles"] = _default_profiles()
        changed = True
    if cfg.get("active_profile") not in cfg["profiles"]:
        cfg["active_profile"] = next(iter(cfg["profiles"]))
        changed = True
    if changed:
        save_config(cfg)
    return cfg


# ── 프리셋 API ─────────────────────────────────────────
def list_profiles():
    cfg = _ensure_profiles(load_config())
    return list(cfg["profiles"].keys())


def get_active_name():
    cfg = _ensure_profiles(load_config())
    return cfg["active_profile"]


def set_active_name(name):
    cfg = _ensure_profiles(load_config())
    if name in cfg["profiles"]:
        cfg["active_profile"] = name
        save_config(cfg)


def get_spec(name=None):
    """이름(없으면 활성) 프리셋을 기본값과 병합해 완전한 스펙으로 반환."""
    cfg = _ensure_profiles(load_config())
    if name is None:
        name = cfg["active_profile"]
    saved = cfg["profiles"].get(name, {})
    return deep_merge(DEFAULT_SPEC, saved)


def get_active_spec():
    return get_spec(None)


def save_profile(name, spec):
    cfg = _ensure_profiles(load_config())
    cfg["profiles"][name] = copy.deepcopy(spec)
    save_config(cfg)


def add_profile(name, spec=None):
    cfg = _ensure_profiles(load_config())
    if name in cfg["profiles"]:
        raise ValueError(f"이미 존재하는 이름입니다: {name}")
    cfg["profiles"][name] = spec if spec is not None else default_spec()
    cfg["active_profile"] = name
    save_config(cfg)


def duplicate_profile(src, new_name):
    cfg = _ensure_profiles(load_config())
    if src not in cfg["profiles"]:
        raise ValueError(f"원본 프리셋이 없습니다: {src}")
    if new_name in cfg["profiles"]:
        raise ValueError(f"이미 존재하는 이름입니다: {new_name}")
    cfg["profiles"][new_name] = copy.deepcopy(cfg["profiles"][src])
    cfg["active_profile"] = new_name
    save_config(cfg)


def rename_profile(old, new):
    cfg = _ensure_profiles(load_config())
    if old not in cfg["profiles"]:
        raise ValueError(f"프리셋이 없습니다: {old}")
    if new in cfg["profiles"] and new != old:
        raise ValueError(f"이미 존재하는 이름입니다: {new}")
    # 순서 유지하며 키 교체
    cfg["profiles"] = {(new if k == old else k): v
                       for k, v in cfg["profiles"].items()}
    if cfg.get("active_profile") == old:
        cfg["active_profile"] = new
    save_config(cfg)


def delete_profile(name):
    cfg = _ensure_profiles(load_config())
    if name not in cfg["profiles"]:
        return
    if len(cfg["profiles"]) <= 1:
        raise ValueError("마지막 프리셋은 삭제할 수 없습니다.")
    del cfg["profiles"][name]
    if cfg.get("active_profile") == name:
        cfg["active_profile"] = next(iter(cfg["profiles"]))
    save_config(cfg)


def export_profile(name, path):
    """프리셋 한 개를 {name, spec} 형태의 JSON 파일로 저장."""
    spec = get_spec(name)
    payload = {"exam_scribe_profile": name, "spec": spec}
    pathlib.Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def import_profile(path, new_name=None):
    """내보낸 JSON 파일을 프리셋으로 가져옴. 반환: 실제 저장된 이름."""
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    spec = payload.get("spec", payload)          # 순수 spec만 든 파일도 허용
    name = new_name or payload.get("exam_scribe_profile") or "가져온 양식"
    cfg = _ensure_profiles(load_config())
    # 이름 충돌 시 (2), (3)… 붙임
    base, n = name, 2
    while name in cfg["profiles"]:
        name = f"{base} ({n})"; n += 1
    cfg["profiles"][name] = deep_merge(DEFAULT_SPEC, spec)
    cfg["active_profile"] = name
    save_config(cfg)
    return name


# ── 기타 설정(사진 폴더 등) ────────────────────────────
# ── config.json 키 소유권 (개선안 21) ──────────────────
# config.json 하나를 두 모듈이 나눠 쓴다. API가 따로라 "누가 무엇을 책임지는지"가
# 코드에 안 드러나 있었다 → 여기에 한 곳으로 모아 적는다.
#
#   키                소유 모듈      접근 방법
#   ---------------   ------------   ----------------------------------------
#   profiles          settings.py    이 파일의 프리셋 API (list/get/save_profile…)
#   active_profile    settings.py    get_active_name() / set_active_name()
#   palette_tabs      palette.py     palette.load_tabs() / save_tabs()
#   default_format    palette.py     palette.get_default_format() / save_…()
#   quick_buttons     settings.py    get_quick_buttons() — 구 버전 잔재(읽기 전용)
#
# 규칙: **소유 모듈이 아닌 곳에서 그 키를 직접 만지지 않는다.** 남의 키가
# 필요하면 소유 모듈의 함수를 부른다. 아래 두 함수는 palette.py 처럼 자기 키를
# 가진 모듈이 config.json 에 드나드는 유일한 통로다(파일 입출력 중복 방지).
CONFIG_KEY_OWNERS = {
    "profiles": "settings",
    "active_profile": "settings",
    "quick_buttons": "settings",
    "photo_dir": "settings",        # 구버전 단일 폴더 — photo_dirs 로 승격됨
    "photo_dirs": "settings",
    "ui_scale": "settings",
    "window_pos": "settings",
    "palette_tabs": "palette",
    "default_format": "palette",
}


# ── 사진 폴더 (\사진이름\ 변환용) ──────────────────────
# 폴더는 여러 개를 연결할 수 있다(photo_dirs, 목록). 예전에는 한 개(photo_dir,
# 문자열)뿐이었으므로 **구 키를 지우지 않고** 읽을 때 목록으로 승격시킨다.
# 목록을 실제로 저장하는 순간(추가/삭제/교체) photo_dirs 가 만들어지고,
# photo_dir 에는 첫 폴더를 계속 써 둔다 — 구버전으로 되돌아가도 최소한 한
# 폴더는 살아 있게 하려는 것.
def _norm_dir(path):
    """저장·비교용 경로 정규화. 슬래시 방향과 끝의 \\ 차이로 중복되는 걸 막는다."""
    s = (path or "").strip()
    return os.path.normpath(s) if s else ""


def _dir_key(path):
    """중복 판정용 키. 윈도우 경로는 대소문자를 구분하지 않는다."""
    n = _norm_dir(path)
    return n.casefold() if os.name == "nt" else n


def _read_photo_dirs():
    """config 의 photo_dirs 만 읽는다(구 키 승격 없음). 깨진 값은 버린다."""
    raw = get_config_value("photo_dirs", None)
    if not isinstance(raw, (list, tuple)):
        return []
    out, seen = [], set()
    for x in raw:
        n = _norm_dir(str(x) if x is not None else "")
        if n and _dir_key(n) not in seen:
            seen.add(_dir_key(n))
            out.append(n)
    return out


def get_photo_dirs():
    """연결된 사진 폴더 목록(list[str]). 등록 순서 = 탐색 우선순위."""
    dirs = _read_photo_dirs()
    if dirs:
        return dirs
    old = get_photo_dir()               # 구 키 승격 — 읽기만 하고 저장은 안 한다
    return [old] if old else []


def _write_photo_dirs(dirs):
    """목록을 저장하고 구 키(photo_dir)도 첫 폴더로 맞춰 둔다."""
    dirs = [_norm_dir(d) for d in dirs if _norm_dir(d)]
    set_config_value("photo_dirs", dirs)
    set_config_value("photo_dir", dirs[0] if dirs else "")
    return dirs


def set_photo_dirs(dirs):
    """목록 전체를 교체. 중복은 제거하고 순서는 유지."""
    out, seen = [], set()
    for d in (dirs or []):
        n = _norm_dir(d)
        if n and _dir_key(n) not in seen:
            seen.add(_dir_key(n))
            out.append(n)
    return _write_photo_dirs(out)


def add_photo_dir(path):
    """폴더 추가. 이미 있으면 아무것도 안 하고 False."""
    n = _norm_dir(path)
    if not n:
        return False
    dirs = get_photo_dirs()             # 구 키만 있던 상태라면 여기서 승격된다
    if _dir_key(n) in {_dir_key(d) for d in dirs}:
        return False
    _write_photo_dirs(dirs + [n])
    return True


def remove_photo_dir(path):
    """폴더 연결 해제. 없던 폴더면 False (파일은 건드리지 않는다)."""
    key = _dir_key(path)
    if not key:
        return False
    dirs = get_photo_dirs()
    left = [d for d in dirs if _dir_key(d) != key]
    if len(left) == len(dirs):
        return False
    _write_photo_dirs(left)
    return True


def get_photo_dir():
    """구버전 호환 — 첫 번째 사진 폴더. 없으면 빈 문자열.

    (get_photo_dirs 가 이 함수를 승격 경로로 부르므로, 여기서 거꾸로
    get_photo_dirs 를 부르면 안 된다 — 무한 재귀.)
    """
    dirs = _read_photo_dirs()
    if dirs:
        return dirs[0]
    return _norm_dir(get_config_value("photo_dir", ""))


def set_photo_dir(path):
    """구버전 호환 — 이 한 폴더만 남긴다(빈 값이면 전부 해제)."""
    n = _norm_dir(path)
    _write_photo_dirs([n] if n else [])


# ── 화면 크기 모드 (작게 1.0 / 크게 1.3) ────────────────
def get_ui_scale():
    try:
        v = float(get_config_value("ui_scale", 1.0))
    except (TypeError, ValueError):
        v = 1.0
    return 1.3 if v > 1.15 else 1.0     # 두 단계만 — 중간값은 반올림


def set_ui_scale(v):
    set_config_value("ui_scale", 1.3 if float(v) > 1.15 else 1.0)


# ── 창 위치 기억 (UI 제안 15) ───────────────────────────
def get_window_pos():
    """마지막 창 위치 (x, y). 저장된 적이 없으면 None."""
    v = get_config_value("window_pos", None)
    if isinstance(v, (list, tuple)) and len(v) == 2:
        try:
            return int(v[0]), int(v[1])
        except (TypeError, ValueError):
            pass
    return None


def set_window_pos(x, y):
    set_config_value("window_pos", [int(x), int(y)])


def get_config_value(key, default=None):
    return load_config().get(key, default)


def set_config_value(key, value):
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)


# ── 팔레트 '빠른입력' 탭 시드 (과학 교사용 기본 기호) ──
# 새 설치 때 palette._seed_tabs() 가 이 목록을 문자 블럭으로 만들어준다.
# 편집은 환경설정의 팔레트에서 하므로 저장 함수는 두지 않는다.
DEFAULT_QUICK_BUTTONS = [
    "Ω", "→", "℃", "·", "×",
    "±", "≒", "≠", "≤", "≥",
    "√", "∴", "½", "²", "³",
    "₁", "₂", "α", "β", "γ",
    "θ", "λ", "μ", "π", "Δ",
]


def get_quick_buttons():
    """시드용 기호 목록. 구 버전에서 편집해둔 값이 config에 있으면 그걸 쓴다."""
    v = get_config_value("quick_buttons", None)
    return list(v) if v is not None else list(DEFAULT_QUICK_BUTTONS)
