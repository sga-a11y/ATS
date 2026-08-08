import struct
import unittest

from bot.battle_tracker import BattleTracker
from bot.state import BattleState


SELF_ROLE = b"SELFROLE"
OTHER_ROLE = b"OTHER___"


def role_appear(
    role_id=OTHER_ROLE,
    *,
    war_type=1,
    kind=7,
    template_id=41050,
    master_id=b"\x00" * 8,
    row=0,
    col=2,
    hp=2104,
    hp_max=3000,
    sp=120,
    sp_max=200,
    level=110,
):
    return (
        bytes((war_type, kind))
        + role_id
        + struct.pack("<H", template_id)
        + master_id
        + bytes((row, col))
        + struct.pack("<IIIIHBB", hp_max, sp_max, hp, sp, level, 0, 1)
    )


def battle_create(*roles):
    return b"\xfa\x00" + bytes((7,)) + struct.pack("<H", 2) + b"".join(roles)


class TestBattleTrackerLifecycle(unittest.TestCase):
    def test_real_role_header_reads_row_before_column_for_atype_four(self):
        raw = role_appear(role_id=SELF_ROLE, row=3, col=4)
        tracker = BattleTracker(local_role_id=SELF_ROLE)

        events = tracker.apply(0x0B, battle_create(raw))

        self.assertTrue(events)
        self.assertIn((3, 4), tracker.units)
        self.assertEqual(tracker.units[(3, 4)].role_id, SELF_ROLE)

    def test_create_turn_and_local_end_are_authoritative(self):
        tracker = BattleTracker(local_role_id=SELF_ROLE)

        events = tracker.apply(0x0B, battle_create(role_appear()))
        tracker.apply(0x34, b"\x01\x00")
        tracker.apply(0x14, b"\x08\x00")

        self.assertEqual((tracker.generation, tracker.turn, tracker.active), (1, 1, True))
        self.assertEqual([event.kind for event in events], ["start", "spawn"])

        tracker.apply(0x0B, b"\x00\x00" + OTHER_ROLE + b"\x00\x00")
        self.assertTrue(tracker.active)

        tracker.apply(0x0B, b"\x00\x00" + SELF_ROLE + b"\x00\x00")
        self.assertFalse(tracker.active)

    def test_turn_start_keeps_roster_hp_and_status(self):
        tracker = BattleTracker(local_role_id=SELF_ROLE)
        tracker.apply(0x0B, battle_create(role_appear()))
        tracker.statuses[(0, 2)] = {1: 11014}

        tracker.apply(0x34, b"\x01\x00")
        tracker.apply(0x34, b"\x01\x00")

        unit = tracker.units[(0, 2)]
        self.assertEqual(tracker.turn, 2)
        self.assertEqual((unit.hp, unit.hp_max), (2104, 3000))
        self.assertEqual(tracker.statuses[(0, 2)], {1: 11014})

    def test_second_create_replaces_previous_generation_atomically(self):
        tracker = BattleTracker(local_role_id=SELF_ROLE)
        tracker.apply(0x0B, battle_create(role_appear(row=0, col=2)))

        tracker.apply(
            0x0B,
            battle_create(role_appear(role_id=b"SECOND__", row=1, col=4, hp=900)),
        )

        self.assertEqual(tracker.generation, 2)
        self.assertEqual(set(tracker.units), {(1, 4)})
        self.assertEqual(tracker.units[(1, 4)].hp, 900)

    def test_truncated_create_does_not_mutate_existing_battle(self):
        tracker = BattleTracker(local_role_id=SELF_ROLE)
        tracker.apply(0x0B, battle_create(role_appear()))
        before = tracker.snapshot()

        events = tracker.apply(0x0B, battle_create(role_appear())[:-1])

        self.assertEqual(events, ())
        self.assertEqual(tracker.snapshot(), before)

    def test_war_style_packet_updates_metadata(self):
        tracker = BattleTracker(local_role_id=SELF_ROLE)
        tracker.apply(0x0B, battle_create())

        tracker.apply(0x0B, b"\x0a\x00" + bytes((3,)) + struct.pack("<HBI", 9, 2, 0x12345678))

        self.assertEqual(tracker.war_style, 3)
        self.assertEqual(tracker.round_limit, 9)
        self.assertEqual(tracker.limit_kind, 2)
        self.assertEqual(tracker.limit_value, 0x12345678)


class TestBattleTrackerIncrementalState(unittest.TestCase):
    def setUp(self):
        self.tracker = BattleTracker(local_role_id=SELF_ROLE)
        self.tracker.apply(0x0B, battle_create(role_appear()))

    def test_zero_status_clears_only_one_category(self):
        self.tracker.apply(
            0x35,
            b"\x01\x00"
            + bytes((0, 2, 1)) + struct.pack("<H", 11014)
            + bytes((0, 2, 3)) + struct.pack("<H", 14021),
        )

        self.tracker.apply(
            0x35,
            b"\x01\x00" + bytes((0, 2, 1)) + struct.pack("<H", 0),
        )

        self.assertEqual(self.tracker.statuses[(0, 2)], {3: 14021})

    def test_truncated_status_does_not_partially_mutate(self):
        packet = (
            b"\x01\x00"
            + bytes((0, 2, 1)) + struct.pack("<H", 11014)
            + bytes((0, 2, 2))
        )

        events = self.tracker.apply(0x35, packet)

        self.assertEqual(events, ())
        self.assertEqual(self.tracker.statuses, {})

    def test_ack_clears_only_matching_pending_source(self):
        self.tracker.register_action((3, 2), 11014, (0, 2))
        self.tracker.register_action((2, 2), 10000, (0, 2))

        events = self.tracker.apply(0x35, b"\x05\x00\x03\x02")

        self.assertEqual([event.kind for event in events], ["ack"])
        self.assertNotIn((3, 2), self.tracker.pending_actions)
        self.assertIn((2, 2), self.tracker.pending_actions)

    def test_flyout_move_transform_exit_and_replacement_update_roster(self):
        self.tracker.apply(0x35, b"\x03\x00\x00\x02")
        self.assertFalse(self.tracker.units[(0, 2)].alive)
        self.assertEqual(self.tracker.units[(0, 2)].state, "flyout")

        self.tracker.apply(0x0B, b"\x05\x00" + role_appear(role_id=b"REPLACE_", hp=1800))
        self.assertEqual(self.tracker.units[(0, 2)].role_id, b"REPLACE_")
        self.tracker.apply(0x35, b"\x07\x00\x00\x02\x01\x04")
        self.assertNotIn((0, 2), self.tracker.units)
        self.assertEqual(self.tracker.units[(1, 4)].role_id, b"REPLACE_")

        self.tracker.apply(0x35, b"\x0e\x00\x01\x04" + struct.pack("<H", 49999))
        self.assertEqual(self.tracker.units[(1, 4)].template_id, 49999)
        self.tracker.apply(0x0B, b"\x01\x00\x01\x04")
        self.assertNotIn((1, 4), self.tracker.units)

    def test_normal_and_extra_buffs_are_structured(self):
        self.tracker.apply(0x35, b"\x0f\x00" + struct.pack("<BBBBh", 0, 2, 4, 3, 25))
        extra = struct.pack("<HBBHBBBBHi", 11014, 2, 9, 300, 1, 3, 2, 12, 0x19, -428)
        self.tracker.apply(0x35, b"\x14\x00\x00\x02\x01" + extra)

        self.assertEqual(self.tracker.buffs[(0, 2)][4], (3, 25))
        self.assertEqual(
            self.tracker.extra_buffs[(0, 2)][300],
            (11014, 2, 9, 1, 3, 2, 12, 0x19, -428),
        )


class TestBattleStateCompatibility(unittest.TestCase):
    def test_sync_exposes_tracker_roster_hp_and_status_to_combat(self):
        tracker = BattleTracker(local_role_id=SELF_ROLE)
        tracker.apply(
            0x0B,
            battle_create(
                role_appear(row=0, col=2, hp=2104),
                role_appear(role_id=SELF_ROLE, row=3, col=1, hp=800, hp_max=1000),
            ),
        )
        tracker.apply(
            0x35,
            b"\x01\x00" + bytes((0, 2, 1)) + struct.pack("<H", 11014),
        )
        state = BattleState()

        state.attach_tracker(tracker)
        state.sync_from_tracker()

        self.assertEqual(state.enemy_slots, [2])
        self.assertEqual(state.enemy_hp, {2: 2104})
        self.assertEqual(state.crowd_status, {(0, 2): {11014}})
        self.assertEqual(state.allies[(3, 1)].hp, 800)
        self.assertTrue(state.in_battle)


if __name__ == "__main__":
    unittest.main()
