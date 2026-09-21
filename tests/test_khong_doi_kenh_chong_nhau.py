# -*- coding: utf-8 -*-
"""HAI DUONG doi kenh khong duoc dam chan nhau, va da dung kenh thi thoi.

User 21/09 (party 7): "m xem co phai la ca team da chuyen kenh xong roi no lai co chuyen kenh lan
nua ko" - dung. Log:

    19:52:48 [ttsau/ttbay/tttam/ttnne/ttmuoi] Doi kenh OK -> 2      <- CA 5 DA XONG
    19:52:48 [ttbay] DIEU PHOI GUI doi kenh 2 (dang o 1) -> ket qua 0
    19:52:56 [ttbay] lenh doi kenh tay: ra diem an toan ... truoc khi doi kenh
    19:53:04 [ttbay] Doi kenh: server bao TRUNG khu dang o -> dang o kenh 2
    19:53:15 [ttnne] (member) manual: da doi kenh -> 2              <- 27 giay sau moi thoi

HAI duong cung doi kenh cho CUNG MOT ACC, khong ai biet ai:
  - luong QUYET DINH cua engine moi (1 nhip/giay) -> `_dieu_phoi_thi_hanh_kenh`;
  - WORKER cua tung acc -> `doi_kenh_theo_lenh_tay` (chay dai, toi 5 phut).

(Luu y: `_dieu_phoi_loop` KHONG lien quan - no bi chan ngay cua dau voi party engine moi. Dong
`DIEU PHOI GUI doi kenh` la do CHINH engine moi goi.)

VAN GIU DU FLOW: user chot "van chay ra safe, flow yeu cau roi, cam bo". Chi bo dung mot thu -
cai goi doi kenh chac chan bi server tu choi.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _than(src, dau, het="\ndef "):
    i = src.find(dau)
    return "" if i < 0 else src[i:src.find(het, i + 10)]


class TestDaDungKenhThiThoi(unittest.TestCase):
    def setUp(self):
        self.than = _than(_doc("run_party_digioi.py"), "def doi_kenh_theo_lenh_tay(")
        self.assertTrue(self.than, "mat ham chung doi kenh")
        self.lenh = "\n".join(d for d in self.than.split("\n") if not d.strip().startswith("#"))

    def test_KHONG_gui_lenh_doi_khi_da_o_kenh_dich(self):
        i = self.lenh.find('_dang_o = int(getattr(c, "current_channel", 0) or 0)')
        self.assertGreater(i, 0, "khong kiem kenh dang o -> gui goi chac chan bi tu choi")
        self.assertLess(i, self.lenh.find("c.switch_channel(ch,"), "kiem SAU khi da gui thi vo nghia")

    def test_VAN_RA_SAFE_du_da_dung_kenh(self):
        """User: "van chay ra safe, flow yeu cau roi, cam bo"."""
        i_safe = self.lenh.find('_safe("lenh doi kenh tay")')
        i_kiem = self.lenh.find('_dang_o = int(')
        self.assertGreater(i_safe, 0)
        self.assertLess(i_safe, i_kiem, "kiem kenh TRUOC khi ra safe -> bo mat buoc ra safe")

    def test_VAN_ve_safe_LAN_HAI(self):
        """Buoc 4 cua flow: doi kenh xong ve lai dung safe da chon (de phong lan truoc fail)."""
        i = self.lenh.find('_dang_o = int(')
        self.assertIn('_safe("sau khi doi kenh', self.lenh[i:],
                      "da dung kenh -> nhay thang ra, bo mat buoc ve safe lan hai")

    def test_van_coi_la_THANH_CONG(self):
        i = self.lenh.find('_dang_o = int(')
        khoi = self.lenh[i:i + 400]
        self.assertIn("ok = True", khoi, "da o dung kenh ma bao that bai -> party di gom kenh lai")


class TestMotAccMotLenhDangBay(unittest.TestCase):
    """L1. Duong tu dong da co `_dp_gui_kenh_dang_chay` cho chinh no, chi thieu ve lenh tay."""

    @classmethod
    def setUpClass(cls):
        cls.src = _doc("run_party_digioi.py")

    def test_lenh_tay_DAT_CO(self):
        than = _than(self.src, "def doi_kenh_theo_lenh_tay(")
        self.assertIn("c._lenh_tay_kenh_dang_chay = True", than)

    def test_HA_CO_trong_FINALLY(self):
        """Co ket True = duong tu dong khong bao gio dam doi kenh cho acc nay nua."""
        than = _than(self.src, "def doi_kenh_theo_lenh_tay(")
        i = than.find("finally:")
        self.assertGreater(i, 0, "khong co finally -> ngoai le giua chung la co ket vinh vien")
        self.assertIn("c._lenh_tay_kenh_dang_chay = False", than[i:])

    def test_duong_TU_DONG_ton_trong_co(self):
        than = _than(self.src, "def _dieu_phoi_thi_hanh_kenh(")
        self.assertTrue(than)
        self.assertIn('getattr(c, "_lenh_tay_kenh_dang_chay", False)', than,
                      "duong tu dong van gui chong len lenh tay")

    def test_co_KHONG_tu_het_han(self):
        """L1b: cam co TU HET HAN thay cho trang thai that."""
        than = _than(self.src, "def _dieu_phoi_thi_hanh_kenh(")
        i = than.find("_lenh_tay_kenh_dang_chay")
        dong = than[than.rfind("\n", 0, i) + 1:than.find("\n", i)]
        self.assertNotIn("time.time()", dong, "lay dong ho de suy 'dang chay' -> co tu het han")


if __name__ == "__main__":
    unittest.main()
