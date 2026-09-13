"""VONG CHO LEADER XU LY PB phai nghe LENH DANG CO HIEU LUC, khong chi lenh moi hon.

User 13/09: "p24, thang daihai cu dung o trac quan, ko tap trung ve cung team".

Vong `_handle_auto_team_dungeon` (nhanh member) truoc day chi co MOT loi ra theo lenh:

    _pb_g0 = st["reform_gen"]      # moc luc BAT DAU cho
    ...
    if _pb_gnow > _pb_g0:  -> bo cho

So voi MOC LUC VAO VONG la acc tu chon "lenh nao nghe": lenh ra truoc do vai giay va VAN dang
chay thi bi coi la lenh cu, nuot luon.

CA THAT (party 24):

    13:19:21 [daihai] (member) pho ban to doi: HOAN - dieu phoi dang ra lenh 'gom'
                      (party dang o 3 MAP khac nhau [12001, 21011, 21852])
    13:20:19 [daihai] (member) PB lv50: leader chuyen sang REFORM (reform_gen 1->2) -> bo cho
    13:20:19 [daihai] (member) cho leader xu ly pho ban doi lv80...
    13:21:19 [daihai] (member) cho leader xu ly pho ban doi lv80...
    13:22:20 [daihai] (member) cho leader xu ly pho ban doi lv80...

Sang lv80 no vao vong MOI, chot moc gen = 2 - dung bang chinh lenh gom dang chay (lenh do da bump
gen len 2 tu 13:19:21). Tu do lenh ay vinh vien la "cu", va daihai dung o Trac Quan cho mot viec
khong ai lam, trong khi dieu phoi lien tuc keu party o 3 map khac nhau.

GIO: doc `party_dang_gom(pidx)` - co DUNG CHUNG ma dieu phoi bat moi nhip cho (VIEC_GOM, VIEC_MOI,
VIEC_DONG_BO), giong het nhung cho khac (`_handle_o5_team`, viec vat, boss the gioi).
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class _Nen(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        i = self.src.find("def _handle_auto_team_dungeon(")
        self.assertGreater(i, 0)
        j = self.src.find("\n    members = [t[0] for t in party_accounts(pidx)]", i)
        self.assertGreater(j, i, "mat moc ket thuc nhanh member")
        self.than = self.src[i:j]


class TestNgheLenhDangChay(_Nen):
    def test_co_doc_co_dung_chung(self):
        self.assertIn("party_dang_gom(pidx)", self.than,
                      "chi so gen voi moc luc vao vong -> nuot lenh dang chay")

    def test_bo_cho_chu_khong_chi_ghi_log(self):
        i = self.than.find("party_dang_gom(pidx)")
        self.assertIn("return True", self.than[i:i + 400], "doc lenh xong van dung do cho tiep")

    def test_VAN_giu_loi_ra_theo_gen(self):
        """Lenh ra SAU luc vao vong van phai bat duoc (hanh vi cu, dung - dung bo)."""
        self.assertIn("_pb_gnow > _pb_g0", self.than)

    def test_dung_CHUNG_co_voi_cac_cho_khac(self):
        """Moi cho mot dinh nghia 'dang co lenh' la som muon lech nhau."""
        self.assertIn("party_dang_gom", self.src)
        i = self.src.find("dat_party_dang_gom(pidx, viec in")
        self.assertGreater(i, 0)
        self.assertIn("VIEC_GOM, VIEC_MOI, VIEC_DONG_BO", self.src[i:i + 120])


class TestCoDungChungVanHanh(unittest.TestCase):
    """Chay that co - khong chi doc chu trong file."""

    def setUp(self):
        C.dat_party_dang_gom(24, False)

    def tearDown(self):
        C.dat_party_dang_gom(24, False)

    def test_dieu_phoi_bat_thi_member_doc_duoc(self):
        C.dat_party_dang_gom(24, True)
        self.assertTrue(C.party_dang_gom(24))

    def test_tat_thi_thoi(self):
        C.dat_party_dang_gom(24, True)
        C.dat_party_dang_gom(24, False)
        self.assertFalse(C.party_dang_gom(24))

    def test_party_khac_khong_anh_huong(self):
        C.dat_party_dang_gom(24, True)
        self.assertFalse(C.party_dang_gom(25))


if __name__ == "__main__":
    unittest.main()
