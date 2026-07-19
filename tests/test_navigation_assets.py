import os
import tempfile
import unittest

from bot import config
from build_product import DATA_FILES, DATA_JSON, validate_navigation_assets


class TestNavigationAssets(unittest.TestCase):
    def test_development_navigation_assets_exist(self):
        self.assertTrue(os.path.isfile(config.WORLD_NAV_PATH))
        self.assertTrue(os.path.isfile(config.GROUND_MAP_PATH))

    def test_desktop_build_lists_navigation_assets(self):
        self.assertIn("world_nav.json", DATA_JSON)
        self.assertEqual(
            DATA_FILES["gamedata/Ground.mmg"],
            "gamedata/Ground.mmg",
        )

    def test_missing_assets_report_explicit_names(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError) as caught:
                validate_navigation_assets(root)
        message = str(caught.exception)
        self.assertIn("world_nav.json", message)
        self.assertIn("gamedata/Ground.mmg", message)

    def test_android_build_packages_and_enables_navigation_assets(self):
        with open("android/app/build.gradle.kts", encoding="utf-8") as fh:
            gradle = fh.read()
        with open(
            "android/app/src/main/python/train_bot/config.py", encoding="utf-8"
        ) as fh:
            android_config = fh.read()
        with open(
            "android/app/src/main/java/com/tsbot/android/BotForegroundService.kt",
            encoding="utf-8",
        ) as fh:
            service = fh.read()

        self.assertIn("prepareSmartNavAssets", gradle)
        self.assertIn("world_nav.json", gradle)
        self.assertIn("gamedata/Ground.mmg", gradle)
        self.assertIn("train_maps.json", gradle)
        self.assertIn("from(trainMaps)", gradle)
        self.assertIn("SMART_WORLD_ROUTING = True", android_config)
        self.assertIn("WORLD_NAV_PATH", android_config)
        self.assertIn("GROUND_MAP_PATH", android_config)
        self.assertIn("materializeSmartNavAssets()", service)


if __name__ == "__main__":
    unittest.main()
