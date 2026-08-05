import ast
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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

    def test_pb110_observer_tracks_battle_start(self):
        game = self.make_client()
        game._battle_start_seq = 7

        game._observe_team_dungeon_packet(0x34, b"\x00" * 9)

        self.assertEqual(game._battle_start_seq, 8)


class TestTeamDungeon110Execution(unittest.TestCase):
    def test_coordinator_runs_pb110_when_whole_party_has_turns(self):
        with mock.patch.object(sys, "argv", [sys.argv[0]]):
            import run_party_digioi as coordinator

        game = SimpleNamespace(
            running=True,
            state=SimpleNamespace(quest_mode=False),
            wait_team_dungeon_status=mock.Mock(return_value=True),
            team_dungeon_remaining=mock.Mock(return_value=1),
            do_team_dungeon=mock.Mock(return_value=True),
            _phoban_until=0.0,
            _team_dungeon_until=0.0,
        )
        state = {
            "lock": threading.Lock(),
            "team_dungeon_done_by": {110: {"member": 1}},
            "team_dungeon_state": {},
            "team_dungeon_broke": {},
            "reconnecting": set(),
            "disc_gen": 0,
            "reform_gen": 0,
        }

        with (
            mock.patch.object(coordinator, "party_accounts", return_value=[("leader",), ("member",)]),
            mock.patch.object(coordinator.config, "PARTY_LEADER_ACC", {0: "leader"}),
        ):
            result = coordinator._handle_auto_team_dungeon(
                game, state, "leader", "leader", 0, True, lambda: False, 110
            )

        self.assertTrue(result)
        game.do_team_dungeon.assert_called_once_with(110)

    def test_dispatch_calls_pb110(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.do_team_dungeon_lv110 = mock.Mock(return_value=True)

        self.assertTrue(game.do_team_dungeon(110))

        game.do_team_dungeon_lv110.assert_called_once_with()

    def test_end_wait_ignores_empty_enemies_and_false_combat(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.running = True
        game._team_dungeon_end_seq = 4
        game.state = BattleState()
        game.state.in_battle = False

        def stop_client(_seconds):
            game.running = False

        with mock.patch.object(client_module.time, "sleep", side_effect=stop_client):
            self.assertFalse(game._wait_team_dungeon_end(4, timeout=1.0))

    def test_wrapper_always_clears_pb110_mode(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.state = BattleState()
        game._team_dungeon_until = 10.0
        game._phoban_until = 10.0

        with mock.patch.object(game, "_do_team_dungeon_lv110_inner", return_value=False):
            self.assertFalse(game.do_team_dungeon_lv110())

        self.assertIsNone(game._active_team_dungeon_level)
        self.assertFalse(game.state.quest_mode)
        self.assertEqual(game._team_dungeon_until, 0.0)
        self.assertEqual(game._phoban_until, 0.0)

    def test_stage_runs_captured_actions_then_waits_for_explicit_end(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.running = True
        game._label = "pb110-test"
        game._battle_start_seq = 10
        game._team_dungeon_end_seq = 20
        game.send = mock.Mock()
        game._route_move = mock.Mock()
        game.heal_full = mock.Mock()
        game._wait_team_dungeon_end = mock.Mock(return_value=True)

        def advance(n=1, gap=0.4):
            game._battle_start_seq += 1

        game._adv_dialog = mock.Mock(side_effect=advance)
        with mock.patch.object(client_module.time, "sleep", return_value=None):
            self.assertTrue(game._run_team_dungeon_lv110_stage(pb110.STAGES[1], 2))

        self.assertEqual(
            game._route_move.call_args_list,
            [
                mock.call(490, 2410),
                mock.call(222, 2446),
                mock.call(126, 2459),
                mock.call(50, 2470),
                mock.call(50, 2470),
            ],
        )
        game.heal_full.assert_called_once_with(force=True)
        game._wait_team_dungeon_end.assert_called_once_with(20)

    def test_force_full_heal_bypasses_post_battle_busy_window(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game._label = "pb110-test"
        game.state = BattleState()
        game.state.char.hp, game.state.char.hp_max = 100, 500
        game.state.char.sp, game.state.char.sp_max = 20, 200
        game.state.pet.hp, game.state.pet.hp_max = 200, 800
        game.state.pet.sp, game.state.pet.sp_max = 30, 300
        game.state.solo_multipet = False
        game.bag_slots = {1: [0x1234, 99]}
        game.active_pet_slot = 3
        game.in_combat = mock.Mock(return_value=True)
        game._heal_unit = mock.Mock()

        game.heal_full(force=True)

        self.assertEqual(game._heal_unit.call_count, 4)
        for call in game._heal_unit.call_args_list:
            self.assertEqual(call.kwargs["thr_override"], 1.0)
            self.assertTrue(call.kwargs["force"])

    @staticmethod
    def configured_inner_client(completes=True):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.running = True
        game._label = "pb110-test"
        game.state = BattleState()
        game._create_team_dungeon_room = mock.Mock(return_value=True)
        game.scene_resume = mock.Mock()
        game.set_party_strategist = mock.Mock()
        game._run_team_dungeon_lv110_stage = mock.Mock(return_value=True)
        game._wait_team_dungeon_complete = mock.Mock(return_value=completes)
        game._adv_dialog = mock.Mock()
        game._route_move = mock.Mock()
        game.heal_full = mock.Mock()
        game.leave_party = mock.Mock()
        return game

    def test_inner_runs_five_stages_and_leaves_after_verified_completion(self):
        game = self.configured_inner_client(completes=True)

        with mock.patch.object(client_module.time, "sleep", return_value=None):
            self.assertTrue(game._do_team_dungeon_lv110_inner())

        self.assertEqual(
            [call.args[1] for call in game._run_team_dungeon_lv110_stage.call_args_list],
            [1, 2, 3, 4, 5],
        )
        game._wait_team_dungeon_complete.assert_called_once_with()
        game.heal_full.assert_called_once_with(force=True)
        game._adv_dialog.assert_called_with(7, gap=0.4)
        game._route_move.assert_called_with(2124, 283)
        game.leave_party.assert_called_once_with()

    def test_inner_does_not_leave_when_final_completion_times_out(self):
        game = self.configured_inner_client(completes=False)

        with mock.patch.object(client_module.time, "sleep", return_value=None):
            self.assertFalse(game._do_team_dungeon_lv110_inner())

        game.leave_party.assert_not_called()
        game._route_move.assert_not_called()


def client_methods(path, wanted):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: ast.dump(node, include_attributes=False)
        for cls in tree.body
        if isinstance(cls, ast.ClassDef) and cls.name == "GameClient"
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    }


class TestTeamDungeon110AndroidParity(unittest.TestCase):
    def test_pb110_module_is_shared_verbatim(self):
        self.assertEqual(
            (ROOT / "bot/team_dungeon_lv110.py").read_bytes(),
            (ROOT / "android/app/src/main/python/train_bot/team_dungeon_lv110.py").read_bytes(),
        )

    def test_pb110_client_methods_match(self):
        wanted = {
            "_observe_team_dungeon_packet",
            "_wait_team_dungeon_end",
            "_wait_team_dungeon_complete",
            "_run_team_dungeon_lv110_stage",
            "do_team_dungeon_lv110",
            "_do_team_dungeon_lv110_inner",
        }

        self.assertEqual(
            client_methods(ROOT / "bot/client.py", wanted),
            client_methods(
                ROOT / "android/app/src/main/python/train_bot/client.py", wanted
            ),
        )


if __name__ == "__main__":
    unittest.main()
