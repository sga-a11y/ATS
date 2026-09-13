"""DIEU PHOI phai biet MAP TRAIN DICH tu dau, khong doi leader toi noi moi biet.

User 13/09: "p15, o trac quan lap pt lam lon gi the".

So bai train nam o HAI cho: `auto_train` (dieu phoi chot, co tu dau) va `train_map_dich` (luong
leader ghi, chi khi DA warp vao bai xong). Bac chan "chi lap party o diem tap ket hoac map train"
(xem `test_chi_lap_party_o_diem_tap_ket.py`) truoc day bam dung cai duoc dien MUON NHAT, nen no
khong bat len trong suot doan duong di - dung luc can nhat.

KHONG phai "chua toi bai thi khong biet dich" (user bac thang): co so map train la `_pick_start_city`
tinh ra thanh tap ket ngay, router thuan du lieu, khong can ai di dau ca. Loi la TRA SAI O.

CA THAT party 15 (tru6006..tru6010, mode train, ca party o 12001 = Cua thanh Trac Quan):
    14:23:43 >>> PARTY 15: TU CHON MAP -> Dam Lay Tang Khau1 (map 21841)   <- da chot tu day
    22:57:15 [party 15] gen 4: viec=moi - cung map/kenh nhung DOI chua du (tat ca = 0)
    22:59:26 [party 15] DIEU PHOI: ca party da chung kenh 2 nhung DOI chua du -> LAP LAI PARTY
    23:01:27 / 23:03:28 / 23:05:29 ...   roster khong bao gio len qua 4
Bai train biet tu 8 tieng truoc, van lap party o thanh di ngang qua.
"""
from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot import config

TRAC_QUAN = 12001
TRUONG_SA = 23001
MAP_TRAIN = 21841


def _st(**kw):
    s = {"lock": threading.RLock()}
    s.update(kw)
    return s


class _Nen(unittest.TestCase):
    PARTY = 40

    def setUp(self):
        self._cfg_cu = getattr(config, "PARTY_CONFIG", {})
        config.PARTY_CONFIG = dict(self._cfg_cu)
        R._party_state.pop(self.PARTY, None)

    def tearDown(self):
        config.PARTY_CONFIG = self._cfg_cu
        R._party_state.pop(self.PARTY, None)

    def _cfg(self, **kw):
        config.PARTY_CONFIG[self.PARTY] = kw


class TestMapTrainDich(_Nen):
    def test_leader_da_toi_noi_thi_lay_so_do(self):
        self._cfg(mode="train", start_city_id=11111)
        self.assertEqual(R._map_train_dich(self.PARTY, _st(train_map_dich=MAP_TRAIN)), MAP_TRAIN)

    def test_dieu_phoi_da_chot_bai_thi_biet_NGAY(self):
        """train_pick: chua ai di dau ca, nhung `auto_train` da co -> du de biet dich."""
        self._cfg(mode="train", train_pick="tu_chon", start_city_id=0)
        self.assertEqual(R._map_train_dich(self.PARTY, _st(auto_train=(MAP_TRAIN, -1))), MAP_TRAIN)

    def test_user_chi_dinh_map_tay_thi_biet_NGAY_tu_config(self):
        self._cfg(mode="train", start_city_id=MAP_TRAIN)
        self.assertEqual(R._map_train_dich(self.PARTY, _st()), MAP_TRAIN)

    def test_train_pick_chua_chot_thi_KHONG_doan_theo_config(self):
        """Party 'Tu chon map': `start_city_id` la 0/rac - doan theo no la ra sai map."""
        self._cfg(mode="train", train_pick="tu_chon", start_city_id=TRAC_QUAN)
        self.assertIsNone(R._map_train_dich(self.PARTY, _st()))

    def test_digioi_train_con_o_pha_DG_thi_chua_co_dich(self):
        self._cfg(mode="digioi_train", start_city_id=MAP_TRAIN)
        self.assertIsNone(R._map_train_dich(self.PARTY, _st(dt_phase="digioi")))
        self.assertEqual(R._map_train_dich(self.PARTY, _st(dt_phase="train")), MAP_TRAIN)

    def test_mode_khac_thi_khong_co_map_train(self):
        for _m in ("digioi", "event", "city", "stand", "cleanbag"):
            self._cfg(mode=_m, start_city_id=MAP_TRAIN)
            self.assertIsNone(R._map_train_dich(self.PARTY, _st()), _m)


class TestChanLapPartyKhiLeaderCHUAToiBai(_Nen):
    """Bac chan phai bat len NGAY CA KHI `train_map_dich` con rong - do moi la luc no co ich."""

    def setUp(self):
        super().setUp()
        self._pick = R._pick_start_city
        R._pick_start_city = lambda pidx, dest: TRUONG_SA
        self._cfg(mode="train", start_city_id=MAP_TRAIN)

    def tearDown(self):
        R._pick_start_city = self._pick
        super().tearDown()

    def test_trac_quan_KHONG_phai_tap_ket_thi_khong_lap_party(self):
        self.assertTrue(R._o_thanh_di_qua(self.PARTY, _st(), TRAC_QUAN),
                        "ca p15: dang o thanh di ngang qua ma van cho lap party")

    def test_o_chinh_thanh_tap_ket_thi_duoc_lap(self):
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, _st(), TRUONG_SA))

    def test_o_chinh_map_train_thi_duoc_lap(self):
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, _st(), MAP_TRAIN))

    def test_train_pick_chua_chot_thi_van_KHONG_ket_luan(self):
        """Chua biet dich that -> tha lap party thua con hon chan oan (L13)."""
        self._cfg(mode="train", train_pick="tu_chon", start_city_id=0)
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, _st(), TRAC_QUAN))


class TestKhongConDocThangTrainMapDich(unittest.TestCase):
    def test_moi_phep_dung_map_train_dich_deu_qua_ham_chung(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _map_train_dich(")
        self.assertGreater(i, 0, "mat ham _map_train_dich")
        j = src.find("\ndef ", i + 10)
        than = src[i:j]
        _doc = [ln.strip() for ln in src.splitlines()
                if ('st.get("train_map_dich")' in ln or "st.get('train_map_dich')" in ln)
                and ln not in than.splitlines()]
        self.assertEqual(_doc, [],
                         "con cho doc thang `train_map_dich` (mu suot duong di): %s" % _doc)


if __name__ == "__main__":
    unittest.main()
