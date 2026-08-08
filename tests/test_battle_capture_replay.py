import unittest
from pathlib import Path

from analyze_pcap import load_frames
from bot.battle_tracker import BattleTracker


CAPTURE = Path(__file__).resolve().parents[1] / "captures/teamdungeon_lv110_mumu12_20260805_202150.pcap"
BATTLE_OPCODES = {0x0B, 0x14, 0x32, 0x33, 0x34, 0x35}


class TestBattleCaptureReplay(unittest.TestCase):
    def test_pb110_replay_builds_complete_protocol_lifecycle(self):
        frames, _ = load_frames(str(CAPTURE))
        first_create = next(
            frame["body"]
            for frame in frames
            if frame["dir"] == "S2C"
            and frame["op"] == 0x0B
            and frame["body"][:2] == b"\xfa\x00"
        )
        tracker = BattleTracker(local_role_id=first_create[7:15])
        counts = {"start": 0, "turn_start": 0, "flyout": 0}
        action_packets = 0
        parsed_action_packets = 0
        action_targets = 0

        for frame in frames:
            if frame["dir"] != "S2C" or frame["op"] not in BATTLE_OPCODES:
                continue
            if frame["op"] == 0x32 and frame["body"][:2] == b"\x01\x00":
                action_packets += 1
            events = tracker.apply(frame["op"], frame["body"])
            action_events = [event for event in events if event.kind == "action"]
            if action_events:
                parsed_action_packets += 1
                action_targets += len(action_events)
            for event in events:
                if event.kind in counts:
                    counts[event.kind] += 1

        self.assertEqual(counts, {"start": 5, "turn_start": 31, "flyout": 8})
        self.assertEqual((parsed_action_packets, action_packets), (354, 354))
        self.assertEqual(action_targets, 1276)
        self.assertEqual(tracker.generation, 5)
        self.assertTrue(all(unit.hp >= 0 and unit.sp >= 0 for unit in tracker.units.values()))
        self.assertTrue(all(unit.hp <= unit.hp_max for unit in tracker.units.values()))
        self.assertTrue(all(unit.sp <= unit.sp_max for unit in tracker.units.values()))


if __name__ == "__main__":
    unittest.main()
