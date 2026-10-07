"""Server bat CAI LAI EXE (pc_app_required_version moi hon exe dang chay) -> KHONG ap core ngam.

Ca that 07/10 (v1.1.202610071122): gui.py doi nen release bat cai lai exe, nhung app ap core bundle
TRUOC, restart roi moi hoi cai exe. Core moi can thu exe cu khong co (`uuid`) -> restart la chet,
khong bao gio toi buoc hoi -> user ket. Core moi viet cho vo (gui.py) moi: exe chua cai thi dung
nap core, di thang vao buoc hoi cai exe.

Kem theo: cai exe moi xong thi `bot_bundle` cu (cu hon exe) phai bi xoa, khong thi exe moi lai nap
core cu de len code dung cua no.
"""
import unittest
from unittest import mock

from bot import updater

VJ = {
    "version": "1.1.202610080900",
    "bundle_version": "1.1.202610080900",
    "bundle_url": "https://x/aTSBot-bundle.zip",
    "pc_app_version": "1.1.202610080900",
    "pc_app_url": "https://x/aTSBot.zip",
    "pc_app_required_version": "1.1.202610071122",
    "pc_app_required": True,
    "notes": "n",
}


class KhongApCoreKhiExeBatBuocTest(unittest.TestCase):
    def setUp(self):
        p1 = mock.patch.object(updater, "UPDATE_SOURCES", [("GitHub", "https://x/version.json")])
        p2 = mock.patch.object(updater, "_fetch_version_json", side_effect=lambda u, timeout: dict(VJ))
        for p in (p1, p2):
            p.start()
            self.addCleanup(p.stop)

    def _bundle_dang_cai(self, ver):
        p = mock.patch.object(updater, "installed_bundle_version", return_value=ver)
        p.start()
        self.addCleanup(p.stop)

    def test_exe_cu_hon_moc_bat_buoc_thi_bo_qua_core_va_hoi_cai_exe(self):
        exe = "1.1.202609281436"           # exe user ket 07/10
        self._bundle_dang_cai("1.1.202609281601")
        self.assertIsNone(updater.check_bundle_update(exe))
        info = updater.check_update(exe)
        self.assertIsNotNone(info)
        self.assertEqual(info[0], "1.1.202610080900")

    def test_exe_da_dat_moc_thi_van_ap_core_ngam(self):
        exe = "1.1.202610071122"
        self._bundle_dang_cai("1.1.202610071122")
        info = updater.check_bundle_update(exe)
        self.assertIsNotNone(info)
        self.assertEqual(info[0], "1.1.202610080900")
        self.assertIsNone(updater.check_update(exe))

    def test_server_cu_khong_co_moc_thi_giu_hanh_vi_cu(self):
        VJ_CU = {k: v for k, v in VJ.items() if k != "pc_app_required_version"}
        self._bundle_dang_cai("1.1.202609281601")
        with mock.patch.object(updater, "_fetch_version_json", side_effect=lambda u, timeout: dict(VJ_CU)):
            self.assertIsNotNone(updater.check_bundle_update("1.1.202609281436"))


class CaiExeXongXoaCoreCuTest(unittest.TestCase):
    def test_bat_update_luon_xoa_bot_bundle(self):
        bat = updater._noi_dung_update_bat("aTSBot.exe", pin_version="")
        self.assertIn('rmdir /s /q "bot_bundle"', bat)
        # xoa TRUOC khi chep exe moi + mo lai app
        self.assertLess(bat.index('rmdir /s /q "bot_bundle"'), bat.index("xcopy"))
        self.assertIn('start "" "aTSBot.exe"', bat)
        self.assertIn('taskkill /f /im "aTSBot.exe"', bat)

    def test_bat_ban_dev_khong_kill_python(self):
        bat = updater._noi_dung_update_bat("python.exe", pin_version="")
        self.assertNotIn("taskkill", bat)


if __name__ == "__main__":
    unittest.main()
