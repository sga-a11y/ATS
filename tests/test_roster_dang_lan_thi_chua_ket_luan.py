"""ROSTER CHUA NHAT TRI thi DIEU PHOI chua duoc ket luan "doi hong" - khong ra lenh pha doi.

User 14/09: 'p17, thay log "chua ra bai, dieu phoi ra lenh moi" la sao' -> "ko cho acc tu quyet,
dieu phoi ra lenh dung la dc".

Roster tren SERVER la MOT su that; `c.party_members` cua nam acc chi la nam ban sao va chung toi
KHONG CUNG LUC. `_thieu_doi` lay ban sao CHAM NHAT lam chuan, nen doi VUA DU bi doc thanh "doi
hong" trong vai giay dau -> sinh lenh LAP LAI PARTY -> leader `leave_party()` -> PHA DUNG CAI DOI
VUA HINH THANH.

CA THAT party 17 (chu706..chu710, map train 23822):
    11:49:21 [party 17] LAP LAI PARTY (chu706=4 chu707=3 chu708=4 chu709=2 chu710=1)
    11:49:31 [party 17] RUT lenh reform gen 3 - da du doi (chu706=4 chu707=4 ... chu710=4)
    11:49:36 [chusau] (LEADER) reform gen 3: ... -> moi lai party
    11:49:36 [chusau] Roi/giai tan party cu -> roster 3 -> 2 -> 1 -> 0
    11:49:37 [party 17] gen 25: viec=moi - DOI chua du (tat ca = 0)
Luc 11:49:21 chu706 va chu708 DA thay du 4 - doi that su da du tren server. Chu ky lap lai y het
luc 11:51:34 -> 11:51:36.

PHAI PHAN BIET voi doi HONG THAT (party 1, 07/09: roster (4,0,0,0,0) DUNG IM 44 phut, user: "du
doi cai lon, bon no co cung party deo dau"). Khac nhau o cho: lech do co TU HET trong vai giay
khong. Qua `ROSTER_LAN_SEC` ma van lech -> doc theo ban sao cham nhat nhu cu.

SUA O DIEU PHOI, khong them cua kiem nao ben acc (user chot).
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


class _C:
    def __init__(self, n):
        self.party_members = tuple(range(n))


def _song(*so):
    return [("u%d" % i, _C(n)) for i, n in enumerate(so)]


class _Nen(unittest.TestCase):
    def setUp(self):
        self.st = {"lock": threading.RLock()}
        self._t = R.time.time
        self.gio = 5000.0
        R.time.time = lambda: self.gio

    def tearDown(self):
        R.time.time = self._t


class TestDangLan(_Nen):
    def test_ca_p17_co_acc_da_thay_du(self):
        """(4,3,4,2,1) - hai acc da thay du 4 -> doi DA du tren server, goi dang lan."""
        self.assertTrue(R._roster_dang_lan(self.st, _song(4, 3, 4, 2, 1)))

    def test_moi_nguoi_deu_thay_du_thi_KHONG_phai_dang_lan(self):
        self.assertFalse(R._roster_dang_lan(self.st, _song(4, 4, 4, 4, 4)))

    def test_KHONG_AI_thay_du_la_doi_hong_that(self):
        """Ca p1 07/09: (4,0,0,0,0) voi party 5 acc -> can=4, max=4 ... xem test duoi."""
        self.assertFalse(R._roster_dang_lan(self.st, _song(3, 0, 0, 0, 0)),
                         "khong acc nao thay du ma van bao 'dang lan' -> nuot lenh gom that")

    def test_doi_tan_sach_thi_KHONG_phai_dang_lan(self):
        self.assertFalse(R._roster_dang_lan(self.st, _song(0, 0, 0, 0, 0)))


class TestCoHanKhongChoMai(_Nen):
    def test_lech_qua_han_thi_thoi_cho(self):
        """Party 1, 07/09: (4,0,0,0,0) DUNG IM 44 phut - phai ket luan hong, khong cho mai."""
        s = _song(4, 0, 0, 0, 0)
        self.assertTrue(R._roster_dang_lan(self.st, s), "vai giay dau van cho la dung")
        self.gio += R.ROSTER_LAN_SEC + 1
        self.assertFalse(R._roster_dang_lan(self.st, s),
                         "cho qua han van bao 'dang lan' -> party hong khong ai gom")

    def test_nhat_tri_roi_thi_QUEN_moc(self):
        """Lan lech sau phai tinh gio lai tu dau."""
        R._roster_dang_lan(self.st, _song(4, 1, 4, 4, 4))
        self.gio += 20
        R._roster_dang_lan(self.st, _song(4, 4, 4, 4, 4))       # nhat tri
        self.assertNotIn("roster_lech_tu", self.st)
        self.gio += 1
        self.assertTrue(R._roster_dang_lan(self.st, _song(4, 1, 4, 4, 4)),
                        "an theo moc cua lan lech truoc -> het han oan")


class TestGanVaoDuongRA_LENH(unittest.TestCase):
    """Cua nay phai dung TRUOC cho bump reform - bump la thu pha doi."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        i = self.src.find("def _engine_chot_kenh(")
        self.assertGreater(i, 0)
        self.than = self.src[i:self.src.find("\ndef ", i + 10)]

    def test_co_cua_chan(self):
        self.assertIn("_roster_dang_lan(st, song)", self.than,
                      "dieu phoi van ket luan 'doi hong' khi goi roster dang lan")

    def test_cua_dat_TRUOC_bump(self):
        _cua = self.than.find("_roster_dang_lan(st, song)")
        _bump = self.than.find("_bump_reform(st, \"chung kenh roi ma doi khong du")
        self.assertGreater(_bump, 0, "mat cho bump")
        self.assertLess(_cua, _bump, "cua chan dat SAU bump -> vo nghia")

    def test_khong_dong_vao_acc(self):
        """User chot: sua o dieu phoi, khong them cua kiem ben acc."""
        i = self.src.find("def _engine_chot_kenh(")
        body = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("_roster_dang_lan(st, song)", body)
        with open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            engine_src = fh.read()
        self.assertFalse("_roster_dang_lan(" in engine_src,
                         "worker tu doc roster dang lan thay vi engine chot")


if __name__ == "__main__":
    unittest.main()
