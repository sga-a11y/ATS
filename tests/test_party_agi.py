import unittest
from unittest.mock import patch
import sys
import ast

_argv = sys.argv
try:
    sys.argv = [sys.argv[0]]
    import run_party_digioi as ctrl
finally:
    sys.argv = _argv


class TestPartyAgi(unittest.TestCase):
    def test_report_warns_only_when_party_spread_is_over_ten(self):
        accounts = [("a", "", True, False), ("b", "", False, False)]
        statuses = {
            "a": {"char": "A", "char_agi": 90, "pet_name": "PA", "pet_agi": 84},
            "b": {"char": "B", "char_agi": 80, "pet_name": "", "pet_agi": 1},
        }
        with patch.object(ctrl, "party_accounts", return_value=accounts), patch.object(
            ctrl, "account_status", side_effect=lambda username: statuses[username]
        ):
            report = ctrl.party_agi_report(0)
        self.assertEqual((report["min"], report["max"], report["spread"]), (80, 90, 10))
        self.assertFalse(report["warning"])
        self.assertIsNone(report["rows"][1]["pet_agi"])

        statuses["b"]["char_agi"] = 79
        with patch.object(ctrl, "party_accounts", return_value=accounts), patch.object(
            ctrl, "account_status", side_effect=lambda username: statuses[username]
        ):
            report = ctrl.party_agi_report(0)
        self.assertEqual(report["spread"], 11)
        self.assertTrue(report["warning"])

    def test_desktop_and_android_party_report_stay_in_sync(self):
        def function(path, name):
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            return ast.dump(node, include_attributes=False)

        self.assertEqual(function("run_party_digioi.py", "party_agi_report"), function(
            "android/app/src/main/python/train_bot/run_party_digioi.py", "party_agi_report"))


if __name__ == "__main__":
    unittest.main()
