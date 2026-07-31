import sys
import unittest
from unittest import mock


with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as coordinator


class TestPartyRestart(unittest.TestCase):
    def setUp(self):
        self.pidx = 9201
        self.username = "restart_old_map_test"
        coordinator._party_state.pop(self.pidx, None)
        coordinator.account_threads.pop(self.username, None)
        coordinator.account_clients.pop(self.username, None)
        coordinator.account_stops.pop(self.username, None)

    def tearDown(self):
        coordinator._party_state.pop(self.pidx, None)
        coordinator.account_threads.pop(self.username, None)
        coordinator.account_clients.pop(self.username, None)
        coordinator.account_stops.pop(self.username, None)

    @mock.patch.object(coordinator, "start_account", return_value=True)
    @mock.patch.object(coordinator, "party_accounts")
    def test_start_party_replaces_all_route_state_after_old_threads_stop(
            self, party_accounts, start_account):
        accounts = [(self.username, "pw", True, True)]
        party_accounts.return_value = accounts
        old = coordinator._pstate(self.pidx)
        old["route_plan"] = {"city": 12001, "gen": 7}
        old["route_plan_ready"].set()
        old["rally_point"] = (100, 200)
        old["reform_gen"] = 7

        self.assertEqual(coordinator.start_party(self.pidx, stagger=0), 1)

        fresh = coordinator._pstate(self.pidx)
        self.assertIsNot(fresh, old)
        self.assertIsNone(fresh["route_plan"])
        self.assertFalse(fresh["route_plan_ready"].is_set())
        self.assertIsNone(fresh["rally_point"])
        self.assertEqual(fresh["reform_gen"], 0)
        start_account.assert_called_once()

    def test_pc_and_android_restart_functions_match(self):
        import ast

        def function_ast(path, name):
            with open(path, encoding="utf-8") as source:
                tree = ast.parse(source.read())
            node = next(item for item in tree.body
                        if isinstance(item, ast.FunctionDef) and item.name == name)
            return ast.dump(node, include_attributes=False)

        self.assertEqual(
            function_ast("run_party_digioi.py", "start_party"),
            function_ast(
                "android/app/src/main/python/train_bot/run_party_digioi.py",
                "start_party",
            ),
        )


if __name__ == "__main__":
    unittest.main()
