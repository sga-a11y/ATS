"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_channel_command_interrupts_previous_blocking_work(self):
        worker = E.AccWorker("a", object(), lambda *args: None)
        worker.giao(E.VIEC_LAP_PARTY)
        worker._huy.clear()
        self.assertTrue(worker.giao(E.VIEC_DOI_KENH))
        self.assertTrue(worker._huy.is_set())

    def test_matching_command_is_not_reissued_while_running(self):
        worker = E.AccWorker("a", object(), lambda *args: None)
        worker.giao(E.VIEC_DOI_KENH)
        self.assertFalse(worker.giao(E.VIEC_DOI_KENH))
