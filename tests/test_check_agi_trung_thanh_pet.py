"""Check AGI: them cot TRUNG THANH cua pet dang dung, < 40 thi canh bao CAM.

User chot 05/09: "them 1 cot Trung thanh cua pet dang dung, khi Trung thanh < 40 thi cung canh
bao cam giong nhu lech agi > 10". Va: KHONG them cau tom tat, chi cot + to cam dong + chu nut.

`< 40` la CHAT DUOI: 40 chua canh bao, 39 moi canh bao.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android")


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class _St:
    def __init__(self, pid, confirmed=True):
        self.active_pet_id = pid
        self.active_pet_confirmed = confirmed


class _C:
    """Client gia. `pet_faith` khoa theo pet_id - giong client that (doc goi 0x0f, offset +27)."""

    def __init__(self, active=0xA05A, faith=None, confirmed=True, ten="Quan Vu"):
        self.state = _St(active, confirmed)
        self.pet_faith = dict(faith or {})
        self.pet_name = ten

    def pet_name_out(self):
        return self.pet_name if self.state.active_pet_confirmed else None


class TestDocTrungThanhCuaPetDANGDUNG(unittest.TestCase):
    """Diem de sai nhat: `pet_faith` co CA 4 con mang theo. Lay bua con dau la bao sai."""

    def test_lay_dung_con_active_khong_phai_con_dau(self):
        c = _C(active=0xA05A, faith={0xA051: 12, 0xA05A: 98, 0x36B9: 100})
        self.assertEqual(R._trung_thanh_pet_dang_dung(c), 98)

    def test_chua_xac_nhan_pet_ra_tran_thi_KHONG_biet(self):
        """`pet_name_out()` tra None = chua chac con nao dang danh -> khong canh bao oan."""
        c = _C(active=0xA05A, faith={0xA05A: 10}, confirmed=False)
        self.assertIsNone(R._trung_thanh_pet_dang_dung(c))

    def test_khong_co_du_lieu_thi_None_chu_khong_no(self):
        self.assertIsNone(R._trung_thanh_pet_dang_dung(_C(active=0xA05A, faith={})))
        self.assertIsNone(R._trung_thanh_pet_dang_dung(_C(active=0, faith={0: 5})))
        self.assertIsNone(R._trung_thanh_pet_dang_dung(object()))


class TestBaoCao(unittest.TestCase):
    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._pa, self._as = R.party_accounts, R.account_status
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self.trang_thai = {}
        R.account_status = lambda u: self.trang_thai.get(u, {})

    def tearDown(self):
        R.party_accounts, R.account_status = self._pa, self._as

    def _dat(self, u, agi_char, agi_pet, faith, pet="Quan Vu"):
        self.trang_thai[u] = {"char": u, "char_agi": agi_char, "pet_name": pet,
                              "pet_agi": agi_pet, "pet_faith": faith}

    def test_cot_moi_co_trong_bao_cao(self):
        self._dat("a1", 76, 76, 98)
        bc = R.party_agi_report(self.PARTY)
        self.assertEqual(bc["rows"][0]["pet_faith"], 98)

    def test_duoi_40_thi_canh_bao(self):
        for u, tt in zip(self.ACCS, (98, 39, 100)):
            self._dat(u, 76, 76, tt)
        bc = R.party_agi_report(self.PARTY)
        self.assertEqual(bc["faith_thap"], ["a2"])
        self.assertTrue(bc["canh_bao"])

    def test_dung_40_thi_CHUA_canh_bao(self):
        """User viet '< 40' -> chat duoi. 40 khong canh bao, 39 moi canh bao."""
        for u in self.ACCS:
            self._dat(u, 76, 76, 40)
        self.assertEqual(R.party_agi_report(self.PARTY)["faith_thap"], [])
        self.assertEqual(R.TRUNG_THANH_CANH_BAO, 40)

    def test_khong_co_pet_thi_khong_tinh(self):
        self._dat("a1", 76, None, None, pet="")
        self._dat("a2", 76, 76, 90)
        self._dat("a3", 76, 76, 90)
        bc = R.party_agi_report(self.PARTY)
        self.assertEqual(bc["faith_thap"], [])
        self.assertIsNone(bc["rows"][0]["pet_faith"])

    def test_HAI_canh_bao_KHONG_lan_nhau(self):
        """`warning` phai giu nguyen nghia CU (chi lech AGI). Nut hien so trong ngoac la DO LECH -
        gop trung thanh vao do la user nhin so lai tuong dang lech AGI."""
        for u in self.ACCS:                     # AGI deu nhau, chi trung thanh thap
            self._dat(u, 76, 76, 10)
        bc = R.party_agi_report(self.PARTY)
        self.assertFalse(bc["warning"], "trung thanh thap ma bao la lech AGI")
        self.assertEqual(bc["spread"], 0)
        self.assertTrue(bc["canh_bao"])

    def test_lech_AGI_van_bao_nhu_cu(self):
        self._dat("a1", 76, 76, 90)
        self._dat("a2", 76, 95, 90)
        self._dat("a3", 76, 76, 90)
        bc = R.party_agi_report(self.PARTY)
        self.assertTrue(bc["warning"])
        self.assertEqual(bc["spread"], 19)
        self.assertEqual(bc["faith_thap"], [])
        self.assertTrue(bc["canh_bao"])


class TestGuiPC(unittest.TestCase):
    def setUp(self):
        self.src = _doc("gui.py")
        i = self.src.find("def _show_party_agi(")
        self.than = self.src[i:self.src.find("\n    def ", i + 10)]

    def test_co_cot_trung_thanh(self):
        self.assertIn('("pet_faith", "Trung thành"', self.than)

    def test_to_cam_dong_trung_thanh_thap(self):
        self.assertIn("tag_configure", self.than, "khong to mau dong nao")
        self.assertIn("ctrl.TRUNG_THANH_CANH_BAO", self.than,
                      "hard-code so 40 o GUI -> sua nguong mot noi la lech")

    def test_KHONG_them_cau_tom_tat(self):
        """User chot: 'ko can dau'."""
        self.assertNotIn("sắp bỏ đi", self.than)
        self.assertNotIn("trung thành <", self.than)

    def test_nut_ghi_RO_tung_loai(self):
        i = self.src.find('agi_btn.configure(text="⚠ Check AGI')
        self.assertGreater(i, 0, "nut khong con phan biet hai loai canh bao")
        khoi = self.src[max(0, i - 700):i + 200]
        self.assertIn('agi_report.get("canh_bao")', khoi)
        self.assertIn("TT ", khoi)


class TestGuiAPK(unittest.TestCase):
    """APK co CUNG man hinh -> phai lam ca hai ban (rule 'APK giong het PC')."""

    def setUp(self):
        self.main = _doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                         "MainActivity.kt")

    def test_AccountStatus_mang_truong_moi(self):
        self.assertIn("val petFaith: Int? = null",
                      _doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                           "AccountStatus.kt"))

    def test_service_doc_pet_faith_tu_python(self):
        self.assertIn('petFaith = gInt("pet_faith")',
                      _doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                           "BotForegroundService.kt"))

    def test_dialog_hien_trung_thanh_va_to_cam(self):
        self.assertIn("Trung thành", self.main)
        self.assertIn("ttThapDong", self.main)

    def test_nut_dung_co_GOP(self):
        self.assertIn("agiCanhBao", self.main)
        self.assertIn('"TT $ttThap"', self.main)

    def test_NGUONG_KHOP_voi_PC(self):
        """Hai ben chep tay cung mot so -> phai co cho chan lech (bai hoc Servers.kt)."""
        m = re.search(r"const val TRUNG_THANH_CANH_BAO = (\d+)", self.main)
        self.assertIsNotNone(m, "APK khong khai nguong")
        self.assertEqual(int(m.group(1)), R.TRUNG_THANH_CANH_BAO,
                         "nguong APK va PC LECH NHAU")


if __name__ == "__main__":
    unittest.main()
