import sys
import unittest
from unittest import mock

from bot.mob_scanner import CenterCandidate, ScanResult

_argv = sys.argv
try:
    sys.argv = ["run_party_digioi.py"]
    import run_party_digioi as coordinator
finally:
    sys.argv = _argv


class Ground:
    def map_fingerprint(self, _map_id):
        return "abc12345"


class Client:
    def __init__(self):
        self.ground = Ground()
        self.current_channel = 2
        self.switched = []

    def get_ground_store(self):
        return self.ground

    def switch_channel(self, channel):
        self.switched.append(channel)


class SequenceEvent:
    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def wait(self, _timeout):
        self.calls += 1
        return self.values.pop(0) if self.values else False


class TestTrainMobScanPolicy(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.tm = {"safe": [(410, 1050)], "mobs": [(590, 1010)]}

    @mock.patch.object(coordinator.mob_spots, "load_complete_centers")
    @mock.patch.object(coordinator, "scan_full_map")
    def test_valid_cache_returns_centers_without_scan_or_channel_reset(self, scan, load):
        load.return_value = [(530, 930), (1150, 530)]

        centers = coordinator._resolve_train_mob_centers(
            self.client, 11013, self.tm, stop=lambda: False
        )

        self.assertEqual(centers, [(530, 930), (1150, 530)])
        scan.assert_not_called()
        self.assertEqual(self.client.switched, [])

    @mock.patch.object(coordinator.mob_spots, "load_complete_centers", return_value=None)
    @mock.patch.object(coordinator, "scan_full_map")
    def test_missing_cache_runs_scan_and_returns_new_centers(self, scan, _load):
        scan.return_value = ScanResult(
            "complete", (CenterCandidate((530, 930), 3, 1.0),), 10, 10
        )

        centers = coordinator._resolve_train_mob_centers(
            self.client, 11013, self.tm, stop=lambda: False
        )

        self.assertEqual(centers, [(530, 930)])
        self.assertEqual(self.client.switched, [2])

    @mock.patch.object(coordinator.mob_spots, "load_complete_centers", return_value=None)
    @mock.patch.object(coordinator, "scan_full_map")
    def test_unavailable_or_incomplete_scan_falls_back_to_configured_points(self, scan, _load):
        for status in ("unavailable", "incomplete"):
            with self.subTest(status=status):
                scan.return_value = ScanResult(status, (), 0, 10)
                self.assertEqual(
                    coordinator._resolve_train_mob_centers(
                        self.client, 11013, self.tm, stop=lambda: False
                    ),
                    [(590, 1010)],
                )

    @mock.patch.object(coordinator.mob_spots, "load_complete_centers", return_value=None)
    @mock.patch.object(coordinator, "scan_full_map")
    def test_complete_empty_scan_does_not_invent_or_fallback_a_point(self, scan, _load):
        scan.return_value = ScanResult("empty", (), 10, 10)

        centers = coordinator._resolve_train_mob_centers(
            self.client, 11013, self.tm, stop=lambda: False
        )

        self.assertEqual(centers, [])

    def test_member_wait_is_unbounded_but_stop_aware(self):
        event = SequenceEvent([False, False, True])

        ready = coordinator._wait_for_rally(event, lambda: False, lambda: True)

        self.assertTrue(ready)
        self.assertEqual(event.calls, 3)

        stopped_event = SequenceEvent([False, False])
        ready = coordinator._wait_for_rally(
            stopped_event, lambda: stopped_event.calls >= 1, lambda: True
        )
        self.assertFalse(ready)


if __name__ == "__main__":
    unittest.main()
