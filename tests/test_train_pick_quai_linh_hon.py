# -*- coding: utf-8 -*-
"""Tick 'Quai linh hon': tu chon map CHI chon map LH-. Khong tick = CHI map thuong (nhu cu)."""
import random
import unittest

from bot import train_pick as TP

MAPS = [(1, "Rung A 100-105", [(10, 0)]), (2, "LH-Hang B 100-105", [(20, 0)]),
        (3, "Map C 100-105", []), (4, "LH-Dong D 100-105", [])]


class QuaiLinhHon(unittest.TestCase):
    def _pick(self, soul, maps=MAPS):
        return TP.pick_train_spot("avg-20", [120], maps, stats={"maps": {}},
                                  rng=random.Random(1), soul=soul)

    def test_khong_tick_chi_map_thuong(self):
        self.assertEqual(self._pick(False)[0], 3)          # map thuong chua quet
        self.assertEqual(self._pick(False, MAPS[:2])[0], 1)

    def test_tick_chi_map_lh(self):
        self.assertEqual(self._pick(True)[0], 4)           # map LH chua quet
        self.assertEqual(self._pick(True, MAPS[:2])[0], 2)

    def test_tick_khong_co_map_lh_thi_none(self):
        self.assertIsNone(self._pick(True, [MAPS[0]]))

    def test_map_thap_nhat_theo_loai(self):
        got = TP.pick_train_spot("avg-20", [30], MAPS[:2], stats={"maps": {}},
                                 rng=random.Random(1), soul=True)
        self.assertEqual(got[0], 2)


if __name__ == "__main__":
    unittest.main()
