"""Canh bao "tui do sap day" + nut "Chu y" mau CAM.

User chot 01/09: "trong chu y, tui do chuyen sang canh bao khi so slot trong <10" (truoc la <= 5).
Tui gan day thi nhieu viec HONG AM THAM truoc khi tui day han: nhan qua mail that bai (xem
`claim_mail`), khong nhat duoc do roi trong tran, khong mua duoc do o lo.

User chot 02/09:
  - "dong bo sang apk lam luon di" -> luat phai nam o CORE (`run_party_digioi`), khong phai chi
    trong `gui.py`. Truoc day chi o GUI nen ban APK KHONG he co muc canh bao tui - dung bay
    "chep tay o dau la lech o do" trong CLAUDE.md.
  - nut "Chu y" chuyen CAM khi co: Ba Dau sap het han / tui gan day / chua co quan doan.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _core():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _gui():
    with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
        return fh.read()


def _kt(ten):
    with io.open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot",
                              "android", ten), encoding="utf-8") as fh:
        return fh.read()


class TestNguongCanhBao(unittest.TestCase):
    def setUp(self):
        self.src = _core()
        i = self.src.find("BAG_CANH_BAO_SLOT_TRONG = ")
        self.assertGreater(i, 0, "khong con hang so nguong -> nguong bi viet cung o giua ham")
        self.than = self.src[i:self.src.find("\ndef bag_notify_skip", i)]

    def test_nguong_la_10(self):
        self.assertIn("BAG_CANH_BAO_SLOT_TRONG = 10", self.src)

    def test_KHONG_con_nguong_5_cu(self):
        self.assertNotIn("if free > 5:", self.than, "van dung nguong 5 cu")

    def test_so_sanh_dung_chieu(self):
        """`free >= nguong` moi bo qua -> con 9 slot VAN canh bao, con 10 thi thoi."""
        self.assertIn("if free >= BAG_CANH_BAO_SLOT_TRONG:", self.than)

    def test_dung_HANG_SO_khong_viet_so_thang(self):
        khoi = self.than[self.than.find("free = c.bag_free_slots()"):]
        self.assertFalse(re.search(r"free\s*[<>=]+\s*\d", khoi),
                         "so sanh voi so viet thang -> sua nguong mot cho, quen cho kia")

    def test_chua_co_snapshot_tui_thi_BO_QUA(self):
        """Chua nhan goi tui -> `bag_free_slots()` = 0 -> bao 'day' oan moi acc vua login."""
        self.assertIn('if not getattr(c, "bag_slots", None):', self.than)


class TestDungChungPCvaAPK(unittest.TestCase):
    def test_luat_nam_o_CORE(self):
        self.assertIn("def bag_notify_items(pidx):", _core())
        self.assertIn("def bag_notify_skip(username):", _core())

    def test_GUI_PC_goi_ham_core_chu_khong_tu_tinh(self):
        g = _gui()
        self.assertIn("ctrl.bag_notify_items(pidx)", g)
        self.assertIn("ctrl.bag_notify_skip(u)", g)
        self.assertNotIn("self.BAG_CANH_BAO_SLOT_TRONG", g, "GUI van tu tinh nguong -> se lech")

    def test_APK_co_cau_noi(self):
        s = _kt("BotForegroundService.kt")
        self.assertIn('notifyRows("bag_notify_items", pidx)', s)
        self.assertIn('callAttr("bag_notify_skip"', s)

    def test_APK_hien_muc_tui_va_dat_LEN_DAU(self):
        s = _kt("MainActivity.kt")
        self.assertIn('it0["kind"] == "bag"', s)
        i_bag = s.find("service?.bagNotifyItems(_pi)")
        i_ba_dau = s.find("service?.baDauNotifyItems(_pi)")
        self.assertGreater(i_bag, 0, "APK khong hien canh bao tui")
        self.assertLess(i_bag, i_ba_dau, "tui phai len dau nhu ben PC")

    def test_APK_co_nut_Bo_qua(self):
        self.assertIn("onBagSkip", _kt("MainActivity.kt"))


class TestNutChuYMauCam(unittest.TestCase):
    """CAM = viec CAN LAM NGAY; vang nhat = luc nao lam cung duoc (thanh chua mo, du diem, lo)."""

    def test_PC_du_ba_loai(self):
        g = _gui()
        i = g.find("NOTIFY_CAM = ")
        self.assertGreater(i, 0)
        khoi = g[i:i + 120]
        for k in ('"_ba_dau"', '"_bag"', '"_legion"'):
            self.assertIn(k, khoi)

    def test_PC_nut_doc_theo_ham_chung(self):
        self.assertIn("_gap = self._party_notify_gap(pidx)", _gui())

    def test_PC_khong_con_chi_xet_ba_dau(self):
        self.assertNotIn("_gap = bool(ctrl.ba_dau_notify_items(pidx))", _gui())

    def test_APK_du_ba_loai(self):
        s = _kt("MainActivity.kt")
        i = s.find("val gapNotify")
        khoi = s[i:i + 220]
        for k in ('"ba_dau"', '"legion"', '"bag"'):
            self.assertIn(k, khoi)


class TestDongHienThi(unittest.TestCase):
    def setUp(self):
        self.src = _gui()

    def test_co_bao_SO_SLOT_TRONG_con_lai(self):
        """Nguong 10 thi "sap day" mo ho - phai noi ro con may slot."""
        i = self.src.find('_line = (f\'{self._mask_user(u)} túi đồ sắp đầy')
        self.assertGreater(i, 0)
        self.assertIn('it["free"]', self.src[i:i + 300])

    def test_ca_hai_truong_hop_deu_bao_slot_trong(self):
        """maxed (khong mua them slot duoc) va chua maxed."""
        i = self.src.find("used, cap, maxed = ")
        khoi = self.src[i:i + 2600]
        self.assertEqual(khoi.count('it["free"]'), 2)

    def test_free_co_trong_du_lieu_thong_bao(self):
        i = _core().find('out.append({"user": u, "kind": "bag"')
        self.assertGreater(i, 0)
        self.assertIn('"free": free', _core()[i:i + 260])


if __name__ == "__main__":
    unittest.main()
