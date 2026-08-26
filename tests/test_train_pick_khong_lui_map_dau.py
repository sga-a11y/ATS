# -*- coding: utf-8 -*-
"""Bat "Tu chon map" ma doc lai khong duoc thi KHONG DUOC lui ve map dau danh sach.

Bug that (user phat hien): party dat "Lv TB -30" nhung bot train "Hoa Dung dao4 120-122" - dung
map DAU TIEN trong train_maps.json (1/118).

Duong di: bat tu chon map thi luu start_city_id = 0 (khong co map co dinh). Luc nap lai, neu
chuoi `train_pick` khong khop PICK_KEYS (doi ten khoa giua cac ban) thi code cu roi xuong nhanh
"tim map theo start_city_id", tim id == 0 -> khong co -> `idx = 0` = MAP DAU. Roi luu de la party
train THAT o map do. Hong AM THAM, khong mot dong canh bao.
"""
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI = os.path.join(ROOT, "gui.py")


def _src():
    with io.open(GUI, encoding="utf-8") as fh:
        return fh.read()


class TestKhongLuiVeMapDau(unittest.TestCase):
    def test_co_nhanh_rieng_khi_start_city_id_bang_0(self):
        s = _src()
        self.assertIn("elif was_train and not _sc_luu:", s,
                      "phai tach rieng truong hop preset VON dat tu chon map")

    def test_dat_lai_mac_dinh_chu_khong_lay_map_dau(self):
        s = _src()
        i = s.find("elif was_train and not _sc_luu:")
        self.assertGreater(i, 0)
        doan = s[i:i + 900]
        self.assertIn("_pick_label(_TP.DEFAULT_PICK)", doan,
                      "phai quay ve che do tu chon mac dinh")
        self.assertNotIn("self.train_maps[idx][1]", doan,
                         "nhanh nay TUYET DOI khong duoc lay map theo idx")

    def test_co_canh_bao_ra_log(self):
        """Hong am tham la cai lam user mat ca buoi moi thay - phai keu len."""
        s = _src()
        i = s.find("elif was_train and not _sc_luu:")
        self.assertIn("log.warning", s[i:i + 900])

    def test_van_giu_duong_cu_cho_map_CO_DINH(self):
        """Party dat map cu the (start_city_id != 0) thi van tim theo id nhu cu."""
        s = _src()
        self.assertIn("if mid == _sc_luu), 0)", s)


class TestNhanTuChonMapVanKhopKhoa(unittest.TestCase):
    def test_moi_khoa_deu_co_nhan(self):
        """`pick in PICK_KEYS` la cua ai vao - khoa va nhan phai khop nhau tuyet doi."""
        from bot import train_pick as TP
        for key in TP.PICK_KEYS:
            self.assertTrue(TP.pick_label(key), "khoa %r khong co nhan" % key)
            self.assertEqual(TP.pick_key(TP.pick_label(key)), key,
                             "nhan cua %r khong tra nguoc ve dung khoa" % key)

    def test_default_pick_la_khoa_hop_le(self):
        from bot import train_pick as TP
        self.assertIn(TP.DEFAULT_PICK, TP.PICK_KEYS)


class TestThuTuMapKhongPhaiNgauNhien(unittest.TestCase):
    def test_map_dau_danh_sach_dung_la_hoa_dung_dao4(self):
        """Neo lai bang chung: map dau la Hoa Dung dao4 - trung khop cai user thay."""
        import json
        p = os.path.join(ROOT, "train_maps.json")
        with io.open(p, encoding="utf-8") as fh:
            maps = json.load(fh)["maps"]
        dau = next(iter(maps.values()))
        self.assertIn("Hoa Dung", dau.get("name", ""),
                      "map dau doi roi -> sua lai mo ta bug trong test nay cho khoi lac huong")


if __name__ == "__main__":
    unittest.main()
