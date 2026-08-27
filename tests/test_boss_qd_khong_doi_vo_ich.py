# -*- coding: utf-8 -*-
"""BOSS QUAN DOAN: khong duoc doi REFORM de danh mot thu ma chinh bot bo qua ngay sau do.

Log that 27/08 14:35-14:36 (party 42):
    [luubhai] (member) boss QD den luot -> TRIGGER REFORM party ve thanh de danh
    ... reform gen 1, gen 2 ... party giai tan + lap lai
nhung luc login chinh acc do da ghi:
    [luubhai] Boss QD: khong co quan doan -> bo qua hoan toan

Nguyen nhan: `legion_boss_available()` (ham quyet dinh TRIGGER REFORM) chi kiem con luot +
cooldown, KHONG kiem `has_legion` va `fight_legion_boss` - trong khi `do_legion_boss()` (ham
THUC SU danh) kiem ca hai va thoat ngay. Hai ham lech dieu kien -> doi reform vo ich mai.
"""
import io
import os
import time
import unittest

from bot.client import GameClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bot(has_legion=True, count=0, mx=3, nxt=0.0, bat=True):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.has_legion = has_legion
    c.legion_boss_count = count
    c.legion_boss_max = mx
    c.legion_boss_next = nxt
    c.fight_legion_boss = bat
    return c


class TestKhongDoiDanhBossKhongDuocPhep(unittest.TestCase):
    def test_khong_co_quan_doan_thi_KHONG_available(self):
        self.assertFalse(_bot(has_legion=False).legion_boss_available())

    def test_tat_setting_thi_KHONG_available(self):
        self.assertFalse(_bot(bat=False).legion_boss_available())

    def test_chua_biet_co_quan_doan_hay_khong_thi_van_thu(self):
        """has_legion None = chua doc duoc 0x05 sub03 -> khong dam ket luan, cu cho thu."""
        self.assertTrue(_bot(has_legion=None).legion_boss_available())

    def test_con_luot_va_co_quan_doan_thi_available(self):
        self.assertTrue(_bot().legion_boss_available())

    def test_het_luot_thi_KHONG_available(self):
        self.assertFalse(_bot(count=3, mx=3).legion_boss_available())

    def test_con_cooldown_thi_KHONG_available(self):
        self.assertFalse(_bot(nxt=time.time() + 600).legion_boss_available())


class TestKhopDieuKienVoiHamDanh(unittest.TestCase):
    def test_do_legion_boss_van_kiem_du_hai_dieu_kien(self):
        """Neu ai do bo check ben do_legion_boss thi 2 ham lai lech - test giu cho khong lech."""
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def do_legion_boss(")
        doan = s[i:i + 2500]
        self.assertIn('getattr(self, "fight_legion_boss", True)', doan)
        self.assertIn("if self.has_legion is False:", doan)


if __name__ == "__main__":
    unittest.main()
