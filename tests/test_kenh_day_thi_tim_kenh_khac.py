"""Moi kenh PARTY DANG DUNG deu day -> phai di tim kenh KHAC con cho, khong dung im cho.

User chot 09/09: "het kenh trong thi cu cho, dung nhay lung tung". Nhung "het kenh trong" phai
hieu la MOI KENH CUA MAP deu day, chu khong phai "moi kenh party dang dung deu day" - party moi
dung co 2 kenh trong ca chuc kenh cua map.

Ca that 21/09 party 34 (user: "p34, moi dua 1 kenh, nhung vi sao lai bao dang o trong pt"):
leader o kenh 10, 2 member o kenh 8, ca hai vao so den. Suot 6 phut:

    02:11:44 [party 34] DIEU PHOI: MOI kenh party dang dung deu DAY [8, 10] -> GIU kenh dich 10,
             cho co cho trong (khong doi y)
    02:11:56 [dvhai]   Doi kenh 10 TIMEOUT sau 4.0s -> ket qua -1
    02:11:57 [dvinnam] Doi kenh 10 TIMEOUT sau 4.0s -> ket qua -1

`lap_party` quay vong 400 lan vi khong bao gio co ai cung kenh de moi.

Goc: nhanh do `return` thang, nen `_kenh_trong_cho_ca_party` - dung cai ham BIET kenh nao con cho,
docstring cua no ghi ro "Moi kenh party dang dung deu trong so den -> tim kenh MOI du cho CA
party" - khong bao gio duoc goi o dung luc can no nhat. Chinh chu thich trong file cung da canh
bao dieu nay tu truoc: "truoc day chi chay khi MOI kenh party dang dung deu hong, tuc gan nhu
khong bao gio".
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestTimKenhKhacTruocKhiDungCho(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("MOI kenh party dang dung deu DAY")
        self.assertGreater(i, 0)
        # lay ca doan TRUOC do (than nhanh `if`) lan sau do
        j = s.rfind("if cu and dem and all(", 0, i)
        self.assertGreater(j, 0)
        self.khoi = s[j:i + 1500]

    def test_co_goi_ham_tim_kenh_con_cho(self):
        self.assertIn("_kenh_trong_cho_ca_party(", self.khoi,
                      "khong hoi ham BIET kenh nao con cho = dung im cho vo han")

    def test_lam_moi_danh_sach_kenh_truoc_khi_tim(self):
        """`c.channels` cu thi tim ra kenh da day tu doi nao."""
        self.assertIn("_lam_moi_ds_kenh(", self.khoi)
        self.assertLess(self.khoi.find("_lam_moi_ds_kenh("),
                        self.khoi.find("_kenh_trong_cho_ca_party("))

    def test_tim_duoc_thi_CHOT_kenh_do(self):
        self.assertIn('st["kenh_dich"] = int(_kenh_moi)', self.khoi)

    def test_KHONG_tim_duoc_moi_dung_cho(self):
        """Giu nguyen luat cu cua user khi that su het cho - chi doi DIEU KIEN de vao do."""
        i = self.khoi.find("KHONG kenh nao")
        self.assertGreater(i, 0, "mat duong 'that su het cho thi cho'")
        self.assertIn("return int(cu)", self.khoi[i:])


class TestHamTimKenhVanDungPhamVi(unittest.TestCase):
    def test_loai_kenh_trong_so_den_va_phai_DU_CHO_ca_party(self):
        s = _src()
        i = s.find("def _kenh_trong_cho_ca_party(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn("in hong", than)
        self.assertIn("toi_da - dang < can", than)


if __name__ == "__main__":
    unittest.main()
