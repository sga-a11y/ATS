"""`_PARTY_JOINED` chi duoc LEADER ghi - roster cua member khong duoc ghi de.

Su co party 15 (27/08 08:48-09:00, ket 13 phut): 08:48:18 member bao "da vao party" ma 08:48:35
leader van dem THIEU roi giai tan; sau do leader gui 446 luot moi, 3/4 member khong nhan duoc
goi moi nao nua.

`0x0d sub06` phat cho MOI client trong party, ma ca 5 acc dung CHUNG mot dict global -> truoc day
ai nhan roster sau cung thi ghi de sach. Mot member nhan roster tam thoi 1 nguoi (dung luc leader
vua giai tan) la xoa sach so dem leader vua dung dung.
"""
from __future__ import annotations

import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as C  # noqa: E402

PIDX = 9901
LEADER = b"L" * 8
M1, M2, M3 = b"1" * 8, b"2" * 8, b"3" * 8


class TestChiLeaderGhi(unittest.TestCase):
    def setUp(self):
        C.reset_party_joined(PIDX)

    tearDown = setUp

    def _leader_ghi(self, members):
        C._sync_party_joined(PIDX, LEADER, [LEADER] + list(members),
                             nguoi_ghi=LEADER, label="leader")

    def _member_ghi(self, nguoi, members):
        C._sync_party_joined(PIDX, LEADER, [LEADER] + list(members),
                             nguoi_ghi=nguoi, label="member")

    def test_leader_ghi_thi_an(self):
        self._leader_ghi([M1, M2, M3])
        self.assertEqual(C.joined_member_count(PIDX), 3)

    def test_leader_KHONG_tinh_la_member(self):
        self._leader_ghi([M1])
        self.assertEqual(C.joined_member_count(PIDX), 1)
        self.assertFalse(C.is_joined(PIDX, LEADER))

    def test_member_KHONG_duoc_ghi_de_so_cua_leader(self):
        """Day la lo hong lam party 15 ket: member thay roster 0 nguoi -> xoa sach."""
        self._leader_ghi([M1, M2, M3])
        self._member_ghi(M1, [])                 # roster tam thoi chi con leader
        self.assertEqual(C.joined_member_count(PIDX), 3,
                         "roster cua member ghi de -> leader dem thieu -> giai tan -> quay vong")

    def test_member_cung_khong_duoc_THEM(self):
        """Ghi de theo chieu nao cung sai: dem thua thi leader tuong du roi danh mot minh."""
        self._leader_ghi([M1])
        self._member_ghi(M1, [M1, M2, M3])
        self.assertEqual(C.joined_member_count(PIDX), 1)

    def test_leader_van_HA_duoc_so_dem(self):
        """Phai la GHI DE that su, khong phai hop nhat - member roi party thi so phai giam."""
        self._leader_ghi([M1, M2, M3])
        self._leader_ghi([M1])
        self.assertEqual(C.joined_member_count(PIDX), 1)

    def test_khong_co_leader_thi_member_duoc_ghi(self):
        """Leader dang relogin / party do NGUOI THAT lam chu -> khong khoa vinh vien."""
        self._member_ghi(M1, [M1, M2])
        self.assertEqual(C.joined_member_count(PIDX), 2)

    def test_quyen_ghi_cua_leader_HET_HAN(self):
        self._leader_ghi([M1, M2, M3])
        src = C._PARTY_JOINED_SRC[PIDX]
        C._PARTY_JOINED_SRC[PIDX] = (src[0], src[1],
                                     time.time() - C.PARTY_JOINED_LEADER_UU_TIEN - 1)
        self._member_ghi(M1, [M1])
        self.assertEqual(C.joined_member_count(PIDX), 1, "leader chet ma member van bi khoa mai")

    def test_giai_tan_thi_xoa_ca_quyen_ghi(self):
        """Giai tan xong, roster CU cua member khong duoc coi la nguon nua."""
        self._leader_ghi([M1, M2, M3])
        C.reset_party_joined(PIDX)
        self.assertNotIn(PIDX, C._PARTY_JOINED_SRC)
        self._member_ghi(M1, [M1])
        self.assertEqual(C.joined_member_count(PIDX), 1)


class TestLogChanDoan(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_log_khi_so_dem_DOI(self):
        self.assertIn("PARTY-JOINED: %d -> %d", self.src)

    def test_log_khi_BO_QUA_roster_member(self):
        self.assertIn("PARTY-JOINED: BO QUA roster cua member", self.src)

    def test_vong_moi_in_ca_so_dem_va_roster(self):
        """446 luot moi ma log cu khong he in leader dang dem duoc may nguoi."""
        i = self.src.find("moi %d member theo entity")
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 500]
        self.assertIn("da join=%d", khoi)
        self.assertIn("roster server=%d", khoi)


if __name__ == "__main__":
    unittest.main()
