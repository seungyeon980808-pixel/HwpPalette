# -*- coding: utf-8 -*-
r"""데이터 보호 안전망 (2026-07-31 안전 점검).

여기서 막으려는 사고는 전부 **사용자 데이터가 조용히 사라지는** 종류다:
  · 설정을 못 읽었는데(일시적 잠금 포함) 기본값을 저장해 팔레트가 증발
  · 잘린 library.json 이 '새 설치'처럼 보여 다음 저장이 빈 창고를 덮어씀
  · 삭제가 조각 파일부터 지워, 저장 실패 시 유령 항목이 남음
  · 이사(migration)가 이름 접두사만 같은 남의 파일을 쓸어 감
  · 로그가 한도 초과로 삭제돼 정작 원인 추적 기록이 사라짐
"""

import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import applog        # noqa: E402
from hwp_palette.core import paths         # noqa: E402
from hwp_palette.core import settings      # noqa: E402
from hwp_palette.model import library      # noqa: E402


# ══════════════════════════════════════════════════════════
# settings — 깨진 config.json
# ══════════════════════════════════════════════════════════
class _ConfigBase(unittest.TestCase):
    """임시 폴더의 config.json 으로 settings 를 격리하는 공통 바탕."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.cfg = self.root / "config.json"
        mock.patch.object(settings, "CONFIG_PATH", self.cfg).start()
        self.addCleanup(mock.patch.stopall)
        self._reset_state()
        self.addCleanup(self._reset_state)

    @staticmethod
    def _reset_state():
        settings._cfg_cache["tok"] = None
        settings._cfg_cache["data"] = None
        settings._load_failed = False
        settings._save_error_notifier = None
        settings._save_error_notified = False
        settings._save_error_pending = None

    def _bak(self, n):
        return self.cfg.with_name(f"config.json.bak{n}")


class CorruptConfigTest(_ConfigBase):

    def test_깨진_설정은_백업에서_복구한다(self):
        self._bak(1).write_text(json.dumps({"a": "백업값"}), encoding="utf-8")
        self.cfg.write_text("{잘린 JSON", encoding="utf-8")
        self.assertEqual(settings.load_config().get("a"), "백업값")
        # 망가진 원본은 조사용 사본으로 남는다
        self.assertTrue((self.root / "config.json.damaged").exists())
        # 복구됐으므로 저장은 허용된다
        self.assertTrue(settings.save_config({"a": "복구후저장"}))
        self.assertEqual(
            json.loads(self.cfg.read_text(encoding="utf-8"))["a"], "복구후저장")

    def test_bak1_도_깨졌으면_다음_백업으로_넘어간다(self):
        self._bak(1).write_text("이것도 깨짐", encoding="utf-8")
        self._bak(2).write_text(json.dumps({"a": 2}), encoding="utf-8")
        self.cfg.write_text("깨짐", encoding="utf-8")
        self.assertEqual(settings.load_config().get("a"), 2)

    def test_백업이_없으면_빈_dict_이고_저장이_거부된다(self):
        self.cfg.write_text("깨짐", encoding="utf-8")
        self.assertEqual(settings.load_config(), {})
        self.assertFalse(settings.save_config({"새": "값"}))
        # 파일은 그대로다 — 기본값으로 덮어쓰지 않았다
        self.assertEqual(self.cfg.read_text(encoding="utf-8"), "깨짐")

    def test_ensure_profiles_가_깨진_설정을_기본값으로_덮어쓰지_않는다(self):
        """핵심 회귀 — 여태는 load 실패 → {} → 기본 프리셋을 **저장**해 버렸다."""
        self.cfg.write_text("깨짐", encoding="utf-8")
        names = settings.list_profiles()      # 내부에서 _ensure_profiles → save
        self.assertTrue(names)                # 화면은 기본값으로 계속 뜬다
        self.assertEqual(self.cfg.read_text(encoding="utf-8"), "깨짐")

    def test_읽기가_다시_성공하면_저장_잠금이_풀린다(self):
        self.cfg.write_text("깨짐", encoding="utf-8")
        settings.load_config()
        self.assertFalse(settings.save_config({"a": 1}))
        self.cfg.write_text(json.dumps({"a": 1}), encoding="utf-8")   # 잠금 해제됨
        self.assertEqual(settings.load_config()["a"], 1)
        self.assertTrue(settings.save_config({"a": 2}))

    def test_파일이_없으면_첫_실행_저장_허용(self):
        self.assertEqual(settings.load_config(), {})
        self.assertTrue(settings.save_config({"a": 1}))

    def test_돌려준_설정은_사본이다(self):
        self.cfg.write_text(json.dumps({"tabs": [{"n": "x"}]}), encoding="utf-8")
        got = settings.load_config()
        got["tabs"][0]["n"] = "오염"
        self.assertEqual(settings.load_config()["tabs"][0]["n"], "x",
                         "돌려준 값을 고쳤더니 캐시가 오염됐다")


class SaveErrorNotifierTest(_ConfigBase):
    """CONTRACT C1 — save_config 실패는 등록된 알림으로 사용자에게 알린다."""

    def test_저장_거부_시_알림이_온다(self):
        calls = []
        settings.set_save_error_notifier(calls.append)
        self.cfg.write_text("깨짐", encoding="utf-8")
        settings.load_config()
        settings.save_config({"a": 1})
        self.assertEqual(len(calls), 1)
        self.assertIn("저장", calls[0])       # 한국어 메시지가 들어 있다

    def test_알림은_세션당_한_번만(self):
        calls = []
        settings.set_save_error_notifier(calls.append)
        self.cfg.write_text("깨짐", encoding="utf-8")
        settings.load_config()
        settings.save_config({"a": 1})
        settings.save_config({"a": 2})
        settings.save_config({"a": 3})
        self.assertEqual(len(calls), 1)

    def test_쓰기_실패도_알린다(self):
        calls = []
        settings.set_save_error_notifier(calls.append)
        with mock.patch.object(settings, "_atomic_write_text",
                               side_effect=OSError("디스크")):
            self.assertFalse(settings.save_config({"a": 1}))
        self.assertEqual(len(calls), 1)

    def test_알림_함수가_터져도_저장_흐름은_죽지_않는다(self):
        def boom(msg):
            raise RuntimeError("boom")
        settings.set_save_error_notifier(boom)
        self.cfg.write_text("깨짐", encoding="utf-8")
        settings.load_config()
        self.assertFalse(settings.save_config({"a": 1}))    # 예외 없이 False

    def test_등록_전_실패는_등록되는_순간_알린다(self):
        """앱이 뜨는 도중(알림 함수 등록 전) 저장 거부가 먼저 나는 시나리오 —
        예전에는 이때 '세션당 한 번' 토큰만 태워 알림이 영영 안 나갔다."""
        self.cfg.write_text("깨짐", encoding="utf-8")
        settings.load_config()
        self.assertFalse(settings.save_config({"a": 1}))    # 아직 알릴 곳 없음
        calls = []
        settings.set_save_error_notifier(calls.append)      # 앱이 다 뜬 시점
        self.assertEqual(len(calls), 1, "미뤄 둔 실패가 등록 때 안 나갔다")
        self.assertIn("저장", calls[0])

    def test_등록_전_실패도_세션당_한_번_규칙은_그대로다(self):
        self.cfg.write_text("깨짐", encoding="utf-8")
        settings.load_config()
        settings.save_config({"a": 1})                      # 등록 전 실패
        calls = []
        settings.set_save_error_notifier(calls.append)      # 여기서 1회
        settings.save_config({"a": 2})                      # 추가 실패들은
        settings.save_config({"a": 3})                      # 더 안 알린다
        self.assertEqual(len(calls), 1)

    def test_실패한_적이_없으면_등록만으로는_알리지_않는다(self):
        settings.load_config()                              # 파일 없음 — 정상
        calls = []
        settings.set_save_error_notifier(calls.append)
        self.assertEqual(calls, [])


class AtomicWriteTest(_ConfigBase):
    """저장은 임시 파일 → os.replace — 쓰다 죽어도 반쪽 파일이 남지 않는다."""

    def test_임시파일을_거쳐_교체된다(self):
        seen = {}
        real_replace = settings.os.replace

        def spy(src, dst):
            seen["src"], seen["dst"] = str(src), str(dst)
            return real_replace(src, dst)

        with mock.patch.object(settings.os, "replace", side_effect=spy):
            self.assertTrue(settings.save_config({"a": 1}))
        self.assertEqual(seen["dst"], str(self.cfg))
        self.assertNotEqual(seen["src"], str(self.cfg))     # 직접 쓰지 않았다
        self.assertEqual(json.loads(self.cfg.read_text(encoding="utf-8")),
                         {"a": 1})

    def test_교체가_실패하면_원본이_그대로_남는다(self):
        self.cfg.write_text(json.dumps({"a": "원본"}), encoding="utf-8")
        settings.load_config()
        with mock.patch.object(settings.os, "replace",
                               side_effect=OSError("디스크")):
            self.assertFalse(settings.save_config({"a": "새것"}))
        self.assertEqual(
            json.loads(self.cfg.read_text(encoding="utf-8"))["a"], "원본")
        self.assertEqual(list(self.root.glob("*.tmp")), [],
                         "실패한 임시 파일이 청소되지 않았다")


# ══════════════════════════════════════════════════════════
# library — 깨진 library.json / 삭제 순서
# ══════════════════════════════════════════════════════════
class _LibraryBase(unittest.TestCase):
    """임시 폴더의 library.json 으로 library 를 격리하는 공통 바탕."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.lib = self.root / "library.json"
        self.frag = self.root / "fragments"
        self.frag.mkdir()
        mock.patch.object(library, "LIBRARY_PATH", self.lib).start()
        mock.patch.object(library, "FRAGMENTS_DIR", self.frag).start()
        # 진짜 config.json 의 팔레트를 건드리지 않게 참조 정리는 끊어 둔다
        mock.patch.object(library, "_purge_palette_refs",
                          lambda *a, **k: None).start()
        self.addCleanup(mock.patch.stopall)
        self._reset_state()
        self.addCleanup(self._reset_state)

    @staticmethod
    def _reset_state():
        library._load_cache["tok"] = None
        library._load_cache["data"] = None
        library._load_failed = False


class CorruptLibraryTest(_LibraryBase):

    def test_잘린_파일은_빈_창고처럼_보이되_저장은_막힌다(self):
        self.lib.write_text('{"문자": [{"잘림', encoding="utf-8")
        data = library.load()
        self.assertEqual(data["문자"], [])          # 화면은 빈 창고로 뜨지만
        with self.assertRaises(RuntimeError):       # 그 위에 저장은 못 한다
            library.save(data)
        self.assertEqual(self.lib.read_text(encoding="utf-8"),
                         '{"문자": [{"잘림')        # 원본은 그대로

    def test_add_char_도_깨진_상태에서는_저장을_멈춘다(self):
        self.lib.write_text("깨짐", encoding="utf-8")
        library.load()
        with self.assertRaises(RuntimeError):
            library.add_char("가나다", "★")

    def test_백업이_있으면_복구한다(self):
        good = {"문자": [{"id": "A", "name": "가", "label": "가",
                          "tags": [], "text": "나"}]}
        (self.root / "library.json.bak1").write_text(
            json.dumps(good, ensure_ascii=False), encoding="utf-8")
        self.lib.write_text("깨짐", encoding="utf-8")
        data = library.load()
        self.assertEqual(data["문자"][0]["name"], "가")
        self.assertTrue((self.root / "library.json.damaged").exists())
        library.save(data)                          # 복구됐으니 예외 없이 저장

    def test_파일이_없으면_새_설치로_정상_동작(self):
        self.assertEqual(library.load(),
                         {"서식": [], "문자": [], "템플릿": [], "양식": [],
                          "subcats": {}})
        library.add_char("가나다", "★")             # 저장도 된다
        self.assertTrue(self.lib.exists())

    def test_다시_읽기가_성공하면_저장이_풀린다(self):
        self.lib.write_text("깨짐", encoding="utf-8")
        library.load()
        self.lib.write_text("{}", encoding="utf-8")
        library.load()                              # 성공 → 잠금 해제
        library.save(copy.deepcopy(library._EMPTY))  # 예외 없음


class DeleteItemTest(_LibraryBase):
    """삭제 순서 — 목록 저장이 먼저, 조각 파일 삭제가 나중."""

    def _seed_template(self, with_file=True):
        item = {"id": "T1", "name": "표", "label": "표", "tags": [],
                "slot_count": 0, "slot_names": []}
        if with_file:
            item["file"] = "t1.hwp"
            (self.frag / "t1.hwp").write_bytes(b"FRAG")
        self.lib.write_text(json.dumps({"템플릿": [item]}, ensure_ascii=False),
                            encoding="utf-8")

    def test_정상_삭제는_저장_후_조각도_지운다(self):
        self._seed_template()
        self.assertTrue(library.delete_item("템플릿", "T1"))
        self.assertFalse((self.frag / "t1.hwp").exists())
        on_disk = json.loads(self.lib.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["템플릿"], [])

    def test_저장이_실패하면_조각_파일은_남는다(self):
        """파일부터 지우면 저장 실패 시 '목록엔 있는데 실체가 없는' 유령이 된다."""
        self._seed_template()
        with mock.patch.object(library, "save", side_effect=OSError("저장실패")):
            with self.assertRaises(OSError):
                library.delete_item("템플릿", "T1")
        self.assertTrue((self.frag / "t1.hwp").exists(),
                        "저장도 못 했는데 조각 파일부터 지워졌다")

    def test_file_키가_없는_구_데이터도_삭제된다(self):
        self._seed_template(with_file=False)        # KeyError 로 죽으면 안 된다
        self.assertTrue(library.delete_item("템플릿", "T1"))
        self.assertEqual(library.list_items("템플릿"), [])

    def test_조각_삭제_실패는_삭제를_막지_않고_기록된다(self):
        self._seed_template()
        logged = []
        with mock.patch.object(library.applog, "exc",
                               side_effect=lambda *a, **k: logged.append(a)):
            with mock.patch.object(pathlib.Path, "unlink",
                                   side_effect=OSError("잠김")):
                self.assertTrue(library.delete_item("템플릿", "T1"))
        self.assertTrue(logged, "unlink 실패가 조용히 삼켜졌다")
        self.assertEqual(json.loads(self.lib.read_text(encoding="utf-8"))
                         ["템플릿"], [])            # 목록에서는 지워졌다


# ══════════════════════════════════════════════════════════
# paths — 이전(migration)은 정확한 이름만, 한 번만
# ══════════════════════════════════════════════════════════
class MigrationExactMatchTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.beside = root / "beside"
        self.folder = root / "folder"
        self.beside.mkdir()
        self.folder.mkdir()

    def test_접두사만_같은_남의_파일은_옮기지_않는다(self):
        """바탕화면의 '미리보기 자료' 폴더가 조용히 사라지던 사고."""
        (self.beside / "미리보기 자료").mkdir()
        (self.beside / "config.json.txt").write_text("메모", encoding="utf-8")
        (self.beside / "app.log좋아").write_text("x", encoding="utf-8")
        paths._migrate_legacy(self.beside, self.folder)
        self.assertTrue((self.beside / "미리보기 자료").exists())
        self.assertTrue((self.beside / "config.json.txt").exists())
        self.assertTrue((self.beside / "app.log좋아").exists())
        self.assertFalse((self.folder / "미리보기 자료").exists())

    def test_진짜_옛_데이터와_백업은_옮긴다(self):
        names = ("config.json", "config.json.bak2", "library.json",
                 "library.json.bak1", "app.log", "window_diag.log")
        for name in names:
            (self.beside / name).write_text("x", encoding="utf-8")
        (self.beside / "미리보기").mkdir()
        paths._migrate_legacy(self.beside, self.folder)
        for name in names + ("미리보기",):
            self.assertTrue((self.folder / name).exists(), name)
            self.assertFalse((self.beside / name).exists(), f"{name} 이 남았다")

    def test_한_번_스캔하면_표식을_남기고_건너뛴다(self):
        """docstring 의 '한 번만' 약속 — 표식 파일이 지킨다."""
        paths._migrate_legacy(self.beside, self.folder)
        self.assertTrue((self.folder / paths._MIGRATED_MARKER).exists())
        (self.beside / "config.json").write_text("{}", encoding="utf-8")
        moved = paths._migrate_legacy(self.beside, self.folder)
        self.assertEqual(moved, 0)
        self.assertTrue((self.beside / "config.json").exists(),
                        "두 번째 스캔이 또 옮겼다")

    def test_잠긴_파일이_있으면_표식을_미룬다(self):
        """첫 실행에 백신·OneDrive 가 잠근 파일 — 그 순간 표식을 박으면
        다음 실행이 스캔을 건너뛰어 데이터가 영영 밖에 남는다."""
        (self.beside / "config.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(pathlib.Path, "replace",
                               side_effect=OSError("잠김")):
            moved = paths._migrate_legacy(self.beside, self.folder)
        self.assertEqual(moved, 0)
        self.assertFalse((self.folder / paths._MIGRATED_MARKER).exists(),
                         "잠긴 파일을 남긴 채 표식을 박았다")
        # 다음 실행 — 잠금이 풀렸으면 이번에는 옮기고 표식도 남긴다
        moved = paths._migrate_legacy(self.beside, self.folder)
        self.assertEqual(moved, 1)
        self.assertTrue((self.folder / "config.json").exists())
        self.assertFalse((self.beside / "config.json").exists())
        self.assertTrue((self.folder / paths._MIGRATED_MARKER).exists())

    def test_새_폴더에_이미_있어_안_옮긴_것은_표식을_막지_않는다(self):
        """dest 가 이미 있는 건 정상 상황 — 다시 훑을 이유가 없다."""
        (self.beside / "config.json").write_text("옛것", encoding="utf-8")
        (self.folder / "config.json").write_text("지금 것", encoding="utf-8")
        paths._migrate_legacy(self.beside, self.folder)
        self.assertTrue((self.folder / paths._MIGRATED_MARKER).exists())
        self.assertEqual((self.folder / "config.json")
                         .read_text(encoding="utf-8"), "지금 것")


# ══════════════════════════════════════════════════════════
# applog — 로그는 지우지 않고 .old 로 민다
# ══════════════════════════════════════════════════════════
class LogRotationTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = pathlib.Path(self.tmp.name) / "app.log"
        mock.patch.object(applog, "LOG_PATH", self.log).start()
        self.addCleanup(mock.patch.stopall)

    def test_한도를_넘으면_지우지_않고_old_로_민다(self):
        """오류가 쏟아질 때 로그를 지우면 정작 원인 추적 기록이 사라진다."""
        self.log.write_text("옛 기록\n" * 10, encoding="utf-8")
        with mock.patch.object(applog, "MAX_BYTES", 10):
            applog.info("새 기록")
        old = self.log.with_name("app.log.old")
        self.assertTrue(old.exists())
        self.assertIn("옛 기록", old.read_text(encoding="utf-8"))
        self.assertIn("새 기록", self.log.read_text(encoding="utf-8"))

    def test_이미_old_가_있어도_교체된다(self):
        old = self.log.with_name("app.log.old")
        old.write_text("아주 옛날", encoding="utf-8")
        self.log.write_text("최근 기록\n" * 5, encoding="utf-8")
        with mock.patch.object(applog, "MAX_BYTES", 10):
            applog.info("새 기록")
        self.assertIn("최근 기록", old.read_text(encoding="utf-8"))

    def test_한도_아래면_그대로_이어_쓴다(self):
        self.log.write_text("기존\n", encoding="utf-8")
        applog.info("추가")
        self.assertFalse(self.log.with_name("app.log.old").exists())
        text = self.log.read_text(encoding="utf-8")
        self.assertIn("기존", text)
        self.assertIn("추가", text)


if __name__ == "__main__":
    unittest.main()
