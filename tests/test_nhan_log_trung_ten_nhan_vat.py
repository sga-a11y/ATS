"""Hai acc TRUNG TEN NHAN VAT (khac server) -> nhan log phai phan biet duoc.

Xay ra that 01/09/2026: party 40 (`dt801`-`dt805`, server dong_trac, dang danh Di Gioi) va party 48
(`dt901`-`dt905`, server dieu_thuyen, mode city) co char trung ten HET:
`dtmot/dthai/dtba/dtbon/dtnam`. Nhan log la ten nhan vat, con GUI map `_char2user[char] = user` la
1-1 nen acc login SAU de len acc truoc => loc log party 48 hut ca dong

    10:17:35 [dtmot] BATTLE SEND g=44 ... skill=12003(Hoa Tien)

cua party 40, trong khi party 48 that su dang `pos=(490,490) map=12003 combat=False`
(user: "party 48 dung o quang truong ma cu bao battle gi the").

Chot: trung ten thi CA HAI acc doi nhan thanh `ten~username` (khong phai chi acc thu hai - de nhan
on dinh, khong phu thuoc thu tu login).
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as bc            # noqa: E402


def _acc(username):
    c = bc.GameClient.__new__(bc.GameClient)
    c._username = username
    c._label = username
    c.char_name = ""
    return c


class TestNhanLogTrungTen(unittest.TestCase):
    def setUp(self):
        bc._NHAN_CHU.clear()

    def test_khong_trung_thi_nhan_van_la_TEN_NHAN_VAT(self):
        """Doi 100% acc sang 'ten~user' se lam log dai va kho doc - chi acc trung moi co duoi."""
        c = _acc("dt801")
        c._dat_nhan_log("dtmot")
        self.assertEqual(c._label, "dtmot")
        self.assertEqual(c.char_name, "dtmot")

    def test_trung_ten_thi_CA_HAI_doi_nhan(self):
        a, b = _acc("dt801"), _acc("dt901")
        a._dat_nhan_log("dtmot")
        b._dat_nhan_log("dtmot")
        self.assertEqual(a._label, "dtmot~dt801", "acc login TRUOC van giu nhan tron -> van lan")
        self.assertEqual(b._label, "dtmot~dt901")

    def test_nhan_van_giu_ten_nhan_vat_o_dau(self):
        """Nguoi doc van phai nhan ra ngay day la nhan vat nao."""
        a, b = _acc("dt801"), _acc("dt901")
        a._dat_nhan_log("dtmot"); b._dat_nhan_log("dtmot")
        for c in (a, b):
            self.assertTrue(c._label.startswith("dtmot"))
            self.assertEqual(c.char_name, "dtmot", "char_name phai giu NGUYEN de hien cot Nhan vat")

    def test_hai_nhan_KHAC_NHAU(self):
        a, b = _acc("dt801"), _acc("dt901")
        a._dat_nhan_log("dtmot"); b._dat_nhan_log("dtmot")
        self.assertNotEqual(a._label, b._label)

    def test_goi_lai_nhieu_lan_khong_sinh_duoi_oan(self):
        """Ten nhan vat den tu 3 nguon goi (0x03, 0x27, spawn) - moi acc co the goi nhieu lan."""
        a = _acc("dt801")
        for _ in range(3):
            a._dat_nhan_log("dtmot")
        self.assertEqual(a._label, "dtmot")

    def test_ten_khac_nhau_khong_anh_huong_nhau(self):
        a, b = _acc("dt801"), _acc("dt901")
        a._dat_nhan_log("dtmot"); b._dat_nhan_log("dthai")
        self.assertEqual((a._label, b._label), ("dtmot", "dthai"))


class TestKhongCon_LABEL_GAN_THANG(unittest.TestCase):
    def test_moi_cho_dat_ten_deu_qua_ham_chung(self):
        """Bo sot mot cho gan `_label = ten` la cho do lai lan nhu cu."""
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("    def _dat_nhan_log(")
        j = s.find("\n    def ", i + 10)
        ngoai = s[:i] + s[j:]
        for xau in ("self._label = nm", "self._label = name"):
            self.assertNotIn(xau, ngoai, "con cho gan nhan thang, khong qua _dat_nhan_log")
        self.assertGreaterEqual(s.count("self._dat_nhan_log("), 3)


class TestGUILocTheoNhan(unittest.TestCase):
    def test_char2user_neo_theo_LABEL_khong_phai_char_name(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def _refresh(self):")
        khoi = s[i:i + 1500]
        self.assertIn("self._char2user[c._label] = u", khoi)
        self.assertNotIn("self._char2user[c.char_name] = u", khoi,
                         "map theo char_name -> acc trung ten de nhau, log lan lai")


class TestAPKLocTheoNhan(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.rpd = fh.read()

    def test_status_co_log_label(self):
        self.assertIn('"log_label": getattr(c, "_label", "") or ""', self.rpd)

    def test_get_account_log_loc_theo_nhan(self):
        i = self.rpd.find("def get_account_log(")
        than = self.rpd[i:self.rpd.find("\ndef ", i + 10)]
        self.assertIn('_st.get("log_label")', than)
        self.assertNotIn('tags.append("[%s]" % char_name)', than,
                         "van loc theo char_name -> APK hut log cua acc trung ten")

    def _kt(self, ten):
        with io.open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot",
                                  "android", ten), encoding="utf-8") as fh:
            return fh.read()

    def test_kotlin_co_truong_logLabel(self):
        self.assertIn("val logLabel: String = \"\"", self._kt("AccountStatus.kt"))
        self.assertIn('logLabel = gString("log_label")', self._kt("BotForegroundService.kt"))

    def test_kotlin_mask_theo_logLabel(self):
        s = self._kt("MainActivity.kt")
        i = s.find("maskAccountLog(onGetLog()")
        self.assertGreater(i, 0)
        self.assertIn("status.logLabel.ifBlank { status.charName }", s[i - 200:i + 300])


if __name__ == "__main__":
    unittest.main()
