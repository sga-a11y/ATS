# -*- coding: utf-8 -*-
"""O NGOC (vi tri 6) phai theo GOI XAC NHAN cua server, khong lech giua 2 bang.

Ca that Lbmba 28/09: ngoc hong -> vut Ngoc Hu -> deo ngoc moi, nhung `equip_by_fit[6]` van ghi
Ngoc Hu. Di boss THAO ngoc -> S:023-016 xoa nham "Ngoc Hu", bot tuong van deo Sieu Phuc Than ->
khong deo lai, train ca tieng khong ngoc. Sau khi thao phai co co deo lai ngay khi ve train.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C

SIEU = 0x5AAB


def _cli():
    c = C.GameClient.__new__(C.GameClient)
    c._label = "t"
    c.running = True
    c.bag_slots = {}
    c.bag_counts = {}
    c.bag_items = {}
    c.equipped_items = []
    c.equip_by_fit = {}
    c.pet_equip_by_fit = {}
    c.pet_equipped = {}
    c._equip_seq = 0
    c.phuc_than_pending = False
    c.phuc_than_deo_lai = False
    c.sent = []
    c.send = lambda op, body: c.sent.append((op, bytes(body)))
    c._recalc_char_equip_stats = lambda: None
    return c


class TestONgoc(unittest.TestCase):
    def test_ngoc_hong_vut_deo_moi_roi_thao_thi_biet_la_da_thao(self):
        c = _cli()
        # login: dang deo Sieu Phuc Than
        c.equip_by_fit[6] = SIEU
        c.equipped_items = [{"id": SIEU, "pos": 6, "damage": 249, "damaged_item_id": 0}]
        # ngoc hong (S:023-035) -> o 6 thanh Ngoc Hu
        raw = bytearray(35)
        raw[0:2] = C.BROKEN_PHUC_THAN_TID.to_bytes(2, "little")
        raw[6] = 250
        raw[27:29] = SIEU.to_bytes(2, "little")
        c._on_equip_broken(bytes(9) + bytes([6]) + bytes(raw) + b"\x00")
        self.assertEqual(c._equipped_phuc_than_tid(), 0)
        # vut Ngoc Hu
        self.assertTrue(c._drop_broken_gem())
        self.assertIsNone(c._gem_record())
        # deo ngoc moi o slot 5, server xac nhan S:023-017
        c.bag_slots[5] = [SIEU, 1]
        self.assertTrue(c.equip_item(5))
        c._on_equip_done(5)
        self.assertEqual(c.equip_by_fit.get(6), SIEU)
        self.assertEqual(c._equipped_phuc_than_tid(), SIEU)
        # thao cho boss -> server xac nhan S:023-016
        c.bag_first_empty_slot = lambda: 9
        self.assertTrue(c.thao_ngoc_phuc_than("boss"))
        c._on_unequip_done(6, o_tui=9)
        self.assertEqual(c._equipped_phuc_than_tid(), 0, "da thao ma bot van tuong dang deo")
        self.assertTrue(c.phuc_than_deo_lai, "ve train phai deo lai ngay")
        self.assertEqual(c.bag_slots.get(9), [SIEU, 1])


if __name__ == "__main__":
    unittest.main()
