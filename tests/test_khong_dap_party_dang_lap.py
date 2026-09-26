"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_repeated_invite_command_does_not_cancel_inflight_invitation(self):
        worker = E.AccWorker("a", object(), lambda *args: None)
        self.assertTrue(worker.giao(E.VIEC_LAP_PARTY))
        worker._huy.clear()
        self.assertFalse(worker.giao(E.VIEC_LAP_PARTY))
        self.assertFalse(worker._huy.is_set())
