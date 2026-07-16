import unittest, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.pathfind import GroundMapStore, find_local_path, find_path, is_line_clear

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


class TestLocalPath(unittest.TestCase):
    def test_direct_route_is_single_smoothed_segment(self):
        grid = bytes(5 * 5)
        self.assertEqual(find_local_path(grid, 5, 5, (1, 1), (5, 5)),
                         [(1, 1), (5, 5)])

    def test_astar_routes_around_wall_and_never_crosses_it(self):
        # X-major grid; wall at x=3 with a gap at y=5.
        cells = bytearray(5 * 5)
        for y in range(1, 5):
            cells[(3 - 1) * 5 + (y - 1)] = 1
        path = find_local_path(bytes(cells), 5, 5, (1, 2), (5, 2))

        self.assertIsNotNone(path)
        self.assertEqual(path[0], (1, 2))
        self.assertEqual(path[-1], (5, 2))
        self.assertTrue(any(y == 5 for _, y in path))
        for a, b in zip(path, path[1:]):
            self.assertTrue(is_line_clear(bytes(cells), 5, 5, a, b))

    def test_blocked_target_uses_adjacent_empty_block(self):
        cells = bytearray(3 * 3)
        cells[(2 - 1) * 3 + (2 - 1)] = 1
        self.assertEqual(find_local_path(bytes(cells), 3, 3, (1, 1), (2, 2))[-1],
                         (2, 1))

    def test_blocked_start_has_no_path(self):
        cells = bytearray(2 * 2)
        cells[0] = 1
        self.assertIsNone(find_local_path(bytes(cells), 2, 2, (1, 1), (2, 2)))


if __name__ == "__main__":
    unittest.main()
