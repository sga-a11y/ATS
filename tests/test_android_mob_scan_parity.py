import ast
import os
import unittest


KEYS = (
    "MOB_SCAN_ENABLED",
    "MOB_SCAN_STATION_STRIDE",
    "MOB_SCAN_QUIET_SECONDS",
    "MOB_SCAN_STATION_TIMEOUT",
    "MOB_SCAN_MIN_SAMPLES",
    "MOB_SCAN_MAX_PATROL_DIAMETER",
    "MOB_SCAN_MERGE_DISTANCE",
    "MOB_SCAN_SECOND_PASS",
    "MOB_PACKET_PROBE_SECONDS",
    "MOB_PACKET_CAPTURE_MAX_PACKETS",
)


def constants(path):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in KEYS:
            values[node.targets[0].id] = ast.literal_eval(node.value)
    return values


class TestAndroidMobScanParity(unittest.TestCase):
    def test_pc_and_android_scan_defaults_match(self):
        desktop = constants("bot/config.py")
        android = constants("android/app/src/main/python/train_bot/config.py")

        self.assertEqual(set(desktop), set(KEYS))
        self.assertEqual(android, desktop)

    def test_android_contains_shared_scanner_cache_and_packet_hook(self):
        for name in ("mob_scanner.py", "mob_spots.py", "scene_fight.py", "smart_route.py", "client.py"):
            self.assertTrue(os.path.isfile(
                os.path.join("android/app/src/main/python/train_bot", name)
            ))
        with open("android/app/src/main/python/train_bot/run_party_digioi.py", encoding="utf-8") as fh:
            coordinator = fh.read()
        self.assertIn("_resolve_train_mob_centers", coordinator)
        self.assertIn("_resolve_train_safe", coordinator)
        self.assertIn("_capture_arrival_safe", coordinator)
        self.assertIn("_stationary_train_mob_probe", coordinator)
        self.assertIn("from .mob_scanner import MobScanSession", coordinator)
        self.assertIn("from .scene_fight import get_scene_fight_seed", coordinator)
        self.assertIn("from . import mob_spots", coordinator)
        with open("android/app/src/main/python/train_bot/mob_spots.py", encoding="utf-8") as fh:
            cache = fh.read()
        self.assertIn("def load_safe", cache)
        self.assertIn("def save_safe", cache)
        with open("android/app/src/main/python/train_bot/client.py", encoding="utf-8") as fh:
            client = fh.read()
        self.assertIn("def arm_mob_packet_capture", client)
        self.assertIn("def finish_mob_packet_capture", client)
        with open("android/app/src/main/python/train_bot/smart_route.py", encoding="utf-8") as fh:
            routing = fh.read()
        self.assertIn("safe is None", routing)
        with open("android/app/src/main/python/train_bot/config.py", encoding="utf-8") as fh:
            android_config = fh.read()
        self.assertIn("SCENE_FIGHT_PATH", android_config)


if __name__ == "__main__":
    unittest.main()
