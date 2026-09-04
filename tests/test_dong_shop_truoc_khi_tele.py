# -*- coding: utf-8 -*-
"""Mo shop/thoai NPC thi PHAI dong truoc khi lam viec khac (user chot 04/09).

Dang mo = SERVER coi la DANG BAN: khong moi/nhan party duoc, va TELEPORT luc do la CHET.
Ba cho co mo thoai NPC: cat do tien trang, ban Noi dat, mua HP/SP.

Bai test nay neo hai duong HONG (khong phai duong thanh cong): loi giua chung van phai dong.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import client as C


class _Gia(C.GameClient):
    def __init__(self, no_o_lenh=None):
        self.sent = []
        self.running = True
        self._label = "test"
        self.bag_slots = {}
        self.bag_counts = {}
        self.current_map = C.GameClient.NOI_DAT_SELL_CITY
        self.auto_bag_clean = True
        self.auto_sell_noi_dat = True
        self.xu = 999999
        self.pos = (0, 0)
        self._no_o = no_o_lenh          # lenh thu may thi nem loi (gia lap dut mang giua chung)
        self._n = 0

    def send(self, op, payload=b""):
        self._n += 1
        if self._no_o is not None and self._n == self._no_o:
            raise OSError("dut mang giua chung")
        self.sent.append((op, bytes(payload)))

    def _wait_combat_clear(self, idle=1.0, cap=60.0):
        return True

    def _move_noi_dat_npc_step(self, x, y, wait=0.55):
        pass

    def _sell_donate_materials(self):
        pass


class TestBanNoiDat(unittest.TestCase):
    def _client(self):
        c = _Gia()
        c.bag_slots = {i: [C.GameClient.NOI_DAT_TID, 60] for i in range(1, 4)}
        c.bag_counts = {C.GameClient.NOI_DAT_TID: 180}
        return c

    def test_duong_thanh_cong_co_dong_dialog(self):
        c = self._client()
        c.sell_noi_dat()
        self.assertEqual(c.sent[-1], (0x14, b"\x06\x00"))

    def test_LOI_giua_vong_ban_van_phai_dong_dialog(self):
        """Truoc day dong dialog nam o cuoi duong thanh cong -> loi la thoat ham ma shop VAN MO."""
        c = self._client()
        # Dem so lenh cua duong binh thuong roi cho no chet o giua vong ban.
        _binh_thuong = self._client()
        _binh_thuong.sell_noi_dat()
        _giua = len(_binh_thuong.sent) - 2
        c = _Gia(no_o_lenh=_giua)
        c.bag_slots = {i: [C.GameClient.NOI_DAT_TID, 60] for i in range(1, 4)}
        c.bag_counts = {C.GameClient.NOI_DAT_TID: 180}
        with self.assertRaises(OSError):
            c.sell_noi_dat()
        self.assertEqual(c.sent[-1], (0x14, b"\x06\x00"),
                         "loi giua chung ma khong dong dialog -> acc ket trang thai DANG BAN")


class TestMuaHpSp(unittest.TestCase):
    def test_dong_dialog_TRUOC_khi_tele(self):
        """`finally` cu chi TELE; dong dialog nam trong `try` nen loi giua chung = tele khi
        shop con mo."""
        _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "bot", "client.py")
        with open(_p, encoding="utf-8") as fh:
            src = fh.read()
        i = src.index("def buy_hp_sp(")
        j = src.index("def follow_route(", i)
        than = src[i:j]
        k_fin = than.index("finally:")
        k_dong = than.index('self.send(0x14, b"\\x06\\x00")', k_fin)
        k_tele = than.index("self._ve_thanh_sau_mua_hpsp()", k_fin)
        self.assertLess(k_dong, k_tele, "phai dong dialog TRUOC khi tele")


if __name__ == "__main__":
    unittest.main()
