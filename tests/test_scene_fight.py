import os
import struct
import tempfile
import unittest

from bot.scene_fight import load_scene_fight


class TestSceneFight(unittest.TestCase):
    def test_reads_map_seed_and_level_range(self):
        record = (
            bytes(5)
            + struct.pack("<HHHH", 20801, 3990, 2490, 80)
            + struct.pack("<H", 86)
            + bytes(10)
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "SceneFight_C.dat")
            with open(path, "wb") as fh:
                fh.write(struct.pack("<I", 1) + record)

            entries = load_scene_fight(path)

        self.assertEqual(entries[20801].point, (3990, 2490))
        self.assertEqual(entries[20801].level_range, (80, 86))

    def test_real_asset_contains_hap_coc_seed(self):
        entries = load_scene_fight("gamedata/SceneFight_C.dat")

        self.assertEqual(entries[20801].point, (3990, 2490))


if __name__ == "__main__":
    unittest.main()
