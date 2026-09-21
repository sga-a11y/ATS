"""TELE TRUNG GIAN (Trac Quan / Ng.Thanh) TRUOC khi tele ve thanh tap ket.

User bao tu lau: "bay ve thanh route truc tiep tu map la hay bi loi ngay doan tele; qua 1 thanh
trung gian truoc thi on dinh" -> `client.pre_route_town_hop`.

Engine CU lam viec nay o BON duong: `follow_route`, `follow_smart_route`, `_do_reform` (gom ve
thanh tap ket) va manual route. Engine MOI thi duong `VIEC_VE_THANH` goi THANG `go_to_town`, nen
party tu 21 tro len bay mot phat ve thanh gan bai train.
User 21/09: "Party 21, t thay no bay ve thanh gan bai train nhat de party di ra bai train, ko co
pre tele ve Trac quan/Nghiep thanh".

DIEU KIEN la "DICH la thanh nao", KHONG phai "dang dung o dau" - sao dung engine cu
(`_do_reform`):

    if _target_city == fc:          # fc = THANH TAP KET (thanh cua route)
        c.pre_route_town_hop()      # -> CO hop
        _town_ok = c.go_to_town(fc, ff, tries=6, ...)
    else:                           # ve thanh GOM du phong (Nghiep Thanh)
        ...                         # -> KHONG hop
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as PE


class _Cli:
    running = True
    _label = "acc"

    def __init__(self, cur=21814):
        self.current_map = cur
        self.goi = []

    def pre_route_town_hop(self):
        self.goi.append("hop")
        self.current_map = 12001

    def go_to_town(self, city, flag=0, **k):
        self.goi.append(("town", int(city), int(flag)))
        self.current_map = int(city)
        return True


class TestCoHopTruocKhiVeThanhTapKet(unittest.TestCase):
    def test_ve_thanh_tap_ket_thi_HOP_TRUOC(self):
        c = _Cli(21814)                      # dang o map la (Trai Pham Thanh)
        PE.thi_hanh(c, PE.VIEC_VE_THANH, lambda: True, dich=(21001, 13))
        self.assertEqual(c.goi[0], "hop", "bay thang ve thanh route -> hay loi doan tele")
        self.assertEqual(c.goi[1], ("town", 21001, 13))

    def test_dang_o_THANH_KHAC_van_hop(self):
        """Engine cu khong kiem "dang dung o dau" - dang o thanh nao cung hop truoc."""
        c = _Cli(23001)                      # dang o Truong Sa
        PE.thi_hanh(c, PE.VIEC_VE_THANH, lambda: True, dich=(21001, 13))
        self.assertEqual(c.goi[0], "hop")

    def test_GIU_NGUYEN_flag(self):
        """Moi thanh mot flag rieng - truyen thieu la bay ve NHAM THANH (p41, 16/09)."""
        c = _Cli(21814)
        PE.thi_hanh(c, PE.VIEC_VE_THANH, lambda: True, dich=(12061, 2))
        self.assertIn(("town", 12061, 2), c.goi)


class TestVeChinhThanhTrungGianThiKHONG_HOP(unittest.TestCase):
    """Ve thanh GOM du phong (Nghiep Thanh) thi di thang - hop nua la them mot lan tele."""

    def test_ve_Nghiep_Thanh(self):
        c = _Cli(21814)
        PE.thi_hanh(c, PE.VIEC_VE_THANH, lambda: True, dich=(12061, 2))
        self.assertNotIn("hop", c.goi)

    def test_ve_Trac_Quan(self):
        c = _Cli(21814)
        PE.thi_hanh(c, PE.VIEC_VE_THANH, lambda: True, dich=(12001, 0))
        self.assertNotIn("hop", c.goi)

    def test_da_o_dung_thanh_thi_khong_lam_gi(self):
        c = _Cli(21001)
        PE.thi_hanh(c, PE.VIEC_VE_THANH, lambda: True, dich=(21001, 13))
        self.assertEqual(c.goi, [])


class TestHaiNoiKhaiThanhTrungGianPhaiKHOP(unittest.TestCase):
    """`party_engine` CO Y khong import `client` (engine phai thuan) nen so bi chep o hai noi.
    Lech mot con la engine hop nham / bo sot."""

    def test_khop_voi_client(self):
        from bot import client as C
        self.assertEqual(set(PE._PRE_ROUTE_CITY_IDS), set(C.PRE_ROUTE_CITY_IDS))

    def test_pre_route_town_hop_dung_chinh_bang_do(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def pre_route_town_hop(self):")
        than = src[i:src.find("\n    def ", i + 10)]
        self.assertIn("PRE_ROUTE_CITIES", than,
                      "hardcode lai danh sach trong ham -> lech voi hang so o tren")


if __name__ == "__main__":
    unittest.main()
