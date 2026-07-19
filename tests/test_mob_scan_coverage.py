import math
import unittest

from bot.pathfind import GroundMapStore


class FakeGroundStore(GroundMapStore):
    def __init__(self, grid, width=12, height=10):
        self._maps = {
            99: {
                "width_px": width * 20,
                "height_px": height * 20,
                "grid_w": width,
                "grid_h": height,
                "grid": bytes(grid),
            }
        }
        self.data = b"test-map-entry-v1"
        self.index = {99: (0, len(self.data))}
        # Keep this synthetic grid at world origin zero. Small real maps are
        # covered by the existing centered-map conversion tests.
        self._maps[99]["width_px"] = 800
        self._maps[99]["height_px"] = 600

    def get(self, map_id):
        return self._maps.get(int(map_id))


class TestMobScanCoverage(unittest.TestCase):
    def setUp(self):
        width, height = 12, 10
        cells = bytearray(width * height)
        # Solid wall at block x=7 separates the right side from the start.
        for y in range(1, height + 1):
            cells[(7 - 1) * height + (y - 1)] = 1
        self.store = FakeGroundStore(cells, width, height)

    def test_world_block_round_trip_uses_block_centers(self):
        self.assertEqual(self.store.world_to_block(99, (30, 50)), (2, 3))
        self.assertEqual(self.store.block_to_world(99, (2, 3)), (30, 50))

    def test_coverage_stations_cover_only_start_component(self):
        stations = self.store.coverage_stations(99, (30, 30), (80, 80))

        self.assertTrue(stations)
        self.assertTrue(all(x < 130 for x, _y in stations))
        self.assertTrue(
            all(self.store.find_world_path(99, (30, 30), point) for point in stations)
        )

    def test_coverage_order_is_serpentine(self):
        stations = self.store.coverage_stations(99, (30, 30), (80, 80))
        rows = {}
        for x, y in stations:
            rows.setdefault((y - 1) // 80, []).append(x)

        ordered_rows = [rows[key] for key in sorted(rows)]
        self.assertEqual(ordered_rows[0], sorted(ordered_rows[0]))
        self.assertEqual(ordered_rows[1], sorted(ordered_rows[1], reverse=True))

    def test_nearest_walkable_center_stays_in_reachable_component(self):
        point = self.store.nearest_walkable_world(99, (210, 90), (30, 30))

        self.assertIsNotNone(point)
        self.assertLess(point[0], 130)
        self.assertIsNotNone(self.store.find_world_path(99, (30, 30), point))

    def test_nearest_walkable_outside_patrol_clearance(self):
        hazards = [(90, 90), (110, 90)]

        safe = self.store.nearest_walkable_outside(
            99, (90, 90), hazards, clearance=40, max_path=120
        )

        self.assertIsNotNone(safe)
        self.assertGreaterEqual(min(math.dist(safe, point) for point in hazards), 40)

    def test_nearest_walkable_outside_does_not_cross_wall(self):
        safe = self.store.nearest_walkable_outside(
            99, (110, 90), [(110, 90)], clearance=60, max_path=160
        )

        self.assertIsNotNone(safe)
        self.assertLess(safe[0], 130)

    def test_nearest_walkable_outside_respects_path_limit(self):
        safe = self.store.nearest_walkable_outside(
            99, (90, 90), [(90, 90)], clearance=200, max_path=40
        )

        self.assertIsNone(safe)

    def test_map_fingerprint_changes_with_map_blob(self):
        before = self.store.map_fingerprint(99)
        self.store.data = self.store.data[:-1] + bytes([self.store.data[-1] ^ 1])

        self.assertNotEqual(before, self.store.map_fingerprint(99))


if __name__ == "__main__":
    unittest.main()
