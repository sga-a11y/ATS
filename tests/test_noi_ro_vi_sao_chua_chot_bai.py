"""CHUA CHOT DUOC BAI TRAIN / CAP QUAI DG thi phai NOI RA, khong `return None` cam lang.

User 14/09: "p29 thay lap party o trac quan" -> tra nguoc thi be tac vi khong co du lieu.

`_auto_train_target` va `_auto_dg_level` deu tra None im lang khi thieu level. Chung chay MOI 2
GIAY, nen mot lan chan keo dai la hang TRAM lan tra None ma khong de lai mot dong nao.

CA THAT party 29, 14/09 (mode digioi_train, train_pick avg-30):
    23:55:36  party start
    23:56:53  [hoangtbay] MODE=digioi_train ma CHUA CO BAI TRAIN (sc=0, train_pick='avg-30')
    23:57:43  [party 29] REFORM gen -> 2 - chung kenh roi ma doi khong du -> lap lai party
    ...       lap lai moi ~2 phut, ca party dung o 12001 (Trac Quan) ...
    00:23:07  >>> PARTY 29: TU CHON MAP -> Trai Pham Thanh1 (map 21811)
27 phut, khoang 810 lan tra None trong im lang. Suot do `auto_train` rong -> dieu phoi khong biet
map train dich -> khong biet thanh tap ket -> lap party bua o thanh di ngang qua.

Truy nguoc khong ra nguyen nhan vi khong co du lieu: pet da xac nhan du ca 5 acc tu 23:55:41,
khong exception (`DIEU PHOI chot map loi` khong xuat hien), khong reconnect.

CHI LOG - khong doi hanh vi chot.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _BatLog(logging.Handler):
    def __init__(self):
        super().__init__()
        self.dong = []

    def emit(self, rec):
        self.dong.append(rec.getMessage())


class _Nen(unittest.TestCase):
    PARTY = 46

    def setUp(self):
        self.h = _BatLog()
        R.log.addHandler(self.h)
        self._lv = R.log.level
        R.log.setLevel(logging.DEBUG)
        self.st = {"lock": threading.RLock()}
        self._t = R.time.time
        self.gio = 1000.0
        R.time.time = lambda: self.gio

    def tearDown(self):
        R.time.time = self._t
        R.log.removeHandler(self.h)
        R.log.setLevel(self._lv)

    def _co(self, chuoi):
        return any(chuoi in d for d in self.h.dong)


class TestBaoKhiBiChanLau(_Nen):
    def test_moi_bi_chan_thi_CHUA_bao(self):
        """Vai giay dau la binh thuong (acc dang login) - bao ngay la spam."""
        R._bao_chan_chot(self.PARTY, self.st, "MAP TRAIN", ["a1(chua login, khong co ban luu)"])
        self.assertFalse(self._co("CHUA CHOT DUOC"))

    def test_chan_qua_nguong_thi_BAO(self):
        R._bao_chan_chot(self.PARTY, self.st, "MAP TRAIN", ["a1(char_level=None)"])
        self.gio += R.CHOT_BAI_BI_CHAN_BAO_SEC + 1
        R._bao_chan_chot(self.PARTY, self.st, "MAP TRAIN", ["a1(char_level=None)"])
        self.assertTrue(self._co("CHUA CHOT DUOC MAP TRAIN"))
        self.assertTrue(self._co("a1(char_level=None)"), "khong noi ro acc nao thieu gi")

    def test_khong_spam_moi_nhip(self):
        """Chay moi 2 giay - bao moi lan la ngap log."""
        R._bao_chan_chot(self.PARTY, self.st, "MAP TRAIN", ["a1"])
        self.gio += R.CHOT_BAI_BI_CHAN_BAO_SEC + 1
        for _ in range(20):
            self.gio += 2
            R._bao_chan_chot(self.PARTY, self.st, "MAP TRAIN", ["a1"])
        self.assertEqual(sum(1 for d in self.h.dong if "CHUA CHOT DUOC" in d), 1)

    def test_chot_duoc_roi_thi_QUEN_moc(self):
        """Lan chan sau phai tinh gio lai tu dau, khong an theo lan truoc."""
        R._bao_chan_chot(self.PARTY, self.st, "MAP TRAIN", ["a1"])
        R._bao_chan_chot(self.PARTY, self.st, "MAP TRAIN", [])       # da chot duoc
        self.assertNotIn("chot_chan_tu", self.st)
        self.gio += 3
        R._bao_chan_chot(self.PARTY, self.st, "MAP TRAIN", ["a1"])   # chan lai
        self.assertFalse(self._co("CHUA CHOT DUOC"), "tinh nham gio cua lan chan truoc")

    def test_bao_ro_ten_viec(self):
        R._bao_chan_chot(self.PARTY, self.st, "CAP QUAI DG", ["a1"])
        self.gio += R.CHOT_BAI_BI_CHAN_BAO_SEC + 1
        R._bao_chan_chot(self.PARTY, self.st, "CAP QUAI DG", ["a1"])
        self.assertTrue(self._co("CHUA CHOT DUOC CAP QUAI DG"))


class TestThieuLevelNoiRoTHIEU_GI(unittest.TestCase):
    """Danh sach thieu phai chi ra thieu GI, khong chi ten acc tron."""

    PARTY = 47
    ACCS = ("q1", "q2")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u,) for u in self.ACCS] if pidx == self.PARTY else []
        for u in self.ACCS:
            R.account_clients.pop(u, None)
            R.account_last.pop(u, None)

    def tearDown(self):
        R.party_accounts = self._pa
        for u in self.ACCS:
            R.account_clients.pop(u, None)
            R.account_last.pop(u, None)

    def test_chua_login_noi_ro(self):
        _t = R._acc_thieu_level(self.PARTY)
        self.assertTrue(any("chua login" in x for x in _t), _t)

    def test_co_client_ma_chua_co_char_level_noi_ro(self):
        class _C:
            char_level = None
            def pet_name_out(self): return None
        R.account_clients["q1"] = _C()
        R.account_clients["q2"] = _C()
        _t = R._acc_thieu_level(self.PARTY)
        self.assertTrue(any("char_level=None" in x for x in _t), _t)


class TestGanVaoCA_HAI_DUONG_CHOT(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def _than(self, ten):
        i = self.src.find("def %s(" % ten)
        self.assertGreater(i, 0, "mat %s" % ten)
        return self.src[i:self.src.find("\ndef ", i + 10)]

    def test_auto_train_target_co_bao(self):
        self.assertIn("_bao_chan_chot(pidx, st, \"MAP TRAIN\"", self._than("_auto_train_target"))

    def test_auto_dg_level_co_bao(self):
        self.assertIn("_bao_chan_chot(pidx, st, \"CAP QUAI DG\"", self._than("_auto_dg_level"))

    def test_khong_con_duong_tra_None_CAM(self):
        for _ten in ("_auto_train_target", "_auto_dg_level"):
            than = self._than(_ten)
            i = than.find("_acc_thieu_level(pidx)")
            j = than.find("return None", i)
            self.assertIn("_bao_chan_chot", than[i:j],
                          "%s van tra None cam lang khi thieu level" % _ten)


if __name__ == "__main__":
    unittest.main()
