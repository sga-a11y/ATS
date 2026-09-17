# -*- coding: utf-8 -*-
"""BOT TU PHAT HIEN SERVER MOI tu CDN tai nguyen cua game.

Client lay danh sach server tu CDN chu khong nhet trong APK (`_lua_dec/Logic/Network.lua`):
    this.servers = json.decode(CGResourceManager.DownloadText("ServerList.dat", true));
Duong dan that (moi ra tu `global-metadata.dat` + logcat Unity, 17/09):
    https://cdn-gz06.mobigame.vn/tsr/ResourcePath_ANDROID.dat  -> {"DataVer":"1.0.9"}
    https://cdn-gz06.mobigame.vn/tsr/<DataVer>/Android/ServerList.dat

CDN CO SERVER MOI TRUOC CA KHI SERVER GAME MO LAI (user 17/09: "dang bao tri de mo server moi,
server chua mo lai nhung client thay update roi") - do la ly do tinh nang nay co ich.

CAC BAI TEST O DAY KHONG GOI MANG: truyen ham `tai` gia. Bai duy nhat cham mang nam o cuoi va TU
BO QUA khi khong co mang.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import servers_cdn


DA_KHAI = {
    "trieu_van": {"label": "Triệu Vân", "ip": "103.82.28.98", "id": 1},
    "dong_trac": {"label": "Đồng Trác", "ip": "103.190.202.63", "id": 19},
}
CDN = [
    {"id": 1, "name": "Triệu Vân", "host": "103.82.28.98", "port": 6614},
    {"id": 19, "name": "Đồng Trác", "host": "103.190.202.63", "port": 6614},
    {"id": 20, "name": "Tiểu Kiều - New", "host": "103.190.202.64", "port": 6614},
]


class TestTimServerMoi(unittest.TestCase):
    def test_chi_lay_id_CHUA_KHAI(self):
        moi = servers_cdn.tim_server_moi(DA_KHAI, CDN)
        self.assertEqual(list(moi.values()),
                         [{"label": "Tiểu Kiều - New", "ip": "103.190.202.64", "id": 20}])

    def test_so_theo_ID_khong_theo_TEN(self):
        """Ten hien thi doi duoc (vd bo chu "New" sau dot mo server), con id la thu di trong goi
        auth - so theo ten thi hom sau se them TRUNG mot server."""
        da_khai = dict(DA_KHAI, tieu_kieu={"label": "Tiểu Kiều", "ip": "103.190.202.64", "id": 20})
        self.assertEqual(servers_cdn.tim_server_moi(da_khai, CDN), {})

    def test_khong_co_gi_moi_thi_rong(self):
        self.assertEqual(servers_cdn.tim_server_moi(DA_KHAI, CDN[:2]), {})


class TestKhoaNoiBo(unittest.TestCase):
    def test_bo_dau_va_snake_case(self):
        self.assertEqual(servers_cdn.khoa_noi_bo("Tiểu Kiều - New"), "tieu_kieu_new")
        self.assertEqual(servers_cdn.khoa_noi_bo("Gia Cát Lượng"), "gia_cat_luong")
        self.assertEqual(servers_cdn.khoa_noi_bo("Đồng Trác"), "dong_trac")

    def test_trung_khoa_thi_them_hau_to(self):
        self.assertEqual(servers_cdn.khoa_noi_bo("Mã Siêu", {"ma_sieu"}), "ma_sieu_2")


class TestCapNhat(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_them_vao_danh_sach_va_luu_overlay(self):
        sv = dict(DA_KHAI)
        them = servers_cdn.cap_nhat(sv, self.d, tai=lambda: CDN)
        self.assertIn("tieu_kieu_new", them)
        self.assertEqual(sv["tieu_kieu_new"]["ip"], "103.190.202.64")
        self.assertEqual(servers_cdn.doc_overlay(self.d), them, "khong luu lai -> lan sau mat")

    def test_KHONG_dung_toi_servers_json(self):
        """`servers.json` dung chung PC/APK va `Servers.kt` co bang FALLBACK chep tay voi CONG CHAN
        BUILD bat hai ben khop. Tu ghi vao do thi moi lan CDN them server la build DO."""
        sv = dict(DA_KHAI)
        servers_cdn.cap_nhat(sv, self.d, tai=lambda: CDN)
        self.assertEqual(os.listdir(self.d), ["servers_cdn.json"])

    def test_mat_mang_thi_VAN_dung_ban_da_phat_hien(self):
        sv = dict(DA_KHAI)
        servers_cdn.cap_nhat(sv, self.d, tai=lambda: CDN)      # lan 1: co mang
        sv2 = dict(DA_KHAI)
        them = servers_cdn.cap_nhat(sv2, self.d, tai=lambda: [])   # lan 2: mat mang
        self.assertIn("tieu_kieu_new", sv2, "mat mang la mat luon server da biet")
        self.assertIn("tieu_kieu_new", them)

    def test_loi_mang_KHONG_nem_ra_ngoai(self):
        """Khoi dong bot khong duoc chet vi CDN loi."""
        def _no():
            raise OSError("khong co mang")
        sv = dict(DA_KHAI)
        self.assertEqual(servers_cdn.cap_nhat(sv, self.d, tai=_no), {})
        self.assertEqual(sv, DA_KHAI)


class TestNoiVaoChoKhoiDong(unittest.TestCase):
    """Neo theo MA: sua nhanh ma quen noi day thi tinh nang co ma khong bao gio chay."""

    def _doc(self, *p):
        with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
            return fh.read()

    def test_config_nap_overlay_luc_khoi_dong(self):
        """Doc FILE, khong hoi mang - khoi dong khong duoc phu thuoc mang."""
        for p in (("bot", "config.py"),
                  ("android", "app", "src", "main", "python", "train_bot", "config.py")):
            s = self._doc(*p)
            self.assertIn("servers_cdn", s, "%s khong nap server da phat hien" % p[-2])
            self.assertIn("doc_overlay(", s)

    def test_co_cho_HOI_CDN_o_thread_nen(self):
        self.assertIn("cap_nhat_nen(", self._doc("gui.py"), "GUI khong hoi CDN")
        self.assertIn("cap_nhat_nen(", self._doc("run_party_digioi.py"),
                      "APK khong co cho nao khac chay Python luc mo app")

    def test_GUI_doc_config_SERVERS_khong_doc_thang_file(self):
        """`config.SERVERS` la noi da nhap them server tu CDN. Doc thang `servers.json` thi server
        moi co trong bot ma KHONG BAO GIO hien ra de chon
        (user 17/09: "t chay ban dev ko thay tu phat hien sv moi")."""
        s = self._doc("gui.py")
        i = s.index("self.servers = [(k, v.get(")
        khoi = s[max(0, i - 600):i]
        self.assertIn("config, \"SERVERS\"", khoi,
                      "GUI dung danh sach server KHONG co server moi phat hien duoc")

    def test_APK_doc_overlay_de_hien_trong_UI(self):
        """Assets read-only nen server moi khong the nam trong `servers.json` cua APK da cai."""
        s = self._doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                      "Servers.kt")
        self.assertIn("servers_cdn.json", s)
        self.assertIn("filesDir", s)

    def test_APK_hoi_CDN_NGAY_khi_mo_app(self):
        """`BotForegroundService` chi start Python khi user bam Start. Cho toi luc do thi lan dau
        mo app KHONG BAO GIO thay server moi - phai Start mot lan roi MO LAI app
        (user 17/09: "ban apk ko tu update server moi")."""
        kt = self._doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                       "Servers.kt")
        self.assertIn("refreshFromCdn", kt, "APK khong chu dong hoi CDN")
        self.assertIn("Python.isStarted()", kt, "khong tu khoi dong Python -> khong goi duoc")
        self.assertIn("servers_cdn", kt, "phai dung CHUNG logic voi ban PC, khong viet lai Kotlin")
        act = self._doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                        "MainActivity.kt")
        self.assertIn("Servers.refreshFromCdn(", act, "mo app khong goi -> khong bao gio chay")

    def test_APK_ve_lai_dropdown_khi_co_server_moi(self):
        """`Servers.ALL` la property thuong - tu no khong lam Compose recompose."""
        kt = self._doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                       "Servers.kt")
        self.assertIn("mutableIntStateOf", kt)
        act = self._doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                        "MainActivity.kt")
        i = act.index("Servers.ALL.forEach")
        self.assertIn("Servers.tick.intValue", act[max(0, i - 300):i],
                      "dropdown khong doc tick -> server moi chi hien o lan mo app sau")

    def test_khai_bao_trong_SHARED(self):
        """File .py moi trong bot/ ma quen khai la sync BAO LOI (xem CLAUDE.md)."""
        self.assertIn('"servers_cdn.py"', self._doc("tools", "sync_apk_python.py"))


class TestCDNThat(unittest.TestCase):
    """Cham mang THAT - tu bo qua khi khong co mang / CDN doi duong dan."""

    def test_lay_duoc_danh_sach(self):
        ds = servers_cdn.tai_danh_sach()
        if not ds:
            self.skipTest("khong co mang hoac CDN doi duong dan")
        self.assertGreater(len(ds), 10)
        for s in ds:
            self.assertTrue(s["host"] and s["id"])


if __name__ == "__main__":
    unittest.main()
