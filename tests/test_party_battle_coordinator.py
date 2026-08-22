import unittest

from bot.battle_tracker import BattleEvent
from bot.party_battle import PartyBattleCoordinator, clear_party_battles, get_party_battle


def event(kind, generation=1, turn=0, **kwargs):
    return BattleEvent(kind, generation, turn, **kwargs)


class TestPartyBattleCoordinator(unittest.TestCase):
    def setUp(self):
        clear_party_battles()
        self.coordinator = PartyBattleCoordinator(19)
        self.coordinator.observe("a", event("start", generation=4))

    def test_acc_cham_VAN_gui_duoc_nhung_sent_state_bao_chua_dong_bo(self):
        """can_send khong con la "cong dong bo phien" - no CHI chan lenh trung (xem docstring
        can_send). Viec "chua thay turn cua minh" chuyen sang sent_state de caller LOG canh bao."""
        turn = event("turn_start", generation=4, turn=1)

        self.assertTrue(self.coordinator.observe("a", turn))

        self.assertTrue(self.coordinator.can_send("a", 4, 1))
        self.assertTrue(self.coordinator.can_send("b", 4, 1), "lech phien lai bi nuot lenh danh")
        self.assertEqual(self.coordinator.sent_state("b", 4, 1), (True, False))

        self.coordinator.observe("b", turn)
        self.assertTrue(self.coordinator.can_send("b", 4, 1))
        self.assertEqual(self.coordinator.sent_state("b", 4, 1), (True, True))

    def test_missing_account_never_blocks_others(self):
        self.coordinator.register_accounts(("a", "b", "frozen"))

        self.coordinator.observe("a", event("turn_start", generation=4, turn=1))

        self.assertTrue(self.coordinator.can_plan(4, 1))
        self.assertTrue(self.coordinator.can_send("a", 4, 1))

    def test_duplicate_turn_packets_open_one_canonical_turn(self):
        turn = event("turn_start", generation=4, turn=1)

        accepted = [self.coordinator.observe(account, turn) for account in "abcde"]

        self.assertEqual(accepted, [True, False, False, False, False])
        self.assertEqual(self.coordinator.active_key, (4, 1))
        self.assertEqual(self.coordinator.common_event_count, 2)  # start + turn

    def test_local_turn_cu_bi_bo_lai_thi_sent_state_bao_lech_nhung_van_gui(self):
        self.coordinator.observe("a", event("turn_start", generation=4, turn=1))
        self.coordinator.observe("a", event("turn_start", generation=4, turn=2))

        # luot chinh thuc da sang 2 -> khong mo lai duoc luot 1 da qua
        self.assertFalse(self.coordinator.open_local_turn("b", 4, 1))

        # b lech ca 2 mat (sai luot, chua thay turn cua minh) - nhung van phai gui duoc
        self.assertEqual(self.coordinator.sent_state("b", 4, 1), (False, False))
        self.assertTrue(self.coordinator.can_send("b", 4, 1))
        self.assertTrue(self.coordinator.can_send("b", 4, 2))

    def test_start_generation_khac_luon_mo_phien_moi_ke_ca_dang_active(self):
        """Server la su that: ca party relogin sau khi PB vo -> server danh so generation lai tu
        dau. Truoc day loai generation nho hon -> phien cu ket vinh vien, moi turn sau deu bi loai."""
        self.assertTrue(self.coordinator.observe("new", event("start", generation=1)))
        self.assertEqual(self.coordinator.generation, 1)

        self.coordinator.observe("a", event("end", generation=1))

        self.assertTrue(self.coordinator.observe("new", event("start", generation=1)))
        self.assertTrue(self.coordinator.observe("new", event("turn_start", generation=1, turn=1)))
        self.assertTrue(self.coordinator.can_send("new", 1, 1))

    def test_invalid_event_does_not_block_valid_copy(self):
        self.assertFalse(self.coordinator.observe("a", None))

        self.assertTrue(
            self.coordinator.observe("b", event("turn_start", generation=4, turn=1))
        )

    def test_mark_sent_prevents_duplicate_send_on_same_socket(self):
        self.coordinator.observe("a", event("turn_start", generation=4, turn=1))

        self.assertTrue(self.coordinator.mark_sent("a", (3, 2), 4, 1))
        self.assertFalse(self.coordinator.can_send("a", 4, 1, source=(3, 2)))
        self.assertFalse(self.coordinator.mark_sent("a", (3, 2), 4, 1))

    def test_reservations_are_shared_for_coordination_but_not_focus_damage(self):
        self.coordinator.observe("a", event("turn_start", generation=4, turn=1))

        self.assertTrue(self.coordinator.reserve("a", "cc", (0, 1), 4, 1))
        self.assertFalse(self.coordinator.reserve("b", "cc", (0, 1), 4, 1))
        self.assertTrue(self.coordinator.reserve("b", "cc", (0, 2), 4, 1))
        self.assertTrue(self.coordinator.reserve("a", "damage", (0, 1), 4, 1))
        self.assertTrue(self.coordinator.reserve("b", "damage", (0, 1), 4, 1))

    def test_reservations_expire_on_next_canonical_turn(self):
        self.coordinator.observe("a", event("turn_start", generation=4, turn=1))
        self.assertTrue(self.coordinator.reserve("a", "protect", (3, 1), 4, 1))
        self.coordinator.observe("a", event("turn_start", generation=4, turn=2))

        self.assertTrue(self.coordinator.reserve("b", "protect", (3, 1), 4, 2))

    def test_delayed_broadcast_action_is_deduplicated_semantically(self):
        self.coordinator.observe("a", event("turn_start", generation=4, turn=1))
        action_a = event(
            "action", generation=4, turn=1, source=(3, 2), position=(0, 1),
            skill_id=11014, payload=(0, 1, 0, ((0x19, -428, 1676),)),
        )
        action_b = event(
            "action", generation=4, turn=1, source=(3, 2), position=(0, 1),
            skill_id=11014, payload=(0, 1, 0, ((0x19, -428, 1676),)),
        )

        self.assertTrue(self.coordinator.observe("a", action_a))
        self.assertFalse(self.coordinator.observe("b", action_b))

    def test_multi_target_action_events_are_not_collapsed(self):
        self.coordinator.observe("a", event("turn_start", generation=4, turn=1))
        first = event(
            "action", generation=4, turn=1, source=(3, 2), position=(0, 1),
            skill_id=11014, payload=(0, 1, 0, ((0x19, -100, 1900),)),
        )
        second = event(
            "action", generation=4, turn=1, source=(3, 2), position=(0, 2),
            skill_id=11014, payload=(0, 1, 0, ((0x19, -100, 1800),)),
        )

        self.assertTrue(self.coordinator.observe("a", first))
        self.assertTrue(self.coordinator.observe("a", second))

    def test_replacement_spawn_at_same_position_is_not_collapsed(self):
        first = event("spawn", generation=4, position=(0, 1), payload=(b"FIRST___", 1, ""))
        replacement = event(
            "spawn", generation=4, position=(0, 1), payload=(b"SECOND__", 2, ""),
        )

        self.assertTrue(self.coordinator.observe("a", first))
        self.assertTrue(self.coordinator.observe("a", replacement))

    def test_party_registry_isolates_different_parties(self):
        first = get_party_battle(19)
        second = get_party_battle(20)

        self.assertIs(first, get_party_battle(19))
        self.assertIsNot(first, second)


if __name__ == "__main__":
    unittest.main()
