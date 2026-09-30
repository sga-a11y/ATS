# -*- coding: utf-8 -*-
"""BOSS QUAN DOAN: lenh vao boss bi nuot vi acc con ket trong tran cu -> gui lai 1 lan.

Log 30/09: 4/5 ca "Boss QD: khong vao duoc tran" nhan `0x14 sub0700` KET TRAN cua chinh acc
1-3s SAU lenh vao boss; 0/411 ca vao duoc co moc nay. Truoc day ca nay -> RELOGIN + khoa 12h,
mat trang 1-2 luot/ngay.
"""
import time
import unittest
from unittest import mock

from bot import client as client_mod
from bot.client import GameClient


def _bot(ket_tran_sau_lenh, vao_lan):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c._username = "test"
    c.running = True
    c.has_legion = True
    c.fight_legion_boss = True
    c.legion_boss_count = 0
    c.legion_boss_max = 3
    c.legion_boss_next = 0.0
    c._genuine_end_seen = 0.0
    c.state = mock.Mock(in_battle=False, boss_mode=False)
    c.sends = []

    def send(op, data):
        c.sends.append((op, data))
        so_lan = sum(1 for o, d in c.sends if (o, d) == (0x27, b"\x77\x00"))
        if (op, data) == (0x14, b"\x08\x00\x01\x00"):
            if ket_tran_sau_lenh and so_lan == 1:
                c._genuine_end_seen = 1.0
            if vao_lan and so_lan >= vao_lan:
                c.state.in_battle = True
    c.send = send
    for ten in ("_wait_combat_clear", "thao_ngoc_phuc_than", "heal_full", "relogin",
                "_doi_pet_boss", "_pet_role_restore"):
        setattr(c, ten, mock.Mock())
    return c


class _DongHo:
    """Dong ho gia: sleep() day gio len, khong cho that. Da vao tran thi lan ngu thu 2 coi nhu
    tran xong (ha in_battle) de thoat vong 'danh cho het tran'."""
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
    c.send_goc = c.send

    def send(op, data):
        c.send_goc(op, data)
        if c._genuine_end_seen:
            c._genuine_end_seen = dh.t + 0.001
    c.send = send
    with mock.patch.object(client_mod, "time", dh), \
            mock.patch.object(client_mod, "_load_legion_boss_next", return_value=0.0), \
            mock.patch.object(client_mod, "_save_legion_boss_next"), \
            mock.patch.object(client_mod, "set_account_activity"):
        c.do_legion_boss()


def _so_lenh_vao(c):
    return sum(1 for o, d in c.sends if (o, d) == (0x27, b"\x77\x00"))


class TestGuiLaiKhiTranCuVuaKet(unittest.TestCase):
    def test_tran_cu_ket_sau_lenh_thi_gui_lai_va_vao_duoc(self):
        c = _bot(ket_tran_sau_lenh=True, vao_lan=2)
        _chay(c)
        self.assertEqual(_so_lenh_vao(c), 2)
        c.relogin.assert_not_called()
        self.assertEqual(c.legion_boss_count, 1)

    def test_khong_co_moc_ket_tran_thi_KHONG_gui_lai(self):
        """Server tu choi that (vd chua du 24h vao quan doan) -> giu nguyen duong cu."""
        c = _bot(ket_tran_sau_lenh=False, vao_lan=0)
        _chay(c)
        self.assertEqual(_so_lenh_vao(c), 1)
        c.relogin.assert_called_once()

    def test_chi_gui_lai_DUNG_1_lan(self):
        c = _bot(ket_tran_sau_lenh=True, vao_lan=0)
        _chay(c)
        self.assertEqual(_so_lenh_vao(c), 2)
        c.relogin.assert_called_once()


if __name__ == "__main__":
    unittest.main()
