"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_wrong_map_moves_before_spot(self):
        result = E.quyet_dinh(snapshot([account(map_id=200), account("b", map_id=200)], dp_viec=E.DP_DI_TRAIN))
        self.assertNotIn(E.VIEC_RA_SPOT, result.values())
        self.assertIn(E.VIEC_VE_MAP, result.values())

    def test_arriving_at_train_map_releases_spot(self):
        self.assertEqual(set(E.quyet_dinh(snapshot()).values()), {E.VIEC_RA_SPOT})

    def test_unknown_map_is_not_arrival(self):
        self.assertNotIn(E.VIEC_RA_SPOT,
                         E.quyet_dinh(snapshot([account(map_id=None), account("b")])).values())
