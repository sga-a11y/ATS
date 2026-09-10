"""Lenh di chuyen KHONG duoc nhay xa - ma 14 `<移動距離過遠>` dut ket noi ca party.

User 10/09: "p1 dang di Pb thi dis toan bo" -> "the thi van la cau chuyen bot chua xac nhan duoc
viec di chuyen da thuc su di chuyen hay chua".

Ca that, pho ban to doi lv80 (map 62012):
    02:56:35 [xGAx] da toi diem (350,2690) sau 6 lenh move (xac nhan (350, 2690))
    02:56:36 [xGAx] khong co smart path (pos=(350, 2690) map=62012) -> replay 1 waypoint capture
    02:56:36 [xGAx]   02:56:36.349 >>gui  0x06 01000146002e0e
    02:56:36 [xGAx] SERVER NGAT KET NOI: di chuyen QUA XA (ma 14)
    02:56:38..40    ca 4 member: THOAT PHO BAN TO DOI (C:047-010)
Leader rot la ca party mat luot pho ban.

GOC: client THAT khong bao gio gui toa do DICH. `MoveController.SendRolePosition()` gui
`Role.player.position` - VI TRI HIEN TAI sau khi da cong tung buoc
`moveDist = deltaTime * speed` (`_lua_dec/Controller/MoveController.lua:194` va `:234`).
Bot thi gui thang dich, nen doan cang dai thi cu nhay cang xa.

Nhanh `replay waypoint capture` la cho chet: waypoint la duong cua NGUOI THAT xuat phat tu vi tri
cua HO - chinh docstring cua ham goi no da ghi dieu do - ma van replay tu cho khac.

Nguong 120 lay theo thang do DA CHAY DUOC: smart path chia (150,3630)->(1210,3590) (1060 don vi)
thanh 11 move-point ~96/buoc, va duong do khong dinh ma 14 lan nao.
"""
from __future__ import annotations

import io
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


class _Cli:
    """Chi cac thu `_move_chia_doan` dung den."""

    ROUTE_BUOC_TOI_DA = C.GameClient.ROUTE_BUOC_TOI_DA
    _move_chia_doan = C.GameClient._move_chia_doan

    def __init__(self, pos=(0, 0), trong_tran=False):
        self.running = True
        self.pos = pos
        self._label = "acc"
        self._trong_tran = trong_tran
        self.da_gui = []

    def in_combat(self, *_a, **_k):
        return self._trong_tran

    def move_to(self, x, y):
        self.da_gui.append((x, y))
        self.pos = (x, y)
        return True


def _ngu(_s):
    return None


class TestChiaDoanKhiDiXa(unittest.TestCase):
    def setUp(self):
        self._sleep = C.time.sleep
        C.time.sleep = _ngu

    def tearDown(self):
        C.time.sleep = self._sleep

    def test_doan_NGAN_thi_gui_mot_lenh(self):
        c = _Cli(pos=(100, 100))
        c._move_chia_doan(140, 130)
        self.assertEqual(c.da_gui, [(140, 130)], "doan ngan ma van chia = cham vo ich")

    def test_doan_DAI_thi_chia_nho(self):
        c = _Cli(pos=(0, 0))
        c._move_chia_doan(1000, 0)
        self.assertGreater(len(c.da_gui), 1, "ban mot lenh nhay 1000 don vi = ma 14")

    def test_MOI_buoc_deu_duoi_nguong(self):
        c = _Cli(pos=(350, 2690))
        c._move_chia_doan(-1200, 5300)          # doan that dai, xien
        truoc = (350, 2690)
        for diem in c.da_gui:
            _d = math.hypot(diem[0] - truoc[0], diem[1] - truoc[1])
            self.assertLessEqual(round(_d, 3), C.GameClient.ROUTE_BUOC_TOI_DA + 1,
                                 "buoc %s -> %s dai %.0f" % (truoc, diem, _d))
            truoc = diem

    def test_diem_CUOI_dung_bang_dich(self):
        """Chia nho khong duoc lam lech dich - buoc cuoi phai la dung (x,y)."""
        c = _Cli(pos=(17, 23))
        c._move_chia_doan(1234, -567)
        self.assertEqual(c.da_gui[-1], (1234, -567))

    def test_cac_buoc_nam_TREN_duong_thang(self):
        c = _Cli(pos=(0, 0))
        c._move_chia_doan(900, 900)
        for bx, by in c.da_gui:
            self.assertEqual(bx, by, "buoc lech khoi duong thang -> di vong, de dinh dia hinh")

    def test_chua_biet_pos_thi_gui_thang(self):
        """Khong biet dang o dau thi khong chia duoc - cu gui, con hon dung im."""
        c = _Cli(pos=None)
        c._move_chia_doan(500, 500)
        self.assertEqual(c.da_gui, [(500, 500)])

    def test_dinh_tran_giua_chung_thi_DUNG(self):
        """Vao tran = lenh move bi server NUOT -> di tiep la tu lech pos."""
        c = _Cli(pos=(0, 0))

        _that = c.move_to

        def _move(x, y):
            _that(x, y)
            if len(c.da_gui) >= 2:
                c._trong_tran = True
            return True

        c.move_to = _move
        self.assertFalse(c._move_chia_doan(2000, 0))
        self.assertLess(len(c.da_gui), 10, "van ban het cac buoc du da vao tran")

    def test_acc_tat_giua_chung_thi_DUNG(self):
        c = _Cli(pos=(0, 0))
        _that = c.move_to

        def _move(x, y):
            _that(x, y)
            c.running = False
            return True

        c.move_to = _move
        self.assertFalse(c._move_chia_doan(2000, 0))
        self.assertEqual(len(c.da_gui), 1)


class TestRouteMoveDungChiaDoan(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.cli = fh.read()

    def test_route_move_KHONG_goi_thang_move_to(self):
        i = self.cli.find("def _route_move(self")
        j = self.cli.find("def _move_chia_doan(self", i)
        self.assertGreater(j, i)
        than = self.cli[i:j]
        self.assertIn("self._move_chia_doan(", than)
        self.assertNotIn("self.move_to(x, y)", than,
                         "replay waypoint capture ban thang mot lenh nhay xa = ma 14")

    def test_nguong_co_can_cu_va_du_nho(self):
        self.assertLessEqual(C.GameClient.ROUTE_BUOC_TOI_DA, 200,
                             "nguong to qua thi van nhay xa")
        self.assertGreater(C.GameClient.ROUTE_BUOC_TOI_DA, 0)


if __name__ == "__main__":
    unittest.main()
