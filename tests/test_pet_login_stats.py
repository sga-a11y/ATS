import json
import unittest
from unittest.mock import patch

from bot import client as client_module, pet_login_stats
from bot.state import BattleState


class TestPetLoginStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("pet_stats.json", encoding="utf-8") as fh:
            cls.data = json.load(fh)

    @staticmethod
    def record(pet_id, level, hp, sp, hpx, spx, equipment=(), agi=0):
        things = [{"id": 0, "element": 0, "element_value": 0, "stone_attr": 0, "stone_lv": 0}
                  for _ in range(6)]
        for slot, item_id in equipment:
            things[slot - 1]["id"] = item_id
        return {
            "marker": 1, "id": pet_id, "level": level, "hp": hp, "sp": sp,
            "hpx": hpx, "spx": spx, "agi": agi,
            "equipment": things, "hp_pill": 0, "sp_pill": 0,
        }

    def test_three_captured_pets_match_game_max_stats(self):
        quan_vu = self.record(41050, 117, 1054, 82, 94, 26,
                              ((2, 19001), (3, 15098), (6, 23006)))
        tuong_nghia_cu = self.record(41038, 105, 1138, 370, 78, 31)
        thai_van_co = self.record(41041, 107, 886, 354, 57, 28)
        self.assertEqual(pet_login_stats.calculate(quan_vu, self.data, style=(1, 1)), (1398, 355))
        self.assertEqual(pet_login_stats.calculate(tuong_nghia_cu, self.data, style=(1, 1)), (1149, 370))
        self.assertEqual(pet_login_stats.calculate(thai_van_co, self.data, style=(1, 1)), (898, 354))

    def test_parse_record_reads_current_stats_equipment_and_pills(self):
        raw = bytearray(254)
        raw[0] = 3
        raw[1:3] = (41050).to_bytes(2, "little")
        raw[7] = 117
        raw[8:12] = (1054).to_bytes(4, "little")
        raw[12:14] = (82).to_bytes(2, "little")
        raw[20:22] = (70).to_bytes(2, "little")
        raw[22:24] = (94).to_bytes(2, "little")
        raw[24:26] = (26).to_bytes(2, "little")
        raw[31] = 0
        raw[35 + 35:35 + 37] = (19001).to_bytes(2, "little")
        raw[35 + 5 * 35:35 + 5 * 35 + 2] = (23006).to_bytes(2, "little")
        raw[251] = 2
        raw[252] = 3
        parsed = pet_login_stats.parse_record(raw, 0)
        self.assertEqual((parsed["marker"], parsed["hp"], parsed["sp"]), (3, 1054, 82))
        self.assertEqual(parsed["agi"], 70)
        self.assertEqual(parsed["equipment"][1]["id"], 19001)
        self.assertEqual(parsed["equipment"][5]["id"], 23006)
        self.assertEqual((parsed["hp_pill"], parsed["sp_pill"]), (2, 3))

    def test_refresh_populates_active_pet_state_for_pre_boss_heal(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.state = BattleState()
        game._label = "test"
        game._active_pet_login = self.record(41050, 117, 1054, 82, 94, 26,
                                             ((2, 19001), (3, 15098), (6, 23006)))
        game._collect_style_flags = {}
        game._collect_card_equipped = []
        game._collect_card_levels = {}
        with patch.object(pet_login_stats, "style_bonus", return_value=(1, 1)):
            game._refresh_active_pet_login_stats()
        self.assertEqual(
            (game.state.pet.hp, game.state.pet.hp_max, game.state.pet.sp, game.state.pet.sp_max),
            (1054, 1398, 82, 355),
        )

    def test_heal_full_now_includes_active_pet_immediately_after_login(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.state = BattleState()
        game.state.pet.hp, game.state.pet.hp_max = 1054, 1398
        game.state.pet.sp, game.state.pet.sp_max = 82, 355
        game.state.solo_multipet = False
        game.bag_slots = {1: [0x1234, 99]}
        game.active_pet_slot = 3
        game._label = "test"
        game.in_combat = lambda: False
        calls = []
        game._heal_unit = lambda *args, **kwargs: calls.append((args, kwargs))
        game.heal_full()
        pet_calls = [call for call in calls if call[0][2] == "pet"]
        self.assertEqual([call[0][0] for call in pet_calls], [3, 3])
        self.assertEqual([call[0][4] for call in pet_calls], ["hp", "sp"])

    def test_active_pet_actual_agi_includes_equipment_style_and_card(self):
        quan_vu = self.record(41050, 117, 1054, 82, 94, 26,
                              ((2, 19001), (3, 15098), (6, 23006)), agi=70)
        self.assertEqual(pet_login_stats.calculate_agi(
            quan_vu, self.data, style_agi=1, card_agi=0), 75)


if __name__ == "__main__":
    unittest.main()
