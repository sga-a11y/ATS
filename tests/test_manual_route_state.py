import ast
import sys
import unittest
from unittest import mock

_argv = sys.argv
try:
    sys.argv = ["run_party_digioi.py"]
    import run_party_digioi as coordinator
finally:
    sys.argv = _argv


class TestManualRouteState(unittest.TestCase):
    def setUp(self):
        self.pidx = 9101
        self.other_pidx = 9102
        self.username = "manual_route_fresh_start_test"
        coordinator._party_state.pop(self.pidx, None)
        coordinator._party_state.pop(self.other_pidx, None)
        coordinator.account_threads.pop(self.username, None)
        coordinator.account_stops.pop(self.username, None)

    def tearDown(self):
        coordinator._party_state.pop(self.pidx, None)
        coordinator._party_state.pop(self.other_pidx, None)
        coordinator.account_threads.pop(self.username, None)
        coordinator.account_stops.pop(self.username, None)

    @staticmethod
    def _seed_stale_route(state):
        state["cmd"] = ("route", 18021, 21011)
        state["cmd_gen"] = 7
        state["manual_route_gen"] = 7
        state["manual_route_plan"] = {"source": 18021, "dest": 21011}
        state["manual_route_source_results"] = {"old": False}
        state["manual_route_city_arrived"] = {"old": True}
        state["manual_route_plan_ready"].set()
        state["manual_route_source_done"].set()
        state["manual_route_party_ready"].set()
        state["manual_route_done"].clear()

    @mock.patch.object(coordinator, "_active_party_usernames", return_value=[])
    @mock.patch.object(coordinator, "_running_party_usernames", return_value=[])
    @mock.patch.object(coordinator, "party_accounts",
                       return_value=[("manual_route_fresh_start_test", "password", False, True)])
    @mock.patch.object(coordinator.threading, "Thread")
    def test_fresh_account_start_clears_only_its_stale_manual_route(
            self, thread_cls, _accounts, _running, _active):
        state = coordinator._pstate(self.pidx)
        other = coordinator._pstate(self.other_pidx)
        self._seed_stale_route(state)
        self._seed_stale_route(other)

        self.assertTrue(coordinator.start_account(
            self.username, "password", self.pidx, False, True
        ))

        self.assertIsNone(state["cmd"])
        self.assertEqual(state["cmd_gen"], 8)
        self.assertEqual(state["manual_route_gen"], 8)
        self.assertIsNone(state["manual_route_plan"])
        self.assertEqual(state["manual_route_source_results"], {})
        self.assertEqual(state["manual_route_city_arrived"], {})
        self.assertFalse(state["manual_route_plan_ready"].is_set())
        self.assertFalse(state["manual_route_source_done"].is_set())
        self.assertFalse(state["manual_route_party_ready"].is_set())
        self.assertFalse(state["manual_route_done"].is_set())

        self.assertEqual(other["cmd"], ("route", 18021, 21011))
        self.assertEqual(other["cmd_gen"], 7)
        thread_cls.return_value.start.assert_called_once()

    @mock.patch.object(coordinator, "_active_party_usernames", return_value=["running"])
    @mock.patch.object(coordinator, "_running_party_usernames", return_value=["running"])
    @mock.patch.object(coordinator, "party_accounts",
                       return_value=[("manual_route_fresh_start_test", "password", False, False)])
    @mock.patch.object(coordinator.threading, "Thread")
    def test_starting_an_extra_account_keeps_active_manual_route(
            self, thread_cls, _accounts, _running, _active):
        state = coordinator._pstate(self.pidx)
        self._seed_stale_route(state)

        self.assertTrue(coordinator.start_account(
            self.username, "password", self.pidx, False, False
        ))

        self.assertEqual(state["cmd"], ("route", 18021, 21011))
        self.assertEqual(state["cmd_gen"], 7)
        thread_cls.return_value.start.assert_called_once()

    def test_pc_and_android_use_the_same_manual_route_reset(self):
        def function_ast(path, name):
            with open(path, encoding="utf-8") as source:
                tree = ast.parse(source.read())
            node = next(
                item for item in tree.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == name
            )
            return ast.dump(node, include_attributes=False)

        android = "android/app/src/main/python/train_bot/run_party_digioi.py"
        for name in (
            "_clear_stale_manual_route",
            "_route_mismatch_timed_out",
            "start_account",
        ):
            self.assertEqual(
                function_ast("run_party_digioi.py", name),
                function_ast(android, name),
            )

    def test_route_mismatch_timer_restarts_when_leader_changes_map(self):
        timer = getattr(coordinator, "_route_mismatch_timed_out", None)
        self.assertIsNotNone(timer)
        state = {}

        self.assertFalse(timer(state, 12000, "members:12061", 100.0))
        self.assertFalse(timer(state, 11000, "members:12061", 160.0))
        self.assertFalse(timer(state, 11000, "members:12061", 174.9))
        self.assertTrue(timer(state, 11000, "members:12061", 175.0))


if __name__ == "__main__":
    unittest.main()
