"""DANG LAP DO DANG THI DE NO LAP NOT - dap party dang hinh thanh la cach chac nhat de no khong du.

User 11/09: "p2 p3 va rat nhieu party khac, leader van chay ra map 1 minh" -> "t bao xem TRUOC DO
co ma, doan dang di ra map train ay".

Doan truoc do (party 3, 08:43:30):

    REFORM gen -> 25 (bump tai :9807) - chung kenh roi ma doi khong du -> lap lai party
    DIEU PHOI: ca party da chung kenh 1 nhung DOI chua du
               (sga005=4 sga007=4 sga008=2 sga009=3 sga010=1) -> LAP LAI PARTY

Bon con so do la roster DANG LEN - leader moi duoc gan het doi thi bi giai tan. Roi moi den man
quen thuoc: di train -> lech map -> gom -> ve thanh -> lap lai -> ... va leader di ra bai mot minh.
Party 19, 6, 7, 24 deu chet o dung cho nay.

Dieu phoi khong hoi ai ca - no TU DOC `c.party_members` (roster server gui ve) cua tung client cung
tien trinh moi 2 giay (L2). Cai thieu khong phai thong tin, ma la mot phep do: `_thieu_doi` chi cho
biet "du chua", va mot party dang moi tung nguoi thi LUC NAO cung "chua du". Lay do lam co de dap
no la sai ve nguyen tac, khong phai sai ve nguong gio.

`_doi_dang_lap` do TONG roster ca party: so do chi tang khi co nguoi THAT SU vao doi va tut ve 0
khi doi tan - tuc tu no phan biet duoc "dang moi do dang" voi "dung im khong ai vao", khong acc
nao phai khai bao gi.
"""
from __future__ import annotations

import io
import os
import re
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# `run_party_digioi` doc `sys.argv[1]` luc import (so phut chay) - khong gia lap thi unittest truyen
# ten test vao do va module vo ngay khi import.
with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class _C:
    def __init__(self, n):
        self.party_members = [object()] * n


def _song(*ns):
    return [("u%d" % i, _C(n)) for i, n in enumerate(ns)]


class TestDoiDangLap(unittest.TestCase):
    """Chay that ham, khong chi doc chu."""

    def setUp(self):
        self.R = R
        self.st = {}

    def test_roster_dang_len_la_DANG_LAP(self):
        """Dung ca party 3: roster tong di len qua tung nhip."""
        self.assertTrue(self.R._doi_dang_lap(self.st, _song(1, 1, 0, 0, 0)))
        self.assertTrue(self.R._doi_dang_lap(self.st, _song(4, 4, 2, 3, 1)))

    def test_roster_dung_yen_qua_lau_thi_KHONG_con_la_dang_lap(self):
        """Khong duoc bien thanh 'mai mai dang lap' -> party hong that se khong ai cuu (L0)."""
        self.R._doi_dang_lap(self.st, _song(2, 2, 0, 0, 0))
        self.st["roster_tong"] = (4, time.time() - self.R.DOI_DANG_LAP_SEC - 1)
        self.assertFalse(self.R._doi_dang_lap(self.st, _song(2, 2, 0, 0, 0)))

    def test_roster_tut_la_doi_TAN_chu_khong_phai_dang_lap(self):
        self.R._doi_dang_lap(self.st, _song(4, 4, 4, 4, 4))
        self.assertFalse(self.R._doi_dang_lap(self.st, _song(0, 0, 0, 0, 0)))

    def test_party_rong_khong_phai_dang_lap(self):
        self.assertFalse(self.R._doi_dang_lap(self.st, _song(0, 0, 0, 0, 0)))


class TestNhanhLapLaiPartyCoCuaChan(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_cua_dung_TRUOC_nhanh_bump(self):
        i_cua = self.src.find("_doi_dang_lap(st, song)")
        i_bump = self.src.find('_bump_reform(st, "chung kenh roi ma doi khong du')
        self.assertGreater(i_cua, 0, "mat cua chan -> lai dap party dang lap")
        self.assertGreater(i_bump, 0)
        self.assertLess(i_cua, i_bump, "phai chan TRUOC khi bump (bump la da giai tan xong)")

    def test_cua_chan_GHI_LY_DO(self):
        self.assertIn("roster DANG LEN", self.src)

    def test_han_ngan_hon_cooldown_lap_lai(self):
        """Hai han phai long nhau, khong cai nao nuot cai nao."""
        self.assertLess(R.DOI_DANG_LAP_SEC, R.LAP_LAI_PARTY_COOLDOWN)


class TestMemberKhongTuLapDuong(unittest.TestCase):
    """Het han cho leader -> MEMBER RA, khong tu lap duong. Buoc dau cua flow "di train" la
    `pre_route_town_hop()` = VE THANH, nen tu di = quay dau ve thanh giua luc leader dang keo."""

    def setUp(self):
        self.src = _src()
        i = self.src.find("ROUTE_PLAN_TIEP_QUAN_SEC:")
        self.assertGreater(i, 0)
        self.khoi = self.src[i:i + 700]

    def test_het_han_thi_RA_chu_khong_tu_lap(self):
        self.assertNotIn("_chot_thanh_tap_ket(False)", self.khoi,
                         "member lai tu lap duong -> tu ve thanh giua chuyen")
        self.assertIn("return", self.khoi)

    def test_member_KHONG_con_duong_nao_tu_lap_duong(self):
        """Chi LEADER duoc lap duong. `_chot_thanh_tap_ket(False)` = ban member -> phai bien mat."""
        self.assertNotIn("_chot_thanh_tap_ket(False)", self.src)

    def test_ghi_ly_do_khi_ra(self):
        self.assertIn("de dieu phoi quyet", self.khoi)


if __name__ == "__main__":
    unittest.main()
