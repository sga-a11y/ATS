"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_controller_observes_partial_roster_without_waiting_for_reports(self):
        from tests.test_party_engine_vong import _Cli
        a, b = _Cli(map_id=100, members=0), _Cli(map_id=100)
        engine = E.PartyEngine(0, lambda: [("a", a, True), ("b", b, False)], can_bao_nhieu=1,
                               map_dich=100, doc_spot=lambda: (20, 30))
        self.assertEqual(set(engine.nhip().values()), {E.VIEC_LAP_PARTY})
        a.party_members = [b"member"]
        self.assertEqual(set(engine.nhip().values()), {E.VIEC_RA_SPOT})
