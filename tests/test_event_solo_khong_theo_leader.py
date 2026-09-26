"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_solo_event_never_follows_group_route(self):
        from bot.party_modes import decide_mode
        people = [account(map_id=50), account("b")]
        self.assertEqual(decide_mode("event", {"a": "ve_map", "b": "lap_party"}, people,
                                     event_kind="chaos_vs", event_map=100),
                         {"a": "solo_event_enter", "b": "solo_event_run"})
