"""Chon kenh: phai TRU RA so acc CUA CHINH PARTY dang dung trong kenh do.

`fit = cap - cur >= need` doi kenh con du `need` cho TRONG. Nhung khi ca party DA o tren map roi,
chinh 5 acc do dang chiem cho trong cac kenh - doi kenh vao day khong ton them cho nao. Khong tru
ra thi tren map dong (su kien) khong kenh nao "du" -> `pick_best_channel` tra None -> caller RETRY
vo han -> party khong bao gio lap duoc.

Log 31/08 party 2 (20:39, map 40NPC 10991, 39 kenh):
    20:39:06 [gamo] Nhan danh sach 39 kenh
    20:39:06 [gamo] KHONG kenh nao du 5 cho trong cho ca party -> RETRY (cho kenh trong)
    ... lap moi 3 giay ...
trong khi ca 5 acc DA o map 10991 (nasau kenh 34, so con lai kenh 39).
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as CL              # noqa: E402
from bot.client import GameClient         # noqa: E402

PIDX = 91


def _cli(entity, channel, map_id=10991, running=True):
    c = GameClient.__new__(GameClient)
    c._label = "t" + entity.hex()[:2]
    c.running = running
    c.party_idx = PIDX
    c.self_entity = entity
    c.current_channel = channel
    c.current_map = map_id
    return c


class TestTruAccCuaMinh(unittest.TestCase):
    def setUp(self):
        CL._PARTY_CLIENTS.pop(PIDX, None)
        self.me = _cli(b"\x01" * 8, 39)
        for i, ch in enumerate((39, 39, 39, 34), start=2):
            CL._register_party_client(PIDX, bytes([i]) * 8, _cli(bytes([i]) * 8, ch))
        CL._register_party_client(PIDX, self.me.self_entity, self.me)

    def tearDown(self):
        CL._PARTY_CLIENTS.pop(PIDX, None)

    def test_dem_dung_so_acc_trong_kenh(self):
        self.assertEqual(self.me._so_acc_party_o_kenh(39), 4)
        self.assertEqual(self.me._so_acc_party_o_kenh(34), 1)
        self.assertEqual(self.me._so_acc_party_o_kenh(7), 0)

    def test_KHONG_dem_acc_o_MAP_KHAC(self):
        """So kenh chi co nghia trong CUNG mot map - dem cheo map la tru khong."""
        CL._register_party_client(PIDX, b"\x09" * 8, _cli(b"\x09" * 8, 39, map_id=21851))
        self.assertEqual(self.me._so_acc_party_o_kenh(39), 4)

    def test_KHONG_dem_acc_da_tat(self):
        CL._register_party_client(PIDX, b"\x0a" * 8, _cli(b"\x0a" * 8, 39, running=False))
        self.assertEqual(self.me._so_acc_party_o_kenh(39), 4)

    def test_loi_thi_tra_0_khong_lam_sap(self):
        c = GameClient.__new__(GameClient)
        c._label = "t"
        self.assertEqual(c._so_acc_party_o_kenh(1), 0)


class TestPickBestChannelDungCongThucMoi(unittest.TestCase):
    def setUp(self):
        CL._PARTY_CLIENTS.pop(PIDX, None)
        self.me = _cli(b"\x01" * 8, 39)
        self.me._chan_event = __import__("threading").Event()
        self.me._chan_event.set()
        self.me.request_channel_list = lambda: None
        for i, ch in enumerate((39, 39, 39, 39), start=2):
            CL._register_party_client(PIDX, bytes([i]) * 8, _cli(bytes([i]) * 8, ch))
        CL._register_party_client(PIDX, self.me.self_entity, self.me)
        self.doi = []
        self.me.switch_channel = lambda ch, **k: (self.doi.append(ch), True)[1]

    def tearDown(self):
        CL._PARTY_CLIENTS.pop(PIDX, None)

    def test_kenh_party_DANG_O_van_duoc_chon(self):
        """Kenh 39 dang 20/20 nhung 5 cho do LA CUA PARTY -> van vao duoc."""
        self.me.channels = {39: (20, 20), 5: (19, 20)}
        r = self.me.pick_best_channel(need=5, exclude=(1,))
        self.assertEqual(r, 39, "kenh party dang o bi loai -> RETRY vo han")

    def test_khong_kenh_nao_du_thi_GOM_VE_KENH_LEADER(self):
        """Van hon la RETRY vo han: leader dang dung trong kenh do nen chac chan co cho."""
        self.me.channels = {39: (20, 20), 5: (20, 20)}
        self.me.party_idx = 999          # khong con acc nao cung party -> khong tru duoc gi
        r = self.me.pick_best_channel(need=5, exclude=(1,))
        self.assertEqual(r, 39, "phai gom ve kenh leader thay vi tra None")


if __name__ == "__main__":
    unittest.main()
