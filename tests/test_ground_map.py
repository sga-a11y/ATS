import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.ground_map import (
    block_to_world,
    block_value,
    center_offset,
    is_obstacle,
    is_sea,
    list_maps,
    world_to_block,
)


class TestGroundMap(unittest.TestCase):
    def test_index_maps_name_to_offset_and_size(self):
        name = b"12831.map"
        entry = bytes([len(name)]) + name + b"x" * 11 + struct.pack("<II", 1234, 567)
        data = b"map data" + entry

        self.assertEqual(list_maps(data), {"12831.map": (1234, 567)})

    def test_grid_is_x_major_and_one_based(self):
        # x=1 contains 10,11,12; x=2 contains 20,21,22.
        m = {"grid_w": 2, "grid_h": 3, "grid": bytes([10, 11, 12, 20, 21, 22])}

        self.assertEqual(block_value(m, 1, 3), 12)
        self.assertEqual(block_value(m, 2, 1), 20)
        self.assertIsNone(block_value(m, 0, 1))

    def test_collision_bits_match_lua(self):
        self.assertFalse(is_obstacle(0))
        self.assertTrue(is_obstacle(1))
        self.assertFalse(is_obstacle(2))
        self.assertTrue(is_obstacle(4))
        self.assertTrue(is_obstacle(None))
        self.assertTrue(is_sea(2))
        self.assertTrue(is_sea(3))

    def test_world_block_conversion_matches_lua(self):
        self.assertEqual(center_offset(640, 480), (80, 60))
        self.assertEqual(world_to_block((90, 70), 80, 60), (1, 1))
        self.assertEqual(block_to_world((1, 1), 80, 60), (90, 70))


if __name__ == "__main__":
    unittest.main()
