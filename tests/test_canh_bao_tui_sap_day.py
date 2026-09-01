"""Canh bao "tui do sap day" trong man Chu y: nguong = con DUOI 10 slot trong.

User chot 01/09: "trong chu y, tui do chuyen sang canh bao khi so slot trong <10" (truoc day la
<= 5). Tui gan day thi nhieu viec HONG AM THAM truoc khi tui day han:
  - nhan qua mail that bai (xem `claim_mail` + documents / KNOWLEDGE muc 7r),
  - nhat do rot trong tran,
  - mua do o lo.
Bao som 10 slot de con kip don tui.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
        return fh.read()


class TestNguongCanhBao(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        i = self.src.find("BAG_CANH_BAO_SLOT_TRONG")
        self.assertGreater(i, 0, "khong con hang so nguong -> nguong bi viet cung o giua ham")
        j = self.src.find("\n    def _party_city_notify", i)
        self.than = self.src[i:j]

    def test_nguong_la_10(self):
        self.assertIn("BAG_CANH_BAO_SLOT_TRONG = 10", self.src)

    def test_KHONG_con_nguong_5_cu(self):
        self.assertNotIn("if free > 5:", self.than, "van dung nguong 5 cu")

    def test_so_sanh_dung_chieu(self):
        """`free >= nguong` moi bo qua -> con dung 9 slot VAN canh bao, dung 10 thi thoi."""
        self.assertIn("if free >= self.BAG_CANH_BAO_SLOT_TRONG:", self.than)

    def test_dung_HANG_SO_khong_viet_so_thang(self):
        khoi = self.than[self.than.find("free = c.bag_free_slots()"):]
        self.assertFalse(re.search(r"free\s*[<>=]+\s*\d", khoi),
                         "so sanh voi so viet thang -> sua nguong o mot cho, quen cho kia")


class TestDongHienThi(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_co_bao_SO_SLOT_TRONG_con_lai(self):
        """Nguong 10 thi "sap day" mo ho - phai noi ro con may slot de user biet gap den dau."""
        i = self.src.find('_line = (f\'{self._mask_user(u)} túi đồ sắp đầy')
        self.assertGreater(i, 0)
        self.assertIn('it["free"]', self.src[i:i + 300])

    def test_ca_hai_truong_hop_deu_bao_slot_trong(self):
        """maxed (khong mua them slot duoc) va chua maxed - bo sot mot cai la dong do thieu tin."""
        i = self.src.find("used, cap, maxed = ")
        khoi = self.src[i:i + 2600]
        self.assertEqual(khoi.count('it["free"]'), 2)

    def test_free_co_trong_du_lieu_thong_bao(self):
        i = self.src.find('out.append((u, {"_bag": True')
        self.assertGreater(i, 0)
        self.assertIn('"free": free', self.src[i:i + 200])


if __name__ == "__main__":
    unittest.main()
