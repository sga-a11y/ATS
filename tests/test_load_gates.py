import unittest, json, os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLoadGates(unittest.TestCase):
    def test_load(self):
        from bot.config import _load_map_gates  # ham moi
        d = {"maps": {"12831": {"gates": [{"x": 310, "y": 1530, "to": 11804}]}}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(d, f); path = f.name
        g = _load_map_gates(path)
        self.assertEqual(g[12831], [(310, 1530, 11804)])
        os.unlink(path)

    def test_missing_file(self):
        from bot.config import _load_map_gates
        self.assertEqual(_load_map_gates("E:/khong/ton/tai.json"), {})


if __name__ == "__main__":
    unittest.main()
