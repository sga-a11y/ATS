"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_finished_account_waits_in_town_for_other_dg_accounts(self):
        a = account(trong_dg=False, con_gio_dg=False)
        b = account("b", trong_dg=True, con_gio_dg=True)
        result = E.quyet_dinh(snapshot([a, b], pha=E.PHA_DG, thanh_dich=12001))
        self.assertEqual(result["a"], E.VIEC_VE_THANH)
        self.assertNotIn(result["b"], (E.VIEC_VE_THANH, E.VIEC_THOAT))

    def test_dg_only_mode_stops_when_time_is_used(self):
        self.assertEqual(set(E.quyet_dinh(snapshot(pha=E.PHA_DG, co_pha_train=False)).values()),
                         {E.VIEC_THOAT})
