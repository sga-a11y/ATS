import json
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


if __name__ == "__main__":
    unittest.main()
