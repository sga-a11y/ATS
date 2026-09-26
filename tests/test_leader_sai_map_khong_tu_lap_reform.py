"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_wrong_map_does_not_stop_account(self):
        result = E.quyet_dinh(snapshot([account(map_id=200), account("b")]))
        self.assertNotIn(E.VIEC_THOAT, result.values())
        self.assertIn(E.VIEC_VE_MAP, result.values())

    def test_failed_travel_is_retried_by_controller(self):
        before = snapshot([account(map_id=200), account("b", map_id=200)], dp_viec=E.DP_DI_TRAIN)
        self.assertEqual(E.quyet_dinh(before), E.quyet_dinh(before))
        self.assertIn(E.VIEC_VE_MAP, E.quyet_dinh(before).values())
