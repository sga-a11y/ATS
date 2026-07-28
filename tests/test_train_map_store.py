import json
import os
import tempfile
import unittest

from bot.train_maps_store import merge_baseline, save_learned_regions


class TestTrainMapStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "train_maps.json")

    def write(self, data):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def read(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_save_regions_preserves_name_and_other_maps(self):
        self.write({
            "maps": {
                "20801": {"name": "RCN1", "safe": [], "mobs": []},
                "99": {"name": "keep", "safe": [], "mobs": []},
            }
        })

        saved = save_learned_regions(
            self.path, 20801, [(100, 200)], [(300, 400)]
        )
        data = self.read()

        self.assertTrue(saved)
        self.assertEqual(data["maps"]["20801"]["name"], "RCN1")
        self.assertEqual(data["maps"]["20801"]["safe"], [[100, 200]])
        self.assertEqual(data["maps"]["20801"]["mobs"], [[300, 400]])
        self.assertIn("99", data["maps"])
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_nonempty_configured_mobs_are_not_overwritten(self):
        self.write({
            "maps": {
                "20801": {"safe": [[1, 2]], "mobs": [[3, 4]]},
            }
        })

        saved = save_learned_regions(
            self.path, 20801, [(10, 20)], [(30, 40)]
        )

        self.assertFalse(saved)
        self.assertEqual(self.read()["maps"]["20801"]["mobs"], [[3, 4]])

    def test_mismatched_pairs_are_rejected(self):
        self.write({"maps": {"20801": {"safe": [], "mobs": []}}})

        saved = save_learned_regions(
            self.path, 20801, [(10, 20)], [(30, 40), (50, 60)]
        )

        self.assertFalse(saved)
        self.assertEqual(self.read()["maps"]["20801"]["mobs"], [])

    def test_merge_preserves_local_learning_and_adds_new_baseline_maps(self):
        baseline = {
            "maps": {
                "1": {"name": "base", "safe": [[1, 1]], "mobs": [[2, 2]]},
                "2": {"name": "new", "safe": [[3, 3]], "mobs": [[4, 4]]},
            }
        }
        local = {
            "maps": {
                "1": {"name": "old", "safe": [[10, 10]], "mobs": [[20, 20]]},
                "3": {"name": "local", "safe": [[30, 30]], "mobs": [[40, 40]]},
            }
        }

        merged = merge_baseline(baseline, local)

        self.assertEqual(merged["maps"]["1"]["mobs"], [[20, 20]])
        self.assertEqual(merged["maps"]["1"]["name"], "base")
        self.assertIn("2", merged["maps"])
        self.assertIn("3", merged["maps"])

    def test_merge_repairs_old_safe_list_when_mobs_match_baseline(self):
        baseline = {
            "maps": {
                "20801": {
                    "name": "RCN1",
                    "safe": [[100, 100], [300, 300]],
                    "mobs": [[200, 200], [400, 400]],
                }
            }
        }
        local = {
            "maps": {
                "20801": {
                    "name": "old",
                    "safe": [[1, 1]],
                    "mobs": [[200, 200], [400, 400]],
                }
            }
        }

        merged = merge_baseline(baseline, local)

        self.assertEqual(merged["maps"]["20801"], baseline["maps"]["20801"])

    def test_merge_treats_default_group_as_unset(self):
        baseline = {
            "maps": {
                "20801": {
                    "name": "RCN1",
                    "safe": [[100, 100]],
                    "mobs": [[200, 200]],
                    "group": "Kinh Bắc",
                }
            }
        }
        local = {
            "maps": {
                "20801": {
                    "name": "old",
                    "safe": [[10, 10]],
                    "mobs": [[20, 20]],
                    "group": "Chưa phân nhóm",
                }
            }
        }

        merged = merge_baseline(baseline, local)

        self.assertEqual(merged["maps"]["20801"]["mobs"], [[20, 20]])
        self.assertEqual(merged["maps"]["20801"]["group"], "Kinh Bắc")

    def test_merge_can_prefer_baseline_for_apk_assets(self):
        baseline = {
            "maps": {
                "20801": {
                    "name": "RCN1",
                    "safe": [[100, 100]],
                    "mobs": [[200, 200]],
                    "group": "Kinh Bắc",
                }
            }
        }
        local = {
            "maps": {
                "20801": {
                    "name": "old",
                    "safe": [[10, 10]],
                    "mobs": [[20, 20]],
                    "group": "User Group",
                },
                "999": {
                    "name": "local only",
                    "safe": [[1, 1]],
                    "mobs": [[2, 2]],
                    "group": "Local",
                },
            }
        }

        merged = merge_baseline(baseline, local, prefer_baseline_existing=True)

        self.assertEqual(merged["maps"]["20801"], baseline["maps"]["20801"])
        self.assertEqual(merged["maps"]["999"], local["maps"]["999"])


if __name__ == "__main__":
    unittest.main()
