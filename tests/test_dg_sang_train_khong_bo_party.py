"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_dg_to_train_retains_both_accounts(self):
        from tests.test_party_engine_vong import _Cli
        clients = [("a", _Cli(), True), ("b", _Cli(), False)]
        engine = E.PartyEngine(0, lambda: clients, co_pha_train=True)
        engine.pha = E.PHA_DG
        engine._doi_pha_neu_het_gio_dg(snapshot(pha=E.PHA_DG))
        self.assertEqual(engine.pha, E.PHA_TRAIN)
        self.assertTrue(all(c.running for _, c, _ in clients))

    def test_member_still_has_dg_time_keeps_party_in_dg_phase(self):
        from tests.test_party_engine_vong import _Cli
        engine = E.PartyEngine(0, lambda: [], co_pha_train=True)
        engine.pha = E.PHA_DG
        engine._doi_pha_neu_het_gio_dg(snapshot([account(), account("b", con_gio_dg=True)], pha=E.PHA_DG))
        self.assertEqual(engine.pha, E.PHA_DG)
