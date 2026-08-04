import ast
import unittest
from unittest.mock import patch

from bot import client as client_module, pet_login_stats


class TestStrategistInt(unittest.TestCase):
    def setUp(self):
        client_module._PARTY_INT.clear()

    @staticmethod
    def game():
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.party_idx = None
        game.self_entity = None
        game._label = "test"
        game.char_int = None
        game.char_agi = None
        game._char_int_base = None
        game._char_equip_int = 0
        game._char_turn3_int = 0
        game._char_agi_base = None
        game._char_equip_agi = 0
        game._char_turn3_agi = 0
        game._mount_base_int = 2
        game._mount_equip_int = 8
        game._mount_equip_agi = 0
        game._collect_style_flags = {}
        game._collect_card_equipped = []
        game._collect_card_levels = {}
        return game

    def test_char_login_uses_full_u16_and_all_static_int_sources(self):
        game = self.game()
        body = bytearray(220)
        body[:2] = b"\x03\x00"
        body[9:11] = (229).to_bytes(2, "little")
        body[53:57] = (70).to_bytes(4, "little", signed=True)
        body[96:98] = (0).to_bytes(2, "little")
        body[107:109] = (5).to_bytes(2, "little")
        packet = b"\x00" * 7 + bytes(body)
        with patch.object(pet_login_stats, "style_attribute", return_value=2), patch.object(
            pet_login_stats, "card_attribute", return_value=1
        ):
            game._parse_char_login_int(packet)
        self.assertEqual(game.char_int, 317)
        self.assertEqual(game._char_int_base, 229)
        self.assertEqual(game._char_equip_int, 70)
        self.assertEqual(game._char_turn3_int, 5)

    def test_best_member_uses_effective_int_above_255(self):
        party = 77
        low = b"low-int1"
        high = b"highint1"
        client_module._register_party_int(party, low, 250)
        client_module._register_party_int(party, high, 311)
        self.assertEqual(client_module.best_int_member(party, [low, high]), high)

    def test_char_login_calculates_effective_agi(self):
        game = self.game()
        body = bytearray(220)
        body[:2] = b"\x03\x00"
        body[15:17] = (41).to_bytes(2, "little")
        body[57:61] = (34).to_bytes(4, "little", signed=True)
        body[96:98] = (0).to_bytes(2, "little")
        body[113:115] = (2).to_bytes(2, "little")
        packet = b"\x00" * 7 + bytes(body)
        with patch.object(pet_login_stats, "style_attribute", return_value=1), patch.object(
            pet_login_stats, "card_attribute", return_value=0
        ):
            game._parse_char_login_int(packet)
        self.assertEqual(game.char_agi, 78)
        self.assertEqual(game._char_agi_base, 41)
        self.assertEqual(game._char_equip_agi, 34)
        self.assertEqual(game._char_turn3_agi, 2)

    def test_desktop_and_android_int_methods_stay_in_sync(self):
        def methods(path):
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            wanted = {"_parse_char_login_int", "_refresh_char_int", "_refresh_char_agi"}
            return {
                node.name: ast.dump(node, include_attributes=False)
                for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "GameClient"
                for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in wanted
            }
        self.assertEqual(methods("bot/client.py"),
                         methods("android/app/src/main/python/train_bot/client.py"))


if __name__ == "__main__":
    unittest.main()
