"""A channel switch must wait for battle and event safety signals."""

import sys
import unittest
from unittest import mock

from bot import party_engine as PE
from tests.test_dieu_phoi_tu_gui_lenh_doi_kenh import Client, channel_decision

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class BattleClient(Client):
    def __init__(self, *, battle=False, grace=False, combat=False):
        super().__init__(2)
        self.state.in_battle = battle
        self.grace = grace
        self.combat = combat

    def _in_battle_end_grace(self):
        return self.grace

    def in_combat(self):
        return self.combat


class TestChannelBattleSafety(unittest.TestCase):
    def _assert_waits(self, client, state=None):
        state = state or {}
        safe = lambda c: R._kenh_doi_duoc_ngay(c, state)
        actions, _ = channel_decision({"a": 2}, 16, allow=lambda _c: safe(client))
        self.assertEqual(actions, {"a": "nghi"})
        self.assertFalse(PE.thi_hanh(client, "doi_kenh", lambda: True,
                                    dich=16, kenh_doi_duoc=safe))
        self.assertEqual(client.calls, [])

    def test_event_battle_active_waits(self):
        self._assert_waits(BattleClient(), {"event_battle_active": True})

    def test_state_in_battle_waits_even_if_idle_combat_is_false(self):
        self._assert_waits(BattleClient(battle=True))

    def test_end_of_battle_grace_waits(self):
        self._assert_waits(BattleClient(grace=True))

    def test_in_combat_waits(self):
        self._assert_waits(BattleClient(combat=True))

    def test_switch_runs_after_all_safety_signals_clear(self):
        client = BattleClient()
        safe = lambda c: R._kenh_doi_duoc_ngay(c, {})
        actions, _ = channel_decision({"a": 2}, 16, allow=lambda _c: safe(client))
        self.assertEqual(actions, {"a": "doi_kenh"})
        self.assertTrue(PE.thi_hanh(client, actions["a"], lambda: True,
                                   dich=16, kenh_doi_duoc=safe))
        self.assertEqual(client.calls[0][0], 16)


if __name__ == "__main__":
    unittest.main()
