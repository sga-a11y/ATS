"""LOGIN GIUA BAI QUAI -> PHAI RA SAFE, ke ca party "Tu chon map".

User 13/09: "party 1, log in va dung cho quai la bi danh lien tuc, deo lap duoc party, truoc la
login xong chay ra diem safe roi ma sao gio van bi danh".

Game cho login lai DUNG CHO logout. Bot train o bai quai -> lan login sau la dung ngay giua bay
quai: bi danh lien tuc, `in_combat` suot, khong moi/nhan loi moi party duoc, va roi rot mang.

Khoi "ra safe truoc login chores" co san, nhung dieu kien cua no la `config.TRAIN_MAPS.get(_early_sc)`
voi `_early_sc = pcfg["start_city_id"]`. Party dat "Tu chon map" (`train_pick`) thi o config do
la 0 - so bai that nam o `st["auto_train"]` do DIEU PHOI chot. Nen:

    _early_sc = 0  ->  _early_tm = None  ->  CA khoi ra-safe bi bo qua

CA THAT party 1 (map train 21833, safe khac diem quai):
    23:16:56 [sga014] RESYNC pos tu 0x03 = (3020,1000) map=21833   <- trong bai
    23:16:57 [sga015] RESYNC pos tu 0x03 = (3020,1000) map=21833
    23:16:59 [chihao188] RESYNC pos tu 0x03 = (3020,1000) map=21833
    23:18:30 [sga013] RECONNECT: server rot -> login lai sau 5s
    23:18:41 [chihao188] RECONNECT: server rot -> login lai sau 5s
Khong mot dong "ve safe truoc login chores" nao, va roster party khong bao gio qua noi 4.

Cung goc benh voi p15 ("o trac quan lap pt"): so bai train nam o hai cho, code doc cai rong.
Xem `test_biet_map_train_dich_tu_dau.py`.
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot import config

MAP_TRAIN = 21833


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestEarlyScLayDuocBaiDieuPhoiChot(unittest.TestCase):
    """`_early_sc` phai ra so bai THAT, khong phai so 0 trong config."""

    PARTY = 42

    def setUp(self):
        self._cfg_cu = getattr(config, "PARTY_CONFIG", {})
        config.PARTY_CONFIG = dict(self._cfg_cu)
        R._party_state.pop(self.PARTY, None)

    def tearDown(self):
        config.PARTY_CONFIG = self._cfg_cu
        R._party_state.pop(self.PARTY, None)

    def test_tu_chon_map_da_chot_thi_biet_bai(self):
        config.PARTY_CONFIG[self.PARTY] = {"mode": "train", "train_pick": "tu_chon",
                                           "start_city_id": 0}
        st = R._pstate(self.PARTY)
        st["auto_train"] = (MAP_TRAIN, -1)
        self.assertEqual(R._map_train_dich(self.PARTY, st), MAP_TRAIN)

    def test_tu_chon_map_CHUA_chot_thi_van_None(self):
        """Chua chot thi giu nguyen hanh vi cu (bo qua khoi ra-safe), khong doan bua."""
        config.PARTY_CONFIG[self.PARTY] = {"mode": "train", "train_pick": "tu_chon",
                                           "start_city_id": 0}
        self.assertIsNone(R._map_train_dich(self.PARTY, R._pstate(self.PARTY)))




if __name__ == "__main__":
    unittest.main()
