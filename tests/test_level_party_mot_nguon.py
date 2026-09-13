"""LEVEL PARTY doc tu MOT NGUON, va PET khong phai dieu kien chot bai train.

User 14/09, hai y:
  - "chon bai train thi dua vao lv nhung con hien tai thoi, dua nao thieu pet thi ke me no di"
  - "van tinh char cua acc do chu"
  - "da co cho tinh lv trung binh roi ma cho nay lai tinh lai a"

1) Doi `active_pet_confirmed` de chot bai train la vo ly: mot con pet chua kip xac nhan khoa CA
   chuoi dieu phoi - `auto_train` rong -> khong biet map train dich -> khong biet thanh tap ket ->
   ca party lap party bua o thanh di ngang qua (Trac Quan) roi teleport lam tan doi.
   Ca that party 29, 14/09 (mode digioi_train, train_pick avg-30, ca party o 12001):
       23:55:36..39  ca 5 acc 'PET login active slot=1'
       23:56:53 [hoangtbay] MODE=digioi_train ma CHUA CO BAI TRAIN (sc=0, train_pick='avg-30')
       23:57:43 [party 29] REFORM gen -> 2 - chung kenh roi ma doi khong du -> lap lai party
       ... lap lai moi 2 phut den 00:20 ...
       00:23:07 >>> PARTY 29: TU CHON MAP -> Trai Pham Thanh1 (map 21811)   <- 27 phut sau

2) Acc thieu pet VAN gop char level - khong loai ai khoi phep tinh, va khong cong so 0 nao.

3) Ba cho doc level party phai dung CHUNG mot nguon (`_party_level_rows`). Chep tay o dau la o do
   lech (bay trong CLAUDE.md).
"""
from __future__ import annotations

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
    def __init__(self, confirmed=True):
        self.active_pet_confirmed = confirmed


class _C:
    def __init__(self, char_level, pet_level=None, pet_confirmed=True):
        self.char_level = char_level
        self.pet_level = pet_level
        self._pet = "Quan Vu" if pet_level else None
        self.state = _State(pet_confirmed)

    def pet_name_out(self):
        return self._pet if self.state.active_pet_confirmed else None


class _Nen(unittest.TestCase):
    PARTY = 44
    ACCS = ("z1", "z2", "z3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u,) for u in self.ACCS] if pidx == self.PARTY else []
        self._cl = dict(R.account_clients)
        self._al = dict(R.account_last)
        for u in self.ACCS:
            R.account_clients.pop(u, None)
            R.account_last.pop(u, None)

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R.account_last.clear(); R.account_last.update(self._al)


class TestPetKhongChanChotBai(_Nen):
    def test_thieu_pet_khong_con_la_THIEU_LEVEL(self):
        for u in self.ACCS:
            R.account_clients[u] = _C(150, pet_level=178)
        R.account_clients["z2"] = _C(150, pet_level=178, pet_confirmed=False)
        self.assertEqual(R._acc_thieu_level(self.PARTY), [],
                         "mot con pet chua xac nhan van khoa ca chuoi dieu phoi")

    def test_chua_co_CHAR_level_thi_van_la_thieu(self):
        """Bo pet khong duoc keo theo bo luon char - khong co char la chua login xong."""
        for u in self.ACCS:
            R.account_clients[u] = _C(150, pet_level=178)
        R.account_clients["z3"] = _C(None)
        _t = R._acc_thieu_level(self.PARTY)
        self.assertEqual([x.split("(")[0] for x in _t], ["z3"])


class TestKhongLoaiAccKhoiPhepTinh(_Nen):
    def test_acc_thieu_pet_VAN_gop_char(self):
        R.account_clients["z1"] = _C(150, pet_level=178)
        R.account_clients["z2"] = _C(177, pet_level=190, pet_confirmed=False)
        R.account_clients["z3"] = _C(151, pet_level=178)
        lv = R._party_levels(self.PARTY)
        self.assertIn(177, lv, "acc thieu pet bi loai khoi phep tinh level party")

    def test_khong_cong_so_0_nao(self):
        """Thieu pet = gop MOT so, khong phai gop them mot so 0."""
        R.account_clients["z1"] = _C(150, pet_level=178)
        R.account_clients["z2"] = _C(150, pet_level=178, pet_confirmed=False)
        R.account_clients["z3"] = _C(150, pet_level=178)
        lv = R._party_levels(self.PARTY)
        self.assertNotIn(0, lv)
        self.assertEqual(len(lv), 5, "3 char + 2 pet (mot acc khong tha pet)")
        self.assertEqual(sorted(lv), [150, 150, 150, 178, 178])


class TestMotNguonDuyNhat(_Nen):
    def test_hai_ham_doc_cung_nguon(self):
        R.account_clients["z1"] = _C(150, pet_level=178)
        R.account_clients["z2"] = _C(150, pet_level=178)
        R.account_clients["z3"] = _C(150, pet_level=178)
        rows = R._party_level_rows(self.PARTY)
        self.assertEqual(len(rows), 3)
        self.assertEqual(R._party_levels(self.PARTY), [150, 178] * 3)
        self.assertEqual(R._party_average_level(self.PARTY),
                         R._average_party_levels(rows))

    def test_acc_da_tat_lay_tu_account_last(self):
        R.account_clients["z1"] = _C(150, pet_level=178)
        R.account_last["z2"] = {"char_level": 151}
        R.account_last["z3"] = {"char_level": 152, "pet_name": "x", "pet_level": 180}
        self.assertEqual(sorted(R._party_levels(self.PARTY)), [150, 151, 152, 178, 180])

    def test_ca_hai_ham_deu_goi_nguon_chung(self):
        """Khong ham nao duoc TU quet `party_accounts` de dung lai rows - chep tay la lech.

        (Cac cho GHI `account_last` luc acc thoat / cho GUI khong tinh: chung luu snapshot mot acc,
        khong phai doc level ca party.)
        """
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        for _ten in ("_party_levels", "_party_average_level"):
            i = src.find("def %s(" % _ten)
            self.assertGreater(i, 0, "mat %s" % _ten)
            than = src[i:src.find("\ndef ", i + 10)]
            self.assertIn("_party_level_rows(pidx)", than, "%s khong dung nguon chung" % _ten)
            self.assertNotIn("party_accounts(pidx)", than,
                             "%s tu quet party_accounts -> chep tay cach doc level" % _ten)


if __name__ == "__main__":
    unittest.main()
