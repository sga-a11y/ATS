"""O TRONG trong bo do = COI mon dang deo o o do ra (user chot 27/08).

Truoc day `apply_outfit` CHI BIET MAC: bo de trong o Giay ma pet dang deo giay thi mac bo xong
giay VAN CON tren nguoi -> bo khong bao gio ra dung hinh. Va vi khong co gi de mac nen ham tra
0 lenh, GUI lai hien nham "Khong gui duoc lenh (o trong / acc mat ket noi)" -> user tuong rot
mang (anh chup 27/08, log `Bo do: da gui 0 lenh mac`).
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402


class _C:
    OUTFIT_FITS = GameClient.OUTFIT_FITS
    apply_outfit = GameClient.apply_outfit

    def __init__(self, dang_mac_pet=None, dang_mac_char=None):
        self._label = "test"
        self.equip_by_fit = dict(dang_mac_char or {})
        self.pet_equip_by_fit = {1: dict(dang_mac_pet or {})}
        self.mac = []          # (follow, slot)
        self.coi = []          # (follow, fit)
        self.tui = {}          # tid -> slot

    def _bag_slot_best(self, tid):
        return self.tui.get(int(tid))

    def equip_item(self, slot):
        self.mac.append((0, slot))
        return True

    def equip_pet_item(self, follow, slot):
        self.mac.append((int(follow), slot))
        return True

    def unequip_item(self, fit_pos, follow=0):
        self.coi.append((int(follow), int(fit_pos)))
        return True


def _khong_ngu():
    import bot.client as m
    return m


class TestOTrongThiCoi(unittest.TestCase):
    def setUp(self):
        import bot.client as m
        self._sleep = m.time.sleep
        m.time.sleep = lambda *_a, **_k: None      # bo 0.35s giua cac lenh cho test nhanh

    def tearDown(self):
        import bot.client as m
        m.time.sleep = self._sleep

    def test_o_trong_thi_COI_mon_dang_deo(self):
        """Bo qv85: 4 mon + Giay/Dac biet de trong, ma pet dang deo giay -> phai coi giay."""
        c = _C(dang_mac_pet={1: 0x11, 2: 0x22, 3: 0x33, 4: 0x44, 5: 0x5613})
        bo = {"pets": {1: {1: 0x11, 2: 0x22, 3: 0x33, 4: 0x44}}}
        gui, thieu = c.apply_outfit(bo)
        self.assertEqual(c.coi, [(1, 5)], "khong coi giay -> bo khong ra dung hinh")
        self.assertEqual(gui, 1, "coi do cung phai tinh la mot lenh da gui")
        self.assertEqual(thieu, [])

    def test_o_trong_ma_dang_KHONG_deo_gi_thi_thoi(self):
        c = _C(dang_mac_pet={1: 0x11})
        gui, _ = c.apply_outfit({"pets": {1: {1: 0x11}}})
        self.assertEqual(c.coi, [])
        self.assertEqual(gui, 0)

    def test_khoa_CHUOI_khong_lam_coi_nham(self):
        """Bo luu ra JSON thi khoa thanh chuoi - tra `muon.get(5)` bang int se truot."""
        c = _C(dang_mac_pet={1: 0x11, 5: 0x5613})
        gui, _ = c.apply_outfit({"pets": {1: {"1": 0x11, "5": 0x5613}}})
        self.assertEqual(c.coi, [], "doc nham khoa chuoi -> COI NHAM mon ma bo dang co")
        self.assertEqual(c.mac, [], "dang mac dung roi ma van gui lenh mac")

    def test_mac_TRUOC_roi_moi_coi(self):
        """Mac xong thi mon cu ve tui = co them o trong cho lenh coi (coi do CAN o tui trong)."""
        c = _C(dang_mac_pet={1: 0x99, 5: 0x5613})
        c.tui = {0x11: 7}
        c.apply_outfit({"pets": {1: {1: 0x11}}})
        self.assertEqual(c.mac, [(1, 7)])
        self.assertEqual(c.coi, [(1, 5)])

    def test_char_cung_ap_dung(self):
        c = _C(dang_mac_char={3: 0x77})
        gui, _ = c.apply_outfit({"char": {1: 0}})
        self.assertEqual(c.coi, [(0, 3)])

    def test_tui_day_khong_coi_duoc_thi_khong_dem(self):
        c = _C(dang_mac_pet={5: 0x5613})
        c.unequip_item = lambda fit_pos, follow=0: False     # tui day
        gui, _ = c.apply_outfit({"pets": {1: {1: 0}}})
        self.assertEqual(gui, 0, "coi khong duoc ma van dem la da gui")


class TestBaoDungChoUser(unittest.TestCase):
    def test_khong_can_gui_KHAC_khong_gui_duoc(self):
        with open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("elif not sent:")
        self.assertGreater(i, 0)
        khoi = src[i:i + 700]
        self.assertIn('text.startswith("Mặc bộ")', khoi,
                      "mac bo khong can thay gi van bao 'acc mat ket noi'")
        self.assertIn("đã đúng bộ sẵn rồi", khoi)


if __name__ == "__main__":
    unittest.main()
