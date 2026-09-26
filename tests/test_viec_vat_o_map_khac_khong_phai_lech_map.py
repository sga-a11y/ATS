"""ACC DANG LAM VIEC VAT o map khac KHONG PHAI la "party lech map".

User 14/09: "lam viec vat thi van o map khac dc ma, nhu danh boss, cat tien trang, ban noi dat".

Viec vat BAT BUOC di map khac:
    ban Noi Dat        -> Nghiep Thanh (12061)
    cat tien trang     -> map kho
    boss the gioi      -> instance rieng
Dem nhung acc do vao `maps` thi party LUC NAO cung "lech map" -> lenh gom lien tuc -> bump reform
-> pha doi dang lanh, trong khi thu duy nhat can lam la DOI no xong viec.

CA THAT party 13, 14/09 (`*` = dang lam viec vat):
    17:30:52 [party 13] TRANG THAI: tonba@21001/k1(L) tonbay@12263/k1 tontam@21001/k1
                                    tonchin@12001/k2* tonmuoi@12001/k2*
    17:31:51 [tonchin] Teleport -> city 12061 (flag 2)       (di ban Noi Dat)
    17:31:51 [tonmuoi] Teleport -> city 12061 (flag 2)
    17:31:52 [tonba] (LEADER) dieu phoi bao GOM (party dang o 2 MAP khac nhau [12061, 21001])
    ... lap lai, ba acc kia da o Tuong Duong tu lau ...

KHONG PHAI "CHO": lenh van chay binh thuong tren so acc con lai (gom map / dong bo kenh / moi
party). Acc dang viec vat GIU loi moi lai, xong viec thi nhan (`account_task.__exit__`).
Cho la cai da lam ca party ket o thanh sang nay (204 lan) - khong lam lai.
"""
from __future__ import annotations

from tests.party_controller_helpers import quyet_party

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
    def __init__(self, map_id, ch=1):
        self.current_map = map_id
        self.current_channel = ch
        self.running = True
        self.party_members = []

    def kenh_dang_chac(self):
        return True


class _Nen(unittest.TestCase):
    PARTY = 70

    def setUp(self):
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self.st["n_members"] = 4
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "train", "start_city_id": 21833}}
        self._gt = R.get_account_task
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [("u%d" % i, "p", i == 0, i == 0) for i in range(5)]

    def tearDown(self):
        R.get_account_task = self._gt
        R.party_accounts = self._pa
        R.config.PARTY_CONFIG = self._pc
        R._party_state.pop(self.PARTY, None)

    def _dat_viec_vat(self, *accs):
        _bo = set(accs)
        R.get_account_task = lambda u: ({"phase": "login_chore"} if u in _bo else {"phase": "train"})


class TestKhongTinhLechMap(_Nen):
    def test_ca_that_p13_hai_acc_di_ban_noi_dat(self):
        """3 acc o Tuong Duong, 2 acc dang ban Noi Dat o Nghiep Thanh -> KHONG phai lech map."""
        self._dat_viec_vat("u3", "u4")
        song = [("u0", _C(21001)), ("u1", _C(21001)), ("u2", _C(21001)),
                ("u3", _C(12061)), ("u4", _C(12061))]
        kh, ly_do, _lt = quyet_party(R, self.PARTY, self.st, song, None)
        self.assertNotEqual(kh["viec"], R.VIEC_GOM,
                            "van ra lenh gom vi acc di lam viec vat: %s" % ly_do)

    def test_lech_map_that_thi_VAN_NHAN_RA(self):
        """Bo acc viec vat khong duoc lam mat kha nang bat lech map that.

        (Lan quyet DAU chi ghi nhan "con lech map"; phai lech LIEN TUC qua han moi ra lenh gom -
        de khong gom oan luc ca party dang di duong. Day chi kiem no NHAN RA.)
        """
        self._dat_viec_vat()          # khong ai lam viec vat
        song = [("u0", _C(21001)), ("u1", _C(21001)), ("u2", _C(21001)),
                ("u3", _C(12061)), ("u4", _C(12061))]
        _lt = None
        for _ in range(2):
            kh, ly_do, _lt = quyet_party(R, self.PARTY, self.st, song, _lt)
        self.assertIn("lech map", ly_do.lower(), ly_do)

    def test_viec_vat_thi_KHONG_nhac_lech_map(self):
        """Nguoc lai: acc viec vat thi ly do khong duoc nhac toi lech map."""
        self._dat_viec_vat("u3", "u4")
        song = [("u0", _C(21001)), ("u1", _C(21001)), ("u2", _C(21001)),
                ("u3", _C(12061)), ("u4", _C(12061))]
        _lt = None
        for _ in range(2):
            kh, ly_do, _lt = quyet_party(R, self.PARTY, self.st, song, _lt)
        self.assertNotIn("MAP khac nhau", ly_do, ly_do)

    def test_khong_tinh_ca_LECH_KENH(self):
        """Cung ly do: no dang o map khac nen so kenh khong so duoc."""
        self._dat_viec_vat("u4")
        song = [("u0", _C(21001, 2)), ("u1", _C(21001, 2)), ("u2", _C(21001, 2)),
                ("u3", _C(21001, 2)), ("u4", _C(12061, 9))]
        kh, ly_do, _lt = quyet_party(R, self.PARTY, self.st, song, None)
        self.assertNotEqual(kh["viec"], R.VIEC_DONG_BO,
                            "dem kenh cua acc dang o map khac: %s" % ly_do)


class TestNeoTrenNguon(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _chup_anh_cap_party(")
        self.than = src[i:src.find("\ndef ", i + 10)]

    def test_loai_acc_viec_vat_khoi_maps(self):
        self.assertIn("_ban_viec_vat = set(_ai_dang_lam_viec_le(song))", self.than)
        i = self.than.find("maps, _chua_biet_map = {}, []")
        self.assertGreater(i, 0)
        self.assertIn("if u in _ban_viec_vat:", self.than[i:i + 400])

    def test_loai_ca_khoi_kenhs(self):
        i = self.than.find("kenhs, _kenh_mo_ho = set(), []")
        self.assertGreater(i, 0)
        self.assertIn("if _u in _ban_viec_vat:", self.than[i:i + 400])

    def test_KHONG_bien_thanh_vong_CHO(self):
        """Cho la cai da lam ca party ket o thanh (204 lan) - khong duoc lam lai."""
        self.assertNotIn("dang lam viec LE hop le -> CHO", self.than)


if __name__ == "__main__":
    unittest.main()
