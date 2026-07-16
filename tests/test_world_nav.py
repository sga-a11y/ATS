import unittest

from bot.world_nav import WorldNavStore


class TestWorldNavStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nav = WorldNavStore("world_nav.json")

    def test_hap_coc_uses_truong_an(self):
        best = self.nav.rank_cities(14821)[0]
        self.assertEqual((best["city"], best["flag"]), (14001, 6))
        self.assertEqual(
            [
                (leg["scene"], leg["door"], leg["target_scene"])
                for leg in best["legs"]
            ],
            [(14001, 1, 22000), (22000, 17, 14821)],
        )

    def test_unknown_destination_returns_empty(self):
        self.assertEqual(self.nav.rank_cities(999999), [])

    def test_get_gate(self):
        self.assertEqual(
            self.nav.get_gate(22000, 17)["center"],
            [560, 2510],
        )


if __name__ == "__main__":
    unittest.main()
