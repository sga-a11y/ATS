"""`tools/loc_block_stats.py`: bo pattern chiem duoi 1% so tran cua diem.

User chot 26/08: "khi nao can t se bao loc luon file block train, bot do phai tinh toan nhieu"
-> lam sach du lieu o NGUON. User chot 30/08: nguong 1%.

Vi sao: luat "co block 1x2/1x3/1x4 thi loai luon diem" bien MOT ghi nhan 0.2% thanh du de vut ca
diem tot nhat - 'Trai Pham Thanh3 145-146' diem 0 co 4x1 426/439 tran ma bi loai vi dung 1 tran
'1x3' -> party 1 phai tut xuong map 142-143.
"""
from __future__ import annotations

import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "loc_block_stats", os.path.join(ROOT, "tools", "loc_block_stats.py"))
LOC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LOC)


class TestLocSpot(unittest.TestCase):
    def test_bo_pattern_le_te(self):
        """Ca that: 4x1 426 / 439 tran, dinh dung 1 tran 1x3 (0.2%)."""
        sp = {"total": 439, "patterns": {"4x1": 426, "3x1": 11, "1x3": 1, "2x1": 1}}
        n, tran, _bo = LOC.loc_spot(sp)
        self.assertEqual(n, 2)
        self.assertEqual(tran, 2)
        self.assertEqual(sp["patterns"], {"4x1": 426, "3x1": 11})

    def test_TRU_total_theo_so_tran_da_bo(self):
        """Khong tru thi ti le cac pattern con lai lech, va diem het cho ghi tran moi."""
        sp = {"total": 439, "patterns": {"4x1": 426, "3x1": 11, "1x3": 1, "2x1": 1}}
        LOC.loc_spot(sp)
        self.assertEqual(sp["total"], 437)

    def test_GIU_pattern_tren_nguong(self):
        sp = {"total": 100, "patterns": {"4x1": 96, "1x3": 4}}
        n, _t, _b = LOC.loc_spot(sp)
        self.assertEqual(n, 0, "4% la tren nguong 1% -> phai giu (luat block cham van an)")
        self.assertEqual(sp["patterns"], {"4x1": 96, "1x3": 4})

    def test_KHONG_BAO_GIO_bo_het(self):
        """Diem ma moi pattern deu be (rat nhieu dang) van phai giu lai dang dong nhat."""
        sp = {"total": 300, "patterns": {str(i): 1 for i in range(300)}}
        LOC.loc_spot(sp)
        self.assertEqual(len(sp["patterns"]), 1)

    def test_spot_rong_thi_khong_dung_toi(self):
        sp = {"total": 0, "patterns": {}}
        self.assertEqual(LOC.loc_spot(sp)[0], 0)

    def test_xoa_last_pattern_khi_no_bi_bo(self):
        """Giu lai 'last_pattern' vua bi bo la de hieu nham diem do hay ra dang do."""
        sp = {"total": 439, "patterns": {"4x1": 438, "1x3": 1},
              "last_pattern": "1x3", "last_slots": ["0:1"]}
        LOC.loc_spot(sp)
        self.assertNotIn("last_pattern", sp)
        self.assertNotIn("last_slots", sp)

    def test_GIU_last_pattern_khi_no_con(self):
        sp = {"total": 439, "patterns": {"4x1": 438, "1x3": 1},
              "last_pattern": "4x1", "last_slots": ["0:1"]}
        LOC.loc_spot(sp)
        self.assertEqual(sp["last_pattern"], "4x1")

    def test_nguong_mac_dinh_1_phan_tram(self):
        self.assertEqual(LOC.NGUONG, 0.01)


class TestFileThuc(unittest.TestCase):
    """KHONG khoa "file phai luon sach": bot DANG CHAY ghi de `train_block_stats.json` moi tran
    (`record_battle` doc lai file roi ghi), nen pattern le te se moc lai lien tuc - khoa la test
    do vo co. Chi kiem cong cu chay duoc tren file that va khong lam hong du lieu."""

    def test_chay_duoc_tren_file_that_va_khong_mat_du_lieu(self):
        import copy
        import json
        with open(os.path.join(ROOT, "train_block_stats.json"), encoding="utf-8") as fh:
            goc = json.load(fh)
        data = copy.deepcopy(goc)
        bo_tran = 0
        for mval in (data.get("maps") or {}).values():
            for spot in (mval.get("spots") or {}).values():
                bo_tran += LOC.loc_spot(spot)[1]
        self.assertEqual(len(data.get("maps") or {}), len(goc.get("maps") or {}),
                         "loc lam MAT map")
        for mkey, mval in (goc.get("maps") or {}).items():
            self.assertEqual(len(data["maps"][mkey].get("spots") or {}),
                             len(mval.get("spots") or {}), "loc lam MAT diem o map %s" % mkey)
            for skey, spot in (mval.get("spots") or {}).items():
                self.assertEqual((data["maps"][mkey]["spots"][skey].get("mobs") or {}),
                                 (spot.get("mobs") or {}), "loc dung vao du lieu QUAI")
                self.assertTrue(data["maps"][mkey]["spots"][skey].get("patterns"),
                                "diem %s/%s bi bo HET pattern" % (mkey, skey))
        tong = sum(int(v) for mval in (goc.get("maps") or {}).values()
                   for s in (mval.get("spots") or {}).values()
                   for v in (s.get("patterns") or {}).values())
        if tong:
            self.assertLess(bo_tran / tong, 0.01, "bo qua nhieu tran (%d/%d)" % (bo_tran, tong))


if __name__ == "__main__":
    unittest.main()
