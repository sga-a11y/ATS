# -*- coding: utf-8 -*-
"""TU TANG TRUNG THANH PET (login): pet < 40 -> Thien Ly Ma (+3) truoc, het moi Danh Ma (+1),
dung toi khi > 40. Pet DUNG 40 -> khong dung. User 30/09: "nho dung cho dung pet, dung lam loi
kieu dung cho pet 2 3 4 nhung lai la dung cho pet 1" -> target PHAI la marker (o) cua CHINH pet do.
"""
import unittest
from unittest import mock

from bot import client as client_mod
from bot.client import GameClient

TLM, DM = 0xbf6b, 0xbf69


def _bot(pets, bag):
    """pets: {marker: (pid, faith)}; bag: {slot: (tid, count)}."""
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c._pet_marker_pid = {m: pid for m, (pid, _f) in pets.items()}
    c.pet_faith = {pid: f for pid, f in pets.values()}
    c.bag_slots = dict(bag)
    c.goi = []

    def use_slot(slot, target=0, qty=1):
        c.goi.append((c.bag_slots[slot][0], target, qty))
        return True
    c.use_slot = use_slot
    return c


def _chay(c):
    with mock.patch.object(client_mod.time, "sleep"):
        c.tang_trung_thanh_pet()


class TestTangTrungThanhPet(unittest.TestCase):
    def test_item_vao_DUNG_o_cua_tung_pet(self):
        """3 pet o 1/2/4 (khong lien tuc). Chi pet o 2 va o 4 thap -> target phai la 2 va 4."""
        c = _bot({1: (101, 80), 2: (102, 35), 4: (104, 39)}, {7: (TLM, 50)})
        _chay(c)
        self.assertEqual(sorted({t for _tid, t, _q in c.goi}), [2, 4])
        self.assertNotIn(1, [t for _tid, t, _q in c.goi])

    def test_dung_plus3_toi_khi_tren_40(self):
        c = _bot({2: (102, 35)}, {7: (TLM, 50)})
        _chay(c)
        self.assertEqual(c.goi, [(TLM, 2, 2)])          # 35 + 6 = 41
        self.assertEqual(c.pet_faith[102], 41)

    def test_39_dung_1_cai_plus3(self):
        c = _bot({3: (103, 39)}, {7: (TLM, 50)})
        _chay(c)
        self.assertEqual(c.goi, [(TLM, 3, 1)])          # 39 + 3 = 42 > 40

    def test_dung_40_thi_KHONG_dung(self):
        c = _bot({1: (101, 40)}, {7: (TLM, 50), 8: (DM, 50)})
        _chay(c)
        self.assertEqual(c.goi, [])

    def test_het_plus3_thi_dung_plus1(self):
        c = _bot({2: (102, 35)}, {7: (TLM, 1), 8: (DM, 50)})
        _chay(c)
        self.assertEqual(c.goi, [(TLM, 2, 1), (DM, 2, 3)])   # 35+3=38, +3x1 = 41
        self.assertEqual(c.pet_faith[102], 41)

    def test_chi_co_plus1(self):
        c = _bot({4: (104, 38)}, {8: (DM, 50)})
        _chay(c)
        self.assertEqual(c.goi, [(DM, 4, 3)])

    def test_khong_dung_item_khac(self):
        c = _bot({2: (102, 10)}, {5: (0x1234, 99), 7: (TLM, 2)})
        _chay(c)
        self.assertEqual({tid for tid, _t, _q in c.goi}, {TLM})

    def test_hai_pet_cung_thap_chia_item_dung_o(self):
        """Pet o 1 dung het +3 -> pet o 3 chi con +1, van phai vao o 3."""
        c = _bot({1: (101, 38), 3: (103, 39)}, {7: (TLM, 1), 8: (DM, 50)})
        _chay(c)
        self.assertEqual(c.goi, [(TLM, 1, 1), (DM, 3, 2)])   # 38+3=41 | 39+2=41


if __name__ == "__main__":
    unittest.main()
