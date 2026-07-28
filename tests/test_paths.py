# -*- coding: utf-8 -*-
"""저장 위치 규칙 (UI 제안 20 — exe 배포).

여기서 막으려는 사고: exe 로 만들었더니 껐다 켤 때마다 팔레트가 초기화되는 것.
원인은 __file__ 이 PyInstaller 의 임시 폴더를 가리키는 것인데, 임시 폴더는
프로그램이 끝나면 지워진다.
"""

import pathlib
import sys
import tempfile
import unittest
import unittest.mock as mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from hwp_palette.core import paths   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


class SourceRunTest(unittest.TestCase):
    r"""소스로 실행할 때 — 데이터는 **data/ 아래 한 곳**에 모인다 (2026-07-28).

    예전에는 프로젝트 루트에 그대로 쏟아졌다. 코드와 사용자 데이터가 같은
    자리에 섞이면 폴더를 열 때마다 무엇이 무엇인지 골라내야 한다.
    자원(assets 등)은 소스에 딸려온 것이라 그대로 루트다.
    """

    def test_frozen_이_아니다(self):
        self.assertFalse(paths.is_frozen())

    def test_데이터_폴더는_data(self):
        self.assertEqual(paths.data_dir(),
                         ROOT / paths.SRC_DATA_FOLDER_NAME)

    def test_자원_폴더는_프로젝트_폴더(self):
        self.assertEqual(paths.resource_dir(), ROOT)

    def test_설정_경로가_data_아래로_간다(self):
        from hwp_palette.core import settings
        from hwp_palette.model import library
        data = ROOT / paths.SRC_DATA_FOLDER_NAME
        self.assertEqual(settings.CONFIG_PATH, data / "config.json")
        self.assertEqual(library.LIBRARY_PATH, data / "library.json")
        self.assertEqual(library.FRAGMENTS_DIR, data / "fragments")


class FrozenTest(unittest.TestCase):
    """exe 로 묶였을 때 — 쓸 수 있는 곳을 찾아 데이터를 남긴다."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))

    def _frozen(self, exe_dir, meipass=None):
        exe = pathlib.Path(exe_dir) / "hwp_palette.exe"
        patches = [mock.patch.object(sys, "executable", str(exe)),
                   mock.patch.object(paths, "is_frozen", lambda: True)]
        if meipass is not None:
            patches.append(mock.patch.object(sys, "_MEIPASS", str(meipass),
                                             create=True))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_exe_옆_내_물감_폴더에_둔다(self):
        r"""**exe 옆에 파일을 흩뿌리지 않는다** (사용자 지적 2026-07-27).

        예전에는 exe 옆에 그대로 뒀다. 바탕화면에 exe 를 두면 config.json ·
        백업 3벌 · library.json · 백업 3벌 · app.log · fragments 까지
        파일 10개 + 폴더 1개가 바탕화면에 흩어졌다.
        """
        beside = self.tmp / "portable"
        beside.mkdir()
        self._frozen(beside)
        self.assertEqual(paths.data_dir(),
                         beside.resolve() / paths.DATA_FOLDER_NAME)

    def test_폴더_하나만_생긴다(self):
        beside = self.tmp / "desktop"
        beside.mkdir()
        self._frozen(beside)
        paths.data_dir()
        made = [p.name for p in beside.iterdir()]
        self.assertEqual(made, [paths.DATA_FOLDER_NAME])

    def test_옛_exe_가_흩뿌린_것을_폴더로_옮긴다(self):
        """v0.1.1 exe 를 써 본 사람의 팔레트가 조용히 사라지면 안 된다."""
        beside = self.tmp / "old"
        beside.mkdir()
        (beside / "config.json").write_text("{}", encoding="utf-8")
        (beside / "config.json.bak1").write_text("{}", encoding="utf-8")
        (beside / "library.json").write_text("{}", encoding="utf-8")
        (beside / "app.log").write_text("", encoding="utf-8")
        self._frozen(beside)

        folder = paths.data_dir()
        for name in ("config.json", "config.json.bak1", "library.json",
                     "app.log"):
            self.assertTrue((folder / name).exists(), name)
            self.assertFalse((beside / name).exists(), f"{name} 이 남아 있다")

    def test_새_폴더에_이미_있으면_덮어쓰지_않는다(self):
        beside = self.tmp / "both"
        (beside / paths.DATA_FOLDER_NAME).mkdir(parents=True)
        (beside / "config.json").write_text("옛것", encoding="utf-8")
        (beside / paths.DATA_FOLDER_NAME / "config.json").write_text(
            "지금 쓰는 것", encoding="utf-8")
        self._frozen(beside)

        folder = paths.data_dir()
        self.assertEqual((folder / "config.json").read_text(encoding="utf-8"),
                         "지금 쓰는 것")

    def test_임시_폴더에_두지_않는다(self):
        # 이것이 이 파일의 핵심. _MEIPASS 는 프로그램이 끝나면 지워진다.
        beside = self.tmp / "app"
        beside.mkdir()
        meipass = self.tmp / "_MEI12345"
        meipass.mkdir()
        self._frozen(beside, meipass=meipass)
        self.assertNotEqual(paths.data_dir(), meipass)
        self.assertEqual(paths.data_dir(),
                         beside.resolve() / paths.DATA_FOLDER_NAME)

    def test_자원은_임시_폴더에서_읽는다(self):
        # 아이콘처럼 딸려온 파일은 거기 풀리므로 여기서 읽는 게 맞다.
        meipass = self.tmp / "_MEI999"
        meipass.mkdir()
        self._frozen(self.tmp, meipass=meipass)
        self.assertEqual(paths.resource_dir(), meipass)

    def test_exe_옆이_막혔으면_AppData_로_물러선다(self):
        beside = self.tmp / "programfiles"
        beside.mkdir()
        appdata = self.tmp / "appdata"
        appdata.mkdir()
        self._frozen(beside)
        real = paths._writable
        # exe 옆(내 물감 폴더)만 못 쓰는 상황을 흉내낸다 — Program Files 처럼
        blocked = beside.resolve() / paths.DATA_FOLDER_NAME
        p = mock.patch.object(paths, "_writable",
                              lambda d: False if d == blocked else real(d))
        p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch.dict("os.environ", {"LOCALAPPDATA": str(appdata)})
        p2.start()
        self.addCleanup(p2.stop)
        self.assertEqual(paths.data_dir(), appdata / paths.APP_NAME)

    def test_어디도_못_쓰면_예외_대신_exe_옆을_돌려준다(self):
        beside = self.tmp / "readonly"
        beside.mkdir()
        self._frozen(beside)
        p = mock.patch.object(paths, "_writable", lambda d: False)
        p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch.dict("os.environ", {"LOCALAPPDATA": "", "APPDATA": ""})
        p2.start()
        self.addCleanup(p2.stop)
        self.assertEqual(paths.data_dir(),                     # 안 터진다
                         beside.resolve() / paths.DATA_FOLDER_NAME)


class WritableTest(unittest.TestCase):

    def test_없는_폴더는_만들어서_쓴다(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, True))
        target = tmp / "새폴더" / "안쪽"
        self.assertTrue(paths._writable(target))
        self.assertTrue(target.is_dir())

    def test_시험용_파일을_남기지_않는다(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, True))
        paths._writable(tmp)
        self.assertEqual(list(tmp.iterdir()), [])


class SpecTest(unittest.TestCase):
    """빌드 설정이 개인 데이터를 exe 에 넣지 않는지."""

    def test_개인_데이터가_datas_에_없다(self):
        spec = (ROOT / "hwp_palette.spec").read_text(encoding="utf-8")
        datas = spec.split("datas=")[1].split("]")[0]
        for name in ("config.json", "library.json", "fragments", "app.log"):
            self.assertNotIn(name, datas, f"{name} 이 exe 에 들어갑니다")

    def test_아이콘은_넣는다(self):
        spec = (ROOT / "hwp_palette.spec").read_text(encoding="utf-8")
        self.assertIn("icon-96.png", spec)

    def test_한글_COM_모듈을_명시했다(self):
        # 빠지면 exe 에서만 '한글을 찾을 수 없습니다'가 난다 (소스로는 잘 됨)
        spec = (ROOT / "hwp_palette.spec").read_text(encoding="utf-8")
        for mod in ("win32com.client", "pythoncom", "pyhwpx"):
            self.assertIn(mod, spec)


if __name__ == "__main__":
    unittest.main()
