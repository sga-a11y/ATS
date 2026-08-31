"""Thu tu uu tien khi TU CHON MAP (user chot 31/08):

    1. map co khoang level thoa man nhung CHUA CO DIEM NAO  -> den do QUET truoc
    2. diem CHUA CO DU LIEU (train_block_stats)             -> gom du lieu
    3. diem KHOP so quai/he                                  -> lay diem it tran nhat

Uu tien 1 la bat buoc, khong phai cho vui: `_needs_train_mob_probe` chi chay khi party DA DUNG
TREN map. Map khong bao gio duoc chon = khong ai toi = khong bao gio duoc quet. Nen no vua la
duong DUY NHAT de map moi config vao duoc dung, vua la cach yeu cau quet lai mot map co du lieu
sai (xoa safe+mobs cua no).
"""
from __future__ import annotations

import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import train_pick  # noqa: E402

# map co diem + co du lieu day du (de khong roi vao uu tien 2)
_STATS = {"maps": {"900": {"spots": {}}}}


def _stats_full(map_id, mobs, level, so_quai=4):
    spots = {}
    for xy in mobs:
        spots[train_pick.train_block_stats.spot_key(xy)] = {
            "battles": 50, "levels": {str(level): 50}, "elements": {"Kim": 50},
            "mobs": {"1": {"count": 50, "pattern": "1x%d" % so_quai}},
        }
    return {"maps": {str(map_id): {"spots": spots}}}


class TestUuTienMapChuaQuet(unittest.TestCase):
    def test_map_chua_quet_duoc_chon_TRUOC(self):
        maps = [
            (900, "Map Cu 137-139", [[100, 100], [200, 200]]),
            (901, "Map Moi 137-139", []),                     # chua quet
        ]
        got = train_pick.pick_train_spot(
            "avg-20", [158], maps, stats=_stats_full(900, [[100, 100], [200, 200]], 138),
            rng=random.Random(1))
        self.assertIsNotNone(got)
        self.assertEqual(got[0], 901, "map co diem duoc chon truoc map chua quet")

    def test_tra_idx_am_de_caller_biet_chua_co_diem(self):
        maps = [(901, "Map Moi 137-139", [])]
        got = train_pick.pick_train_spot("avg-20", [158], maps, stats={"maps": {}},
                                         rng=random.Random(1))
        self.assertEqual(got[1], -1, "tra idx 0 thi caller tuong la bai so 1 co that")

    def test_ly_do_noi_ro(self):
        maps = [(901, "Map Moi 137-139", [])]
        got = train_pick.pick_train_spot("avg-20", [158], maps, stats={"maps": {}},
                                         rng=random.Random(1))
        self.assertIn("CHUA QUET", got[3])

    def test_map_LECH_LEVEL_thi_khong_uu_tien(self):
        """Chua quet nhung khong thuoc khoang level -> khong duoc keo len truoc."""
        maps = [
            (900, "Map Cu 137-139", [[100, 100]]),
            (902, "Map Khac 40-42", []),
        ]
        got = train_pick.pick_train_spot(
            "avg-20", [158], maps, stats=_stats_full(900, [[100, 100]], 138), rng=random.Random(1))
        self.assertEqual(got[0], 900)

    def test_map_hon_KHONG_duoc_uu_tien(self):
        maps = [(903, "LH-Map Hon 137-139", [])]
        got = train_pick.pick_train_spot("avg-20", [158], maps, stats={"maps": {}},
                                         rng=random.Random(1))
        self.assertTrue(got is None or got[0] != 903, "map hon van bi loai nhu cu")

    def test_VAN_giu_uu_tien_2_va_3(self):
        """Khong con map chua quet -> quay ve luat cu: diem chua co du lieu truoc."""
        maps = [(900, "Map Cu 137-139", [[100, 100], [200, 200]])]
        got = train_pick.pick_train_spot("avg-20", [158], maps, stats={"maps": {}},
                                         rng=random.Random(1))
        self.assertIsNotNone(got)
        self.assertIn("chua co du lieu", got[3])


class TestLogNoiRoChuaQuet(unittest.TestCase):
    def test_khong_in_diem_0(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("TU CHON MAP ->")
        khoi = s[i:i + 700]
        self.assertIn("CHUA QUET", khoi, "idx=-1 in ra 'diem 0' -> doc log tuong co bai so 0")


if __name__ == "__main__":
    unittest.main()
