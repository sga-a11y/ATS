import sys
import unittest
from unittest import mock

_argv = sys.argv
try:
    sys.argv = ["run_party_digioi.py"]
    import run_party_digioi as coordinator
finally:
    sys.argv = _argv


class Ground:
    def __init__(self):
        self.projected = []

    def map_fingerprint(self, _map_id):
        return "ground1"

    def nearest_walkable_world(self, map_id, point, reachable_from):
        self.projected.append((map_id, point, reachable_from))
        return 4120, 2520


class Client:
    def __init__(self):
        self.current_map = 20801
        self.pos = (4110, 2510)
        self.ground = Ground()
        self._label = "test"

    def get_ground_store(self):
        return self.ground


class TestTrainSafePolicy(unittest.TestCase):
    def setUp(self):
        self.client = Client()

    @mock.patch.object(coordinator.mob_spots, "load_safe", return_value=(4100, 2500))
    def test_resolve_prefers_fingerprint_valid_cached_safe(self, _load):
        safe = coordinator._resolve_train_safe(
            self.client, 20801, [(100, 200)]
        )

        self.assertEqual(safe, (4100, 2500))

    @mock.patch.object(coordinator.mob_spots, "load_safe", return_value=None)
    def test_resolve_falls_back_to_configured_safe(self, _load):
        safe = coordinator._resolve_train_safe(
            self.client, 20801, [(100, 200), (300, 400)]
        )

        self.assertEqual(safe, (300, 400))

    @mock.patch.object(coordinator.mob_spots, "save_safe")
    def test_capture_projects_and_saves_actual_arrival(self, save):
        safe = coordinator._capture_arrival_safe(
            self.client, 20801, came_from_other_map=True
        )

        self.assertEqual(safe, (4120, 2520))
        self.assertEqual(
            self.client.ground.projected,
            [(20801, (4110, 2510), (4110, 2510))],
        )
        save.assert_called_once_with(20801, "ground1", (4120, 2520))

    @mock.patch.object(coordinator.mob_spots, "save_safe")
    def test_login_on_target_map_does_not_overwrite_safe(self, save):
        safe = coordinator._capture_arrival_safe(
            self.client, 20801, came_from_other_map=False
        )

        self.assertIsNone(safe)
        save.assert_not_called()

    def test_login_on_target_map_without_safe_requires_bootstrap(self):
        self.assertTrue(
            coordinator._needs_train_safe_bootstrap(20801, 20801, [])
        )

    def test_known_safe_or_other_login_map_skips_bootstrap(self):
        self.assertFalse(
            coordinator._needs_train_safe_bootstrap(
                20801, 20801, [(4120, 2520)]
            )
        )
        self.assertFalse(
            coordinator._needs_train_safe_bootstrap(12001, 20801, [])
        )


if __name__ == "__main__":
    unittest.main()
