# -*- coding: utf-8 -*-
"""CHO ACC LOGIN THI CA PARTY RA SAFE, khong dung giua bai quai.

Ca that 28/09 party 1 (user: "dang cho 1 dua login mai chua xong thi cho bon khac chay ve vi tri
an toan duoc ko, cu dung cho quai cho quai bem nay gio"):

    13:43:44 gen 8: viec=lam - moi 3/5 acc login xong -> chua ket luan map/kenh, cho du roi moi quyet
    14:02:08 ENGINE: sga005/sga007/sga008/tuyetdo -> train     <- dung (1380,880) map train 21863
    14:02:06 CHUA CHOT DUOC CAP QUAI DG sau 1150s - dang cho level cua 1 acc: sga006(chua login)
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R
from bot import party_engine as PE

PIDX = 990
MAP = 21863
SAFES = [[910, 530], [910, 850], [1710, 890], [1750, 990]]


class TestChoLoginRaSafe(unittest.TestCase):
    def setUp(self):
        R._pstate(PIDX).pop("safe_cho_login", None)
        self.clients = {u: SimpleNamespace(pos=(1380, 880)) for u in ("a1", "a2", "a3", "a4")}
        self.p = [mock.patch.dict(R.account_clients, self.clients),
                  mock.patch.object(R.config, "TRAIN_MAPS", {MAP: {"safe": SAFES}})]
        for p in self.p:
            p.start()

    def tearDown(self):
        for p in self.p:
            p.stop()

    def _anh(self, thieu=True, map_id=MAP):
        accs = [PE.AnhAcc(u, la_leader=(u == "a1"), map_id=map_id, kenh=1)
                for u in ("a1", "a2", "a3", "a4")]
        return SimpleNamespace(accs=accs, thieu_acc_song=thieu)

    def test_thieu_acc_dang_train_thi_ra_safe(self):
        ket = R._engine_cho_login_decisions(PIDX, self._anh(), {u: "train" for u in self.clients})
        self.assertEqual(set(ket.values()), {"ve_safe_cho"})
        self.assertEqual(R._pstate(PIDX)["safe_cho_login"], (MAP, (1710, 890)))

    def test_toi_safe_roi_thi_dung_yen(self):
        self.clients["a2"].pos = (1712, 895)
        ket = R._engine_cho_login_decisions(PIDX, self._anh(), {u: "train" for u in self.clients})
        self.assertEqual(ket["a2"], "nghi")
        self.assertEqual(ket["a1"], "ve_safe_cho")

    def test_du_acc_thi_khong_dung_vao(self):
        vao = {u: "train" for u in self.clients}
        self.assertEqual(R._engine_cho_login_decisions(PIDX, self._anh(thieu=False), vao), vao)

    def test_map_khong_co_safe_thi_khong_dung_vao(self):
        vao = {u: "nghi" for u in self.clients}
        self.assertEqual(R._engine_cho_login_decisions(PIDX, self._anh(map_id=12001), vao), vao)

    def test_viec_vat_khong_bi_de(self):
        vao = {u: "train" for u in self.clients}
        vao["a3"] = "login_chore"
        self.assertEqual(R._engine_cho_login_decisions(PIDX, self._anh(), vao)["a3"], "login_chore")

    def test_engine_cho_phep_viec_moi(self):
        self.assertIn("ve_safe_cho", PE.BAN_THI_CHO)


if __name__ == "__main__":
    unittest.main()
