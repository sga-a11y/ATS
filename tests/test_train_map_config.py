import json
import ast
import math
import os
import tempfile
import unittest
from unittest import mock

from bot import config


class TestTrainMapConfig(unittest.TestCase):
    def test_android_train_mob_loader_uses_numeric_map_id(self):
        path = (
            "android/app/src/main/java/com/tsbot/android/MainActivity.kt"
        )
        with open(path, encoding="utf-8") as fh:
            source = fh.read()

        start = source.index("fun trainMobOptions")
        end = source.index("\n}", start)
        body = source[start:end]

        self.assertIn("mapKey.toIntOrNull()", body)
        self.assertIn('maps.callAttr("get", mapId)', body)

    def test_rung_cuu_nguyen_has_promoted_safe_and_mob_centers(self):
        maps = config._load_train_maps()

        entry = maps[20801]
        self.assertEqual(len(entry["safe"]), len(entry["mobs"]))
        self.assertEqual(len(entry["mobs"]), 10)
        self.assertIn((1150, 1710), entry["mobs"])
        self.assertTrue(all(
            math.dist(safe, mob) <= 600
            for safe, mob in zip(entry["safe"], entry["mobs"])
        ))

    def test_empty_safe_list_stays_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "train_maps.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"maps": {"999": {"safe": [], "mobs": []}}}, fh)
            with mock.patch.object(config, "TRAIN_MAPS_PATH", path):
                maps = config._load_train_maps()

        self.assertEqual(maps[999]["safe"], [])

    def test_android_loader_uses_integer_keys_and_empty_safe(self):
        path = "android/app/src/main/python/train_bot/config.py"
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        loader = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_load_train_maps"
        )
        calls = []
        namespace = {
            "json": json,
            "_read_asset": lambda _name: json.dumps({
                "maps": {"999": {"safe": [], "mobs": []}}
            }),
            "TRAIN_MAPS_PATH": "app/train_maps.json",
            "materialize_train_maps": lambda path, baseline: (
                calls.append((path, baseline)) or baseline
            ),
            "_log_asset_error": lambda *_args: None,
        }
        exec(compile(ast.Module(body=[loader], type_ignores=[]), path, "exec"), namespace)

        maps = namespace["_load_train_maps"]()

        self.assertEqual(maps, {999: {"safe": [], "mobs": []}})
        self.assertEqual(calls[0][0], "app/train_maps.json")

    def test_android_static_data_loaders_read_bundled_assets(self):
        path = "android/app/src/main/python/train_bot/config.py"
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }

        for name in (
            "_load_train_routes",
            "_load_events",
            "_load_json_root",
            "_load_pets",
            "_load_npc_names",
            "_load_skill_info",
            "_load_donate_items",
            "_load_use_items",
            "_load_servers",
        ):
            with self.subTest(loader=name):
                self.assertIn("_read_asset", ast.unparse(functions[name]))

    def test_pc_config_exposes_writable_train_maps_path(self):
        self.assertTrue(config.TRAIN_MAPS_PATH.endswith("train_maps.json"))


if __name__ == "__main__":
    unittest.main()
