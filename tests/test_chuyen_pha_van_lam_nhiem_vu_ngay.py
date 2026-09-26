"""Daily work is deferred during DG and becomes eligible after the phase changes."""
import sys
import unittest
from types import SimpleNamespace as NS
from unittest import mock
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot
with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class TestDailyPhase(unittest.TestCase):
    def test_dg_defers_daily_until_train(self):
        anh = snapshot([account(xong_daily=False, trong_dg=True, con_gio_dg=True)], pha=E.PHA_DG)
        self.assertNotEqual(E.quyet_dinh(anh)["a"], E.VIEC_DAILY)
        anh.pha = E.PHA_TRAIN
        anh.accs[0].trong_dg = False
        self.assertEqual(E.quyet_dinh(anh)["a"], E.VIEC_DAILY)

    def test_completed_daily_does_not_restart_every_tick(self):
        anh = snapshot([account(xong_daily=True)], pha=E.PHA_TRAIN)
        self.assertNotEqual(E.quyet_dinh(anh)["a"], E.VIEC_DAILY)

    def test_daily_runs_world_boss_dungeon_and_claim(self):
        client = mock.Mock(current_map=50)
        with mock.patch.dict(R.config.PARTY_CONFIG, {0: {"do_daily": True, "auto_world_boss": True}}, clear=True), \
                mock.patch.object(R, "_map_train_dich", return_value=100):
            R._nhiem_vu_ngay_engine_moi(client, 0)
        client.do_world_boss_all.assert_called_once()
        client.do_daily_dungeon.assert_called_once()
        client.claim_daily_quests.assert_called_once_with(heavy=True)

    def test_disabled_daily_does_not_call_game(self):
        client = mock.Mock()
        with mock.patch.dict(R.config.PARTY_CONFIG, {0: {"do_daily": False}}, clear=True):
            R._nhiem_vu_ngay_engine_moi(client, 0)
        self.assertEqual(client.mock_calls, [])

    def test_claim_does_not_use_old_team_dungeon_barrier(self):
        client = mock.Mock(current_map=100)
        hook = client._o5_team_fn
        client.claim_daily_quests.side_effect = lambda **kw: self.assertIsNone(client._o5_team_fn)
        with mock.patch.dict(R.config.PARTY_CONFIG, {0: {"auto_world_boss": False}}, clear=True), \
                mock.patch.object(R, "_map_train_dich", return_value=100):
            R._nhiem_vu_ngay_engine_moi(client, 0)
        self.assertIs(client._o5_team_fn, hook)
        hook.assert_not_called()
