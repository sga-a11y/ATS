"""THU TU CUNG: GOM MAP -> GOM KENH -> MOI PARTY. Khong duoc nhay bac.

User chot (08/09, nhac lai 11/09): "gom lai thi cai dau tien phai check la co cung map hay ko" ->
"lech map thi phai dong bo map truoc chu, sao lai di dong bo kenh".

BAC BI THIEU: cung map roi ma CON LECH KENH thi truoc day roi thang xuong `VIEC_MOI`. Hai lenh da
nhau - moi party thi phai O TRONG DOI, con doi kenh thi phai ROI DOI - va moi nguoi khac kenh la vo
ich vi server khong chuyen loi moi qua kenh.

CA THAT (party 7, 11/09):

    18:01:43 [party 7] gen 7: viec=moi - cung map/kenh nhung DOI chua du (tat ca = 0)
    18:01:43 [party 7] DIEU PHOI: party lech kenh {1: 3, 2: 2} -> CHOT kenh dich = 1
    18:01:45 [party 7] DIEU PHOI: party lech kenh {1: 3, 2: 2} -> CHOT kenh dich = 8
    18:01:53 [party 7] gen 10: viec=gom - party dang o 2 MAP khac nhau [12001, 12061]

Cau ly do "cung map/kenh" con noi doi: kenh dang lech {1: 3, 2: 2}.

KHONG doi `lech_lau` o bac kenh: an han do sinh ra de tranh ra lenh GOM (keo ca party ve thanh)
oan khi acc dang teleport. Con dong bo kenh TAI CHO thi khong ton gi, ma de lech thi viec dang lam
(moi party) khong bao gio xong.
"""
from __future__ import annotations

from tests.party_controller_helpers import quyet_party

import io
import os
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot import config


class _C:
    """Client gia - dieu phoi CHI duoc doc nhung truong nay."""

    def __init__(self, map_id, channel, roster=0, running=True):
        self.current_map = map_id
        self.current_channel = channel
        self.running = running
        self.party_members = [b"x" * 8] * roster

    def digioi_minutes_live(self):
        return 0.0

    def kenh_dang_chac(self):
        return True


class _Nen(unittest.TestCase):
    PARTY = 3
    ACCS = ("b1", "b2", "b3")

    def setUp(self):
        self._accounts = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "b1", u == "b1") for u in self.ACCS]
        self._clients = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self._pcfg = dict(getattr(config, "PARTY_CONFIG", {}))
        config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}

    def tearDown(self):
        R.party_accounts = self._accounts
        R.account_clients.clear()
        R.account_clients.update(self._clients)
        R._party_state.pop(self.PARTY, None)
        config.PARTY_CONFIG = self._pcfg

    def _quyet(self, clients, lech_tu=None):
        for u, c in clients.items():
            R.account_clients[u] = c
        st = R._pstate(self.PARTY)
        kh, ly_do, _ = quyet_party(R, self.PARTY, st, R._acc_song(self.PARTY), lech_tu)
        return kh, ly_do


class TestBacKenhTruocKhiMoi(_Nen):
    def test_cung_map_LECH_KENH_thi_DONG_BO_chu_khong_MOI(self):
        """Dung ca party 7: cung map 12001, kenh {1,2}, doi rong."""
        kh, ly_do = self._quyet({"b1": _C(12001, 1), "b2": _C(12001, 2), "b3": _C(12001, 1)})
        self.assertEqual(kh["viec"], R.VIEC_DONG_BO, ly_do)
        self.assertIn("LECH KENH", ly_do)

    def test_cung_map_CUNG_KENH_thieu_doi_thi_MOI(self):
        kh, ly_do = self._quyet({"b1": _C(12001, 1), "b2": _C(12001, 1), "b3": _C(12001, 1)})
        self.assertEqual(kh["viec"], R.VIEC_MOI, ly_do)

    def test_KHONG_doi_lech_lau_o_bac_kenh(self):
        """Lech kenh chan dung viec dang lam -> xu ngay, khong cho het an han."""
        kh, _ = self._quyet({"b1": _C(12001, 1), "b2": _C(12001, 2), "b3": _C(12001, 1)},
                            lech_tu=None)
        self.assertEqual(kh["viec"], R.VIEC_DONG_BO)

    def test_DU_DOI_thi_khong_dong_bo_kenh_nua(self):
        """Du doi = da cung instance (server cam o chung doi ma khac phan khu) -> so kenh nho co
        the sai, khong duoc lay no ra pha party dang lanh."""
        kh, ly_do = self._quyet({"b1": _C(12001, 1, roster=2), "b2": _C(12001, 2, roster=2),
                                 "b3": _C(12001, 1, roster=2)})
        self.assertNotEqual(kh["viec"], R.VIEC_DONG_BO, ly_do)


class TestBacMapTruocBacKenh(_Nen):
    def test_lech_map_thi_CHUA_den_luot_kenh(self):
        """Lech ca map lan kenh -> phai lo map truoc."""
        kh, ly_do = self._quyet({"b1": _C(12001, 1), "b2": _C(12061, 2), "b3": _C(12001, 1)})
        self.assertNotEqual(kh["viec"], R.VIEC_DONG_BO, ly_do)

    def test_chot_kenh_KHONG_chay_khi_dang_gom_map(self):
        """`_engine_chot_kenh` phai nghe ket luan cua dieu phoi trong CUNG nhip."""
        for u, c in {"b1": _C(12001, 1), "b2": _C(12061, 2), "b3": _C(12001, 1)}.items():
            R.account_clients[u] = c
        st = R._pstate(self.PARTY)
        st["kenh_dich"] = 9
        _dich = R._engine_chot_kenh(self.PARTY, st, R._acc_song(self.PARTY),
                                       {"viec": R.VIEC_GOM, "map": 12001})
        self.assertEqual(_dich, 9, "dang gom map ma van di chot kenh moi")


class TestThuTuTrongMa(unittest.TestCase):
    """Neo thu tu ngay trong chuoi `if/elif` - doi cho la doi luat."""

    def setUp(self):
        # LUAT cap party da chuyen vao `bot/party_engine.py` (21/09), phan thi hanh van o
        # `run_party_digioi.py` -> doc CA HAI, luat truoc.
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src += fh.read()

    def test_bac_map_dung_truoc_bac_kenh_truoc_bac_moi(self):
        i_map = self.src.find("elif len(maps) > 1:")
        i_kenh = self.src.find("elif len(kenhs) > 1 and not anh.du_doi:")
        i_moi = self.src.find("elif not anh.du_doi:")
        self.assertGreater(i_map, 0, "mat bac gom map")
        self.assertGreater(i_kenh, 0, "mat bac gom kenh truoc khi moi")
        self.assertGreater(i_moi, 0, "mat bac moi party")
        self.assertLess(i_map, i_kenh, "bac map phai dung TRUOC bac kenh")
        self.assertLess(i_kenh, i_moi, "bac kenh phai dung TRUOC bac moi party")


if __name__ == "__main__":
    unittest.main()
