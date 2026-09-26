"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_full_roster_on_wrong_map_must_travel(self):
        result = E.quyet_dinh(snapshot([account(map_id=200), account("b", map_id=200)], dp_viec=E.DP_DI_TRAIN))
        self.assertNotIn(E.VIEC_TRAIN, result.values())
        self.assertIn(E.VIEC_VE_MAP, result.values())

    def test_correct_map_and_roster_can_train(self):
        people = [account(viec_dang_lam=E.VIEC_TRAIN), account("b", viec_dang_lam=E.VIEC_TRAIN)]
        self.assertEqual(set(E.quyet_dinh(snapshot(people)).values()), {E.VIEC_TRAIN})
