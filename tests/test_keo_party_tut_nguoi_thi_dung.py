"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_lost_member_cancels_travel_on_next_tick(self):
        worker = E.AccWorker("a", object(), lambda *args: None)
        worker.giao(E.VIEC_VE_MAP)
        worker._huy.clear()
        next_action = E.quyet_dinh(snapshot([account(so_member=0), account("b")]))["a"]
        self.assertEqual(next_action, E.VIEC_LAP_PARTY)
        worker.giao(next_action)
        self.assertTrue(worker._huy.is_set())

    def test_manual_party_route_refuses_partial_roster(self):
        from bot.party_route import decide_route
        plan = dict(users=["a", "b"], source=100, dest=200, city=100, phase="dest")
        result = decide_route(plan, snapshot().accs, "a", joined_members=0)
        self.assertEqual(result.phase, "gather")
        self.assertNotIn("route_dest", result.actions.values())
