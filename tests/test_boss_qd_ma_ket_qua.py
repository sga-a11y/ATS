# -*- coding: utf-8 -*-
"""BOSS QUAN DOAN: doc ma ket qua `S:039-119` (0x27 sub77) thay vi doan.

Khach bao 02/10 (TSM): acc vao QD chua du 24h -> danh boss QD bi "mat ket noi". Truoc day bot
khong doc ma nay: van gui `0x14 08000100` roi RELOGIN. Ma (protocal.lua 039-119):
1 OK, 2 cooldown, 3 het luot, 4 co doi, 5 dang tran, 6 khong co boss, 7 chua du 24h.
User chot: 4 -> roi doi roi thu lai; 5 -> cho xong tran roi thu lai; 6 -> 3h; 7 -> khoa 12h.
"""
import unittest
from unittest import mock

from bot import client as client_mod
from bot.client import GameClient

VAO = (0x27, b"\x77\x00")
GATE = (0x14, b"\x08\x00\x01\x00")


def _bot(cac_ma):
    """cac_ma: ma server tra cho tung lan gui lenh vao boss (het list -> lap lai ma cuoi)."""
    c = GameClient.__new__(GameClient)
    c._label = c._username = "test"
    c.running = True
    c.has_legion = True
    c.fight_legion_boss = True
    c.legion_boss_count = 0
    c.legion_boss_max = 3
    c.legion_boss_next = 0.0
    c._genuine_end_seen = 0.0
    c._legion_enter_result = None
    c.state = mock.Mock(in_battle=False, boss_mode=False)
    c.sends = []

    def send(op, data):
        c.sends.append((op, data))
        if (op, data) == VAO:
            n = sum(1 for s in c.sends if s == VAO)
            c._legion_enter_result = cac_ma[min(n, len(cac_ma)) - 1]
        if (op, data) == GATE and c._legion_enter_result == 1:
            c.state.in_battle = True
    c.send = send
    for ten in ("_wait_combat_clear", "thao_ngoc_phuc_than", "heal_full", "relogin",
                "leave_party", "_doi_pet_boss", "_pet_role_restore"):
        setattr(c, ten, mock.Mock())
    c._wait_combat_clear.return_value = True
    return c


class _DongHo:
    def __init__(self, c):
        self.c, self.t, self.ngu_trong_tran = c, 1000.0, 0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s
        if self.c.state.in_battle:
            self.ngu_trong_tran += 1
            if self.ngu_trong_tran > 1:
                self.c.state.in_battle = False

    def strftime(self, *a):
        return "00:00"

    def localtime(self, *a):
        return None


def _chay(c):
    dh = _DongHo(c)
    with mock.patch.object(client_mod, "time", dh), \
            mock.patch.object(client_mod, "_load_legion_boss_next", return_value=0.0), \
            mock.patch.object(client_mod, "_save_legion_boss_next") as luu, \
            mock.patch.object(client_mod, "set_account_activity"):
        kq = c.do_legion_boss()
    return kq, dh, luu


def _dem(c, goi):
    return sum(1 for s in c.sends if s == goi)


class TestMaKetQuaBossQD(unittest.TestCase):
    def test_handler_doc_ma_039_119(self):
        c = GameClient.__new__(GameClient)
        c._legion_enter_result = None
        pkt = b"\xc0\x91\x0a\x00\x00\x00\x27\x77\x00\x07"
        if pkt[7:9] == b"\x77\x00" and len(pkt) >= 10:   # giong handler 0x27
            c._legion_enter_result = pkt[9]
        self.assertEqual(c._legion_enter_result, 7)
        with open(client_mod.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertIn('pkt[7:9] == b"\\x77\\x00" and len(pkt) >= 10', src)

    def test_ma_7_chua_du_24h_khoa_12h_KHONG_relogin_KHONG_gui_gate(self):
        c = _bot([7])
        kq, dh, luu = _chay(c)
        c.relogin.assert_not_called()
        self.assertEqual(_dem(c, GATE), 0)
        self.assertEqual(_dem(c, VAO), 1)
        self.assertAlmostEqual(c.legion_boss_next - 1000.0, 12 * 3600, delta=10)
        self.assertEqual(kq, c.legion_boss_next)
        luu.assert_called()
        self.assertFalse(c.state.boss_mode)

    def test_ma_6_khong_co_boss_thu_lai_3h(self):
        c = _bot([6])
        _chay(c)
        c.relogin.assert_not_called()
        self.assertEqual(_dem(c, GATE), 0)
        self.assertAlmostEqual(c.legion_boss_next - 1000.0, 3 * 3600, delta=10)

    def test_ma_3_het_luot(self):
        c = _bot([3])
        kq, _, _ = _chay(c)
        self.assertIsNone(kq)
        self.assertEqual(c.legion_boss_count, 3)
        c.relogin.assert_not_called()

    def test_ma_4_roi_doi_roi_thu_lai_vao_duoc(self):
        c = _bot([4, 1])
        _chay(c)
        c.leave_party.assert_called_once_with(server_bao_dang_o_party=True)
        self.assertEqual(_dem(c, VAO), 2)
        self.assertEqual(_dem(c, GATE), 1)
        self.assertEqual(c.legion_boss_count, 1)
        c.relogin.assert_not_called()

    def test_ma_5_cho_xong_tran_roi_thu_lai_vao_duoc(self):
        c = _bot([5, 1])
        _chay(c)
        c._wait_combat_clear.assert_called()
        self.assertEqual(_dem(c, VAO), 2)
        self.assertEqual(c.legion_boss_count, 1)
        c.relogin.assert_not_called()

    def test_ma_4_mai_khong_het_thi_KHONG_relogin(self):
        c = _bot([4])
        _chay(c)
        c.relogin.assert_not_called()
        self.assertEqual(_dem(c, GATE), 0)
        self.assertAlmostEqual(c.legion_boss_next - 1000.0, 600, delta=60)

    def test_ma_1_vao_tran_binh_thuong(self):
        c = _bot([1])
        _chay(c)
        self.assertEqual(_dem(c, GATE), 1)
        self.assertEqual(c.legion_boss_count, 1)
        c.relogin.assert_not_called()


if __name__ == "__main__":
    unittest.main()
