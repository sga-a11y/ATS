"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_missing_roster_prevents_training(self):
        self.assertEqual(E.quyet_dinh(snapshot([account(so_member=0), account("b")])),
                         {"a": E.VIEC_LAP_PARTY, "b": E.VIEC_LAP_PARTY})

    def test_full_roster_releases_training(self):
        self.assertEqual(set(E.quyet_dinh(snapshot()).values()), {E.VIEC_RA_SPOT})

    def test_battle_is_not_interrupted_by_regroup(self):
        result = E.quyet_dinh(snapshot([account(dang_danh=True), account("b", map_id=200)]))
        self.assertEqual(result["a"], E.VIEC_NGHI)
