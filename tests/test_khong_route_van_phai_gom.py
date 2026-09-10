"""KHONG CO ROUTE VAN PHAI GOM (L0) - khong duoc "bo qua".

Route la duong DI BO toi bai train. Gom ca party ve cung mot THANH thi khong can duong nao ca,
chi can teleport. Tra ve ngay = lenh gom cua dieu phoi KHONG BAO GIO duoc thi hanh, con vong goi
thi lap lai mai.

Ca that 08/09 party 1 (user: "p1, van deo them ve cung kenh") - vong 18 giay, leader xGAx dung MOT
MINH o Trac Quan 12001 trong khi bon member o Truong Sa 23001:

    00:53:58 [xGAx] (LEADER) MODE=train start_city=0
    00:54:22 [xGAx] (LEADER) reform: khong co smart/legacy route -> bo qua
    00:54:24 [xGAx] (LEADER) party dang o 2 MAP KHAC NHAU [12001, 23001] -> se gom ve cung map/kenh
    00:54:40 [xGAx] (LEADER) reform: khong co smart/legacy route -> bo qua
    00:54:42 [xGAx] (LEADER) party dang o 2 MAP KHAC NHAU [12001, 23001] -> se gom ve cung map/kenh

`start_city=0` nen khong co thanh dich, khong co route - the la no NHAN RA phai gom roi TU CHOI
gom. Cung bug nay da duoc sua RIENG cho thap 2K (`_thi_hanh_gom`) tu 06/09; ngoai thap van con.

Diem gom = THANH DANG CO NHIEU ACC NHAT: it phai di chuyen nhat, va thuong da so party da tu ve
day roi (o ca that la 4/5 acc). Doc thang `account_clients` - khong acc nao bao cao.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _C:
    def __init__(self, m, running=True):
        self.current_map = m
        self.running = running


class TestThanhDongAccNhat(unittest.TestCase):
    ACCS = ("a", "b", "c", "d", "e")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)

    def _dat(self, maps):
        for u, m in zip(self.ACCS, maps):
            R.account_clients[u] = _C(m)

    def test_lay_thanh_dong_nhat(self):
        """Ca that: 4 acc o Truong Sa 23001, leader o Trac Quan 12001 -> gom ve 23001."""
        self._dat([12001, 23001, 23001, 23001, 23001])
        self.assertEqual(R._thanh_dong_acc_nhat(0), 23001)

    def test_bo_qua_acc_KHONG_o_thanh(self):
        """Acc o bai train / pho ban khong phai diem gom duoc."""
        self._dat([12001, 12001, 21836, 21836, 21836])
        self.assertEqual(R._thanh_dong_acc_nhat(0), 12001)

    def test_khong_ai_o_thanh_thi_None(self):
        self._dat([21836, 21836, 21836, 21836, 21836])
        self.assertIsNone(R._thanh_dong_acc_nhat(0))

    def test_bo_qua_acc_da_ROT(self):
        self._dat([23001, 23001, 12001, 12001, 12001])
        for u in ("c", "d", "e"):
            R.account_clients[u].running = False
        self.assertEqual(R._thanh_dong_acc_nhat(0), 23001)

    def test_HOA_thi_moi_acc_tinh_ra_CUNG_mot_thanh(self):
        """Hai thanh cung 2 acc - phai deterministic, khong thi party toe ra hai huong."""
        self._dat([23001, 23001, 12001, 12001, 21836])
        self.assertEqual(R._thanh_dong_acc_nhat(0), 12001)   # hoa -> so nho

    def test_map_0_khong_tinh(self):
        """Acc chua nhan `0x03` co `current_map = 0`."""
        self._dat([0, 0, 23001, 21836, 21836])
        self.assertEqual(R._thanh_dong_acc_nhat(0), 23001)


class TestNhanhKhongRoute(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.s = fh.read()

    def test_KHONG_con_bo_qua(self):
        i = self.s.find("reform: khong co smart/legacy route -> VAN GOM")
        self.assertGreater(i, 0, "nhanh khong-route van 'bo qua' -> lenh gom khong duoc thi hanh")

    def test_co_thanh_dich_that(self):
        """`{'missing': True}` = ke hoach rong; phai co `city` de con teleport ve."""
        i = self.s.find("reform: khong co smart/legacy route -> VAN GOM")
        khoi = self.s[i - 1400:i + 400]
        self.assertIn('"city": int(_tg)', khoi)

    def test_uu_tien_thanh_dong_acc_roi_moi_gather_city(self):
        i = self.s.find("_thanh_dong_acc_nhat(pidx) or _gather_city(")
        self.assertGreater(i, 0, "phai co ca duong lui khi khong ai dang o thanh")

    def test_khong_con_cho_nao_dat_missing(self):
        """Con cho nao set `missing` la con duong quay lai hanh vi cu."""
        self.assertNotIn('"missing": True', self.s)


if __name__ == "__main__":
    unittest.main()
