# -*- coding: utf-8 -*-
"""LUAT "muon lv THAP HON map thap nhat cua game -> lay MAP THAP NHAT" phai xu duoc ca truong hop
chinh map do CHUA QUET quai.

Vong ha level o tren da co uu tien nay tu lau (uu tien 1: map chua quet -> den quet truoc, tra
idx = -1 de caller quet xong roi random 1 bai), rieng nhanh "map thap nhat" o cuoi thi thieu: no
goi thang `_profs(lo)`, map chua quet thi rong -> tra None.

Ca that 16/09 party 46 (user: "p46 ko tim duoc map train"): level party
[32,32,33,33,43,44,44,44,63,119], map thap nhat la "Rung Dong Quan2 24-25" (lv24) voi mobs rong
-> `TU CHON MAP khong tim duoc diem nao` lap lai moi giay, party dung im ca buoi.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import train_pick


class TestMapThapNhatMaCHUA_QUET_QUAI(unittest.TestCase):
    def test_tra_map_thap_nhat_voi_idx_am_mot(self):
        maps = [(11802, "Rung Dong Quan2 24-25", []),
                (21841, "Dam Lay Tang Khau1 60-65", [])]
        got = train_pick.pick_train_spot("avg-30", [32, 33, 44, 63, 119], maps)
        self.assertIsNotNone(got, "map thap nhat chua quet quai -> van phai chon duoc")
        map_id, idx, lv, why = got
        self.assertEqual(map_id, 11802, "phai lay MAP THAP NHAT")
        self.assertEqual(idx, -1, "chua co diem -> caller quet xong roi random 1 bai")
        self.assertIn("CHUA QUET", why)

    def test_van_uu_tien_map_DA_QUET_khi_co(self):
        """Da quet roi (`mobs` = danh sach toa do diem) thi lay diem that, khong di quet lai."""
        maps = [(11802, "Rung Dong Quan2 24-25", [(1310, 550)]),
                (21841, "Dam Lay Tang Khau1 60-65", [])]
        got = train_pick.pick_train_spot("avg-30", [32, 33, 44, 63, 119], maps)
        self.assertIsNotNone(got)
        self.assertEqual(got[0], 11802)
        self.assertEqual(got[1], 0, "map da quet quai ma van doi di quet lai")


if __name__ == "__main__":
    unittest.main()
