import json
import os
import tempfile
import unittest
from unittest.mock import patch

import bot.client as client_module


class TestItemDataLoading(unittest.TestCase):
    def setUp(self):
        self.old_known = client_module._known_items
        self.old_gamedata = client_module._gamedata_items
        client_module._known_items = None
        client_module._gamedata_items = None
        self.addCleanup(self._restore)

    def _restore(self):
        client_module._known_items = self.old_known
        client_module._gamedata_items = self.old_gamedata

    def test_gamedata_items_fall_back_to_android_asset(self):
        payload = json.dumps({
            "0xb3d6": {"name": "Dai Phuc Than", "battle": False, "hp": 0, "sp": 0}
        })

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                with patch("bot._appdir.app_dir", return_value=tmp), \
                        patch.object(client_module.config, "_read_asset", return_value=payload, create=True):
                    items = client_module._load_gamedata_items()
            finally:
                os.chdir(cwd)

        self.assertEqual(items[0xB3D6]["name"], "Dai Phuc Than")

    def test_known_items_fall_back_to_android_asset(self):
        payload = json.dumps({
            "items": {
                "0xff8c": {"name": "Di Gioi Ho Phu", "type": "use", "hp": 0, "sp": 0}
            }
        })

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                with patch("bot._appdir.app_dir", return_value=tmp), \
                        patch.object(client_module.config, "_read_asset", return_value=payload, create=True):
                    items = client_module._load_known_items()
            finally:
                os.chdir(cwd)

        self.assertEqual(items[0xFF8C]["name"], "Di Gioi Ho Phu")


if __name__ == "__main__":
    unittest.main()
