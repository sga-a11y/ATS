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

    def test_template_id_trong_bang_LA_quai_khoang(self):
        """Doi luat (co chu y): nay nhan dien theo config.MINERAL_NPC_IDS (252 con, crack tu
        NPC kind==16, khop CheckMineral cua client) chu khong doan theo TEN - heuristic ten cu
        sot gan het. Test cu assertFalse(tid=0x61C7) la SAI: 0x61C7 chinh la "Khoang Sat".
        """
        from bot import config
        self.assertIn(0x61C7, getattr(config, "MINERAL_NPC_IDS", ()))
        self.assertTrue(BattleState._is_mineral_enemy(tid=0x61C7))
        # id KHONG nam trong bang thi khong duoc coi la khoang
        self.assertFalse(BattleState._is_mineral_enemy(tid=0x0001))


if __name__ == "__main__":
    unittest.main()
