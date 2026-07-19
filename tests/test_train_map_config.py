import json
import ast
import os
import tempfile
import unittest
from unittest import mock

from bot import config


class TestTrainMapConfig(unittest.TestCase):
    def test_empty_safe_list_stays_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "train_maps.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"maps": {"999": {"safe": [], "mobs": []}}}, fh)
            with mock.patch.object(config, "_base_dir", return_value=directory):
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
        namespace = {
            "json": json,
            "_read_asset": lambda _name: json.dumps({
                "maps": {"999": {"safe": [], "mobs": []}}
            }),
            "_log_asset_error": lambda *_args: None,
        }
        exec(compile(ast.Module(body=[loader], type_ignores=[]), path, "exec"), namespace)

        maps = namespace["_load_train_maps"]()

        self.assertEqual(maps, {999: {"safe": [], "mobs": []}})


if __name__ == "__main__":
    unittest.main()
