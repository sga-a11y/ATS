# -*- coding: utf-8 -*-
"""APK phai co man TUI DO (truoc do khong co gi - PC co BagDialog, APK khong).

Phan Python (`bag_info` / `bag_cmd`) test bang client gia; phan Kotlin doc thang .kt vi
`gradlew compileReleaseKotlin` chi noi code BIEN DICH DUOC, khong noi no con noi dung sang
Python (bai hoc trong CLAUDE.md).
"""
import os
import re
import sys
import unittest

_GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _GOC)
sys.argv = [sys.argv[0]]        # run_party_digioi doc int(sys.argv[1]) ngay o muc module

import run_party_digioi as R
from bot import client as C

_KTDIR = os.path.join(_GOC, "android", "app", "src", "main", "java", "com", "tsbot", "android")


def _doc(p):
    with open(os.path.join(_GOC, p), encoding="utf-8") as fh:
        return fh.read()


def _kt(name):
    with open(os.path.join(_KTDIR, name), encoding="utf-8") as fh:
        return fh.read()


class _Gia(C.GameClient):
    def __init__(self):
        self.running = True
        self._label = "test"
        self.bag_slots = {}
        self.da_chay = []
        self.trong_tran = False

    def bag_capacity(self):
        return 100

    def bag_used_slots(self):
        return len(self.bag_slots)

    def bag_slot_maxed(self):
        return False

    def is_fashion_item(self, tid):
        return False

    def queue_bag_cmd(self, ten, fn):
        return bool(self.trong_tran)     # True = da xep hang (dang trong tran)

    def use_slot(self, slot, target=0, qty=1):
        self.da_chay.append(("use", slot, target)); return True

    def decompose_slot(self, slot, wait=1.2):
        self.da_chay.append(("decompose", slot)); return True

    def discard_item(self, slot, qty=1):
        self.da_chay.append(("discard", slot, qty)); return True

    def deposit_fashion_slot(self, slot, wait=1.0):
        self.da_chay.append(("fashion", slot)); return True


class TestBagInfo(unittest.TestCase):
    def setUp(self):
        self.c = _Gia()
        R.account_clients["u1"] = self.c

    def tearDown(self):
        R.account_clients.pop("u1", None)

    def test_acc_chua_chay_tra_RONG(self):
        """Tui do la snapshot SONG - khong cache duoc (hien so cu roi bam phan giai = mat nham do)."""
        self.assertEqual(R.bag_info("khong-co-acc"), {})

    def test_liet_ke_o_va_co_cho_phep(self):
        self.c.bag_slots = {5: [0x52DD, 1]}      # Cam Quan Oan - trang bi
        info = R.bag_info("u1")
        self.assertEqual(info["cap"], 100)
        self.assertEqual(len(info["slots"]), 1)
        o = info["slots"][0]
        self.assertEqual((o["slot"], o["id"], o["cnt"]), (5, 0x52DD, 1))
        self.assertEqual(o["name"], "Cấm Quân Oản")
        self.assertTrue(o["equip"], "trang bi phai co nut Trang bi")
        for k in ("use", "dis", "fashion", "bank", "tab", "q", "st"):
            self.assertIn(k, o, "thieu co %r -> Kotlin phai tu suy = se lech luat client" % k)

    def test_o_rong_khong_liet_ke(self):
        self.c.bag_slots = {1: [0x52DD, 0]}
        self.assertEqual(R.bag_info("u1")["slots"], [])

    def test_mon_cam_gui_ngan_hang_thi_bank_False(self):
        gd = C._load_gamedata_items()
        gd[0x1234] = {"name": "mon cam", "restrict": 32}
        try:
            self.c.bag_slots = {2: [0x1234, 1]}
            self.assertFalse(R.bag_info("u1")["slots"][0]["bank"])
            gd[0x1234]["restrict"] = 0
            self.assertTrue(R.bag_info("u1")["slots"][0]["bank"])
        finally:
            gd.pop(0x1234, None)


class TestBagCmd(unittest.TestCase):
    def setUp(self):
        self.c = _Gia()
        R.account_clients["u1"] = self.c

    def tearDown(self):
        R.account_clients.pop("u1", None)

    def test_acc_chua_chay(self):
        self.assertTrue(R.bag_cmd("khong-co", "use", 1).startswith("False"))

    def test_lenh_la_bi_tu_choi(self):
        """UI chi duoc goi cac lenh trong danh sach TRANG."""
        self.assertTrue(R.bag_cmd("u1", "gui_het_do_di", 1).startswith("False"))
        self.assertEqual(self.c.da_chay, [])

    def test_chay_dung_lenh(self):
        self.assertEqual(R.bag_cmd("u1", "decompose", 7), "True")
        self.assertEqual(self.c.da_chay, [("decompose", 7)])

    def test_bo_mang_theo_so_luong(self):
        self.assertEqual(R.bag_cmd("u1", "discard", 3, 9), "True")
        self.assertEqual(self.c.da_chay, [("discard", 3, 9)])

    def test_dang_trong_tran_thi_XEP_HANG(self):
        """Client that chan thao tac tui do khi dang danh - gui bua la server nuot im lang."""
        self.c.trong_tran = True
        self.assertEqual(R.bag_cmd("u1", "decompose", 7), "queued")
        self.assertEqual(self.c.da_chay, [], "da xep hang thi KHONG duoc chay ngay")


class TestGiaoDienAPK(unittest.TestCase):
    def test_co_dialog_va_duoc_hien(self):
        src = _kt("MainActivity.kt")
        self.assertIn("fun BagDialog(", src)
        self.assertRegex(src, r"\n\s+BagDialog\(", "dinh nghia roi nhung KHONG hien")
        self.assertIn('Text("Túi", maxLines = 1)', src)
        self.assertIn("onOpenBag", src)

    def test_bon_tab_giong_client(self):
        src = _kt("MainActivity.kt")
        for t in ("Tất cả", "Trang bị", "Vật phẩm", "Nguyên liệu"):
            self.assertIn('"%s"' % t, src)

    def test_do_mac_duoc_thi_KHONG_hien_nut_Su_dung(self):
        """Hai lenh khac han nhau (0x17 sub0b deo len nguoi / sub0f tieu hao) - nham la sai lenh."""
        src = _kt("MainActivity.kt")
        m = re.search(r"if \(s\.canEquip\) \{.*?\} else if \(s\.canUse\) \{", src, re.S)
        self.assertIsNotNone(m, "phai la if/else - khong duoc hien ca hai nut cung luc")

    def test_sap_xep_theo_st_giong_client(self):
        """Client sap theo (sort ASC, id ASC), KHONG theo so o."""
        src = _kt("MainActivity.kt")
        self.assertIn("compareBy({ it.st }, { it.id })", src)

    def test_cau_noi_service(self):
        src = _kt("BotForegroundService.kt")
        for f, py in (("bagInfoJson", "bag_info"), ("bagCmd", "bag_cmd")):
            self.assertIn("fun %s(" % f, src)
            self.assertIn('"%s"' % py, src)

    def test_them_list_cat_ghi_file_CHUNG(self):
        """List cat dung chung moi acc -> phai ghi qua Python, khong luu vao PartyStore."""
        src = _kt("MainActivity.kt")
        m = re.search(r"onAddCatDo = \{.*?\n            \},", src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("BotForegroundService.saveCatDoItems", m.group(0))


if __name__ == "__main__":
    unittest.main()
