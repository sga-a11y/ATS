"""`da toi diem (x,y)`: KHONG duoc tu gan dich roi bao la toi - nhung cung KHONG DUOC NGOI CHO.

`navigate_to` tung ket thuc bang `self.pos = (x, y)` roi in "da toi diem" - TU GAN cho minh cai
dich roi bao da toi. Lenh move bi tran chien nuot / dia hinh chan / het `waypoint_moves` giua
duong deu cho ra dung dong log do.

NHUNG KHONG CO CACH HOI VI TRI: `0x0c 0100` la `C:012-001 <換場景完畢>` - goi THONG BAO, server
khong tra loi. Goi no de "xac nhan" chi ngoi cho HET GIO 2s MOI LAN di chuyen roi van in
"(chua xac nhan duoc)" (user hoi 31/08: "sao van chua xac nhan duoc?").

=> Chi xac nhan khi THUC SU co nguon sua pos ve trong luc di - `_position_generation` doi:
   `0x03` self-spawn / `S:007-000` / `S:012-000` / `S:013-004` / bam theo leader.
   Khong co thi giu dead-reckoning, KHONG cho.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402


class _Bot(GameClient):
    def __init__(self, chuoi_toa_do):
        self._label = "test"
        self.running = True
        self.pos = (0, 0)
        self.current_map = 21851
        self.flee_mode = False
        self._need_scene_resume = False
        self._position_generation = 0
        self.da_move = []
        self._chuoi = list(chuoi_toa_do)   # toa do server tra ve moi lan hoi
        self.so_lan_hoi = 0

    # --- cat het phan mang/di duong, chi giu phan XAC NHAN ---
    def move_to(self, x, y):
        self.da_move.append((x, y))
        # Chi gia lap "co nguon sua pos" o cac luot DI BU (nham dung dich), khong phai o cac
        # waypoint noi suy giua duong - de dem duoc so vong xac nhan.
        if (x, y) == getattr(self, "_dich", None):
            self.nguon_sua_pos()

    def in_combat(self, idle_secs=1.0):
        return False

    def nguon_sua_pos(self):
        """Gia lap NGUON SERVER sua pos trong luc di (0x03 / S:007-000 / S:012-000 / S:013-004 /
        bam theo leader): doi `_position_generation` thi navigate_to moi coi la co gi de xac nhan."""
        self.so_lan_hoi += 1
        tra = self._chuoi.pop(0) if self._chuoi else None
        if tra is not None:
            self.pos = tra
            self._position_generation += 1
        return tra


def _di(bot, dich=(860, 1520)):
    """Chay DUNG doan xac nhan cuoi navigate_to (khong chay phan tim duong)."""
    bot._dich = dich
    bot.nguon_sua_pos()          # nguon dau tien ve ngay sau khi di xong chang chinh
    return GameClient.navigate_to(bot, dich[0], dich[1], moves_needed=0, step=0.0)


class TestXacNhanDaToi(unittest.TestCase):
    def test_co_nguon_sua_pos_va_DUNG_CHO_thi_True(self):
        bot = _Bot([(860, 1520)])
        self.assertTrue(_di(bot))
        self.assertEqual(bot.so_lan_hoi, 1)

    def test_lech_trong_nguong_van_la_toi(self):
        """Server tra toa do lam tron; lech vai chuc don vi khong phai la chua toi."""
        bot = _Bot([(860 + GameClient.NAV_TOI_NOI - 5, 1520)])
        self.assertTrue(_di(bot))

    def test_nguon_noi_CON_O_XA_thi_DI_BU_roi_kiem_lai(self):
        bot = _Bot([(1150, 1510), (860, 1520)])
        self.assertTrue(_di(bot))
        self.assertEqual(bot.so_lan_hoi, 2, "khong hoi lai sau khi di bu")
        self.assertGreater(len(bot.da_move), 0, "khong di bu, chi kiem roi thoi")
        self.assertIn((860, 1520), bot.da_move, "di bu phai nham DUNG dich")

    def test_di_bu_may_lan_van_khong_toi_thi_FALSE(self):
        bot = _Bot([(1150, 1510)] * 60)   # nguon nao ve cung noi "van con o xa"
        self.assertFalse(_di(bot), "van bao da toi trong khi dang dung cach dich 290 don vi")
        self.assertEqual(bot.pos, (1150, 1510), "khong duoc tu gan dich khi da biet la chua toi")

    def test_KHONG_co_nguon_nao_thi_KHONG_CHO(self):
        """Day la truong hop THUONG GAP nhat (di lai binh thuong, khong doi scene): khong duoc
        ngoi cho het gio roi moi bao - phi 2s moi lan di chuyen cua moi acc."""
        bot = _Bot([None])
        self.assertTrue(_di(bot))
        self.assertEqual(bot.pos, (860, 1520))

    def test_log_noi_ro_ba_truong_hop(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        for txt in ("server xac nhan", "chua xac nhan duoc",
                    "TUONG da toi", "KHONG toi duoc"):
            self.assertIn(txt, s, "thieu log: %s" % txt)

    def test_co_du_hai_nhanh_xac_nhan(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertGreater(s.find("sau %d lenh move (xac nhan %s)"), 0, "mat nhanh 'da xac nhan'")
        self.assertGreater(s.find("TUONG da toi (%d,%d) nhung SERVER noi dang o %s"), 0,
                           "mat nhanh 'chua toi -> di bu'")


if __name__ == "__main__":
    unittest.main()
