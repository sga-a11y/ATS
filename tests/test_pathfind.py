import unittest, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.pathfind import find_path

# graph: map_id -> [(x,y,to)]
G = {
    12001: [(310, 1530, 11804)],
    11804: [(50, 60, 12831), (70, 80, 11805)],
    12831: [],
}


class TestFindPath(unittest.TestCase):
    def test_same_map_empty(self):
        self.assertEqual(find_path(G, 12831, 12831), [])

    def test_two_hops(self):
        self.assertEqual(find_path(G, 12001, 12831),
                         [(310, 1530, 11804), (50, 60, 12831)])

    def test_no_path(self):
        self.assertIsNone(find_path(G, 12831, 12001))

    def test_unknown_src(self):
        self.assertIsNone(find_path(G, 99999, 12831))


if __name__ == "__main__":
    unittest.main()
