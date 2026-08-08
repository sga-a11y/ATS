import struct
import unittest

from bot.battle_tracker import BattleTracker
from tests.test_battle_tracker import SELF_ROLE, battle_create, role_appear


HP = 0x19
SP = 0x1A


def attack_result(source, skill_id, *targets, fight_area=0):
    target_data = bytearray()
    for position, result, attributes in targets:
        target_data.extend((*position, result, 0, len(attributes)))
        for kind, value, sign in attributes:
            target_data.extend(bytes((kind,)) + struct.pack("<I", value) + bytes((sign,)))
    chunk = (
        bytes(source)
        + struct.pack("<H", skill_id)
        + bytes((fight_area, len(targets)))
        + target_data
    )
    return b"\x01\x00" + struct.pack("<H", len(chunk)) + chunk


def absolute_update(is_revive, *records):
    data = bytearray(b"\x01\x00" + bytes((is_revive,)))
    for position, kind, value in records:
        data.extend(bytes(position) + bytes((kind,)) + struct.pack("<i", value))
    return bytes(data)


class TestBattleActionResults(unittest.TestCase):
    def setUp(self):
        self.tracker = BattleTracker(local_role_id=SELF_ROLE)
        enemy = role_appear(row=0, col=1, hp=2104, hp_max=3000, sp=100, sp_max=200)
        ally = role_appear(
            role_id=SELF_ROLE,
            row=3,
            col=2,
            hp=100,
            hp_max=1000,
            sp=20,
            sp_max=300,
        )
        self.tracker.apply(0x0B, battle_create(enemy, ally))

    def test_damage_is_signed_delta_not_absolute_hp(self):
        events = self.tracker.apply(
            0x32,
            attack_result((3, 2), 11014, ((0, 1), 1, ((HP, 428, 1),))),
        )

        self.assertEqual(self.tracker.units[(0, 1)].hp, 1676)
        self.assertEqual(events[0].payload[-1], ((HP, -428, 1676),))

    def test_heal_and_sp_are_clamped_to_maximum(self):
        self.tracker.apply(
            0x32,
            attack_result(
                (3, 2),
                10001,
                ((3, 2), 1, ((HP, 5000, 0), (SP, 5000, 0))),
            ),
        )

        unit = self.tracker.units[(3, 2)]
        self.assertEqual((unit.hp, unit.sp), (1000, 300))

    def test_miss_does_not_apply_attribute_delta(self):
        self.tracker.apply(
            0x32,
            attack_result((3, 2), 11014, ((0, 1), 0, ((HP, 428, 1),))),
        )

        self.assertEqual(self.tracker.units[(0, 1)].hp, 2104)

    def test_successful_freeze_is_kept_until_server_clears_status(self):
        self.tracker.apply(
            0x32,
            attack_result((3, 2), 11014, ((0, 1), 1, ())),
        )
        self.tracker.apply(0x34, b"\x01\x00")

        self.assertEqual(self.tracker.statuses[(0, 1)], {1: 11014})

        self.tracker.apply(
            0x35,
            b"\x01\x00" + bytes((0, 1, 1)) + struct.pack("<H", 0),
        )

        self.assertNotIn((0, 1), self.tracker.statuses)

    def test_successful_barrier_is_kept_until_server_clears_status(self):
        self.tracker.apply(
            0x32,
            attack_result((3, 2), 10010, ((3, 2), 1, ())),
        )
        self.tracker.apply(0x34, b"\x01\x00")

        self.assertEqual(self.tracker.statuses[(3, 2)], {2: 10010})

    def test_missed_effect_skill_does_not_create_status(self):
        self.tracker.apply(
            0x32,
            attack_result((3, 2), 11014, ((0, 1), 0, ())),
        )

        self.assertNotIn((0, 1), self.tracker.statuses)

    def test_absolute_update_reads_full_int32_and_revives(self):
        unit = self.tracker.units[(3, 2)]
        unit.hp = 0
        unit.hp_max = 200000
        unit.alive = False

        events = self.tracker.apply(
            0x33,
            absolute_update(1, ((3, 2), HP, 70000)),
        )

        self.assertEqual(unit.hp, 70000)
        self.assertTrue(unit.alive)
        self.assertEqual(events[0].payload, (HP, 70000, True))

    def test_truncated_action_does_not_apply_earlier_target(self):
        valid = attack_result((3, 2), 11014, ((0, 1), 1, ((HP, 428, 1),)))

        events = self.tracker.apply(0x32, valid[:-1])

        self.assertEqual(events, ())
        self.assertEqual(self.tracker.units[(0, 1)].hp, 2104)


if __name__ == "__main__":
    unittest.main()
