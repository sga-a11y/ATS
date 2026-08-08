import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as coordinator


class TestDigioiChannelReport(unittest.TestCase):
    @staticmethod
    def make_state():
        return {
            "lock": threading.Lock(),
            "channel_sync_gen": 8,
            "channel_map_reports": {"leader": (True, 49942)},
            "channel_failed": threading.Event(),
            "channel_failed_reason": "",
        }

    def test_late_member_retry_reports_into_current_sync_generation(self):
        self.assertTrue(
            hasattr(coordinator, "_record_channel_map_report"),
            "member retry must be able to report after leaving startup channel sync",
        )
        state = self.make_state()

        ok = coordinator._record_channel_map_report(
            state, "member", 49942, sync_gen=8, expected_map=49942
        )

        self.assertTrue(ok)
        self.assertEqual(state["channel_map_reports"]["member"], (True, 49942))

    def test_stale_retry_cannot_write_into_a_new_sync_generation(self):
        self.assertTrue(hasattr(coordinator, "_record_channel_map_report"))
        state = self.make_state()

        ok = coordinator._record_channel_map_report(
            state, "member", 49942, sync_gen=7, expected_map=49942
        )

        self.assertFalse(ok)
        self.assertNotIn("member", state["channel_map_reports"])

    def test_reform_leader_clears_stale_channel_ready_before_arrival_barrier(self):
        self.assertTrue(hasattr(coordinator, "_prepare_reform_channel_sync"))
        state = self.make_state()
        state["channel"] = 58
        state["channel_ready"] = threading.Event()
        state["channel_ready"].set()

        coordinator._prepare_reform_channel_sync(state)

        self.assertFalse(state["channel_ready"].is_set())
        self.assertIsNone(state["channel"])

    def test_each_account_refreshes_current_channel_before_sync_picker_runs(self):
        source = (Path(__file__).parents[1] / "run_party_digioi.py").read_text(
            encoding="utf-8"
        )
        sync_start = source.index("        def do_channel_sync():")
        sync_end = source.index("\n        def _do_reform", sync_start)
        sync_source = source[sync_start:sync_end]

        refresh_at = sync_source.index("c.refresh_current_channel(")
        pick_at = sync_source.index("c.pick_best_channel(")

        self.assertLess(refresh_at, pick_at)


if __name__ == "__main__":
    unittest.main()
