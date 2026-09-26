"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_certain_same_channel_does_not_switch(self):
        self.assertNotIn(E.VIEC_DOI_KENH, E.quyet_dinh(snapshot()).values())

    def test_uncertain_same_channel_is_not_assumed_synchronized(self):
        from tests.test_party_engine_vong import _Cli
        a, b = _Cli(members=0), _Cli()
        b.kenh_dang_chac = lambda: False
        engine = E.PartyEngine(0, lambda: [("a", a, True), ("b", b, False)],
                               can_bao_nhieu=1, doc_kenh_dich=lambda: None)
        self.assertEqual(engine.nhip()["b"], E.VIEC_DOI_KENH)
