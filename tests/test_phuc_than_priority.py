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
BROKEN_GEM = 0x59F0
EXPECTED_PRIORITY = (
    (SUPER_GEM, "equip"),
    (GREAT_GEM, "equip"),
    (GREAT_BAG, "use"),
)


class TestPhucThanPriority(unittest.TestCase):
    def _run_items(self, bag_slots, equipped=None):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.bag_slots = {slot: [tid, count] for slot, (tid, count) in bag_slots.items()}
        game.equipped_items = list(equipped or [])
        game.running = True
        game._label = "test"
        game.sock = None           # discard_equipped() goi send() -> can co thuoc tinh sock
        game.send = lambda *a, **k: None
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

    @staticmethod
    def _thing(tid, damage=0, damaged_item_id=0):
        raw = bytearray(35)
        raw[0:2] = tid.to_bytes(2, "little")
        raw[6] = damage
        raw[27:29] = damaged_item_id.to_bytes(2, "little")
        return bytes(raw)

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

    def test_equipped_super_is_not_replaced_by_lower_priority_items(self):
        equip, used = self._run_items(
            {1: (GREAT_GEM, 1), 2: (GREAT_BAG, 2)},
            [{"id": SUPER_GEM, "damage": 0, "damaged_item_id": 0}],
        )
        self.assertEqual(equip, [])
        self.assertEqual(used, [])

    def test_equipped_great_is_kept_when_no_super_is_available(self):
        equip, used = self._run_items(
            {1: (GREAT_GEM, 1), 2: (GREAT_BAG, 2)},
            [{"id": GREAT_GEM, "damage": 0, "damaged_item_id": 0}],
        )
        self.assertEqual(equip, [])
        self.assertEqual(used, [])

    def test_equipped_great_is_upgraded_to_super(self):
        equip, used = self._run_items(
            {3: (SUPER_GEM, 1), 4: (GREAT_BAG, 2)},
            [{"id": GREAT_GEM, "damage": 0, "damaged_item_id": 0}],
        )
        self.assertEqual(equip, [3])
        self.assertEqual(used, [])

    def test_broken_equipped_gem_does_not_count_as_protection(self):
        equip, used = self._run_items(
            {5: (GREAT_GEM, 1), 6: (GREAT_BAG, 2)},
            [{"id": BROKEN_GEM, "damage": 250, "damaged_item_id": SUPER_GEM}],
        )
        self.assertEqual(equip, [5])
        self.assertEqual(used, [])

    def test_login_equipment_snapshot_parses_full_thing_data(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        packet = b"\x00" * 7 + b"\x0b\x00" + bytes([2]) + self._thing(0x4E21) + self._thing(
            SUPER_GEM, damage=12
        )
        game._parse_equipment_snapshot(packet)
        self.assertEqual(len(game.equipped_items), 2)
        # Neo theo Y NGHIA (tap con), khong so khop NGUYEN dict: ban ghi nay duoc THEM truong
        # dan theo nhu cau - "pos" (o dang deo ngoc, luc lam Phuc Than) roi element/stone (luc
        # tinh lai chi so khi thay do). So khop nguyen dict thi cu them truong la test do oan
        # trong khi hanh vi khong he doi.
        for k, v in {"id": SUPER_GEM, "pos": 6, "damage": 12, "damaged_item_id": 0}.items():
            self.assertEqual(game.equipped_items[1][k], v)
        # 4 truong ThingData can de tinh cong tu do (xem pet_login_stats.equipment_bonus)
        for k in ("element", "element_value", "stone_attr", "stone_lv"):
            self.assertIn(k, game.equipped_items[1])

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

    def test_desktop_and_android_keep_phuc_than_methods_in_sync(self):
        def methods(path):
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            wanted = {
                "_parse_equipment_snapshot",
                "_equipped_phuc_than_tid",
                "_use_items_from_cfg",
            }
            return {
                node.name: ast.dump(node, include_attributes=False)
                for cls in tree.body
                if isinstance(cls, ast.ClassDef) and cls.name == "GameClient"
                for node in cls.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted
            }

        self.assertEqual(
            methods("bot/client.py"),
            methods("android/app/src/main/python/train_bot/client.py"),
        )


if __name__ == "__main__":
    unittest.main()
