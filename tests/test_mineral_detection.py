import unittest
from types import SimpleNamespace

from bot.combat import _is_mineral_battle
from bot.state import BattleState


class TestMineralDetection(unittest.TestCase):
    def test_name_must_start_with_khoang_and_space(self):
        self.assertTrue(BattleState._is_mineral_enemy(name="Khoáng Sắt"))
        self.assertFalse(BattleState._is_mineral_enemy(name="Trình Khoáng"))
        self.assertFalse(BattleState._is_mineral_enemy(name="KhoángSắt"))

    def test_combat_fallback_uses_same_prefix_rule(self):
        state = SimpleNamespace(
            mineral_battle=False,
            enemy_names={"Trình Khoáng"},
        )
        self.assertFalse(_is_mineral_battle(state))

        state.enemy_names = {"Khoáng Đồng"}
        self.assertTrue(_is_mineral_battle(state))

    def test_template_id_alone_does_not_mark_mineral(self):
        self.assertFalse(BattleState._is_mineral_enemy(tid=0x61C7))


if __name__ == "__main__":
    unittest.main()
