import unittest
import sys

_argv = sys.argv
try:
    sys.argv = ["run_party_digioi.py"]
    from run_party_digioi import _travel_to_train_map
finally:
    sys.argv = _argv


class RecordingClient:
    def __init__(self, smart_result, legacy_result=None):
        self.smart_result = smart_result
        self.legacy_result = legacy_result
        self.calls = []
        self._label = "test"

    def follow_smart_route(self, map_id, safe, abort=None):
        self.calls.append("smart")
        return self.smart_result

    def follow_route(self, route):
        self.calls.append("legacy")
        return self.legacy_result

    def go_to_town(self, map_id, flag=0):
        self.calls.append(f"go_to_town:{map_id}")
        return True


class TestTrainRoutingPolicy(unittest.TestCase):
    def test_smart_route_runs_before_legacy_route(self):
        client = RecordingClient(smart_result=True, legacy_result=True)
        self.assertTrue(
            _travel_to_train_map(
                client, 14821, (1230, 470), {"steps": []}
            )
        )
        self.assertEqual(client.calls, ["smart"])

    def test_legacy_route_is_temporary_fallback(self):
        client = RecordingClient(smart_result=False, legacy_result=True)
        self.assertTrue(
            _travel_to_train_map(
                client, 14821, (1230, 470), {"steps": []}
            )
        )
        self.assertEqual(client.calls, ["smart", "legacy"])

    def test_missing_both_routes_stops_without_direct_teleport(self):
        client = RecordingClient(smart_result=False)
        self.assertFalse(
            _travel_to_train_map(client, 14821, (1230, 470), None)
        )
        self.assertNotIn("go_to_town:14821", client.calls)


if __name__ == "__main__":
    unittest.main()
