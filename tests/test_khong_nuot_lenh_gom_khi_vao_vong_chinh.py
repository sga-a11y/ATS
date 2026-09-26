"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_fresh_regroup_generation_is_observed(self):
        result = E.quyet_dinh(snapshot(reform_moi=True))
        self.assertEqual(set(result.values()), {E.VIEC_VE_THANH})

    def test_retired_regroup_does_not_move_full_party_back_to_town(self):
        self.assertNotIn(E.VIEC_VE_THANH, E.quyet_dinh(snapshot(reform_moi=False)).values())
