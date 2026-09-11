"""DONG AGI: den luot no thi BO QUA so diem DE DANH.

User 11/09:
    "rieng dong nang agi thi khi tinh den dong do se bo qua cai point de danh, tat nhien la van
     phai hoan thanh cac dong truoc do roi moi den luot dong agi.
     vi du set up: de danh 33 / hpx 22 / int 55 / agi 44
     -> khi int moi duoc 50 thi van de danh 33 point vi chua den dong agi
     -> khi int da du 55 roi thi tang agi den 44 luon ko can quan tam den viec phai de danh nua"

LY DO: "de danh" ton tai de GIU DIEM CHO CAC DONG PHIA SAU chua toi luot. AGI la dong quyet dinh
luot danh va no nam cuoi bang, nen khi da toi luot no thi khong con dong nao phai giu cho - giu
tiep la giu MAI MAI.

THU TU KHONG DOI: cac dong TREN phai xong het roi moi den luot agi. Dong tren chua dat ma het phan
diem duoc tieu (con - de_danh) thi DUNG o do, khong duoc nhay xuong agi de moi khoa.
"""
from __future__ import annotations

import logging
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot.client import ATTR_KEY_TO_CODE as K

CFG = {"reserve": 33, "rules": [{"stat": "hpx", "target": 22},
                                {"stat": "int", "target": 55},
                                {"stat": "agi", "target": 44}]}


class _Client:
    """Client toi thieu: chi nhung thu `auto_cong_diem` doc/goi."""

    def __init__(self, con, goc):
        self._label = "test"
        self.con = int(con)
        self.goc = dict(goc)
        self.da_cong = []

    def attr_point_left(self):
        return self.con

    def char_diem_goc(self):
        return dict(self.goc)

    def add_attr_point(self, ma, add):
        self.goc[ma] = self.goc.get(ma, 0) + add
        self.con -= add
        self.da_cong.append((ma, add))
        return True


def _chay(con, goc, cfg=CFG):
    c = _Client(con, goc)
    R.auto_cong_diem(c, cfg, label="test")
    return c


class TestViDuCuaUser(unittest.TestCase):
    """Dung nguyen bo so user dua ra: de danh 33 / hpx 22 / int 55 / agi 44."""

    @classmethod
    def setUpClass(cls):
        logging.disable(logging.INFO)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_int_moi_50_va_KHONG_du_diem_vuot_thi_van_giu_33(self):
        """"khi int moi duoc 50 thi van de danh 33 point vi chua den dong agi"."""
        c = _chay(35, {K["hpx"]: 22, K["int"]: 50, K["agi"]: 0})
        self.assertEqual(c.con, 33, "phai giu dung 33 diem de danh")
        self.assertEqual(c.goc[K["agi"]], 0, "chua xong int ma da nhay xuong agi")

    def test_int_du_55_thi_agi_tieu_ca_phan_de_danh(self):
        """"khi int da du 55 roi thi tang agi den 44 luon ko can quan tam den de danh"."""
        c = _chay(40, {K["hpx"]: 22, K["int"]: 55, K["agi"]: 0})
        self.assertEqual(c.goc[K["agi"]], 40, "agi phai an ca 33 diem de danh")
        self.assertEqual(c.con, 0)

    def test_xong_int_trong_cung_luot_thi_di_tiep_sang_agi(self):
        """Thu tu van nguyen: xong dong tren TRUOC, roi moi toi agi - nhung trong cung mot luot."""
        c = _chay(40, {K["hpx"]: 22, K["int"]: 50, K["agi"]: 0})
        self.assertEqual(c.da_cong[0], (K["int"], 5), "phai hoan thanh int truoc")
        self.assertEqual(c.goc[K["agi"]], 35, "xong int roi thi agi duoc tieu ca phan de danh")


class TestThuTuKhongDoi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.INFO)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_dong_dau_chua_dat_thi_khong_nhay_xuong_agi(self):
        """hpx chua du -> dung o do, khong duoc muon khoa cua agi de tieu tiep."""
        c = _chay(35, {K["hpx"]: 10, K["int"]: 0, K["agi"]: 0})
        self.assertEqual(c.con, 33)
        self.assertEqual(c.goc[K["agi"]], 0)
        self.assertEqual(c.goc[K["int"]], 0)

    def test_agi_da_dat_muc_thi_khong_tieu_gi_them(self):
        """Dat muc roi thi bo qua - va KHONG duoc vi the ma xai mat so de danh."""
        c = _chay(40, {K["hpx"]: 22, K["int"]: 55, K["agi"]: 44})
        self.assertEqual(c.da_cong, [])
        self.assertEqual(c.con, 40)

    def test_khong_co_dong_agi_thi_de_danh_giu_nguyen(self):
        cfg = {"reserve": 33, "rules": [{"stat": "hpx", "target": 22},
                                        {"stat": "int", "target": 99}]}
        c = _chay(40, {K["hpx"]: 22, K["int"]: 50}, cfg)
        self.assertEqual(c.con, 33, "khong co dong agi thi khong ai duoc mo khoa de danh")

    def test_de_danh_0_thi_khong_doi_gi(self):
        cfg = {"reserve": 0, "rules": [{"stat": "int", "target": 55}, {"stat": "agi", "target": 44}]}
        c = _chay(20, {K["int"]: 55, K["agi"]: 0}, cfg)
        self.assertEqual(c.goc[K["agi"]], 20)


class TestKhongTieuQuaSoCo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.INFO)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_dong_dau_tien_chua_dat_thi_chi_tieu_phan_VUOT_de_danh(self):
        """Bang trang: hpx can 22 ma chi duoc tieu 7 (40 - 33) -> cong 7 roi DUNG.
        Khong duoc vi "cuoi bang co agi" ma mo khoa de danh ngay tu dong dau."""
        c = _chay(40, {K["hpx"]: 0, K["int"]: 0, K["agi"]: 0})
        self.assertEqual(sum(x[1] for x in c.da_cong), 7)
        self.assertEqual(c.con, 33, "phai con nguyen so de danh")
        self.assertEqual(c.goc[K["agi"]], 0)

    def test_khong_cong_qua_muc_dich(self):
        c = _chay(999, {K["hpx"]: 22, K["int"]: 55, K["agi"]: 40})
        self.assertEqual(c.goc[K["agi"]], 44, "cong vuot muc dich la sai bang rule")


if __name__ == "__main__":
    unittest.main()
