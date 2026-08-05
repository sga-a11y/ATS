import unittest
from pathlib import Path

from analyze_pcap import load_frames
from bot import client as client_module, config
from bot import team_dungeon_lv110 as pb110
from bot.state import BattleState


ROOT = Path(__file__).resolve().parents[1]
ANDROID_UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(
    encoding="utf-8"
)
ANDROID_PARTY = (ROOT / "android/app/src/main/java/com/tsbot/android/Party.kt").read_text(
    encoding="utf-8"
)
ANDROID_STORE = (ROOT / "android/app/src/main/java/com/tsbot/android/PartyStore.kt").read_text(
    encoding="utf-8"
)
CAPTURE = ROOT / "captures/teamdungeon_lv110_mumu12_20260805_202150.pcap"
REPLACEMENTS = [
    (0x9D39, 0x9D3D),
    (0x9D3B, 0x9D3D),
    (0x9D3E, 0x9D42),
    (0x9D3E, 0x9D41),
    (0x9D3E, 0x9D40),
    (0x9D43, 0x9D49),
    (0x9D43, 0x9D4A),
    (0x9D43, 0x9D4B),
]


class TestTeamDungeon110Config(unittest.TestCase):
    def test_pc_missing_setting_defaults_110_off(self):
        self.assertEqual(config.TEAM_DUNGEON_LEVELS, (20, 50, 80, 110))
        self.assertEqual(
            config.normalize_team_dungeons(None),
            {20: True, 50: True, 80: True, 110: False},
        )

    def test_pc_preserves_explicit_110_setting(self):
        self.assertTrue(config.normalize_team_dungeons({"110": True})[110])

    def test_android_ui_and_store_default_110_off(self):
        self.assertIn("private val TeamDungeonLevels = listOf(20, 50, 80, 110)", ANDROID_UI)
        self.assertIn("110 to (src[110] ?: false)", ANDROID_UI)
        self.assertIn("110 to false", ANDROID_PARTY)
        self.assertIn("110 to false", ANDROID_STORE)
        self.assertIn("listOf(20, 50, 80, 110)", ANDROID_STORE)


class TestTeamDungeon110Capture(unittest.TestCase):
    def test_decoder_accepts_only_exact_reinforcement_shape(self):
        packet = b"\x00" * 7 + bytes.fromhex(
            "060001399d0000000000003d9d000000000000"
        )

        old_entity, new_entity = pb110.decode_reinforcement(packet)

        self.assertEqual(int.from_bytes(old_entity[:2], "little"), 0x9D39)
        self.assertEqual(int.from_bytes(new_entity[:2], "little"), 0x9D3D)
        self.assertIsNone(pb110.decode_reinforcement(b"\x00" * 7 + b"\x06\x00"))
        self.assertIsNone(
            pb110.decode_reinforcement(
                b"\x00" * 7
                + bytes.fromhex("010001399d0000000000003d9d000000000000")
            )
        )

    def test_capture_contains_five_encounters_reinforcements_and_completion(self):
        frames, _ = load_frames(str(CAPTURE))
        actual = []
        for frame in frames:
            if frame["dir"] != "S2C" or frame["op"] != 0x35:
                continue
            decoded = pb110.decode_reinforcement(b"\x00" * 7 + frame["body"])
            if decoded:
                actual.append(
                    tuple(int.from_bytes(entity[:2], "little") for entity in decoded)
                )

        self.assertEqual(actual, REPLACEMENTS)
        self.assertEqual(
            sum(
                frame["dir"] == "S2C"
                and frame["op"] == 0x14
                and frame["body"][:2] == b"\x07\x00"
                for frame in frames
            ),
            4,
        )
        self.assertTrue(
            any(
                frame["dir"] == "S2C"
                and frame["op"] == 0x18
                and frame["body"][:5] == bytes.fromhex("0100ae3001")
                for frame in frames
            )
        )


class TestTeamDungeon110PacketState(unittest.TestCase):
    @staticmethod
    def make_client():
        game = client_module.GameClient.__new__(client_module.GameClient)
        game._label = "pb110-test"
        game.running = True
        game._active_team_dungeon_level = 110
        game._team_dungeon_end_seq = 0
        game._team_dungeon_reinforcement_seq = 0
        game._battle_end_grace_until = 0.0
        game.state = BattleState()
        return game

    def test_reinforcement_restores_battle_without_ending_stage(self):
        game = self.make_client()
        game.state.in_battle = False
        packet = b"\x00" * 7 + bytes.fromhex(
            "060001399d0000000000003d9d000000000000"
        )

        game._observe_team_dungeon_packet(0x35, packet)

        self.assertTrue(game.state.in_battle)
        self.assertEqual(game._team_dungeon_reinforcement_seq, 1)
        self.assertEqual(game._team_dungeon_end_seq, 0)

    def test_only_0700_increments_normal_end_sequence(self):
        game = self.make_client()

        game._observe_team_dungeon_packet(0x14, b"\x00" * 7 + b"\x08\x00\x04")
        self.assertEqual(game._team_dungeon_end_seq, 0)

        game._observe_team_dungeon_packet(0x14, b"\x00" * 7 + b"\x07\x00")
        self.assertEqual(game._team_dungeon_end_seq, 1)


if __name__ == "__main__":
    unittest.main()
