# -*- coding: utf-8 -*-
"""Loader items_gamedata.json phai giu DU truong ma bot dua vao de quyet dinh.

Bug that (03/09/2026): `_load_gamedata_items()` chep tay tung truong va thieu
fc/mat/lv/kd. Khong ai bao loi - dict.get tra None -> 0 - nen tinh nang "tu mo hop
trang bi" coi MOI mon la "khong phan giai duoc, khong donate duoc" va VUT SACH
hang tram trang bi cua user. Bai test nay neo lai: them truong moi vao JSON ma
quen khai bao trong loader thi do day.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import client as C


class TestGamedataLoaderGiuDuTruong(unittest.TestCase):
    def setUp(self):
        self.gd = C._load_gamedata_items()

    def test_co_du_truong_quyet_dinh(self):
        """Moi ban ghi phai co day du truong bot doc, khong duoc thieu im lang."""
        can = ("name", "fc", "mat", "lv", "kd", "ft", "hp", "sp", "battle", "restrict", "st", "q")
        rec = self.gd[0x52dd]  # Cam Quan Oan
        for k in can:
            self.assertIn(k, rec, "loader mat truong %r -> bot doc ra 0 ma khong bao loi" % k)

    def test_gia_tri_khop_file_json(self):
        """Gia tri phai la cua chinh item do, khong phai 0 mac dinh."""
        self.assertEqual(self.gd[0x52dd]["mat"], 6)    # Cam Quan Oan
        self.assertEqual(self.gd[0x52dd]["lv"], 13)
        self.assertEqual(self.gd[0x5854]["fc"], 260)   # Hoai Nam Ngoa - phan giai duoc

    def test_trang_bi_thuong_donate_duoc(self):
        """Mon trang bi binh thuong PHAI qua ArmyFilter (truoc day bi vut het)."""
        cl = C.GameClient.__new__(C.GameClient)
        for tid in (0x52dd, 0x5792):  # Cam Quan Oan, Xich De Hai
            self.assertTrue(cl._donate_quan_doan_duoc(tid, self.gd[tid]),
                            "0x%04x phai donate duoc" % tid)

    def test_sach_khong_donate_duoc(self):
        """Sach (mat=37, ngoai dai 1..36) van dung la khong donate duoc."""
        cl = C.GameClient.__new__(C.GameClient)
        self.assertFalse(cl._donate_quan_doan_duoc(0x4945, self.gd[0x4945]))  # Hoai Nam Tu


if __name__ == "__main__":
    unittest.main()
