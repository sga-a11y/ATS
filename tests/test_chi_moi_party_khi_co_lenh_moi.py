"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_sync_blocks_invites(self):
        self.assertNotIn(E.VIEC_LAP_PARTY, E.quyet_dinh(snapshot(dp_viec=E.DP_DONG_BO)).values())

    def test_invite_decision_applies_to_whole_party(self):
        self.assertEqual(set(E.quyet_dinh(snapshot(dp_viec=E.DP_MOI)).values()), {E.VIEC_LAP_PARTY})

    def test_in_transit_town_cannot_start_inviting(self):
        self.assertNotIn(E.VIEC_LAP_PARTY,
                         E.quyet_dinh(snapshot(thanh_di_ngang=True)).values())
