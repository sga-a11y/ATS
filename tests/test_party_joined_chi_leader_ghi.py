"""SO NGUOI DA VAO PARTY: doc ROSTER SERVER, khong con "chi leader duoc ghi so nho".

### File nay truoc day giu luat gi, va vi sao luat do bien mat (23/09)

Ban cu giu mot so rieng `_PARTY_JOINED`. `0x0d sub06` phat cho MOI client trong party, ma ca 5 acc
dung CHUNG mot dict global -> ai nhan roster sau cung thi ghi de sach. Mot member nhan roster tam
thoi 1 nguoi (dung luc leader vua giai tan) la xoa sach so dem leader vua dung dung.

Su co party 15 (27/08 08:48-09:00, ket 13 phut): 08:48:18 member bao "da vao party" ma 08:48:35
leader van dem THIEU roi giai tan; sau do leader gui 446 luot moi, 3/4 member khong nhan duoc goi
moi nao nua.

Cach chua hoi do: `_sync_party_joined` + `_PARTY_JOINED_SRC` + `PARTY_JOINED_LEADER_UU_TIEN` -
mot bo may TRONG TAI xem ai duoc ghi so. Nhung `S:013-006 <隊伍資料>` da mang san **+隊員數量(1)** va
danh sach ID; `_on_party` nap thang vao `client.party_members` va chinh comment o do viet "ROSTER
SERVER LA SU THAT". Tuc ca bo may trong tai do dung de phan xu mot con so server dua san.

User chot 23/09: *"t tuong server luon tra ve so member trong pt cua minh, m phai tu dem theo tri
nho a"* -> bo so nho, doc thang roster cua leader. Khong con ai ghi thi khong can trong tai.

Va so nho da de ra mot bug that truoc khi bi bo: nhanh "PARTY MA" cho LEADER `mark_joined` CHINH
MINH (doi truong dang ket chinh la no), trong khi `_sync_party_joined` CO TINH loai leader ra
("Leader KHONG tinh la member") -> 5 -> 4 -> 5 -> ... Ca that 23/09 party 25 (user: "party Di gioi
du nguoi roi nhung leader ko chay long vong"):
    06:03:45..06:05:04 [daisau] PARTY-JOINED: 5 -> 4 (nguoi ghi=c2b317e6, LEADER)
    05:58:56 [party 25] ENGINE: 'lap_party' giao lai 20 lan lien tiep cho daim09

### Luat con lai, va chinh la luat file nay giu

Hai tinh chat cua ban cu PHAI duoc giu nguyen, vi chung sinh tu ca hong that:
  1. LEADER KHONG tinh la member (`party_members` cua `S:013-006` khong gom doi truong).
  2. Roster cua party KHAC khong duoc dinh vao so cua party minh.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as C  # noqa: E402

PIDX = 9901
LEADER_ACC = "lead9901"
M1, M2, M3 = b"1" * 8, b"2" * 8, b"3" * 8


class _C:
    def __init__(self, user, members=(), ent=b"L" * 8):
        self._username = user
        self._label = user
        self.party_members = list(members)
        self.party_leader = ent
        self.running = True
        self.self_entity = ent


class _Nen(unittest.TestCase):
    def setUp(self):
        self._cu = dict(C._PARTY_CLIENTS)
        C._PARTY_CLIENTS.clear()
        self._p = mock.patch.object(C.config, "PARTY_LEADER_ACC", {PIDX: LEADER_ACC}, create=True)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        C._PARTY_CLIENTS.clear()
        C._PARTY_CLIENTS.update(self._cu)

    def _leader(self, members):
        c = _C(LEADER_ACC, members)
        C._PARTY_CLIENTS[PIDX] = {c.self_entity: c}
        return c


class TestDocRosterServer(_Nen):
    def test_dem_dung_so_member(self):
        self._leader([M1, M2, M3])
        self.assertEqual(C.joined_member_count(PIDX), 3)

    def test_leader_KHONG_tinh_la_member(self):
        """Luat giu nguyen tu ban cu - va la ca goc cua bug party 25 (23/09)."""
        c = self._leader([M1, M2])
        self.assertNotIn(c.self_entity, C._roster_server(PIDX))
        self.assertEqual(C.joined_member_count(PIDX), 2)

    def test_roster_doi_la_so_doi_NGAY(self):
        """Khong co do tre cua so nho: doc thang nen nhip sau da dung."""
        c = self._leader([M1, M2])
        c.party_members = [M1]
        self.assertEqual(C.joined_member_count(PIDX), 1)

    def test_leader_giai_tan_thi_so_ve_0_ma_khong_ai_phai_XOA(self):
        """`reset_party_joined` tung ton tai chi de "quen" so nho. Server tu lo."""
        c = self._leader([M1, M2])
        c.party_members = []          # leave_party -> S:013-006 ke tiep rong
        self.assertEqual(C.joined_member_count(PIDX), 0)

    def test_party_KHAC_khong_dinh_vao_so_cua_minh(self):
        """`0x0d sub06` phat toan map. Nguon la client CUA LEADER PARTY NAY, tim theo username."""
        _khac = _C("leader-party-khac", [M1, M2, M3], ent=b"X" * 8)
        C._PARTY_CLIENTS[PIDX] = {_khac.self_entity: _khac}
        self.assertEqual(C.joined_member_count(PIDX), 0, "dem nham roster cua party khac")

    def test_leader_chua_login_thi_0(self):
        self.assertEqual(C.joined_member_count(PIDX), 0)


class TestKhongCanTRONG_TAI(_Nen):
    """Bo so nho thi moi duong ghi phai vo hai - khong con gi de phan xu."""

    def test_mark_joined_vo_hai(self):
        self._leader([M1])
        C.mark_joined(PIDX, M2)
        self.assertEqual(C.joined_member_count(PIDX), 1)

    def test_unmark_joined_vo_hai(self):
        self._leader([M1, M2])
        C.unmark_joined(PIDX, M1)
        self.assertEqual(C.joined_member_count(PIDX), 2)

    def test_reset_party_joined_vo_hai(self):
        self._leader([M1, M2])
        C.reset_party_joined(PIDX)
        self.assertEqual(C.joined_member_count(PIDX), 2)

    def test_KHONG_con_bo_may_trong_tai(self):
        for _ten in ("_sync_party_joined", "_PARTY_JOINED_SRC", "PARTY_JOINED_LEADER_UU_TIEN",
                     "_PARTY_JOINED", "_PARTY_JOINED_RO"):
            self.assertFalse(hasattr(C, _ten), "con sot %s" % _ten)


if __name__ == "__main__":
    unittest.main()
