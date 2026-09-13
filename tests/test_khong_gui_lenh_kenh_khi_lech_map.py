"""LECH MAP THI CHUA TOI LUOT KENH - khong gui lenh doi kenh cho ai ca.

User 13/09: "cai do la no chot kenh ngu, khac map ma di chot lenh".

Kenh la thu THEO TUNG MAP: kenh 2 co o map nay, khong co o map kia. Gui lenh doi kenh cho acc
dang o map khac la chac chan hong - server tra `S:007-002` ma 2 <沒有該分區>.

CUA CU KHONG DU: `_dieu_phoi_chot_kenh` da co cua "dang gom map -> chua den luot kenh" (11/09),
nhung no chi chan viec CHOT DICH MOI, roi `return st.get("kenh_dich")` - tra ve dich CU. Ham thi
hanh van cam dich cu do gui cho MOI acc trong party, ke ca dua dang o map khac.

CA THAT 13/09 - `thbay` ve Nghiep Thanh (12061) ban Noi Dat trong khi party o 21001:

    12:55:35 [thbay] Ban Noi Dat: co 271 cai -> di NPC Nha buon Ng.Thanh
    12:55:38 [thbay] Doi kenh 2 THAT BAI: khong co khu do de doi (result=2)
    12:55:51 [thbay] Doi kenh 2 THAT BAI: khong co khu do de doi (result=2)
    ... lap deu moi 12 giay suot ca chuyen di ...

Map 12061 khong he co kenh 2. Lenh hong bam theo acc suot luc no dang lam viec khac (vi pham L8:
lenh hong phai dong cua).
"""
from __future__ import annotations

import io
import os
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _State:
    def __init__(self):
        self.in_battle = False


class _C:
    def __init__(self, kenh, map_id):
        self.running = True
        self.current_channel = kenh
        self.current_map = map_id
        self.state = _State()
        self._label = "acc%s" % kenh
        self.da_gui = []
        self._dp_gui_kenh_luc = 0.0
        self._dp_gui_kenh_dang_chay = False

    def in_combat(self, idle_secs=None):
        return False

    def _in_battle_end_grace(self):
        return False

    def switch_channel(self, ch, wait=None, retries=None, theo_lenh=False):
        self.da_gui.append(int(ch))
        self.current_channel = int(ch)
        return True


class TestLechMapThiKhongGui(unittest.TestCase):
    def setUp(self):
        self.st = {"lock": threading.RLock(), "event_battle_active": False}

    def test_ca_that_thbay_khong_bi_gui_lenh_kenh(self):
        """thbay o 12061 (ban Noi Dat), party o 21001 -> khong ai duoc lenh doi kenh."""
        thbay = _C(kenh=1, map_id=12061)
        con_lai = [_C(kenh=1, map_id=21001) for _ in range(4)]
        song = [("thbay", thbay)] + [("u%d" % i, c) for i, c in enumerate(con_lai)]
        n = R._dieu_phoi_thi_hanh_kenh(0, self.st, song, 2)
        self.assertEqual(n, 0)
        self.assertEqual(thbay.da_gui, [], "gui lenh kenh cho acc dang o map khac")
        for c in con_lai:
            self.assertEqual(c.da_gui, [])

    def test_cung_map_thi_VAN_gui_binh_thuong(self):
        """Bo cua qua tay thi khong bao gio dong bo duoc kenh nua."""
        a, b = _C(kenh=1, map_id=21001), _C(kenh=7, map_id=21001)
        n = R._dieu_phoi_thi_hanh_kenh(0, self.st, [("a", a), ("b", b)], 2)
        self.assertEqual(n, 2)

    def test_acc_chua_biet_map_thi_khong_tinh_la_lech(self):
        """`current_map=None` = chua doc duoc, khong phai 'map khac'."""
        a = _C(kenh=1, map_id=21001)
        b = _C(kenh=7, map_id=21001)
        b.current_map = None
        n = R._dieu_phoi_thi_hanh_kenh(0, self.st, [("a", a), ("b", b)], 2)
        self.assertEqual(n, 2)

    def test_mot_acc_thi_khong_bao_gio_lech(self):
        a = _C(kenh=1, map_id=12061)
        self.assertEqual(R._dieu_phoi_thi_hanh_kenh(0, self.st, [("a", a)], 2), 1)


class TestNeoTrongMa(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_cua_nam_TRUOC_vong_gui(self):
        i = self.src.find("def _dieu_phoi_thi_hanh_kenh(")
        self.assertGreater(i, 0)
        j = self.src.find("for _u, c in song:", i)
        self.assertGreater(j, i)
        self.assertIn("len(_maps) > 1", self.src[i:j],
                      "cua phai chan TRUOC khi gui, khong phai loc tung acc")

    def test_co_log_de_truy(self):
        i = self.src.find("def _dieu_phoi_thi_hanh_kenh(")
        j = self.src.find("for _u, c in song:", i)
        self.assertIn("chua gui lenh kenh", self.src[i:j])
        self.assertIn("kenh_cho_map_log", self.src[i:j], "khong chan spam -> ngap log moi 2 giay")


if __name__ == "__main__":
    unittest.main()
