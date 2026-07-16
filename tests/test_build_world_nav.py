import json
import struct
import unittest

from tools.build_world_nav import parse_door_graph, parse_eve_doors, parse_warps


class TestWorldNavBuilder(unittest.TestCase):
    def test_parse_warp_record(self):
        raw = struct.pack("<iIHHii", 1, 21707, 14001, 11810, 770, 610)
        self.assertEqual(parse_warps(raw, {14001: 6}), [{
            "city": 14001,
            "flag": 6,
            "mark": 11810,
            "arrival": [770, 610],
            "name_id": 21707,
        }])

    def test_skips_warp_without_known_flag(self):
        raw = struct.pack("<iIHHii", 1, 21715, 57001, 12224, 1050, 750)
        self.assertEqual(parse_warps(raw, {}), [])

    def test_parse_door_edge(self):
        raw = struct.pack("<iBiB4B", 14001, 1, 22000, 1, 1, 2, 1, 1)
        self.assertEqual(parse_door_graph(raw), [{
            "from": 14001001,
            "to": 22000001,
            "scene": 14001,
            "target_scene": 22000,
            "door": 1,
            "priority": 2,
        }])

    def test_parse_door_center_from_minimal_event(self):
        raw = (
            struct.pack("<iHHHH", 0, 0, 1, 17, 1)
            + b"\x06"
            + struct.pack("<iiiiBHHB", 26, 122, 6, 9, 1, 606, 2429, 0)
        )
        self.assertEqual(parse_eve_doors(raw, 0)[17]["center"], [560, 2510])

    def test_generated_asset_has_hap_coc_gate(self):
        try:
            with open("world_nav.json", encoding="utf-8") as fh:
                nav = json.load(fh)
        except FileNotFoundError:
            self.skipTest("world_nav.json has not been generated yet")
        self.assertEqual(nav["gates"]["22000"]["17"]["center"], [560, 2510])


if __name__ == "__main__":
    unittest.main()
