"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_fresh_snapshot_reads_changed_channel(self):
        from tests.test_party_engine_vong import _Cli
        a, b = _Cli(map_id=100), _Cli(map_id=100, kenh=2)
        engine = E.PartyEngine(0, lambda: [("a", a, True), ("b", b, False)], can_bao_nhieu=1)
        self.assertIn(E.VIEC_DOI_KENH, engine.nhip().values())
        b.current_channel = 1
        self.assertNotIn(E.VIEC_DOI_KENH, engine.nhip().values())
