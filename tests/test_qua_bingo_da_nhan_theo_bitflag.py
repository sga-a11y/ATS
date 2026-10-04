"""Qua bingo "da nhan" phai TINH LAI tu BitFlag moi lan (giong Jiugongge.UpdateState), khong HOP.

Ca 03/10: acc offline luc 0h login -> server gui bang BitFlag cu (co 1541..1547 bat) roi moi tat
co. Bot HOP (`|=`) nen giu "da nhan [1..7]" cua hom qua -> 146 acc 5/9 o ma claim 0 line, GUI
hien du 7 tick qua.
"""
import struct
import unittest

from bot.client import GameClient


def _full_table(on_flags):
    data = bytearray(200)
    for f in on_flags:
        data[(f - 1) // 8] |= 1 << ((f - 1) % 8)
    return b"\x00" * 7 + b"\x02\x00" + struct.pack("<H", len(data)) + bytes(data)


def _update(flag, on):
    return b"\x00" * 7 + b"\x01\x00" + struct.pack("<I", 1) + struct.pack("<H", flag) + bytes([on])


def _s91_3(line, gid=1):
    return b"\x00" * 7 + b"\x03\x00\x01" + struct.pack("<H", gid) + bytes([line])


class TestQuaBingoTheoBitFlag(unittest.TestCase):
    def setUp(self):
        self.c = GameClient("user", "token")
        self.c._label = "hero"

    def test_server_tat_co_thi_bo_da_nhan(self):
        self.c._apply_bitflags(_full_table(range(1541, 1548)))
        self.assertEqual(self.c._claimed_lines, set(range(1, 8)))
        for f in range(1541, 1548):
            self.c._apply_bitflags(_update(f, 0))
        self.assertEqual(self.c._claimed_lines, set())
        self.assertEqual(self.c._claimed_by_grid.get(1), set())

    def test_s91_3_giu_qua_vua_nhan_qua_lan_tinh_lai(self):
        self.c._apply_bitflags(_full_table([]))
        self.c._on_daily_quest_packet(_s91_3(4))
        self.assertEqual(self.c._claimed_lines, {4})
        # goi BitFlag khac toi (khong lien quan) -> tinh lai van giu line 4
        self.c._apply_bitflags(_update(2, 1))
        self.assertEqual(self.c._claimed_lines, {4})
        self.assertTrue(self.c._bitflag_get(1544))

    def test_daily_status_khong_con_tick_cu(self):
        self.c._apply_bitflags(_full_table(range(1541, 1548)))
        for f in range(1541, 1548):
            self.c._apply_bitflags(_update(f, 0))
        self.assertEqual(self.c.daily_status()["claimed"], [])


if __name__ == "__main__":
    unittest.main()
