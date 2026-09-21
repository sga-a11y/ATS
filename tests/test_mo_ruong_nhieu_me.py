# -*- coding: utf-8 -*-
"""MO RUONG: moi luot login mo toi da 5 ME, khong phai 1.

User 21/09: "bay gio luc login thi cai mo ruong trang bi, ruong PB la chi mo 1 lan, vi truoc so
loi, ma gio chay ngon roi, ma cho moi lan login check mo 5 lan".

Luat CU (user chot 04/09, gio da noi long): "luc login ko can mo den het ruong, chi can mo 1 lan".
Dinh nghia MOT ME thi GIU NGUYEN: het stack ruong do HOAC day tui, cai nao toi truoc.

Ruong PB nam chung danh sach `bliss_bag.json` voi ruong trang bi (cung di qua
`tu_mo_hop_trang_bi`), nen mot cho sua la phu ca hai.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


def _than(src, dau, het="\n    def "):
    i = src.find(dau)
    return "" if i < 0 else src[i:src.find(het, i + 10)]


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestSoMe(unittest.TestCase):
    def test_hang_so_la_5(self):
        self.assertEqual(C.GameClient.MO_RUONG_MOI_LOGIN, 5)

    def test_CO_vong_lap_theo_me(self):
        than = _than(_doc("bot", "client.py"), "    def tu_mo_hop_trang_bi(")
        self.assertIn("for _me in range(self.MO_RUONG_MOI_LOGIN):", than,
                      "van mo mot me roi dung han")

    def test_DINH_NGHIA_MOT_ME_giu_nguyen(self):
        """Mot me = min(ca stack, so o trong). Doi cai nay la login keo dai han."""
        than = _than(_doc("bot", "client.py"), "    def tu_mo_hop_trang_bi(")
        self.assertIn("n = max(1, min(int(self.bag_slots[slot][1]), trong // can))", than)

    def test_DUNG_SOM_khi_khong_con_gi_de_mo(self):
        """Khong con ruong nao mo duoc ma van quay du 5 vong = keo dai login vo ich."""
        than = _than(_doc("bot", "client.py"), "    def tu_mo_hop_trang_bi(")
        self.assertIn("if not _xong_me:", than)

    def test_TUI_DAY_thi_dung_HAN_khong_quay_tiep(self):
        """Tui day thi me sau cung khong mo duoc - phai `return`, khong phai `break` mot vong."""
        than = _than(_doc("bot", "client.py"), "    def tu_mo_hop_trang_bi(")
        i = than.find('kq["bo_qua"] = "tui day')
        self.assertGreater(i, 0)
        self.assertIn("return kq", than[i:i + 300])

    def test_van_DON_DO_SOT_moi_me(self):
        """Don xong moi co cho mo me moi - bo di thi me 2 gap tui day ngay."""
        than = _than(_doc("bot", "client.py"), "    def tu_mo_hop_trang_bi(")
        self.assertGreaterEqual(than.count("self._don_do_ruong_con_sot(_tick, boxes, gd, kq)"), 3)

    def test_ham_van_TRA_VE_ket_qua(self):
        than = _than(_doc("bot", "client.py"), "    def tu_mo_hop_trang_bi(")
        self.assertTrue(than.rstrip().endswith("return kq"),
                        "thieu return cuoi -> ham tra None, caller `_kq.get` no ngay")


class TestAPKGiong(unittest.TestCase):
    def test_apk_cung_5_me(self):
        apk = _doc("android", "app", "src", "main", "python", "train_bot", "client.py")
        self.assertIn("MO_RUONG_MOI_LOGIN = 5", apk)
        self.assertIn("for _me in range(self.MO_RUONG_MOI_LOGIN):", apk)


if __name__ == "__main__":
    unittest.main()
