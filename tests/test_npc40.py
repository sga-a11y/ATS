import json
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from analyze_pcap import load_frames
from bot import client as client_module
from bot import npc40
from bot.npc40 import is_repeat_dialog, is_repeat_prompt, party_defeated, run_loop
from bot.state import BattleState


ROOT = Path(__file__).resolve().parents[1]


def _c2s_dialog_bodies(name):
    frames, _ = load_frames(str(ROOT / "captures" / name))
    return [f["body"] for f in frames if f["dir"] == "C2S" and f["op"] == 0x14]


class TestNpc40Protocol(unittest.TestCase):
    def test_captures_confirm_yes_and_no_packets(self):
        yes = _c2s_dialog_bodies("40npc_loop_20260720.pcap")
        no = _c2s_dialog_bodies("40npc_choose_no_20260720.pcap")

        self.assertIn(b"\x09\x00\x1e", yes)
        self.assertIn(b"\x09\x00\x1f", no)
        self.assertEqual(no[-3:], [b"\x09\x00\x1f", b"\x06\x00", b"\x06\x00"])

    def test_repeat_prompt_matches_only_exact_server_signal(self):
        self.assertTrue(is_repeat_prompt(0x41, b"\x00" * 7 + b"\x0a\x00\x01"))
        self.assertFalse(is_repeat_prompt(0x41, b"\x00" * 7 + b"\x0a\x00\x00"))
        self.assertFalse(is_repeat_prompt(0x14, b"\x00" * 7 + b"\x0a\x00\x01"))

    def test_repeat_dialog_requires_choice_ready_page(self):
        self.assertTrue(is_repeat_dialog(
            0x14, b"\x00" * 7 + b"\x01\x00\x00\x00\x00\x01\x06\x03\x05" + b"\x00" * 7 + b"\x03\x00"))
        self.assertFalse(is_repeat_dialog(0x14, b"\x00" * 7 + b"\x08\x00\x2a"))
        self.assertFalse(is_repeat_dialog(0x14, b"\x00" * 7 + b"\x01\x00\x03\x00\x02\x00"))

    def test_party_defeated_requires_known_units_and_no_survivor(self):
        unknown = {}
        alive = {
            (3, 2): SimpleNamespace(hp_max=900, hp=1),
            (2, 2): SimpleNamespace(hp_max=1200, hp=0),
        }
        wiped = {
            (3, 2): SimpleNamespace(hp_max=900, hp=0),
            (2, 2): SimpleNamespace(hp_max=1200, hp=0),
        }

        self.assertEqual(party_defeated(unknown), (False, 0, 0))
        self.assertEqual(party_defeated(alive), (False, 1, 2))
        self.assertEqual(party_defeated(wiped), (True, 0, 2))

    def test_battle_action_updates_party_hp_used_by_defeat_detection(self):
        state = BattleState()
        state.ally_hpmax[(3, 2)] = 900
        state.allies.clear()  # 0x34 clears volatile units before late 0x32 action packets
        packet = (b"\x00" * 7 + b"\x01\x00\x11\x00\x01\x02\x10\x27\x01\x01"
                  + b"\x03\x02\x01\x00\x01\x19\x00\x00\x00\x00\x01")

        state.update_0x32(packet)

        self.assertEqual(state.allies[(3, 2)].hp, 0)
        self.assertEqual(party_defeated(state.allies), (True, 0, 1))


class _ScriptedClient:
    def __init__(self):
        self.running = True
        self.sent = []
        self.moves = []
        self.ready = 0
        self._battle_start_seq = 0
        self._npc40_prompt_seq = 0
        self._npc40_last_defeated = False
        self._npc40_last_alive = 10
        self._npc40_last_total = 10

    def navigate_to(self, x, y, flee=True):
        self.moves.append((x, y, flee))
        return True

    def _wait_combat_clear(self, idle=1.0, cap=20.0):
        return True

    def rearm_ready(self):
        self.ready += 1

    def send(self, opcode, payload):
        self.sent.append((opcode, payload))
        yes_count = sum(p == b"\x09\x00\x1e" for _, p in self.sent)
        if payload == b"\x06\x00" and yes_count > self._battle_start_seq:
            self._battle_start_seq += 1


class TestNpc40Loop(unittest.TestCase):
    def test_repeat_prompt_sends_only_one_advance_while_battle_is_loading(self):
        client = _ScriptedClient()
        client.send = lambda opcode, payload: client.sent.append((opcode, payload))
        sleeps = 0

        def delayed_battle_start(_seconds):
            nonlocal sleeps
            sleeps += 1
            if sleeps == 5:
                client._battle_start_seq += 1

        self.assertTrue(npc40._confirm_repeat_battle(
            client, 0, threading.Event(), delayed_battle_start,
            poll_interval=0.1, checks=20,
        ))
        self.assertEqual(client.sent, [
            (0x14, b"\x09\x00\x1e"),
            (0x14, b"\x06\x00"),
        ])

    def test_loop_repeats_after_win_then_selects_no_after_defeat(self):
        client = _ScriptedClient()
        losses = []
        heals = []

        def scripted_sleep(_seconds):
            if client._battle_start_seq > client._npc40_prompt_seq:
                client._npc40_prompt_seq += 1
                client._npc40_last_defeated = client._npc40_prompt_seq >= 2

        with mock.patch.object(
                npc40, "in_event_window", side_effect=[True, True, True, False]):
            result = run_loop(
                client,
                (910, 290),
                threading.Event(),
                lambda: losses.append(True),
                before_repeat=lambda: heals.append(True),
                sleep_fn=scripted_sleep,
                poll_interval=0,
                max_advances=4,
            )

        choices = [payload for opcode, payload in client.sent
                   if opcode == 0x14 and payload[:2] == b"\x09\x00"]
        self.assertTrue(result)
        self.assertEqual(client.moves, [(910, 290, False)])
        self.assertEqual(client.ready, 1)
        self.assertEqual(choices, [
            b"\x09\x00\x1e", b"\x09\x00\x1e",
            b"\x09\x00\x1e", b"\x09\x00\x1f",
        ])
        self.assertEqual(client.sent[-3:], [
            (0x14, b"\x09\x00\x1f"),
            (0x14, b"\x06\x00"),
            (0x14, b"\x06\x00"),
        ])
        self.assertEqual(losses, [True])
        self.assertEqual(heals, [])

    def test_casualty_closes_dialog_before_heal_then_reopens_npc(self):
        client = _ScriptedClient()
        heal_at = []

        def scripted_sleep(_seconds):
            if client._battle_start_seq > client._npc40_prompt_seq:
                client._npc40_prompt_seq += 1
                client._npc40_last_alive = 5 if client._npc40_prompt_seq == 1 else 10

        with mock.patch.object(npc40, "in_event_window", side_effect=[True, False]):
            self.assertTrue(run_loop(
                client, (910, 290), threading.Event(), lambda: None,
                before_repeat=lambda: heal_at.append(len(client.sent)),
                sleep_fn=scripted_sleep, poll_interval=0, max_advances=4,
            ))

        self.assertEqual(len(heal_at), 1)
        before_heal = [payload for _opcode, payload in client.sent[:heal_at[0]]]
        self.assertEqual(before_heal[-3:], [npc40.CHOOSE_NO, npc40.ADVANCE, npc40.ADVANCE])
        after_heal = client.sent[heal_at[0]:]
        self.assertIn((npc40.OP_EVENT, npc40.OPEN_EVENT), after_heal)
        self.assertIn((npc40.OP_DIALOG, npc40.OPEN_NPC), after_heal)

    def test_npc40_config_contains_captured_party_point(self):
        events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))["events"]
        self.assertEqual(events["npc_40"]["party_battle"], {
            "kind": "npc_repeat",
            "point": [910, 290],
        })

    def test_android_asset_and_sync_script_include_npc40_flow(self):
        android_events = json.loads((
            ROOT / "android/app/src/main/assets/train_bot_data/events.json"
        ).read_text(encoding="utf-8"))["events"]
        self.assertEqual(android_events["npc_40"]["party_battle"]["point"], [910, 290])
        sync_source = (ROOT / "tools/sync_apk_python.py").read_text(encoding="utf-8")
        self.assertIn('"npc40.py"', sync_source)
        self.assertIn('"events.json"', sync_source)


class TestNpc40ClientIntegration(unittest.TestCase):
    def _client(self, hp, started=True):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game._label = "test"
        game.running = True
        game._npc40_started = started
        game.bag_slots = {}        # heal_full() doc tui -> fixture __new__ phai tu dat
        game.bag_counts = {}
        game._battle_start_seq = 0
        game._npc40_prompt_seq = 0
        game._npc40_prompt_pending = False
        game._npc40_prompt_pending_at = 0.0
        game._npc40_last_defeated = False
        game._battle_end_grace_until = 0.0
        game.state = SimpleNamespace(
            in_battle=True,
            allies={(3, 2): SimpleNamespace(hp_max=900, hp=hp)},
        )
        return game

    def test_inactive_observer_preserves_train_battle_latch(self):
        game = self._client(hp=1, started=False)
        game.state._battle_counted = True
        game._battle_end_grace_until = 123.0

        game._observe_npc40_packet(0x41, b"\x00" * 7 + b"\x0a\x00\x01")

        self.assertTrue(game.state.in_battle)
        self.assertTrue(game.state._battle_counted)
        self.assertEqual(game._npc40_prompt_seq, 0)
        self.assertFalse(game._npc40_last_defeated)
        self.assertEqual(game._battle_end_grace_until, 123.0)

    def test_packet_observer_tracks_battle_and_defeat_prompt(self):
        game = self._client(hp=0)

        game._observe_npc40_packet(0x34, b"\x00" * 9)
        game._observe_npc40_packet(0x41, b"\x00" * 7 + b"\x0a\x00\x00")
        game._observe_npc40_packet(0x41, b"\x00" * 7 + b"\x0a\x00\x01")

        self.assertEqual(game._npc40_prompt_seq, 0)
        self.assertTrue(game.state.in_battle)

        game._observe_npc40_packet(
            0x14, b"\x00" * 7 + b"\x01\x00\x00\x00\x00\x01\x06\x03\x05" + b"\x00" * 7 + b"\x03\x00")

        self.assertEqual(game._battle_start_seq, 1)
        self.assertEqual(game._npc40_prompt_seq, 1)
        self.assertTrue(game._npc40_last_defeated)
        self.assertEqual((game._npc40_last_alive, game._npc40_last_total), (0, 1))
        self.assertFalse(game.state.in_battle)

    def test_packet_observer_waits_through_status_page_for_choice_dialog(self):
        game = self._client(hp=1)

        game._observe_npc40_packet(0x41, b"\x00" * 7 + b"\x0a\x00\x01")
        game._observe_npc40_packet(0x14, b"\x00" * 7 + b"\x08\x00\x2a")

        self.assertEqual(game._npc40_prompt_seq, 0)
        self.assertTrue(game.state.in_battle)
        self.assertTrue(game._npc40_prompt_pending)

        game._observe_npc40_packet(
            0x14, b"\x00" * 7 + b"\x01\x00\x00\x00\x00\x01\x06\x03\x05" + b"\x00" * 7 + b"\x03\x00")

        self.assertEqual(game._npc40_prompt_seq, 1)
        self.assertFalse(game.state.in_battle)
        self.assertFalse(game._npc40_prompt_pending)

    def test_start_worker_runs_once_and_stop_sets_event(self):
        game = self._client(hp=1, started=False)
        game._npc40_thread = None
        game._npc40_stop = threading.Event()
        calls = []

        before_repeat = lambda: None

        def fake_loop(client, point, stop_event, on_loss, before_repeat=None):
            calls.append((client, point, stop_event, on_loss, before_repeat))
            return False

        with mock.patch.object(npc40, "run_loop", side_effect=fake_loop):
            self.assertTrue(game.start_npc40_loop((910, 290), lambda: None, before_repeat))
            game._npc40_thread.join(2)
            self.assertFalse(game.start_npc40_loop((910, 290), lambda: None))
            game.stop_npc40_loop()

        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][4], before_repeat)
        self.assertTrue(game._npc40_stop.is_set())

    def test_npc40_quest_battle_does_not_use_items_inside_repeat_dialog(self):
        game = self._client(hp=1)
        game.state.quest_mode = True
        game.state.boss_mode = False
        game.state.in_battle = False
        game._heal_after_battle_active = False
        game.do_heal = mock.Mock()

        with mock.patch.object(client_module.time, "sleep", return_value=None):
            game._heal_after_battle()
        self.assertFalse(hasattr(game, "_heal_after_battle_thread"))
        game.do_heal.assert_not_called()

    def test_npc40_between_battles_revives_dead_char_even_with_zero_threshold(self):
        game = self._client(hp=1)
        game.state.in_battle = False
        game.state.char = SimpleNamespace(hp=0, hp_max=600)
        game.do_heal = mock.Mock()
        game._heal_unit = mock.Mock()

        game.heal_npc40_between_battles()

        game.do_heal.assert_called_once_with(force=True)
        game._heal_unit.assert_called_once_with(
            0, game.state.char, "char", "hp_char", "hp",
            thr_override=0.01, force=True,
        )


if __name__ == "__main__":
    unittest.main()
