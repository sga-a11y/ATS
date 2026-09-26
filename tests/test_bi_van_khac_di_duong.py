""""BI VAN khoi train map" KHAC "ca party dang DI DUONG toi bai".

User 13/09: "dang di ra bai train ma sao cu co log dieu phoi ra lenh gom the" (party 4).

CA THAT:

    14:27:26 [tmo] da toi diem (20,460) sau 12 lenh move (xac nhan (20, 460))
    14:27:26 [tmo] _enter_gate idx=8 @(20,460): lan thu 1 (t=0s, map van 21003)
    14:27:27 [tha] (member) BI VAN khoi train map (dang o 21003, vd chet) -> de DIEU PHOI ra lenh gom
    14:27:27 [bat] (member) BI VAN khoi train map (dang o 21003, vd chet) -> de DIEU PHOI ra lenh gom
    14:27:28 [lin] (member) BI VAN khoi train map (dang o 21003, vd chet) -> de DIEU PHOI ra lenh gom
    14:27:31 [bub] (member) BI VAN khoi train map (dang o 21003, vd chet) -> de DIEU PHOI ra lenh gom

Ca nam deu o 21003, dung sau leader cho no mo cong ra bai. KHONG AI van ca.

Dieu kien cu chi hoi "MINH co o bai train khong" - ma luc ca party dang tren duong toi bai thi
KHONG AI o bai, nen dua nao cung tu ket luan minh bi van. Dong log do con nhac toi "lenh gom" nen
doc log tuong dieu phoi dang gom lien tuc (no chi la ACC bao trang thai, xem
`test_lenh_gom_khong_bi_nuot_boi_cooldown.py`).

"Bi van" dung nghia = MINH roi ra TRONG KHI party van dang o bai. Bot thay map cua ca party nen
tu phan biet duoc, khong can ai bao cao.
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

BAI_TRAIN = 21872
TREN_DUONG = 21003


class _C:
    def __init__(self, map_id, running=True):
        self.current_map = map_id
        self.running = running


class _Nen(unittest.TestCase):
    PARTY = 3
    ACCS = ("a1", "a2", "a3", "a4", "a5")

    def setUp(self):
        self._accounts = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "a1", u == "a1") for u in self.ACCS]
        self._clients = dict(R.account_clients)
        R.account_clients.clear()

    def tearDown(self):
        R.party_accounts = self._accounts
        R.account_clients.clear()
        R.account_clients.update(self._clients)

    def _dat(self, maps):
        for u, m in zip(self.ACCS, maps):
            R.account_clients[u] = _C(m)


class TestDiDuongThiKHONG_phai_bi_van(_Nen):
    def test_ca_party_tren_duong_thi_khong_ai_o_bai(self):
        """Dung ca party 4: ca nam o 21003, cho leader mo cong."""
        self._dat([TREN_DUONG] * 5)
        for u in self.ACCS:
            self.assertFalse(R._co_ai_dang_o_map(self.PARTY, BAI_TRAIN, tru=u),
                             "%s tu coi minh bi van trong khi ca party dang di duong" % u)

    def test_leader_da_toi_bai_thi_member_con_lai_LA_bi_van(self):
        self._dat([BAI_TRAIN, TREN_DUONG, TREN_DUONG, TREN_DUONG, TREN_DUONG])
        self.assertTrue(R._co_ai_dang_o_map(self.PARTY, BAI_TRAIN, tru="a2"))

    def test_chinh_minh_o_bai_KHONG_tinh_la_nguoi_khac(self):
        """Khong tru minh ra thi acc dang o bai tu thay 'co nguoi o bai' -> vo nghia."""
        self._dat([BAI_TRAIN, TREN_DUONG, TREN_DUONG, TREN_DUONG, TREN_DUONG])
        self.assertFalse(R._co_ai_dang_o_map(self.PARTY, BAI_TRAIN, tru="a1"))

    def test_acc_da_TAT_khong_tinh(self):
        self._dat([TREN_DUONG] * 5)
        R.account_clients["a1"] = _C(BAI_TRAIN, running=False)
        self.assertFalse(R._co_ai_dang_o_map(self.PARTY, BAI_TRAIN, tru="a2"))

    def test_map_rong_thi_tra_False(self):
        self._dat([BAI_TRAIN] * 5)
        self.assertFalse(R._co_ai_dang_o_map(self.PARTY, None, tru="a1"))
        self.assertFalse(R._co_ai_dang_o_map(self.PARTY, 0, tru="a1"))




if __name__ == "__main__":
    unittest.main()
