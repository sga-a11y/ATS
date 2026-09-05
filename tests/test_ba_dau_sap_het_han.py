"""BA DAU sap het han -> bao o man "Chu y", nut Chu y doi mau CAM.

"Ba Dau" (`0xb5f1`) = tu hoi day HP/SP sau moi tran, KHONG ton item. Xem KNOWLEDGE.md muc 7p.
Han dung ve qua `S:023-135 <各種到期時間>` (opcode 0x17 sub 135 = 0x87), truong `thoi gian(8)` la
MOC HET HAN dang OLE Automation Date - KHONG phai so giay con lai, KHONG phai unix timestamp.
Phai so voi GIO SERVER (`CGTimer.serverTime`), khong phai gio may.

User chot 01/09:
  - con >0 VA <1 ngay moi bao; time = 0 (da het) thi KHONG bao nua,
  - co canh bao nay thi nut "Chu y" doi mau CAM giong nut "Check AGI" luc lech,
  - CHI kiem luc login.
"""
from __future__ import annotations

import datetime
import io
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import run_party_digioi as rpd          # noqa: E402
finally:
    sys.argv = _argv

from bot.client import GameClient           # noqa: E402

MOC = datetime.datetime(1899, 12, 30)


def _ole(dt):
    return (dt - MOC).total_seconds() / 86400.0


def _goi_han(loai, dt, ket_qua=1):
    """S:023-135: 9 byte header gia + ket qua(1) + loai(1) + thoi gian(8)."""
    return b"\x00" * 9 + bytes([ket_qua, loai]) + struct.pack("<d", _ole(dt))


def _bot(lech_gio=datetime.timedelta(0)):
    c = GameClient.__new__(GameClient)
    c._label = "t"
    c.han_dung = {}
    c._server_time_span = lech_gio
    return c


class TestDocGoiHanDung(unittest.TestCase):
    def test_doc_dung_moc_het_han(self):
        het = datetime.datetime(2026, 9, 2, 14, 30)
        c = _bot()
        c._on_han_dung(_goi_han(1, het))
        self.assertEqual(c.han_dung["ba_dau"].replace(microsecond=0), het)

    def test_phan_biet_dung_3_loai(self):
        c = _bot()
        het = datetime.datetime(2026, 9, 2, 14, 30)
        for loai, khoa in ((1, "ba_dau"), (2, "da_thu_ho"), (3, "the_vip")):
            c._on_han_dung(_goi_han(loai, het))
            self.assertIn(khoa, c.han_dung)

    def test_ket_qua_2_la_THAT_BAI_khong_phai_loai_2(self):
        c = _bot()
        c._on_han_dung(_goi_han(1, datetime.datetime(2026, 9, 2), ket_qua=2))
        self.assertEqual(c.han_dung, {}, "coi ket qua 2 la du lieu -> ghi han rac")

    def test_thoi_gian_0_thi_XOA_han(self):
        """Client: `if time ~= 0` moi set, nguoc lai la xoa."""
        c = _bot()
        c.han_dung["ba_dau"] = datetime.datetime(2026, 9, 2)
        c._on_han_dung(b"\x00" * 9 + bytes([1, 1]) + struct.pack("<d", 0.0))
        self.assertNotIn("ba_dau", c.han_dung)

    def test_goi_cut_khong_lam_sap(self):
        c = _bot()
        c._on_han_dung(b"\x00" * 9 + b"\x01")
        self.assertEqual(c.han_dung, {})


class TestGioServer(unittest.TestCase):
    def test_luu_DO_LECH_chu_khong_luu_moc(self):
        """Gio server troi tiep theo dong ho may, khong dung yen o moc vua nhan."""
        c = _bot(None)
        c._server_time_span = None
        gio = datetime.datetime.now() + datetime.timedelta(hours=3)
        c._nho_gio_server(struct.pack("<d", _ole(gio)))
        self.assertIsNotNone(c._server_time_span)
        self.assertAlmostEqual(c._server_time_span.total_seconds(), 3 * 3600, delta=5)

    def test_gio_rac_thi_BO_QUA(self):
        c = _bot(None)
        c._server_time_span = None
        c._nho_gio_server(struct.pack("<d", 0.0))
        self.assertIsNone(c._server_time_span, "gio rac ma nhan -> tinh han sai bet")

    def test_chua_co_gio_server_thi_KHONG_DOAN(self):
        c = _bot(None)
        c._server_time_span = None
        c.han_dung["ba_dau"] = datetime.datetime.now() + datetime.timedelta(hours=2)
        self.assertIsNone(c.han_dung_con_lai("ba_dau"))

    def test_con_lai_tinh_theo_GIO_SERVER(self):
        """Gio may lech 10 tieng so voi server -> con lai phai theo server."""
        c = _bot(datetime.timedelta(hours=10))
        c.han_dung["ba_dau"] = datetime.datetime.now() + datetime.timedelta(hours=12)
        con = c.han_dung_con_lai("ba_dau")
        self.assertAlmostEqual(con.total_seconds(), 2 * 3600, delta=5)

    def test_DA_HET_HAN_thi_tra_None(self):
        c = _bot()
        c.han_dung["ba_dau"] = datetime.datetime.now() - datetime.timedelta(minutes=1)
        self.assertIsNone(c.han_dung_con_lai("ba_dau"))


class TestNguongBao(unittest.TestCase):
    def setUp(self):
        rpd.ba_dau_notify.clear()
        rpd.ba_dau_notify_dismissed.clear()

    def _kiem(self, con):
        c = _bot()
        if con is not None:
            c.han_dung["ba_dau"] = datetime.datetime.now() + con
        rpd._kiem_han_ba_dau(c, "accX")
        return rpd.ba_dau_notify.get("accX")

    def test_con_duoi_1_ngay_thi_BAO(self):
        self.assertIsNotNone(self._kiem(datetime.timedelta(hours=5)))

    def test_con_TREN_1_ngay_thi_KHONG_bao(self):
        self.assertIsNone(self._kiem(datetime.timedelta(days=3)))

    def test_DA_HET_HAN_thi_KHONG_bao(self):
        """User chot: "khi time =0 roi thi ko bao nua"."""
        self.assertIsNone(self._kiem(datetime.timedelta(minutes=-1)))

    def test_KHONG_CO_Ba_Dau_thi_KHONG_bao(self):
        self.assertIsNone(self._kiem(None))

    def test_het_sap_het_thi_XOA_thong_bao_cu(self):
        rpd.ba_dau_notify["accX"] = "cu"
        self.assertIsNone(self._kiem(datetime.timedelta(days=3)))

    def test_noi_dung_co_GIO_PHUT_NGAY(self):
        luc = self._kiem(datetime.timedelta(hours=3))
        self.assertIn("giờ", luc)
        self.assertIn("phút", luc)
        self.assertIn("ngày", luc)

    def test_bo_qua_duoc(self):
        self._kiem(datetime.timedelta(hours=3))
        rpd.ba_dau_notify_skip("accX")
        self.assertEqual([i for i in rpd.ba_dau_notify_items(0) if i["user"] == "accX"], [])


class TestChayLucLogin(unittest.TestCase):
    def test_goi_trong_viec_vat_luc_login(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("_kiem_han_ba_dau(c, username, label)")
        self.assertGreater(i, 0, "khong goi luc login")
        i_pet = s.find('pcfg.get("auto_pet_skill", True)')
        self.assertGreater(i_pet, i, "phai nam trong khoi viec vat luc login")


class TestGUI(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_gop_vao_man_chu_y(self):
        self.assertIn("ctrl.ba_dau_notify_items(pidx)", self.src)

    def test_dat_TRUOC_quan_doan(self):
        """User chot 01/09: Ba Dau la viec CO HAN GIO -> phai len truoc quan doan/du diem."""
        i = self.src.find("def _party_notify_items(self, pidx):")
        self.assertGreater(i, 0)
        than = self.src[i:self.src.find("\n    def ", i + 10)]
        i_ba_dau = than.find("ctrl.ba_dau_notify_items(pidx)")
        i_quan_doan = than.find("_party_legion_notify(pidx)")
        i_tui = than.find("_party_bag_notify(pidx)")
        self.assertGreater(i_ba_dau, i_tui, "van sau tui do la dung")
        self.assertLess(i_ba_dau, i_quan_doan, "Ba Dau phai len TRUOC quan doan")

    def test_co_dong_hien_thi_dung_cau_chu(self):
        i = self.src.find('if it.get("_ba_dau"):')
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 900]
        self.assertIn("Ba Đậu Yêu sẽ hết hạn vào lúc", khoi)
        self.assertIn("ctrl.ba_dau_notify_skip(_u)", khoi)
        self.assertIn("_skips.append", khoi, "khong vao _skips thi 'Bo qua tat ca' khong phu")

    def test_nut_Chu_y_doi_mau_CAM(self):
        """Cung mau voi nut 'Check AGI' luc lech (#f59e0b)."""
        # 04/09: `_gap` gio lay tu `_gap_notify` da tinh o tren (dung chung voi cham party/nhom).
        i = self.src.find("_gap = _gap_notify")
        self.assertGreater(i, 0, "nut Chu y khong doi mau -> khong noi bat duoc")
        khoi = self.src[i:i + 700]
        self.assertIn('bg="#f59e0b"', khoi)
        self.assertIn('bg="#fff3cd"', khoi, "het canh bao phai tra ve mau vang nhat")

    def test_mau_CAM_giong_nut_check_AGI(self):
        # 05/09: chu nut doi dang (them "TT n" cho canh bao trung thanh pet) nen khong neo theo
        # chuoi cu nua - neo theo CHO doi mau.
        i_agi = self.src.find('agi_btn.configure(text="⚠ Check AGI')
        self.assertGreater(i_agi, 0, "nut Check AGI khong con nhanh canh bao")
        self.assertIn('bg="#f59e0b"', self.src[i_agi:i_agi + 300])


class TestAPKCoCanhBao(unittest.TestCase):
    def _kt(self, ten):
        with io.open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot",
                                  "android", ten), encoding="utf-8") as fh:
            return fh.read()

    def test_service_co_cau_noi(self):
        s = self._kt("BotForegroundService.kt")
        # `ba_dau_notify_items` di qua helper chung `notifyRows(fn, pidx)` -> ten ham la THAM SO.
        self.assertIn('"ba_dau_notify_items"', s)
        self.assertIn('callAttr("ba_dau_notify_skip"', s)

    def test_gop_vao_man_chu_y_va_dat_TRUOC_quan_doan(self):
        s = self._kt("MainActivity.kt")
        i = s.find("baDauNotifyItems(_pi)")
        j = s.find("legionNotifyItems(_pi)")
        self.assertGreater(i, 0, "APK khong hien canh bao Ba Dau")
        self.assertLess(i, j, "Ba Dau phai len TRUOC quan doan")

    def test_co_dong_hien_thi(self):
        s = self._kt("MainActivity.kt")
        self.assertIn('it0["kind"] == "ba_dau"', s)
        self.assertIn("Ba Đậu Yêu sẽ hết hạn vào lúc", s)

    def test_nut_Chu_y_doi_mau_CAM(self):
        """`StatusConnecting` = 0xFFF59E0B - DUNG mau cam voi nut Check AGI ben PC (#f59e0b)."""
        s = self._kt("MainActivity.kt")
        # Loai CAN LAM NGAY -> nut cam. Ban APK chua co muc "tui gan day" nen chi 2 loai.
        # Loai CAN LAM NGAY -> nut cam (user chot 02/09: Ba Dau / tui gan day / chua co quan doan)
        i = s.find("val gapNotify")
        self.assertGreater(i, 0)
        for _k in ('"ba_dau"', '"legion"', '"bag"'):
            self.assertIn(_k, s[i:i + 220])
        i = s.find("val gapNotify")
        self.assertIn("StatusConnecting", s[i:i + 600])
        self.assertIn("val StatusConnecting = Color(0xFFF59E0B)", self._kt("Theme.kt"))


if __name__ == "__main__":
    unittest.main()
