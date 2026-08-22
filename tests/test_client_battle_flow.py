import unittest

from bot import protocol
from bot import combat
from bot.client import GameClient
from bot.party_battle import clear_party_battles
from tests.test_battle_tracker import SELF_ROLE, battle_create, role_appear


class TestClientBattleFlow(unittest.TestCase):
    def setUp(self):
        clear_party_battles()

    @staticmethod
    def make_client(label, party_idx=19):
        game = GameClient(label, "token")
        game._label = label
        game.party_idx = party_idx
        game.self_entity = SELF_ROLE
        game.state.self_entity = SELF_ROLE
        game.battle_tracker.local_role_id = SELF_ROLE
        game.auto_combat = True
        game._arm_calls = 0
        game._arm_decision = lambda: setattr(game, "_arm_calls", game._arm_calls + 1)
        return game

    @staticmethod
    def packet(opcode, body):
        return protocol.build_packet(opcode, body)

    def start_battle(self, game):
        roles = (
            role_appear(row=0, col=1, hp=2000),
            role_appear(role_id=SELF_ROLE, row=3, col=2, hp=1000, hp_max=1000),
            role_appear(role_id=b"PETROLE_", row=2, col=2, hp=800, hp_max=800),
        )
        game._track_battle_packet(0x0B, self.packet(0x0B, battle_create(*roles)))

    def test_status_packet_never_arms_a_decision(self):
        game = self.make_client("a")
        self.start_battle(game)

        game._track_battle_packet(
            0x35,
            self.packet(0x35, b"\x01\x00\x00\x01\x01\x06\x2b"),
        )

        self.assertEqual(game._arm_calls, 0)

    def test_local_turn_builds_options_from_roster_and_arms_once(self):
        game = self.make_client("a")
        self.start_battle(game)

        game._track_battle_packet(0x34, self.packet(0x34, b"\x01\x00"))

        self.assertEqual(game._arm_calls, 1)
        self.assertEqual(game.available[3], [(2, 1)])
        self.assertEqual(game.available[2], [(2, 1)])
        self.assertTrue(game._battle_can_send((3, 2)))

    def test_acc_chua_thay_turn_cua_minh_VAN_duoc_gui(self):
        """DOI CHINH SACH (bug that 17:09): truoc day acc chua thay turn cua chinh no thi bi CHAN
        gui -> phien lech la nuot sach lenh danh, tran dung hinh (enemy_hp 488/488/488 suot 4 luot).
        Nay can_send CHI chan lenh TRUNG. Chua dong bo thi VAN GUI, chi log canh bao."""
        fast = self.make_client("fast")
        slow = self.make_client("slow")
        self.start_battle(fast)
        self.start_battle(slow)

        fast._track_battle_packet(0x34, self.packet(0x34, b"\x01\x00"))

        self.assertTrue(fast._battle_can_send((3, 2)))
        self.assertTrue(slow._battle_can_send((3, 2)), "lech phien lai bi nuot lenh danh")
        slow._track_battle_packet(0x34, self.packet(0x34, b"\x01\x00"))
        self.assertTrue(slow._battle_can_send((3, 2)))

    def test_account_missing_create_bootstraps_on_its_own_turn_packet(self):
        fast = self.make_client("fast")
        late = self.make_client("late")
        self.start_battle(fast)
        fast._track_battle_packet(0x34, self.packet(0x34, b"\x01\x00"))

        self.assertEqual(late.battle_tracker.generation, 0)

        late._track_battle_packet(0x34, self.packet(0x34, b"\x01\x00"))

        self.assertEqual(
            (late.battle_tracker.generation, late.battle_tracker.turn),
            (1, 1),
        )
        self.assertEqual(late.state.enemy_hp, {1: 2000})
        self.assertEqual(late._arm_calls, 1)
        self.assertTrue(late._battle_can_send((3, 2)))

    def test_first_local_turn_advances_bootstrapped_start_snapshot(self):
        source = self.make_client("source")
        first = self.make_client("first")
        self.start_battle(source)

        first._track_battle_packet(0x34, self.packet(0x34, b"\x01\x00"))

        self.assertEqual(
            (first.battle_tracker.generation, first.battle_tracker.turn),
            (1, 1),
        )
        self.assertEqual(first._battle_coordinator().active_key, (1, 1))
        self.assertEqual(first._arm_calls, 1)

    def test_dialog_does_not_end_active_tracker(self):
        game = self.make_client("a")
        self.start_battle(game)

        game._track_battle_packet(0x14, self.packet(0x14, b"\x08\x00\x04"))

        self.assertTrue(game.battle_tracker.active)
        self.assertTrue(game.state.in_battle)

    def test_empty_enemy_roster_and_idle_time_do_not_end_battle_without_server_end(self):
        game = self.make_client("a", party_idx=19001)
        game.state.in_battle = True
        game.state.enemy_slots = []
        game.last_turn_time = 0.0

        self.assertTrue(game.in_combat())
        self.assertTrue(game.state.in_battle)

    def test_server_end_packet_ends_an_active_battle(self):
        game = self.make_client("a")
        self.start_battle(game)
        game._dispatch(0x35, self.packet(0x35, b"\x03\x00\x00\x01"))

        game._dispatch(0x14, self.packet(0x14, b"\x08\x00\x04"))

        self.assertFalse(game.battle_tracker.active)
        self.assertFalse(game.state.in_battle)

    def test_pb110_reinforcement_dialog_does_not_end_empty_wave(self):
        game = self.make_client("a")
        game._active_team_dungeon_level = 110
        self.start_battle(game)
        game._dispatch(0x35, self.packet(0x35, b"\x03\x00\x00\x01"))

        game._dispatch(0x14, self.packet(0x14, b"\x08\x00\x04"))

        self.assertTrue(game.battle_tracker.active)
        self.assertTrue(game.state.in_battle)

    def test_only_matching_local_fight_over_ends_tracker(self):
        game = self.make_client("a")
        self.start_battle(game)

        game._track_battle_packet(
            0x0B,
            self.packet(0x0B, b"\x00\x00OTHER___\x00\x00"),
        )
        self.assertTrue(game.state.in_battle)
        game._track_battle_packet(
            0x0B,
            self.packet(0x0B, b"\x00\x00SELFROLE\x00\x00"),
        )
        self.assertFalse(game.state.in_battle)

    def test_dispatch_uses_tracker_and_does_not_clear_roster_each_turn(self):
        game = self.make_client("a")
        roles = (
            role_appear(row=0, col=1, hp=2000),
            role_appear(role_id=SELF_ROLE, row=3, col=2, hp=1000, hp_max=1000),
        )

        game._dispatch(0x0B, self.packet(0x0B, battle_create(*roles)))
        game._dispatch(0x34, self.packet(0x34, b"\x01\x00"))

        self.assertEqual(game.state.enemy_hp, {1: 2000})
        self.assertEqual(game.battle_tracker.turn, 1)
        self.assertEqual(game._arm_calls, 1)

    def test_dispatch_zero_status_record_does_not_arm_decision(self):
        game = self.make_client("a")
        self.start_battle(game)

        game._dispatch(
            0x35,
            self.packet(0x35, b"\x01\x00\x03\x02\x01\x00\x00"),
        )

        self.assertEqual(game._arm_calls, 0)

    def test_dispatch_dialog_cannot_end_active_battle(self):
        game = self.make_client("a")
        self.start_battle(game)

        game._dispatch(0x14, self.packet(0x14, b"\x08\x00\x04"))

        self.assertTrue(game.state.in_battle)

    def test_send_la_MOT_LAN_moi_source_nhung_khong_doi_local_turn(self):
        """Chong TRUNG thi giu; chan vi "chua co local turn" thi BO (xem test lech phien o tren)."""
        game = self.make_client("a")
        self.start_battle(game)
        sent = []
        game.send = lambda opcode, payload: sent.append((opcode, payload))
        decision = combat.Decision(3, 2, 1, 10000, b=0)

        game._track_battle_packet(0x34, self.packet(0x34, b"\x01\x00"))
        self.assertTrue(game._send_combat(decision, tail=b"\x01\x02"))
        self.assertFalse(game._send_combat(decision, tail=b"\x03\x04"),
                         "gui TRUNG cung (source,g,t) - phai bi chan")

        self.assertEqual(len(sent), 1)
        self.assertIn((3, 2), game.battle_tracker.pending_actions)

    def test_action_ack_clears_only_local_pending_source(self):
        game = self.make_client("a")
        self.start_battle(game)
        game.send = lambda opcode, payload: None
        game._track_battle_packet(0x34, self.packet(0x34, b"\x01\x00"))
        game._send_combat(combat.Decision(3, 2, 1, 10000, b=0), tail=b"\x01\x02")

        game._dispatch(0x35, self.packet(0x35, b"\x05\x00\x03\x02"))

        self.assertNotIn((3, 2), game.battle_tracker.pending_actions)

    def test_authoritative_end_runs_existing_end_hooks_once(self):
        game = self.make_client("a")
        self.start_battle(game)
        game._active_team_dungeon_level = 110
        game._heal_calls = 0
        game._heal_after_battle = lambda: setattr(game, "_heal_calls", game._heal_calls + 1)
        before = game._team_dungeon_end_seq

        end = self.packet(0x0B, b"\x00\x00SELFROLE\x00\x00")
        game._track_battle_packet(0x0B, end)
        game._track_battle_packet(0x0B, end)

        self.assertGreater(game._genuine_end_seen, 0)
        self.assertEqual(game._team_dungeon_end_seq, before + 1)
        self.assertEqual(game._heal_calls, 1)

    def test_pb110_dialog_summary_does_not_double_count_tracker_end(self):
        game = self.make_client("a")
        game._active_team_dungeon_level = 110
        self.start_battle(game)
        before = game._team_dungeon_end_seq

        game._observe_team_dungeon_packet(0x14, self.packet(0x14, b"\x07\x00"))
        game._track_battle_packet(
            0x0B,
            self.packet(0x0B, b"\x00\x00SELFROLE\x00\x00"),
        )

        self.assertEqual(game._team_dungeon_end_seq, before + 1)

    def test_send_and_ack_have_per_account_logs(self):
        # Log SEND/ACK bi GATE boi _log_battle_verbose() = "chi in o LEADER". Test nay tung do
        # config THAT cua may dev (PARTY_LEADER_ACC[19]='dieu901' != 'a') -> gate tat -> khong co
        # dong log nao -> fail. Tren may sach (config.example.py) lai pass. Test khong duoc phu
        # thuoc config cua may chay: ep PARTY_LEADER_ACC rong = "solo" -> gate luon bat.
        from bot import config
        _cu = config.PARTY_LEADER_ACC
        config.PARTY_LEADER_ACC = {}
        self.addCleanup(setattr, config, "PARTY_LEADER_ACC", _cu)
        game = self.make_client("a")
        self.start_battle(game)
        game.send = lambda opcode, payload: None
        game._track_battle_packet(0x34, self.packet(0x34, b"\x01\x00"))

        with self.assertLogs("bot", level="INFO") as captured:
            game._send_combat(combat.Decision(3, 2, 1, 10000, b=0), tail=b"\x01\x02")
            game._track_battle_packet(0x35, self.packet(0x35, b"\x05\x00\x03\x02"))

        lines = "\n".join(captured.output)
        self.assertIn("[a] BATTLE SEND g=1 t=1 source=(3, 2)", lines)
        self.assertIn("[a] BATTLE ACK g=1 t=1 source=(3, 2)", lines)


if __name__ == "__main__":
    unittest.main()
