"""PB VO -> dieu phoi KEO CA PARTY ra khoi instance, khong de leader tu lo mot minh.

PB XONG thi server gui `S:047-012 <副本結束>` cho tung client va moi acc tu roi (xem
tests/test_pho_ban_ket_thuc_tu_roi.py). Nhung PB VO thi KHONG co goi do - khong acc nao tu biet
duong ra.

Truoc day moi leader goi `_exit_pb_or_reconnect` cho CHINH NO. Ket qua (user 07/09):
"leader o ngoai con member van trong PB kia" - leader ve thanh, member con nguyen trong map 62xxx,
va `go_to_town` cua ho thi BAIL vi dang trong pho ban to doi:

    10:40:39 [luubhai] go_to_town: DANG TRONG pho ban to doi (map=62012) -> khong teleport
    10:40:39 [luubhai] (member) reform: CHUA ve duoc Hội Kê (map=62012) -> nghi 10s thu lai

Ca party chay trong MOT tien trinh nen keo het ra la mot lenh - L2: khong ai phai cho ai bao cao,
va khong ai phai tu mo duong cho minh.
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


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class _C:
    def __init__(self, map_id, running=True, ok=True):
        self.current_map = map_id
        self.running = running
        self._ok = ok
        self.da_thoat = 0

    def leave_team_dungeon(self):
        self.da_thoat += 1
        return self._ok


class TestKeoCaParty(unittest.TestCase):
    PIDX = 3131
    ACCS = ("lead", "m1", "m2", "m3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)

    def test_moi_acc_TRONG_instance_deu_duoc_keo_ra(self):
        for u in self.ACCS:
            R.account_clients[u] = _C(62012)
        self.assertEqual(R._thoat_pb_ca_party(self.PIDX, "thu"), 4)
        for u in self.ACCS:
            self.assertEqual(R.account_clients[u].da_thoat, 1, u)

    def test_acc_da_o_NGOAI_thi_khong_gui_lenh_thua(self):
        R.account_clients["lead"] = _C(12001)     # da ve thanh
        R.account_clients["m1"] = _C(62012)
        R.account_clients["m2"] = _C(49942)       # Di Gioi - khong phai instance PB
        R.account_clients["m3"] = _C(62012)
        self.assertEqual(R._thoat_pb_ca_party(self.PIDX, "thu"), 2)
        self.assertEqual(R.account_clients["lead"].da_thoat, 0)
        self.assertEqual(R.account_clients["m2"].da_thoat, 0)

    def test_acc_dang_relogin_thi_bo_qua(self):
        R.account_clients["lead"] = _C(62012, running=False)
        R.account_clients["m1"] = _C(62012)
        self.assertEqual(R._thoat_pb_ca_party(self.PIDX, "thu"), 1)

    def test_mot_acc_LOI_khong_chan_cac_acc_con_lai(self):
        class _Hong(_C):
            def leave_team_dungeon(self):
                raise OSError("socket dong")
        R.account_clients["lead"] = _Hong(62012)
        R.account_clients["m1"] = _C(62012)
        R.account_clients["m2"] = _C(62012)
        self.assertEqual(R._thoat_pb_ca_party(self.PIDX, "thu"), 2)

    def test_client_thieu_thi_bo_qua(self):
        R.account_clients["m1"] = _C(62012)
        self.assertEqual(R._thoat_pb_ca_party(self.PIDX, "thu"), 1)


class TestGoiDuChoPhaiGoi(unittest.TestCase):
    def test_nhanh_leader_cho_report(self):
        s = _src()
        i = s.find("đồng đội rớt / PB vỡ khi chờ report")
        self.assertGreater(i, 0)
        self.assertIn("_thoat_pb_ca_party(", s[i:i + 900])

    def test_nhanh_lv50_80_110(self):
        s = _src()
        i = s.find('"phó bản đội vỡ" if active else "phó bản đội fail"')
        self.assertGreater(i, 0)
        self.assertIn("_thoat_pb_ca_party(", s[max(0, i - 700):i])

    def test_nhanh_lv20_chi_keo_khi_KHONG_ok(self):
        """PB lv20 xong binh thuong thi moi acc tu ra khi nhan `S:047-012` - gui them lenh thoat
        la thua, va co the cat mat man hinh phan thuong cua chinh no."""
        s = _src()
        i = s.find('_thoat_pb_ca_party(pidx, "PB lv20 vỡ")')
        self.assertGreater(i, 0)
        self.assertIn("if not ok:", s[max(0, i - 300):i])


if __name__ == "__main__":
    unittest.main()
