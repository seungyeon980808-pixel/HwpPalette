# -*- coding: utf-8 -*-
r"""library.py 순수 로직 테스트 (개선안 22).

library.load()는 사용자의 개인 library.json을 읽으므로, 여기서는 가짜 데이터로
갈아끼워 파일과 무관하게 검증한다.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import library        # noqa: E402


def _fake_data(**by_category):
    data = {cat: [] for cat in library.CATEGORIES}
    data.update(by_category)
    return data


class NormalizeLabelTest(unittest.TestCase):
    r"""사용자가 \라벨\ 통째로 입력해도 알맹이로 저장돼야 조회가 된다."""

    def test_감싼_역슬래시를_벗긴다(self):
        self.assertEqual(library.normalize_label(r"\계획서표지\ "), "계획서표지")

    def test_이미_알맹이면_그대로(self):
        self.assertEqual(library.normalize_label("계획서표지"), "계획서표지")

    def test_빈_값은_빈_문자열(self):
        self.assertEqual(library.normalize_label(None), "")
        self.assertEqual(library.normalize_label("   "), "")


class ResolveEditedLabelTest(unittest.TestCase):
    r"""이름을 바꿨는데 라벨이 옛 이름으로 남던 버그 (2026-07-25).

    수정 창의 라벨 칸은 '자세히' 안에 접혀 있어 사용자 눈에 안 보이는데 옛 값이
    미리 채워진다. 그래서 이름만 고치면 라벨이 조용히 어긋났고, 팔레트 버튼은
    id 로 찾으니 잘 되어서 "버튼은 되는데 변환만 안 되는" 증상이 됐다.
    """

    def test_라벨을_안_지었으면_이름을_따라간다(self):
        # 학교합답1사진3선지 → …5선지 로 이름만 고친 경우
        self.assertEqual(
            library.resolve_edited_label(
                "학교합답1사진3선지", "학교합답1사진3선지",
                "학교합답1사진5선지", "학교합답1사진3선지"),
            "학교합답1사진5선지")

    def test_일부러_다르게_지은_라벨은_지킨다(self):
        # 원안지 → 원안지양식 처럼 의도적으로 다른 라벨
        self.assertEqual(
            library.resolve_edited_label(
                "원안지", "원안지양식", "원안지(2026)", "원안지양식"),
            "원안지양식")

    def test_라벨을_직접_고쳤으면_그것을_쓴다(self):
        self.assertEqual(
            library.resolve_edited_label("가", "가", "나", "내가정한라벨"),
            "내가정한라벨")

    def test_이름도_라벨도_그대로면_그대로(self):
        self.assertEqual(
            library.resolve_edited_label("가", "가", "가", "가"), "가")

    def test_감싼_역슬래시가_있어도_같은_것으로_본다(self):
        # 라벨 칸에 \가\ 로 적혀 있어도 '안 건드린 것'으로 봐야 한다
        self.assertEqual(
            library.resolve_edited_label("가", "가", "나", "\\가\\"), "나")


class UniqueNameTest(unittest.TestCase):
    """이름은 분류 안에서 유일해야 한다 (개선안 3의 전제)."""

    def test_겹치지_않으면_그대로(self):
        self.assertEqual(library._unique_name([{"name": "가"}], "나"), "나")

    def test_겹치면_번호를_붙인다(self):
        self.assertEqual(library._unique_name([{"name": "결재란"}], "결재란"),
                         "결재란 (2)")

    def test_번호도_겹치면_다음_번호로(self):
        items = [{"name": "결재란"}, {"name": "결재란 (2)"}]
        self.assertEqual(library._unique_name(items, "결재란"), "결재란 (3)")


class FindLabelOwnerTest(unittest.TestCase):
    r"""라벨 중복 검사 — 이름과 달리 분류를 가로질러 겹칠 수 있다."""

    def setUp(self):
        self.data = _fake_data(
            서식=[{"id": "A", "name": "강조", "label": "강조"}],
            문자=[{"id": "B", "name": "인사말", "label": "인사말"}],
        )
        patcher = mock.patch.object(library, "load", return_value=self.data)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_안_쓰이는_라벨이면_None(self):
        self.assertIsNone(library.find_label_owner("처음보는라벨"))

    def test_다른_분류의_같은_라벨을_찾아낸다(self):
        cat, item = library.find_label_owner("강조")
        self.assertEqual(cat, "서식")
        self.assertEqual(item["id"], "A")

    def test_자기_자신은_충돌로_보지_않는다(self):
        # 수정 화면에서 라벨을 그대로 두고 이름만 바꾸는 흔한 경우
        self.assertIsNone(library.find_label_owner("강조", exclude_id="A"))

    def test_감싼_역슬래시를_넣어도_같은_라벨로_본다(self):
        self.assertIsNotNone(library.find_label_owner("\\강조\\"))

    def test_빈_라벨은_충돌_없음(self):
        self.assertIsNone(library.find_label_owner(""))


class CaptureDirectSaveTest(unittest.TestCase):
    r"""조각을 최종 위치에 '바로' 저장하는지 (WinError 32 회피).

    예전엔 _tmp_*.hwp 로 저장 후 이름을 바꿨는데, 한글이 그 파일을 물고 있어
    이름 바꾸기가 [WinError 32] 로 터졌다. 이제 save_to(목적지) 로 넘겨
    처음부터 최종 경로에 저장하므로 바꿀 일이 없다.
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.frag = root / "fragments"
        self.frag.mkdir()
        for p in (mock.patch.object(library, "LIBRARY_PATH", root / "library.json"),
                  mock.patch.object(library, "FRAGMENTS_DIR", self.frag)):
            p.start()
            self.addCleanup(p.stop)

    def test_목적지에_바로_저장한다(self):
        saved_to = {}

        def save_to(dest):
            saved_to["path"] = dest
            dest.write_bytes(b"FRAG")

        library.add_template_from_capture("표", save_to, slot_count=2)
        # 저장 함수가 받은 경로가 곧 최종 위치 (임시 이름이 아니다)
        self.assertEqual(saved_to["path"].parent, self.frag)
        self.assertFalse(saved_to["path"].name.startswith("_tmp_"))
        item = library.list_items("템플릿")[0]
        self.assertTrue((self.frag / item["file"]).exists())
        self.assertEqual(item["slot_count"], 2)

    def test_저장이_안_되면_등록하지_않고_알린다(self):
        # save_to 가 파일을 안 만들면 (캡처 실패) 예외를 올린다
        with self.assertRaises(RuntimeError):
            library.add_template_from_capture("표", lambda dest: None)
        self.assertEqual(library.list_items("템플릿"), [])

    def test_구버전_임시파일을_청소한다(self):
        (self.frag / "_tmp_111.hwp").write_bytes(b"x")
        (self.frag / "_tmp_222.hwp").write_bytes(b"x")
        keep = self.frag / "abc123.hwp"
        keep.write_bytes(b"real")
        library.cleanup_temp_fragments()
        self.assertFalse((self.frag / "_tmp_111.hwp").exists())
        self.assertFalse((self.frag / "_tmp_222.hwp").exists())
        self.assertTrue(keep.exists())          # 진짜 조각은 안 건드린다


class LabelLookupTest(unittest.TestCase):
    r"""\라벨\ → 항목 조회. 중복 시 먼저 만난 것이 이긴다."""

    def test_중복_라벨은_먼저_만난_것이_이긴다(self):
        data = _fake_data(
            서식=[{"id": "A", "name": "먼저", "label": "겹침"}],
            문자=[{"id": "B", "name": "나중", "label": "겹침"}],
        )
        with mock.patch.object(library, "load", return_value=data):
            out = library.label_lookup()
        self.assertEqual(out["겹침"][0], "서식")
        self.assertEqual(out["겹침"][1]["id"], "A")

    def test_내장_문자가_병합된다(self):
        with mock.patch.object(library, "load", return_value=_fake_data()):
            out = library.label_lookup()
        self.assertIn("원1", out)
        self.assertEqual(out["원1"][0], "문자")

    def test_사용자_항목이_내장_문자를_이긴다(self):
        data = _fake_data(문자=[{"id": "A", "name": "내것", "label": "원1",
                                 "text": "내가정한값"}])
        with mock.patch.object(library, "load", return_value=data):
            out = library.label_lookup()
        self.assertEqual(out["원1"][1]["text"], "내가정한값")


class PhotoLookupTest(unittest.TestCase):
    r"""사진 폴더 → \파일이름\ 라벨."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        import settings
        # 폴더가 여러 개가 된 뒤로는 get_photo_dirs 가 실제 조회 경로다
        # (get_photo_dir 만 목킹하면 사용자가 UI 로 폴더를 추가해 둔 순간
        #  실제 config 값이 새어 들어와 테스트가 흔들린다, 2026-07-26)
        patcher = mock.patch.object(settings, "get_photo_dirs",
                                    return_value=[str(self.dir)])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _touch(self, name):
        (self.dir / name).write_bytes(b"IMG")

    def test_이미지_파일만_라벨이_된다(self):
        self._touch("실험사진1.png")
        self._touch("메모.txt")            # 이미지가 아니므로 제외
        out = library._photo_lookup()
        self.assertIn("실험사진1", out)
        self.assertNotIn("메모", out)
        cat, item = out["실험사진1"]
        self.assertEqual(cat, "사진")
        self.assertTrue(item["path"].endswith("실험사진1.png"))

    def test_폴더_미설정이면_빈_결과(self):
        import settings
        with mock.patch.object(settings, "get_photo_dirs", return_value=[]):
            self.assertEqual(library._photo_lookup(), {})

    def test_없는_폴더면_빈_결과(self):
        import settings
        with mock.patch.object(settings, "get_photo_dirs",
                               return_value=[str(self.dir / "없는폴더")]):
            self.assertEqual(library._photo_lookup(), {})

    def test_같은_이름의_png와_jpg면_하나만(self):
        self._touch("사진.png")
        self._touch("사진.jpg")
        out = library._photo_lookup()
        self.assertEqual(len(out), 1)

    def test_label_lookup_에서_등록_항목이_사진을_이긴다(self):
        self._touch("인사말.png")
        data = _fake_data(문자=[{"id": "A", "name": "인사말", "label": "인사말",
                                 "text": "안녕"}])
        with mock.patch.object(library, "load", return_value=data):
            out = library.label_lookup()
        self.assertEqual(out["인사말"][0], "문자")      # 사진이 아니라 등록 항목

    def test_label_lookup_에_사진이_병합된다(self):
        self._touch("실험사진1.png")
        with mock.patch.object(library, "load", return_value=_fake_data()):
            out = library.label_lookup()
        self.assertEqual(out["실험사진1"][0], "사진")


if __name__ == "__main__":
    unittest.main()
