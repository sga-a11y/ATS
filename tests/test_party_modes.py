import unittest
from types import SimpleNamespace

from bot.party_modes import decide_mode, execute_mode_action


def acc(username, map_id, *, fighting=False, busy=False, alive=True):
    return SimpleNamespace(username=username, map_id=map_id, dang_danh=fighting,
                           dang_ban=busy, song=alive, viec_dang_lam="nghi")


class DecideModeTests(unittest.TestCase):
    def test_active_solo_event_continues_through_its_battle(self):
        account = acc("a", 99, fighting=True, busy=True)
        account.viec_dang_lam = "solo_event_run"
        self.assertEqual(decide_mode("event", {"a": "nghi"}, [account],
                                     event_kind="chaos_vs", event_map=99),
                         {"a": "solo_event_run"})

    def test_train_keeps_existing_party_decisions(self):
        original = {"a": "train", "b": "lap_party"}
        self.assertEqual(decide_mode("train", original, [acc("a", 100), acc("b", 100)]),
                         original)

    def test_city_moves_to_configured_town_then_keeps_party_invite(self):
        first = decide_mode("city", {"a": "ve_map", "b": "lap_party"},
                            [acc("a", 12), acc("b", 50)], target_map=50)
        self.assertEqual(first, {"a": "city", "b": "lap_party"})
        arrived = decide_mode("city", {"a": "train"}, [acc("a", 50)], target_map=50)
        self.assertEqual(arrived, {"a": "nghi"})

    def test_city_unknown_target_or_position_does_not_claim_arrival(self):
        self.assertEqual(decide_mode("city", {"a": "ve_map"}, [acc("a", None)],
                                     target_map=50), {"a": "nghi"})
        self.assertEqual(decide_mode("city", {"a": "ve_map"}, [acc("a", 12)]),
                         {"a": "nghi"})

    def test_stand_and_cleanbag_do_not_travel_or_train(self):
        original = {"a": "ve_map", "b": "lap_party", "c": "train"}
        people = [acc("a", 12), acc("b", 12), acc("c", 12)]
        self.assertEqual(decide_mode("stand", original, people),
                         {"a": "nghi", "b": "lap_party", "c": "nghi"})
        self.assertEqual(decide_mode("cleanbag", original, people),
                         {"a": "nghi", "b": "lap_party", "c": "nghi"})

    def test_daily_and_manual_commands_keep_priority(self):
        original = {"a": "daily", "b": "lenh_tay", "c": "login_chore"}
        people = [acc(name, 12) for name in original]
        self.assertEqual(decide_mode("city", original, people, target_map=50), original)
        self.assertEqual(decide_mode("event", original, people,
                                     event_kind="chaos_vs", event_map=99), original)

    def test_manual_pending_overrides_mode_action(self):
        self.assertEqual(decide_mode("city", {"a": "train"}, [acc("a", 12)],
                                     target_map=50, manual_pending={"a"}),
                         {"a": "lenh_tay"})

    def test_solo_chaos_never_inherits_party_or_channel_actions(self):
        original = {"a": "lap_party", "b": "doi_kenh", "c": "ve_map"}
        people = [acc("a", 10), acc("b", 99), acc("c", 99)]
        self.assertEqual(decide_mode("event", original, people,
                                     event_kind="chaos_vs", event_map=99),
                         {"a": "solo_event_enter", "b": "solo_event_run",
                          "c": "solo_event_run"})

    def test_solo_chaos_exits_when_done_or_window_closed(self):
        original = {"a": "train", "b": "train"}
        people = [acc("a", 99), acc("b", 99)]
        self.assertEqual(decide_mode("event", original, people,
                                     event_kind="chaos_vs", event_map=99,
                                     event_done={"a"}),
                         {"a": "solo_event_exit", "b": "solo_event_run"})
        self.assertEqual(decide_mode("event", original, people,
                                     event_kind="chaos_vs", event_map=99,
                                     event_open=False),
                         {"a": "solo_event_exit", "b": "solo_event_exit"})

    def test_solo_chaos_missing_event_map_waits_without_party_commands(self):
        self.assertEqual(decide_mode("event", {"a": "lap_party"}, [acc("a", 99)],
                                     event_kind="chaos_vs"), {"a": "nghi"})

    def test_battle_and_busy_worker_do_not_receive_new_movement(self):
        people = [acc("a", 10, fighting=True), acc("b", 10, busy=True)]
        self.assertEqual(decide_mode("city", {"a": "train", "b": "daily"},
                                     people, target_map=50),
                         {"a": "nghi", "b": "daily"})


class ExecuteModeActionTests(unittest.TestCase):
    def test_city_calls_existing_route_once_with_configured_destination(self):
        calls = []
        client = object()
        result = execute_mode_action("city", client, target_map=50, city_flag=3,
                                     go_to_city=lambda c, m, f: calls.append((c, m, f)) or True)
        self.assertTrue(result)
        self.assertEqual(calls, [(client, 50, 3)])

    def test_solo_event_uses_existing_enter_and_worker_loop(self):
        calls = []
        client = SimpleNamespace(current_map=99,
                                 go_to_event=lambda ev: calls.append(("enter", ev)) or True)
        event = {"dest_map": 99, "party_battle": {"point": [910, 290]}}
        self.assertTrue(execute_mode_action("solo_event_enter", client, event=event))
        self.assertTrue(execute_mode_action(
            "solo_event_run", client, event=event, one_battle=True,
            run_chaos=lambda c, p, abort, before, once, ev:
                calls.append(("run", c, p, once, ev)) or True))
        self.assertEqual(calls, [("enter", event),
                                 ("run", client, (910, 290), True, event)])

    def test_cancelled_action_never_calls_game_api(self):
        calls = []
        self.assertFalse(execute_mode_action(
            "city", object(), target_map=50, abort=lambda: True,
            go_to_city=lambda *_: calls.append("move")))
        self.assertEqual(calls, [])

    def test_solo_run_refuses_wrong_map_and_does_not_register(self):
        calls = []
        client = SimpleNamespace(current_map=12)
        self.assertFalse(execute_mode_action(
            "solo_event_run", client, event={"dest_map": 99},
            run_chaos=lambda *_: calls.append("register")))
        self.assertEqual(calls, [])

    def test_solo_event_exit_leaves_map_then_stops_account(self):
        calls = []
        client = object()
        event = {"dest_map": 99}
        self.assertTrue(execute_mode_action(
            "solo_event_exit", client, event=event,
            leave_solo_event=lambda c, ev: calls.append(("leave", c, ev)),
            stop=lambda c: calls.append(("stop", c))))
        self.assertEqual(calls, [("leave", client, event), ("stop", client)])


if __name__ == "__main__":
    unittest.main()
