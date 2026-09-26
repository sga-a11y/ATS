"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_replacement_cancels_travel(self):
        worker = E.AccWorker("a", object(), lambda *args: None)
        worker.giao(E.VIEC_VE_THANH)
        worker._huy.clear()
        worker.giao(E.VIEC_NGHI)
        self.assertFalse(worker._con_lam())

    def test_same_route_keeps_abort_false(self):
        worker = E.AccWorker("a", object(), lambda *args: None)
        worker.giao(E.VIEC_VE_THANH)
        worker._huy.clear()
        worker.giao(E.VIEC_VE_THANH)
        self.assertTrue(worker._con_lam())
