"""Nut "Ap che do cho moi party" (Settings): `gui._doi_che_do_preset`.

User chot 02/10: DG/Train CHI doi che do - cap quai DG + map train van RIENG tung party;
mode event thi dong bo ve CUNG event. (Loc cung nha phat hanh nam o SettingsDialog.)
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import gui  # noqa: E402
finally:
    sys.argv = _argv

doi = gui._doi_che_do_preset

SRC_DGT = {"mode": "digioi_train", "start_city_id": 0, "mob_index": -1,
           "train_pick": "avg_minus_30", "mob_min": 2, "mob_max": 4,
           "mob_elements": [0, 1], "mob_soul": False, "city_flag": 0,
           "di_gioi_level": 5, "di_gioi_pick": ""}


class TestDoiCheDo(unittest.TestCase):
    def test_train_sang_dg_train_giu_map_va_cap_quai_rieng(self):
        p = {"mode": "train", "start_city_id": 12345, "mob_index": 2, "train_pick": "",
             "di_gioi_level": 9, "di_gioi_pick": "x", "accounts": [{"u": "a"}]}
        d = doi(p, SRC_DGT)
        self.assertEqual(d["mode"], "digioi_train")
        self.assertEqual((d["start_city_id"], d["mob_index"], d["train_pick"]), (12345, 2, ""))
        self.assertEqual((d["di_gioi_level"], d["di_gioi_pick"]), (9, "x"))
        self.assertEqual(d["accounts"], [{"u": "a"}])

    def test_dg_sang_train_chua_co_map_thi_muon_map_party_mau(self):
        # DG thuan luu sc=49942 - de nguyen thi thanh MAP TRAIN 49942 (rac).
        p = {"mode": "digioi", "start_city_id": 49942, "di_gioi_level": 3}
        d = doi(p, SRC_DGT)
        self.assertEqual(d["train_pick"], "avg_minus_30")
        self.assertEqual(d["start_city_id"], 0)
        self.assertEqual(d["mob_index"], -1)
        self.assertEqual(d["di_gioi_level"], 3)

    def test_sang_dg_dat_lai_city_dg(self):
        p = {"mode": "train", "start_city_id": 12345, "di_gioi_level": 7}
        d = doi(p, {"mode": "digioi", "di_gioi_level": 1})
        self.assertEqual((d["mode"], d["start_city_id"]), ("digioi", 49942))
        self.assertEqual(d["di_gioi_level"], 7)

    def test_event_dong_bo_cung_event(self):
        p = {"mode": "event", "event_key": "nhi_kieu", "loandau_mot_tran": False}
        d = doi(p, {"mode": "event", "event_key": "npc_40", "loandau_mot_tran": True})
        self.assertEqual((d["event_key"], d["loandau_mot_tran"]), ("npc_40", True))
        self.assertEqual(d["start_city_id"], 0)

    def test_city_giu_thanh_rieng_neu_da_la_city(self):
        p = {"mode": "city", "start_city_id": 111, "city_flag": 3}
        d = doi(p, {"mode": "city", "start_city_id": 222, "city_flag": 4})
        self.assertEqual((d["start_city_id"], d["city_flag"]), (111, 3))
        d = doi({"mode": "digioi", "start_city_id": 49942}, {"mode": "city", "start_city_id": 222, "city_flag": 4})
        self.assertEqual((d["start_city_id"], d["city_flag"]), (222, 4))

    def test_khong_sua_preset_goc(self):
        p = {"mode": "train", "start_city_id": 5}
        doi(p, {"mode": "digioi"})
        self.assertEqual(p, {"mode": "train", "start_city_id": 5})


if __name__ == "__main__":
    unittest.main()
