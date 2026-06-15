import unittest, struct, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.decode_warp import parse_warp


class TestDecodeWarp(unittest.TestCase):
    def test_parse_two_records(self):
        # header=2, roi 2 record 16B: [id u32][src u16][dst u16][x u32][y u32]
        blob = struct.pack("<I", 2)
        blob += struct.pack("<IHHII", 21699, 12001, 11804, 310, 1530)
        blob += struct.pack("<IHHII", 21701, 12061, 11806, 160, 900)
        rows = parse_warp(blob)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"id": 21699, "src": 12001, "dst": 11804, "x": 310, "y": 1530})
        self.assertEqual(rows[1]["src"], 12061)


if __name__ == "__main__":
    unittest.main()
