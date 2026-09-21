"""Mua slot tui: server KHONG tra gia khi acc dang trong Di Gioi / instance.

Ca that 21/09 (user: "engine moi: trong chu y thi cho mua slot hinh nhu bi loi" - nut hien
"Mua slot (?)"). MOI acc ghi "Mo rong tui: khong hoi duoc gia" hom do deu dang o map 49942
(= `config.DIGIOI_MAP_ID`):

    01:32:51 [vumuoi] da VAO DI GIOI (map=49942)
    01:44:41 [vumuoi] Mo rong tui: khong hoi duoc gia -> dung      <- thu lai 3 lan, cach 20s
    01:45:00 [vumuoi] Mo rong tui: khong hoi duoc gia -> dung
    01:45:20 [vumuoi] Mo rong tui: khong hoi duoc gia -> dung

Flow cu goi `tu_mo_rong_tui` trong `lam_login_chores` - NGAY SAU LOGIN, luc acc con o thanh - nen
khong bao gio cham chuyen nay. Engine moi giao `VIEC_LOGIN_CHORE` theo nhip nen co the roi dung
luc acc da vao Di Gioi.

Ham TU KIEM lay thay vi tin nguoi goi - cung nguyen tac voi `_handle_auto_team_dungeon` tu cho
het tran.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


class _Fake:
    _label = "acc"
    running = True
    BAG_EXPAND_MAX_LAN = C.GameClient.BAG_EXPAND_MAX_LAN

    def __init__(self, map_id):
        self.current_map = map_id
        self.query_bag_slot_price = mock.Mock(return_value=(100, 0))
        self.buy_bag_slot = mock.Mock(return_value=True)
        self.bag_slot_maxed = mock.Mock(return_value=False)
        self.bag_capacity = mock.Mock(return_value=100)

    in_di_gioi = C.GameClient.in_di_gioi


def _chay(map_id, gioi_han=250):
    f = _Fake(map_id)
    return C.GameClient.tu_mo_rong_tui(f, gioi_han), f


class TestKhongMuaTrongDiGioi(unittest.TestCase):
    def test_trong_DI_GIOI_thi_KHONG_hoi_gia(self):
        n, f = _chay(C.config.DIGIOI_MAP_ID)
        self.assertEqual(n, 0)
        f.query_bag_slot_price.assert_not_called()

    def test_trong_INSTANCE_cung_khong(self):
        n, f = _chay(62002)
        self.assertEqual(n, 0)
        f.query_bag_slot_price.assert_not_called()

    def test_o_THANH_thi_mua_binh_thuong(self):
        """Khong duoc vi chan Di Gioi ma chan luon duong mua that."""
        _n, f = _chay(12001)
        self.assertTrue(f.query_bag_slot_price.called)


class TestGUI_NoiRoLyDoThayVi_DauHoi(unittest.TestCase):
    def test_gui_kiem_di_gioi_truoc_khi_hoi_gia(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _price():")
        self.assertGreater(i, 0)
        than = src[i:i + 1200]
        self.assertIn("in_di_gioi()", than)
        self.assertLess(than.find("in_di_gioi()"), than.find("query_bag_slot_price"),
                        "phai kiem Di Gioi TRUOC, khong thi lai hien '(?)' vo nghia")


class TestKhongHoiDuocGiaPhaiGhiLOG(unittest.TestCase):
    """Tra None im lang = khong ai biet vi sao GUI hien '(?)' - dung cai bay da ngon ca ngay
    20/09 o 2K (`_fight_one` im lang khi khong co thoai)."""

    def test_co_log_khi_khong_nhan_duoc_gia(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def query_bag_slot_price(")
        than = src[i:src.find("\n    def ", i + 10)]
        self.assertIn("log.", than, "im lang khi that bai -> lan sau lai phai mo")


if __name__ == "__main__":
    unittest.main()
