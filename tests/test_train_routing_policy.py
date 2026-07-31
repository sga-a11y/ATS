import unittest
import sys

_argv = sys.argv
try:
    sys.argv = ["run_party_digioi.py"]
    import run_party_digioi as coordinator
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
    def test_train_disconnect_regroups_after_fast_reconnect(self):
        self.assertTrue(
            coordinator._should_restart_mode_after_disconnect(
                train_on_map=True, reconnecting=set()
            )
        )

    def test_non_train_mode_without_pending_reconnect_does_not_restart(self):
        self.assertFalse(
            coordinator._should_restart_mode_after_disconnect(
                train_on_map=False, reconnecting=set()
            )
        )

    def test_disconnect_marks_normal_train_for_coordinated_reform(self):
        self.assertTrue(
            coordinator._party_is_in_train_phase(
                {"mode": "train", "start_city_id": 20801}, {"dt_phase": "digioi"}
            )
        )

    def test_disconnect_marks_digioi_train_only_in_train_phase(self):
        pcfg = {"mode": "digioi_train", "start_city_id": 20801}
        self.assertFalse(coordinator._party_is_in_train_phase(pcfg, {"dt_phase": "digioi"}))
        self.assertTrue(coordinator._party_is_in_train_phase(pcfg, {"dt_phase": "train"}))

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

    def test_missing_safe_still_attempts_smart_route(self):
        client = RecordingClient(smart_result=True)

        self.assertTrue(_travel_to_train_map(client, 20801, None, None))
        self.assertEqual(client.calls, ["smart"])

    def test_member_waits_for_leader_route_when_safe_is_unknown(self):
        self.assertTrue(
            coordinator._train_route_available(
                smart_route=None, legacy_route=None, has_leader=True
            )
        )


if __name__ == "__main__":
    unittest.main()
