"""CHUA BIET MAP CUA MOT NGUOI = CHUA XONG BAC GOM MAP. Khong duoc tut xuong bac kenh.

User 13/09: "p4 p9 lai bi cai loi lech kenh ma deo gom kenh lai" -> "cai lon gi ma chua biet map,
phai biet cung map roi moi den doan dong bo kenh chu" -> "cai nay sua bao lan roi ma van de sai a".

Dung: chuoi map -> kenh -> moi da sua ba lan (them bac gom kenh 11/09; cua "dang gom map thi chua
den luot kenh" 12/09; lan nay 13/09). Ca ba lan deu chi va phan SO SANH GIUA CAC MAP, khong dung
toi goc: phep dem BO QUA acc chua biet map.

    maps = {}
    for u, c in song:
        m = getattr(c, "current_map", None)
        if m is not None:                     # <- acc map=None bi lo di
            maps.setdefault(int(m), []).append(u)
    lech = len(maps) > 1

4 dua cung map + 1 dua chua biet map -> `len(maps) == 1` -> "cung map" -> tut xuong bac kenh ->
`_engine_chot_kenh` moi phat hien thieu du lieu va `return None` IM LANG -> khong bao gio chot
duoc kenh dich -> khong mot lenh doi kenh nao duoc gui.

CA THAT (party 9; party 4 y het):

    14:46:38 [party 9] gen 8: pha=event map=12922 kenh=None viec=dong_bo
                       - cung map nhung LECH KENH [1, 2] -> gom kenh truoc khi moi
    14:47:41 / 14:48:42 / 14:49:39 / 14:50:46 / 14:51:48 / 14:52:48 / 14:53:48
                       van 'dong_bo' ... CHO them Ns

BAY PHUT, khong MOT dong `Chuyen kenh ->` nao cua ca nam acc. Trong thap 2K, acc bi keo sang scene
moi thi `current_map` rong mot luc ("request scene khong co self-spawn", "pos=None map=..."), du
de dinh cho nay.

Test cu (`test_thu_tu_map_roi_kenh_roi_moi.py`) chi neo THU TU ba nhanh nen van xanh.
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

from bot import config


class _C:
    def __init__(self, map_id, channel, roster=0):
        self.current_map = map_id
        self.current_channel = channel
        self.running = True
        self.party_members = [b"x" * 8] * roster

    def digioi_minutes_live(self):
        return 0.0

    def kenh_dang_chac(self):
        return True


class _Nen(unittest.TestCase):
    PARTY = 8      # party 9
    ACCS = ("lbo006", "lbo007", "lbo008", "lbo009", "lbo010")

    def setUp(self):
        self._accounts = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "lbo006", u == "lbo006") for u in self.ACCS]
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
        # `_dieu_phoi_quyet` chot `nguoi_keo` cho party nay - co do o cap MODULE (bot.client), phai
        # tra lai, khong thi test khac doc nham co cua minh.
        from bot import client as _C
        _C.dat_nguoi_keo(self.PARTY, None)
        _C.dat_party_dang_gom(self.PARTY, False)

    def _quyet(self, cs):
        for u, c in zip(self.ACCS, cs):
            R.account_clients[u] = c
        st = R._pstate(self.PARTY)
        kh, ly_do, _ = quyet_party(R, self.PARTY, st, R._acc_song(self.PARTY), None)
        return kh, ly_do


class TestChuaBietMapThiDungODoc(_Nen):
    def test_ca_that_party_9(self):
        """4 dua cung map 12922 (kenh 1/2 lech), 1 dua chua biet map."""
        cs = [_C(12922, 1), _C(12922, 1), _C(12922, 2), _C(12922, 1), _C(None, 1)]
        kh, ly_do = self._quyet(cs)
        self.assertEqual(kh["viec"], R.VIEC_LAM, ly_do)
        self.assertIn("chua doc duoc map", ly_do)
        self.assertIn("lbo010", ly_do, "phai chi ro dua nao chua biet map")

    def test_biet_du_map_roi_thi_MOI_den_luot_kenh(self):
        cs = [_C(12922, 1), _C(12922, 1), _C(12922, 2), _C(12922, 1), _C(12922, 1)]
        kh, ly_do = self._quyet(cs)
        self.assertEqual(kh["viec"], R.VIEC_DONG_BO, ly_do)
        self.assertIn("LECH KENH", ly_do)

    def test_biet_du_map_va_cung_kenh_thi_den_luot_MOI(self):
        cs = [_C(12922, 1) for _ in range(5)]
        kh, ly_do = self._quyet(cs)
        self.assertEqual(kh["viec"], R.VIEC_MOI, ly_do)

    def test_LECH_MAP_ro_rang_thi_van_GOM_truoc(self):
        """Chua biet map cua 1 dua, nhung nhung dua da biet thi LECH nhau -> gom map van uu tien."""
        cs = [_C(12922, 1), _C(12921, 1), _C(12922, 1), _C(12922, 1), _C(None, 1)]
        kh, ly_do = self._quyet(cs)
        self.assertNotEqual(kh["viec"], R.VIEC_DONG_BO, ly_do)


class TestChotKenhKhongCON_IM_LANG(unittest.TestCase):
    def setUp(self):
        # LUAT cap party da chuyen vao `bot/party_engine.py` (21/09), phan thi hanh van o
        # `run_party_digioi.py` -> doc CA HAI, luat truoc.
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src += fh.read()
        i = self.src.find("def _engine_chot_kenh(")
        self.assertGreater(i, 0)
        j = self.src.find("\ndef ", i + 10)
        self.than = self.src[i:j]

    def test_thieu_du_lieu_thi_NOI_RA(self):
        self.assertIn("chua chot duoc kenh dich", self.than,
                      "return None im lang -> khong the truy vi sao khong ai doi kenh")

    def test_lech_map_thi_NOI_RA(self):
        self.assertIn("chua chot kenh dich - con lech map", self.than)

    def test_co_chan_spam(self):
        self.assertIn("chot_kenh_thieu_log", self.than)


class TestGocLoi(unittest.TestCase):
    """Neo chinh cho da lot ba lan: phep dem map phai GIU LAI acc chua biet map."""

    def setUp(self):
        # LUAT cap party da chuyen vao `bot/party_engine.py` (21/09), phan thi hanh van o
        # `run_party_digioi.py` -> doc CA HAI, luat truoc.
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src += fh.read()

    def test_co_giu_danh_sach_chua_biet_map(self):
        i = self.src.find("maps, _chua_biet_map = {}, []")
        self.assertGreater(i, 0)
        self.assertIn("_chua_biet_map", self.src[i:i + 400],
                      "bo qua acc chua biet map -> lai ket luan 'cung map' bang mot phep dem thieu")

    def test_bac_nay_dung_TRUOC_bac_kenh(self):
        i_chua = self.src.find("elif anh.chua_biet_map:")
        i_kenh = self.src.find("elif len(kenhs) > 1 and not anh.du_doi:")
        self.assertGreater(i_chua, 0)
        self.assertGreater(i_kenh, 0)
        self.assertLess(i_chua, i_kenh)


if __name__ == "__main__":
    unittest.main()
