import sys
import unittest
from unittest import mock

from bot.mob_scanner import CenterCandidate, LearnedRegion, ScanResult

_argv = sys.argv
try:
    sys.argv = ["run_party_digioi.py"]
    import run_party_digioi as coordinator
finally:
    sys.argv = _argv


class Ground:
    def map_fingerprint(self, _map_id):
        return "abc12345"

    def nearest_walkable_world(self, _map_id, point, _start):
        return point


class Client:
    def __init__(self):
        self.ground = Ground()
        self.current_channel = 2
        self.current_map = 20801
        self.pos = (4110, 2510)
        self.self_entity = b"leader00"
        self.switched = []
        self.running = True
        self.finished_capture = []
        self.events = []

    def get_ground_store(self):
        return self.ground

    def switch_channel(self, channel):
        self.events.append("switch")
        self.switched.append(channel)

    def known_party_entities(self):
        return {b"leader00", b"member00"}

    def begin_mob_observation(self, observer):
        self.events.append("begin")
        self.observer = observer

    def end_mob_observation(self, observer):
        self.events.append("end")
        self.observer = None

    def navigate_to(self, x, y, **_kwargs):
        self.events.append(("navigate", x, y))
        self.pos = (x, y)
        return True

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
    def test_empty_train_map_requires_probe_even_when_old_cache_exists(self, load):
        load.return_value = [(530, 930)]

        needed = coordinator._needs_train_mob_probe(
            self.client, 20801, {"safe": [], "mobs": []}
        )

        self.assertTrue(needed)
        load.assert_not_called()

    @mock.patch.object(coordinator.mob_spots, "load_complete_centers")
    @mock.patch.object(coordinator, "scan_full_map")
    def test_configured_points_ignore_old_center_cache(self, scan, load):
        load.return_value = [(530, 930), (1150, 530)]

        centers = coordinator._resolve_train_mob_centers(
            self.client, 11013, self.tm, stop=lambda: False
        )

        self.assertEqual(centers, [(590, 1010)])
        load.assert_not_called()
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

    @mock.patch.object(coordinator.mob_spots, "load_complete_centers")
    @mock.patch.object(coordinator, "_stationary_train_mob_probe")
    @mock.patch.object(coordinator, "scan_full_map")
    def test_empty_train_map_retrains_even_when_old_center_cache_exists(
            self, scan, probe, load):
        load.return_value = [(530, 930), (1150, 530)]
        probe.return_value = []
        train_map = {"safe": [], "mobs": []}

        centers = coordinator._resolve_train_mob_centers(
            self.client, 20801, train_map, stop=lambda: False
        )

        self.assertEqual(centers, [])
        probe.assert_called_once_with(
            self.client, 20801, train_map=train_map, stop=mock.ANY
        )
        load.assert_not_called()
        scan.assert_not_called()

    @mock.patch.object(coordinator, "save_learned_regions", return_value=True)
    @mock.patch.object(coordinator.mob_spots, "save_complete")
    @mock.patch.object(coordinator, "compute_regions")
    @mock.patch.object(coordinator, "get_scene_fight_seed", return_value=(3990, 2490))
    def test_stationary_probe_promotes_aligned_regions_to_train_map(
            self, _seed, compute, save_cache, save_train_maps):
        compute.return_value = [
            LearnedRegion(CenterCandidate((3910, 2470), 2, 0.8), (3710, 2470)),
            LearnedRegion(CenterCandidate((2910, 1470), 1, 0.7), (2710, 1470)),
        ]
        train_map = {"safe": [(4050, 2430)], "mobs": []}
        clock = mock.Mock(side_effect=[0.0, 0.0, 30.0, 60.0])
        sleeps = []

        centers = coordinator._stationary_train_mob_probe(
            self.client, 20801, train_map=train_map, stop=lambda: False, seconds=60,
            clock=clock, sleep=sleeps.append,
        )

        self.assertEqual(centers, [(3910, 2470), (2910, 1470)])
        self.assertEqual(train_map["safe"], [(3710, 2470), (2710, 1470)])
        self.assertEqual(train_map["mobs"], centers)
        save_train_maps.assert_called_once_with(
            coordinator.config.TRAIN_MAPS_PATH,
            20801,
            train_map["safe"],
            centers,
        )
        self.assertEqual(self.client.events[:3], ["begin", "switch", ("navigate", 3990, 2490)])
        self.assertEqual(self.client.events[-1], "end")
        self.assertEqual(self.client.switched, [2])
        self.assertTrue(sleeps)
        self.assertEqual(self.client.finished_capture, [True])
        save_cache.assert_not_called()

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
