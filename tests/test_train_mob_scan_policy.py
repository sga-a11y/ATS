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
        self.running = True
        self.finished_capture = []

    def get_ground_store(self):
        return self.ground

    def switch_channel(self, channel):
        self.switched.append(channel)

    def finish_mob_packet_capture(self):
        self.finished_capture.append(True)
        return "probe.jsonl", 12


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
    def test_configured_points_return_without_coverage_scan(self, scan, _load):
        centers = coordinator._resolve_train_mob_centers(
            self.client, 11013, self.tm, stop=lambda: False
        )

        self.assertEqual(centers, [(590, 1010)])
        scan.assert_not_called()
        self.assertEqual(self.client.switched, [])

    @mock.patch.object(coordinator.mob_spots, "load_complete_centers", return_value=None)
    @mock.patch.object(coordinator, "_stationary_train_mob_probe")
    @mock.patch.object(coordinator, "scan_full_map")
    def test_missing_centers_runs_stationary_probe_without_scan(
            self, scan, probe, _load):
        probe.return_value = []
        train_map = {"safe": [], "mobs": []}

        centers = coordinator._resolve_train_mob_centers(
            self.client, 20801, train_map, stop=lambda: False
        )

        self.assertEqual(centers, [])
        probe.assert_called_once_with(self.client, 20801, stop=mock.ANY)
        scan.assert_not_called()

    def test_stationary_probe_switches_channel_waits_and_finishes_capture(self):
        clock = mock.Mock(side_effect=[0.0, 0.0, 30.0, 60.0])
        sleeps = []

        centers = coordinator._stationary_train_mob_probe(
            self.client, 20801, stop=lambda: False, seconds=60,
            clock=clock, sleep=sleeps.append,
        )

        self.assertEqual(centers, [])
        self.assertEqual(self.client.switched, [2])
        self.assertTrue(sleeps)
        self.assertEqual(self.client.finished_capture, [True])

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
