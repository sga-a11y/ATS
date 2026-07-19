import unittest

from bot import config


class TestTrainMapConfig(unittest.TestCase):
    def test_empty_safe_list_stays_empty(self):
        self.assertEqual(config.TRAIN_MAPS[20801]["safe"], [])


if __name__ == "__main__":
    unittest.main()
