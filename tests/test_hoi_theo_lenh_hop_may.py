"""Hoi HP/SP theo lenh server S:065-010 + xoa co "het thuoc" moi tran (29/09).

Ca that: `vanba` bao "char HET thuoc HP" luc 12:27 roi 1.5h khong hoi lan nao, chet ve thanh
lien tuc - `_no_item` chi duoc xoa o nhanh 0x34 legacy, nhanh nay bi skip khi
battle_tracker.generation != 0 (generation chi tang).
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as f:
        return f.read()


class TestHoiTheoLenhHopMay(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_xoa_no_item_o_su_kien_start_cua_tracker(self):
        i = self.src.find('if event.kind == "start":')
        self.assertGreater(i, 0)
        self.assertIn("self._no_item.clear()", self.src[i:i + 600])

    def test_s065_010_goi_hoi_nhanh(self):
        i = self.src.find("S:065-010 an thuoc kind=")
        self.assertGreater(i, 0, "mat handler S:065-010")
        than = self.src[i:i + 1200]
        self.assertIn("_heal_after_battle(theo_hop_may=True)", than)
        self.assertIn("_npc40_started", than, "40NPC: khong duoc chen 0x17 luc prompt mo")

    def test_fast_bo_sleep_trong_heal_unit(self):
        i = self.src.find("    def _heal_unit(")
        j = self.src.find("    def scan_furnace(", i)
        than = self.src[i:j]
        self.assertIn("fast: bool = False", than)
        self.assertIn("if target == 0 and not fast:", than)
        self.assertIn("if not fast:\n                    time.sleep(0.2)", than)


if __name__ == "__main__":
    unittest.main()
