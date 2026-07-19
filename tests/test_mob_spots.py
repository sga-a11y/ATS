import json
import os
import tempfile
import unittest
from unittest import mock

from bot import mob_spots


class TestMobSpotsCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "mob_spots.json")
        self.path_patch = mock.patch.object(mob_spots, "_path", return_value=self.path)
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def test_complete_round_trip_is_center_only(self):
        mob_spots.save_complete(
            11013, "abc12345", [(530, 930), (1150, 530)],
            coverage={"visited": 12, "total": 12, "completed": list(range(12))},
            settings={"stride": [320, 240]},
        )

        self.assertEqual(
            mob_spots.load_complete_centers(11013, "abc12345"),
            [(530, 930), (1150, 530)],
        )
        with open(self.path, encoding="utf-8") as fh:
            saved_map = json.load(fh)["maps"]["11013"]
        self.assertEqual(set(saved_map), {
            "fingerprint", "status", "updated_at", "coverage", "settings", "centers"
        })
        self.assertEqual(saved_map["centers"], [[530, 930], [1150, 530]])
        serialized = json.dumps(saved_map)
        for forbidden in ("entity", "waypoint", "polygon", "bounds", "trace"):
            self.assertNotIn(forbidden, serialized.lower())

    def test_changed_fingerprint_invalidates_complete_centers(self):
        mob_spots.save_complete(11013, "old00000", [(530, 930)], {}, {})

        self.assertIsNone(mob_spots.load_complete_centers(11013, "new00000"))
        self.assertEqual(mob_spots.load_progress(11013, "new00000"), {})

    def test_incomplete_progress_is_not_a_complete_result(self):
        mob_spots.save_progress(
            11013, "abc12345", [0, 2], [(530, 930)],
            coverage={"visited": 2, "total": 8}, settings={"stride": [320, 240]},
        )

        self.assertIsNone(mob_spots.load_complete_centers(11013, "abc12345"))
        progress = mob_spots.load_progress(11013, "abc12345")
        self.assertEqual(progress["coverage"]["completed"], [0, 2])
        self.assertEqual(progress["centers"], [[530, 930]])

    def test_empty_scan_is_retryable_not_a_complete_result(self):
        mob_spots.save_complete(20801, "ground1", [], {"visited": 124}, {})

        self.assertIsNone(mob_spots.load_complete_centers(20801, "ground1"))
        self.assertEqual(
            mob_spots.load_progress(20801, "ground1")["status"],
            "empty",
        )

    def test_write_uses_atomic_replace_without_leaving_tmp(self):
        mob_spots.save_complete(11013, "abc12345", [(530, 930)], {}, {})

        self.assertTrue(os.path.isfile(self.path))
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_safe_round_trip_survives_incomplete_scan(self):
        mob_spots.save_safe(20801, "ground1", (4110, 2510))
        mob_spots.save_progress(
            20801, "ground1", [0], [], {"total": 2}, {}
        )

        self.assertEqual(
            mob_spots.load_safe(20801, "ground1"),
            (4110, 2510),
        )

    def test_changed_fingerprint_invalidates_safe(self):
        mob_spots.save_safe(20801, "ground1", (4110, 2510))

        self.assertIsNone(mob_spots.load_safe(20801, "ground2"))


if __name__ == "__main__":
    unittest.main()
