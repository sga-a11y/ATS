import unittest
from unittest.mock import patch

from bot import combat
from bot.battle_tracker import BattleEvent, BattleTracker
from bot.party_battle import PartyBattleCoordinator
from bot.state import BattleState, Unit


class TestCombatTurnClaims(unittest.TestCase):
    def setUp(self):
        self.claims = {}
        self.lock = combat.threading.Lock()

    def test_claim_stays_locked_for_the_whole_turn(self):
        self.assertTrue(
            combat._short_claim(
                self.claims, self.lock, 19, (0, 2), "acc-a", turn_token=101
            )
        )
        self.assertFalse(
            combat._short_claim(
                self.claims, self.lock, 19, (0, 2), "acc-b", turn_token=101
            )
        )

    def test_claim_is_released_on_the_next_turn(self):
        self.assertTrue(
            combat._short_claim(
                self.claims, self.lock, 19, (0, 2), "acc-a", turn_token=101
            )
        )
        self.assertTrue(
            combat._short_claim(
                self.claims, self.lock, 19, (0, 2), "acc-b", turn_token=102
            )
        )

    def test_two_ice_casters_in_one_party_choose_different_targets(self):
        combat._cc_claims.pop(19, None)

        def make_state(label, atype):
            state = BattleState()
            state.label = label
            state.party_idx = 19
            state.my_atype = atype
            state.enemy_gen = 77
            state.enemy_slots = [1, 2]
            state.enemy_hp = {1: 1000, 2: 1000}
            state.char.hp = state.char.hp_max = 500
            state.char.sp = 500
            return state

        first = make_state("acc-a", 1)
        second = make_state("acc-b", 3)
        decision_a = combat._try_cc_skill(
            first, combat.config.UNIT_CHAR, 11014, first.char,
            [(1, 1), (1, 2)], "high", require_mode=False,
        )
        decision_b = combat._try_cc_skill(
            second, combat.config.UNIT_CHAR, 11014, second.char,
            [(3, 1), (3, 2)], "high", require_mode=False,
        )

        self.assertIsNotNone(decision_a)
        self.assertIsNotNone(decision_b)
        self.assertNotEqual((decision_a.b, decision_a.target), (decision_b.b, decision_b.target))

    def test_cc_reservation_lives_in_party_coordinator_not_module_cache(self):
        tracker = BattleTracker()
        tracker.generation = 8
        tracker.turn = 3
        tracker.active = True
        coordinator = PartyBattleCoordinator(19)
        coordinator.observe("acc-a", BattleEvent("start", 8, 0))
        coordinator.observe("acc-a", BattleEvent("turn_start", 8, 3))

        def make_state(label, atype):
            state = BattleState()
            state.label = label
            state.party_idx = 19
            state.my_atype = atype
            state.enemy_gen = 77
            state.enemy_slots = [1, 2]
            state.enemy_hp = {1: 5000, 2: 4000}
            state.char.hp = state.char.hp_max = 500
            state.char.sp = 500
            state.attach_tracker(tracker, coordinator)
            return state

        first = make_state("acc-a", 1)
        second = make_state("acc-b", 3)
        decision_a = combat._try_cc_skill(
            first, combat.config.UNIT_CHAR, 11014, first.char,
            [(1, 1), (1, 2)], "high", require_mode=False,
        )
        combat._cc_claims.clear()
        decision_b = combat._try_cc_skill(
            second, combat.config.UNIT_CHAR, 11014, second.char,
            [(3, 1), (3, 2)], "high", require_mode=False,
        )

        self.assertEqual((decision_a.b, decision_a.target), (0, 1))
        self.assertEqual((decision_b.b, decision_b.target), (0, 2))

    def test_revive_targets_are_reserved_in_party_coordinator(self):
        tracker = BattleTracker()
        tracker.generation = 9
        tracker.turn = 4
        tracker.active = True
        coordinator = PartyBattleCoordinator(19)
        coordinator.observe("acc-a", BattleEvent("start", 9, 0))
        coordinator.observe("acc-a", BattleEvent("turn_start", 9, 4))

        def make_state(label):
            state = BattleState()
            state.label = label
            state.party_idx = 19
            state.my_atype = 2
            state.self_slot = 2
            state.enemy_gen = 88
            state.enemy_slots = [1]
            state.enemy_hp = {1: 5000}
            state.char.hp = state.char.hp_max = 500
            state.char.sp = 5000
            for slot in (1, 3):
                dead = Unit(f"dead-{slot}")
                dead.hp = 0
                dead.hp_max = 1000 - slot
                dead.sp = dead.sp_max = 100
                state.allies[(3, slot)] = dead
            state.attach_tracker(tracker, coordinator)
            return state

        first = make_state("acc-a")
        second = make_state("acc-b")
        decision_a = combat._revive_decision_for_skill(
            first, combat.config.UNIT_CHAR, first.char, 11013,
        )
        combat._revive_claims.clear()
        combat._revive_pool.clear()
        decision_b = combat._revive_decision_for_skill(
            second, combat.config.UNIT_CHAR, second.char, 11013,
        )

        self.assertIsNotNone(decision_a)
        self.assertIsNotNone(decision_b)
        self.assertNotEqual((decision_a.b, decision_a.target), (decision_b.b, decision_b.target))

    def test_party_support_action_reserves_heal_target_without_barrier(self):
        tracker = BattleTracker()
        tracker.generation = 10
        tracker.turn = 5
        tracker.active = True
        coordinator = PartyBattleCoordinator(19)
        coordinator.observe("acc-a", BattleEvent("start", 10, 0))
        coordinator.observe("acc-a", BattleEvent("turn_start", 10, 5))
        state = BattleState()
        state.attach_tracker(tracker, coordinator)

        first = combat._claim_support_action(
            state, "heal_hp", (3, 1), "acc-a", 500, combat._heal_decide,
        )
        second = combat._claim_support_action(
            state, "heal_hp", (3, 1), "acc-b", 600, combat._heal_decide,
        )

        self.assertTrue(first)
        self.assertFalse(second)

    def test_custom_heal_rule_uses_party_turn_reservation(self):
        tracker = BattleTracker()
        tracker.generation = 11
        tracker.turn = 6
        tracker.active = True
        coordinator = PartyBattleCoordinator(19)
        coordinator.observe("acc-a", BattleEvent("start", 11, 0))
        coordinator.observe("acc-a", BattleEvent("turn_start", 11, 6))

        def make_state(label):
            state = BattleState()
            state.label = label
            state.party_idx = 19
            state.my_atype = 2
            state.char.sp = 500
            state.battle_config = {"char": [{
                "enabled": True,
                "condition": "always",
                "skill": combat.config.SKILL_HEAL_ONE,
                "target": "ally_low_hp",
            }]}
            ally = Unit("low")
            ally.hp = 100
            ally.hp_max = 1000
            state.allies[(3, 1)] = ally
            state.attach_tracker(tracker, coordinator)
            return state

        first = make_state("acc-a")
        second = make_state("acc-b")
        with patch.object(combat, "_heal_decide", return_value=True):
            decision_a = combat._custom_decision(
                first, combat.config.UNIT_CHAR, "char",
                [combat.config.SKILL_HEAL_ONE], first.char, [(2, 1)],
            )
            decision_b = combat._custom_decision(
                second, combat.config.UNIT_CHAR, "char",
                [combat.config.SKILL_HEAL_ONE], second.char, [(2, 1)],
            )

        self.assertIsNotNone(decision_a)
        self.assertIsNone(decision_b)


class TestBattleStatusRestore(unittest.TestCase):
    @staticmethod
    def status_packet(*entries):
        body = bytearray(b"\x01\x00")
        for row, col, status_kind, skill_id in entries:
            body.extend((row, col, status_kind))
            body.extend(int(skill_id).to_bytes(2, "little"))
        return bytes(body)

    def test_restore_status_merges_records_like_the_game_client(self):
        state = BattleState()

        state.update_0x35_status(self.status_packet(
            (0, 1, 1, 11014),
            (3, 1, 2, 10010),
        ))
        state.update_0x35_status(self.status_packet(
            (3, 2, 2, 10010),
        ))

        self.assertEqual(state.crowd_skills(0, 1), {11014})
        self.assertEqual(state.protection_skills(3, 1), {10010})
        self.assertEqual(state.protection_skills(3, 2), {10010})

    def test_zero_skill_clears_only_that_target_status_kind(self):
        state = BattleState()

        state.update_0x35_status(self.status_packet(
            (0, 1, 1, 11014),
            (0, 1, 3, 14021),
            (3, 1, 2, 10010),
        ))
        state.update_0x35_status(self.status_packet(
            (0, 1, 1, 0),
        ))

        self.assertEqual(state.crowd_skills(0, 1), {14021})
        self.assertEqual(state.protection_skills(3, 1), {10010})

    def test_next_turn_does_not_freeze_the_same_enemy_again(self):
        state = BattleState()
        state.label = "status-cc"
        state.party_idx = 99201
        state.my_atype = 2
        state.enemy_gen = 2
        state.enemy_slots = [1, 2]
        state.enemy_hp = {1: 5000, 2: 4000}
        state.char.hp = state.char.hp_max = 500
        state.char.sp = 500
        combat._cc_claims.pop(state.party_idx, None)
        state.update_0x35_status(self.status_packet((0, 1, 1, 11014)))

        decision = combat._try_cc_skill(
            state, combat.config.UNIT_CHAR, 11014, state.char,
            [(2, 1), (2, 2)], "high", require_mode=False,
        )

        self.assertIsNotNone(decision)
        self.assertEqual((decision.b, decision.target), (0, 2))

    def test_next_turn_does_not_put_boundary_on_protected_ally_again(self):
        state = BattleState()
        state.label = "status-protect"
        state.party_idx = 99202
        state.my_atype = 0
        state.boss_mode = True
        state.enemy_slots = [1]
        state.enemy_hp = {1: 5000}
        state.char.hp = state.char.hp_max = 500
        state.char.sp = 500
        for slot in (1, 2):
            ally = Unit(f"ally-{slot}")
            ally.hp = ally.hp_max = 500
            state.allies[(3, slot)] = ally
        combat._protect_claims.pop(state.party_idx, None)
        state.update_0x35_status(self.status_packet((3, 1, 2, 10010)))

        decision = combat._try_protect(
            state, combat.config.UNIT_CHAR, [10010], state.char
        )

        self.assertIsNotNone(decision)
        self.assertEqual((decision.b, decision.target), (3, 2))


class TestCombatPhaseHpGate(unittest.TestCase):
    @staticmethod
    def make_state(enemy_hp):
        state = BattleState()
        state.label = "hp-gate"
        state.party_idx = 99150
        state.my_atype = 2
        state.self_slot = 2
        state.quest_mode = True
        state.enemy_gen = 15
        state.enemy_slots = [1]
        state.enemy_hp = {1: enemy_hp}
        state.char.hp = state.char.hp_max = 500
        state.char.sp = 500
        return state

    def setUp(self):
        combat._cc_claims.pop(99150, None)
        combat._protect_claims.pop(99150, None)
        combat._break_claims.pop(99150, None)

    def test_hp_1500_skips_automatic_cc_and_ally_protection(self):
        state = self.make_state(1500)
        state.enemy_slots = [1, 2, 3, 4]
        state.enemy_hp = {pos: 1500 for pos in state.enemy_slots}

        cc = combat._try_cc(
            state, combat.config.UNIT_CHAR, [11014], state.char, [(2, 1)], "high"
        )
        protection = combat._try_protect(
            state, combat.config.UNIT_CHAR, [10010], state.char
        )

        self.assertIsNone(cc)
        self.assertIsNone(protection)

    def test_hp_1501_keeps_automatic_cc_and_ally_protection(self):
        cc_state = self.make_state(1501)
        protection_state = self.make_state(1501)
        for state in (cc_state, protection_state):
            state.enemy_slots = [1, 2, 3, 4]
            state.enemy_hp = {1: 1501, 2: 1500, 3: 1500, 4: 1500}

        cc = combat._try_cc(
            cc_state, combat.config.UNIT_CHAR, [11014], cc_state.char, [(2, 1)], "high"
        )
        protection = combat._try_protect(
            protection_state, combat.config.UNIT_CHAR, [10010], protection_state.char
        )

        self.assertIsNotNone(cc)
        self.assertIsNotNone(protection)

    def test_hp_1500_still_allows_breaking_enemy_protection(self):
        state = self.make_state(1500)
        state.protect_status = {(0, 1): {10010}}

        decision = combat._try_break_enemy_protect(
            state, combat.config.UNIT_CHAR, [11012], state.char, [(2, 1)]
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision.skill, 11012)


if __name__ == "__main__":
    unittest.main()
