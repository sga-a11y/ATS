import unittest
from types import SimpleNamespace

from bot.party_route import decide_route, execute_route_action


def account(user, map_id, channel=1, alive=True):
    return SimpleNamespace(username=user, map_id=map_id, kenh=channel, song=alive)


def plan(**changes):
    value = {"source": 200, "dest": 300, "city": 100, "flag": 4,
             "users": ["lead", "member"], "phase": "gather", "lag_since": None}
    value.update(changes)
    return value


class DecideRouteTests(unittest.TestCase):
    def test_gathers_every_account_before_channel_or_route(self):
        result = decide_route(plan(), [account("lead", 10), account("member", 100)],
                              "lead", channel_target=1, joined_members=0, now=10)
        self.assertEqual(result.actions, {"lead": "route_gather", "member": "nghi"})
        self.assertEqual(result.phase, "gather")
        self.assertFalse(result.complete)

    def test_all_at_source_skip_city_and_wait_for_real_roster(self):
        result = decide_route(plan(), [account("lead", 200), account("member", 200)],
                              "lead", channel_target=1, joined_members=0)
        self.assertEqual(result.actions, {"lead": "lap_party", "member": "lap_party"})
        self.assertEqual(result.phase, "sync_source")
        ready = decide_route(plan(phase=result.phase),
                             [account("lead", 200), account("member", 200)],
                             "lead", channel_target=1, joined_members=1)
        self.assertEqual(ready.actions, {"lead": "route_dest", "member": "nghi"})
        self.assertEqual(ready.phase, "dest")

    def test_channel_must_be_known_and_match_before_invite(self):
        waiting = decide_route(plan(phase="sync_city"),
                               [account("lead", 100, 1), account("member", 100, 2)],
                               "lead", joined_members=0)
        self.assertEqual(waiting.actions, {"lead": "nghi", "member": "nghi"})
        switching = decide_route(plan(phase="sync_city"),
                                 [account("lead", 100, 1), account("member", 100, 2)],
                                 "lead", channel_target=1, joined_members=0)
        self.assertEqual(switching.actions, {"lead": "nghi", "member": "doi_kenh"})

    def test_already_same_channel_invites_without_selected_target(self):
        result = decide_route(plan(phase="sync_city"),
                              [account("lead", 100, 7), account("member", 100, 7)],
                              "lead", joined_members=0)
        self.assertEqual(result.actions, {"lead": "lap_party", "member": "lap_party"})

    def test_only_route_leader_traverses_source_then_destination(self):
        source = decide_route(plan(phase="source"),
                              [account("lead", 100), account("member", 100)],
                              "lead", channel_target=1, joined_members=1)
        self.assertEqual(source.actions, {"lead": "route_source", "member": "nghi"})
        arrived = decide_route(plan(phase="source"),
                               [account("lead", 200), account("member", 200)],
                               "lead", channel_target=1, joined_members=1)
        self.assertEqual(arrived.actions, {"lead": "route_dest", "member": "nghi"})

    def test_short_follower_lag_keeps_route_action_but_timeout_regathers(self):
        recent = decide_route(plan(phase="dest", lag_since=80),
                              [account("lead", 250), account("member", 200)],
                              "lead", channel_target=1, joined_members=1, now=100)
        self.assertEqual(recent.actions["lead"], "route_dest")
        self.assertEqual(recent.lag_since, 80)
        stale = decide_route(plan(phase="dest", lag_since=80),
                             [account("lead", 250), account("member", 200)],
                             "lead", channel_target=1, joined_members=1, now=111)
        self.assertEqual(stale.phase, "gather")
        self.assertNotEqual(stale.actions["lead"], "route_dest")

    def test_missing_account_or_unknown_map_never_completes_or_traverses(self):
        for people in ([account("lead", 200)],
                       [account("lead", 200), account("member", None)],
                       [account("lead", 200), account("member", 200, alive=False)]):
            result = decide_route(plan(phase="dest"), people, "lead",
                                  channel_target=1, joined_members=1)
            self.assertFalse(result.complete)
            self.assertNotIn("route_dest", result.actions.values())

    def test_progress_to_another_map_restarts_follower_grace(self):
        result = decide_route(plan(phase="dest", lag_since=80, leader_map=240),
                              [account("lead", 250), account("member", 240)],
                              "lead", channel_target=1, joined_members=1, now=111)
        self.assertEqual(result.phase, "dest")
        self.assertEqual(result.actions["lead"], "route_dest")
        self.assertEqual(result.lag_since, 111)

    def test_completion_waits_for_every_account_at_destination(self):
        partial = decide_route(plan(phase="dest"),
                               [account("lead", 300), account("member", 200)],
                               "lead", channel_target=1, joined_members=1, now=10)
        self.assertFalse(partial.complete)
        done = decide_route(plan(phase="dest"),
                            [account("lead", 300), account("member", 300)],
                            "lead", channel_target=1, joined_members=1)
        self.assertTrue(done.complete)

    def test_temporary_party_disbands_before_completion(self):
        p = plan(phase="dest", temporary_party=True)
        people = [account("lead", 300), account("member", 300)]
        leaving = decide_route(p, people, "lead", joined_members=1)
        self.assertFalse(leaving.complete)
        self.assertEqual(leaving.actions,
                         {"lead": "route_finish", "member": "route_finish"})
        done = decide_route(p, people, "lead", joined_members=0)
        self.assertTrue(done.complete)


class ExecuteRouteTests(unittest.TestCase):
    def test_gather_uses_existing_city_hop_and_town_teleport(self):
        calls = []
        client = SimpleNamespace(pre_route_town_hop=lambda: calls.append("hop"),
                                 go_to_town=lambda city, flag: calls.append((city, flag)) or True)
        self.assertTrue(execute_route_action("route_gather", client, plan()))
        self.assertEqual(calls, ["hop", (100, 4)])

    def test_route_uses_existing_smart_paths_and_cancel_predicate(self):
        calls = []
        client = SimpleNamespace(
            current_map=100,
            follow_smart_route=lambda dest, safe, abort, flee:
                calls.append(("source", dest, flee, abort())) or True,
            follow_smart_scene_route=lambda source, dest, safe, abort, flee:
                calls.append(("dest", source, dest, flee, abort())) or True)
        p = plan()
        self.assertTrue(execute_route_action("route_source", client, p, abort=lambda: False))
        client.current_map = 200
        self.assertTrue(execute_route_action("route_dest", client, p, abort=lambda: False))
        self.assertEqual(calls, [("source", 200, False, False),
                                 ("dest", 200, 300, False, False)])

    def test_cancel_before_action_prevents_game_calls(self):
        calls = []
        client = SimpleNamespace(go_to_town=lambda *_: calls.append("travel"))
        self.assertFalse(execute_route_action("route_gather", client, plan(),
                                              abort=lambda: True))
        self.assertEqual(calls, [])

    def test_destination_retry_resumes_from_current_intermediate_map(self):
        calls = []
        client = SimpleNamespace(current_map=250,
            follow_smart_scene_route=lambda source, dest, safe, abort, flee:
                calls.append((source, dest)) or source == 250)
        self.assertTrue(execute_route_action("route_dest", client, plan()))
        self.assertEqual(calls, [(250, 300)])

    def test_finish_uses_supplied_party_cleanup(self):
        calls = []
        client = object()
        self.assertTrue(execute_route_action("route_finish", client, plan(),
                                             finish=lambda c: calls.append(c)))
        self.assertEqual(calls, [client])


if __name__ == "__main__":
    unittest.main()
