import ast
import unittest
from unittest.mock import patch

from bot import client as client_module
from bot import config


SUPER_GEM = 0x5AAB
GREAT_GEM = 0x5A2D
GREAT_BAG = 0xB5F4
GREAT_BLESSING = 0xB3D6
BLESSING = 0xB3D5
EXPECTED_PRIORITY = (
    (SUPER_GEM, "equip"),
    (GREAT_GEM, "equip"),
    (GREAT_BAG, "use"),
)


class TestPhucThanPriority(unittest.TestCase):
    def _run_items(self, bag_slots):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.bag_slots = {slot: [tid, count] for slot, (tid, count) in bag_slots.items()}
        game.running = True
        game._label = "test"
        equip_calls = []
        use_calls = []

        def equip_item(slot):
            equip_calls.append(slot)
            return True

        def use_slot(slot, qty=1, target=0):
            use_calls.append((slot, qty, target))
            return True

        game.equip_item = equip_item
        game.use_slot = use_slot
        phuc_than_cfg = {
            tid: value
            for tid, value in config.USE_LOGIN_ITEMS.items()
            if value.get("phuc_than")
        }
        with patch.object(client_module, "_load_gamedata_items", return_value={}), patch.object(
            client_module.time, "sleep", return_value=None
        ):
            game._use_items_from_cfg(phuc_than_cfg, "test")
        return equip_calls, use_calls

    def test_super_gem_wins_over_great_gem_and_bag(self):
        equip, used = self._run_items(
            {1: (GREAT_BAG, 2), 2: (GREAT_GEM, 1), 3: (SUPER_GEM, 1)}
        )
        self.assertEqual(equip, [3])
        self.assertEqual(used, [])

    def test_great_gem_wins_over_bag(self):
        equip, used = self._run_items({1: (GREAT_BAG, 2), 2: (GREAT_GEM, 1)})
        self.assertEqual(equip, [2])
        self.assertEqual(used, [])

    def test_bag_is_used_once_when_both_gems_are_missing(self):
        equip, used = self._run_items({4: (GREAT_BAG, 5)})
        self.assertEqual(equip, [])
        self.assertEqual(used, [(4, 1, 0)])

    def test_no_protective_item_performs_no_action(self):
        equip, used = self._run_items({})
        self.assertEqual(equip, [])
        self.assertEqual(used, [])

    def test_normal_blessings_still_run_but_bag_is_skipped_when_gem_exists(self):
        equip, used = self._run_items(
            {
                1: (GREAT_BAG, 3),
                2: (SUPER_GEM, 1),
                3: (GREAT_BLESSING, 5),
                4: (BLESSING, 7),
            }
        )
        self.assertEqual(equip, [2])
        self.assertEqual(used, [(3, 5, 0), (4, 7, 0)])

    def test_desktop_and_android_define_the_same_priority(self):
        def read_priority(path):
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    if any(
                        isinstance(target, ast.Name)
                        and target.id == "PHUC_THAN_PROTECTION_PRIORITY"
                        for target in node.targets
                    ):
                        return ast.literal_eval(node.value)
            return None

        self.assertEqual(read_priority("bot/client.py"), EXPECTED_PRIORITY)
        self.assertEqual(
            read_priority("android/app/src/main/python/train_bot/client.py"),
            EXPECTED_PRIORITY,
        )


if __name__ == "__main__":
    unittest.main()
