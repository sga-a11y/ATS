import sys
import unittest
from unittest import mock

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    from run_party_digioi import (
        _is_npc_repeat_party_event,
        _should_restart_event_party,
        _should_resync_incomplete_digioi_party,
    )


NPC_REPEAT = {"party_battle": {"kind": "npc_repeat", "point": [910, 290]}}


class TestNpc40PartyPolicy(unittest.TestCase):
    def test_digioi_party_resyncs_after_short_incomplete_invite_window(self):
        self.assertFalse(_should_resync_incomplete_digioi_party(True, False, 2, 4, 19.9))
        self.assertTrue(_should_resync_incomplete_digioi_party(True, False, 2, 4, 20.0))

    def test_digioi_solo_and_complete_party_do_not_resync(self):
        self.assertFalse(_should_resync_incomplete_digioi_party(True, True, 0, 4, 30.0))
        self.assertFalse(_should_resync_incomplete_digioi_party(True, False, 4, 4, 30.0))

    def test_auto_party_requires_event_mode_leader_and_supported_kind(self):
        self.assertTrue(_is_npc_repeat_party_event("event", True, NPC_REPEAT))
        self.assertFalse(_is_npc_repeat_party_event("event", False, NPC_REPEAT))
        self.assertFalse(_is_npc_repeat_party_event("train", True, NPC_REPEAT))
        self.assertFalse(_is_npc_repeat_party_event("event", True, {}))

    def test_disconnect_restarts_only_active_npc_party_loop(self):
        self.assertTrue(_should_restart_event_party(True, True, 4, 3))
        self.assertFalse(_should_restart_event_party(True, False, 4, 3))
        self.assertFalse(_should_restart_event_party(False, True, 4, 3))
        self.assertFalse(_should_restart_event_party(True, True, 3, 3))


if __name__ == "__main__":
    unittest.main()
