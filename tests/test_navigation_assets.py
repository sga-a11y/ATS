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


if __name__ == "__main__":
    unittest.main()
