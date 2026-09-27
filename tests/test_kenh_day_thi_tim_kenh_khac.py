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


class TestKhongConNhanhMoiKenhDeuDay(unittest.TestCase):
    """(27/09) Bo han so den. Ca party 34 o tren sinh ra tu chinh so den: hai kenh bi cam vi
    TIMEOUT (-1) nen "moi kenh party dang dung deu day". Khong con so den thi khong con tinh trang
    do: kenh luon chon tu danh sach `S:007-001`, server bao day sau danh sach thi hoi lai."""

    def test_khong_con_nhanh_moi_kenh_deu_day(self):
        self.assertNotIn("MOI kenh party dang dung deu DAY", _src())

    def test_ma_4_moi_thi_HOI_LAI_danh_sach(self):
        s = _src()
        i = s.find("if _day_moi:")
        self.assertGreater(i, 0)
        self.assertIn("_lam_moi_ds_kenh(", s[i:i + 800])


class TestHamTimKenhVanDungPhamVi(unittest.TestCase):
    def test_phai_DU_CHO_ca_party_va_khong_nhan_so_den(self):
        s = _src()
        i = s.find("def _kenh_trong_cho_ca_party(pidx, st, song):")
        self.assertGreater(i, 0)
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertNotRegex(than, r"\bhong\b")
        self.assertIn("toi_da - dang < can", than)


if __name__ == "__main__":
    unittest.main()
