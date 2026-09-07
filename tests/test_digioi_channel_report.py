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
            "channel_failed": threading.Event(),
            "channel_failed_reason": "",
        }

    def test_dung_map_thi_KHONG_dat_co_hong(self):
        """`channel_map_reports` da bo (07/09): bang bao cao vi pham L2 - leader doc thang
        `account_clients[u].current_map` + `kenh_that()` la biet het. Ham chi con MOT viec: acc
        thay minh SAI MAP thi dat co hong, vi do la thu leader khong tu thay duoc."""
        self.assertFalse(hasattr(coordinator, "_record_channel_map_report"),
                         "bang bao cao map van con -> L2")
        state = self.make_state()

        ok = coordinator._ghi_sync_that_bai(
            state, "member", 49942, sync_gen=8, expected_map=49942
        )

        self.assertTrue(ok)
        self.assertFalse(state["channel_failed"].is_set())

    def test_SAI_map_thi_dat_co_hong(self):
        state = self.make_state()

        ok = coordinator._ghi_sync_that_bai(
            state, "member", 12001, sync_gen=8, expected_map=49942
        )

        self.assertFalse(ok)
        self.assertTrue(state["channel_failed"].is_set())
        self.assertIn("12001", state["channel_failed_reason"])

    def test_gen_cu_KHONG_dat_duoc_co_hong_cua_vong_moi(self):
        """Acc retry cham mot nhip khong duoc pha vong sync dang chay."""
        state = self.make_state()

        ok = coordinator._ghi_sync_that_bai(
            state, "member", 12001, sync_gen=7, expected_map=49942
        )

        self.assertFalse(ok)
        self.assertFalse(state["channel_failed"].is_set())

    def test_khong_con_doi_acc_bao_cao(self):
        source = (Path(__file__).parents[1] / "run_party_digioi.py").read_text(encoding="utf-8")
        self.assertNotIn('st["channel_map_reports"]', source)
        for d in source.splitlines():
            if "log." in d:
                self.assertNotIn("cho acc bao cao map", d, d.strip())

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
