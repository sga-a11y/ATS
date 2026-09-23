# -*- coding: utf-8 -*-
"""AI DA VAO PARTY: HOI SERVER, KHONG TU NHO.

`S:013-006 <隊伍資料> <<+隊長玩家ID(8) +隊員數量(1) <<+玩家ID(8)>>>>` - SERVER gui thang doi truong,
SO LUONG member va danh sach ID. `_on_party` nap vao `client.party_members`, va chinh comment o do
viet "ROSTER SERVER LA SU THAT". Khong co gi phai dem theo tri nho.

Ban cu giu so rieng `_PARTY_JOINED`, bom tu `mark_joined` (3 cho) / `unmark_joined` (5 cho), roi
lai bi roster ghi de. Vi ca 5 acc deu nhan `0x0d sub06` va cung ghi vao MOT dict chung, chung ghi
de lan nhau (party 15, 27/08) - nen phai dung them `_PARTY_JOINED_SRC` + luat "chi leader duoc ghi
trong 30 giay" de phan xu. Ca mot bo may trong tai cho mot con so server da dua san.

VA NO DE RA BUG THAT: nhanh "PARTY MA" chay cho MOI acc, nen voi LEADER thi "doi truong dang ket"
luon la NO -> no `mark_joined` CHINH MINH -> so len 5; con `_sync_party_joined` CO TINH loai leader
ra ("Leader KHONG tinh la member") -> gat ve 4. Lap vo tan, so dem chap chon nen "du doi" khi dung
khi sai, engine giao lai `lap_party` mai.

Ca that 23/09 party 25 (user: "party Di gioi du nguoi roi nhung leader ko chay long vong"):
    06:03:45..06:05:04 [daisau] PARTY-JOINED: 5 -> 4 (nguoi ghi=c2b317e6, LEADER)
                       | ['d7b317e6','dfb317e6','f2b317e6','fbb317e6']    <- lap moi 2-5 giay
    05:58:56 [party 25] ENGINE: 'lap_party' giao lai 20 lan lien tiep cho daim09
    TRANG THAI: roster leader=0/4 -> 2/4 -> 1/4, khong bao gio dung yen o 4/4
Leader ket o buoc lap party, khong bao gio sang duoc buoc chay long vong. Party 1 (22/09, `nanam`)
cung dong lap nay.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


class _C:
    def __init__(self, user, members=(), leader=None):
        self._username = user
        self._label = user
        self.party_members = list(members)
        self.party_leader = leader
        self.running = True
        self.self_entity = b"me" + user.encode()[:6]


class _Nen(unittest.TestCase):
    PIDX = 7
    LEADER = "lead01"

    def setUp(self):
        self._cli = dict(C._PARTY_CLIENTS)
        C._PARTY_CLIENTS.clear()
        self._p = mock.patch.object(C.config, "PARTY_LEADER_ACC", {self.PIDX: self.LEADER},
                                    create=True)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        C._PARTY_CLIENTS.clear()
        C._PARTY_CLIENTS.update(self._cli)

    def _dat(self, members):
        c = _C(self.LEADER, members)
        C._PARTY_CLIENTS[self.PIDX] = {c.self_entity: c}
        return c


class TestDemTheoRosterServer(_Nen):
    def test_dem_dung_so_member_roster(self):
        self._dat([b"m1", b"m2", b"m3", b"m4"])
        self.assertEqual(C.joined_member_count(self.PIDX), 4)

    def test_KHONG_tinh_leader_la_member(self):
        """`party_members` cua `S:013-006` khong gom doi truong - do la ca goc cua bug 23/09."""
        c = self._dat([b"m1", b"m2"])
        self.assertNotIn(c.self_entity, C._roster_server(self.PIDX))
        self.assertEqual(C.joined_member_count(self.PIDX), 2)

    def test_is_joined_theo_roster(self):
        self._dat([b"m1", b"m2"])
        self.assertTrue(C.is_joined(self.PIDX, b"m1"))
        self.assertFalse(C.is_joined(self.PIDX, b"mX"))

    def test_leader_chua_login_thi_0_chu_khong_no(self):
        self.assertEqual(C.joined_member_count(self.PIDX), 0)
        self.assertFalse(C.is_joined(self.PIDX, b"m1"))

    def test_roster_rong_thi_0(self):
        """Leader vua `leave_party()` -> server giai tan -> roster rong. Khong can ai 'quen' ho."""
        self._dat([])
        self.assertEqual(C.joined_member_count(self.PIDX), 0)

    def test_tim_leader_theo_USERNAME_khong_theo_entity(self):
        """Entity doi moi lan login - dung lam khoa la giu entity chet (xem `_PARTY_ENTITIES`)."""
        c = self._dat([b"m1"])
        C._PARTY_CLIENTS[self.PIDX] = {b"entity-cu-khac-han": c}   # entity cu, username van dung
        self.assertEqual(C.joined_member_count(self.PIDX), 1)


class TestSoNhoDaBIEN_MAT(_Nen):
    """Bo so nho thi cac ham ghi phai thanh VO HAI - khong con duong nao lam lech so dem."""

    def test_mark_joined_khong_lam_gi(self):
        self._dat([b"m1"])
        C.mark_joined(self.PIDX, b"THEM")
        self.assertEqual(C.joined_member_count(self.PIDX), 1, "van con duong tu bom so dem")

    def test_unmark_joined_khong_lam_gi(self):
        self._dat([b"m1", b"m2"])
        C.unmark_joined(self.PIDX, b"m1")
        self.assertEqual(C.joined_member_count(self.PIDX), 2, "van con duong tu tru so dem")

    def test_reset_party_joined_khong_lam_gi(self):
        self._dat([b"m1", b"m2"])
        C.reset_party_joined(self.PIDX)
        self.assertEqual(C.joined_member_count(self.PIDX), 2, "van con duong xoa so dem")

    def test_KHONG_con_bien_so_nho_nao(self):
        for _ten in ("_PARTY_JOINED", "_PARTY_JOINED_RO", "_PARTY_JOINED_SRC",
                     "_sync_party_joined", "_dong_bo_joined_ro"):
            self.assertFalse(hasattr(C, _ten), "con sot %s - mot nguon su that thu hai" % _ten)


class TestNhanhPartyMa(unittest.TestCase):
    """Nhanh "PARTY MA" van phai giu luat goc, chi bo cai `mark_joined`."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("_la_leader_minh = ")
        self.assertGreater(i, 0, "mat nhanh PARTY MA")
        self.khoi = s[i:i + 3000]

    def test_KHONG_con_mark_joined(self):
        i_elif = self.khoi.find("elif not _la_minh:")
        self.assertGreater(i_elif, 0)
        self.assertNotIn("mark_joined(", self.khoi[:i_elif],
                         "leader van tu danh dau chinh minh")

    def test_VAN_GIU_luat_khong_roi_party_cua_leader_minh(self):
        """Party 7, 31/08: ca 4 member tu da minh ra khoi doi vua vao -> vong vo tan."""
        self.assertIn("elif not _la_minh:", self.khoi,
                      "mat cua 'chi roi khi la party cua NGUOI KHAC'")
        i_roi = self.khoi.find("c.leave_party()")
        self.assertGreater(i_roi, self.khoi.find("elif not _la_minh:"),
                           "duong roi party khong con nam sau cua chan")


if __name__ == "__main__":
    unittest.main()
