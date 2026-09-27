"""Mode EVENT: engine moi phai giu hai co ma `run_account` (engine cu) dat luc login.

    c.state.force_quest_mode = (mode == "event")   -> moi tran event danh quest_mode
    c.default_pet_role = "quest" if event else "train"

Commit 26/09 bo `run_account` ma khong chuyen hai co nay sang engine: party KHONG CO LEADER BOT
(nguoi that moi) danh event bang combo TRAIN (quest chi bat khi tran > 6 quai), va pet bi tra ve
vai train sau moi viec co doi vai.

Kem: party khong leader bot, acc da o map event duoc giao `lap_party` -> phai MO CUA nhan loi moi
(`set_party_invite_ready(True)`), khong moi ai.
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace as NS
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as PE
from bot.state import BattleState

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _cli():
    return NS(state=BattleState(), default_pet_role="train")


class TestEventLuonQuestMode(unittest.TestCase):
    def test_mode_event_bat_force_quest_va_pet_quest(self):
        c = _cli()
        R._cap_nhat_tuy_chon_client(c, {"mode": "event"})
        self.assertTrue(c.state.force_quest_mode)
        self.assertTrue(c.state.quest_mode)
        self.assertEqual(c.default_pet_role, "quest")

    def test_het_tran_van_giu_quest(self):
        c = _cli()
        R._cap_nhat_tuy_chon_client(c, {"mode": "event"})
        c.state.reset_enemies(reset_quest=True)
        self.assertTrue(c.state.quest_mode)

    def test_mode_khac_tra_ve_train(self):
        c = _cli()
        R._cap_nhat_tuy_chon_client(c, {"mode": "event"})
        R._cap_nhat_tuy_chon_client(c, {"mode": "train"})
        self.assertFalse(c.state.force_quest_mode)
        self.assertEqual(c.default_pet_role, "train")


class TestKhongLeaderThiMoCuaNhanLoiMoi(unittest.TestCase):
    def test_lap_party_voi_acc_khong_phai_leader_chi_mo_cua(self):
        c = mock.Mock()
        c._pe_la_leader = False
        moi = mock.Mock()
        self.assertTrue(PE.thi_hanh(c, PE.VIEC_LAP_PARTY, lambda: True, moi_party=moi))
        c.set_party_invite_ready.assert_called_once_with(True)
        moi.assert_not_called()


if __name__ == "__main__":
    unittest.main()
