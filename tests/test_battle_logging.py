import unittest

from bot.battle_tracker import BattleEvent
from bot.party_battle import PartyBattleCoordinator


class TestBattleLogging(unittest.TestCase):
    def test_five_broadcast_copies_emit_one_common_line(self):
        coordinator = PartyBattleCoordinator(19)
        start = BattleEvent("start", 2, 0, payload=(105, 1))
        turn = BattleEvent("turn_start", 2, 1)

        with self.assertLogs("bot", level="INFO") as captured:
            for account in ("a", "b", "c", "d", "e"):
                coordinator.observe(account, start)
            for account in ("a", "b", "c", "d", "e"):
                coordinator.observe(account, turn)

        lines = "\n".join(captured.output)
        self.assertEqual(lines.count("[P19 BATTLE g=2] START"), 1)
        self.assertEqual(lines.count("[P19 BATTLE g=2 t=1] TURN START"), 1)

    def test_action_log_contains_source_target_skill_and_hp_delta(self):
        coordinator = PartyBattleCoordinator(6)
        coordinator.observe("a", BattleEvent("start", 1, 0))
        coordinator.observe("a", BattleEvent("turn_start", 1, 1))
        action = BattleEvent(
            "action",
            1,
            1,
            position=(0, 1),
            source=(3, 2),
            skill_id=11014,
            payload=(0, 1, 0, ((0x19, -428, 1676),)),
        )

        with self.assertLogs("bot", level="INFO") as captured:
            coordinator.observe("a", action)
            coordinator.observe("b", action)

        line = "\n".join(captured.output)
        self.assertIn("[P6 BATTLE g=1 t=1]", line)
        self.assertIn("(3,2) skill=11014 -> (0,1)", line)
        self.assertIn("HP -428 => 1676", line)


if __name__ == "__main__":
    unittest.main()
