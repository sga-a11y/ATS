import unittest
from unittest.mock import patch

from bot.client import GameClient, execute_smart_route


HAP_COC_ROUTE = {
    "dest_map": 14821,
    "safe": [1230, 470],
    "city": 14001,
    "flag": 6,
    "legs": [
        {
            "scene": 14001,
            "target_scene": 22000,
            "gate": 1,
            "gate_center": [940, 670],
        },
        {
            "scene": 22000,
            "target_scene": 14821,
            "gate": 17,
            "gate_center": [560, 2510],
        },
    ],
}


class FakeClient:
    running = True
    current_map = 14001
    pos = (770, 610)

    def __init__(self, fail_gate=None, wrong_scene=False):
        self.calls = []
        self.fail_gate = fail_gate
        self.wrong_scene = wrong_scene
        self._label = "test"

    def navigate_to(self, x, y, **kwargs):
        self.calls.append(("navigate", x, y))
        self.pos = (x, y)

    def _enter_gate(self, x, y, gate, expected_map=None):
        self.calls.append(("gate", gate, x, y, expected_map))
        if gate == self.fail_gate:
            return False
        if self.wrong_scene and gate == 1:
            self.current_map = 99999
        else:
            self.current_map = 22000 if gate == 1 else 14821
        self.pos = (1760, 20) if gate == 1 else (3150, 230)
        return True

    def pre_route_town_hop(self):
        self.calls.append(("pre_hop",))

    def go_to_town(self, city, flag):
        self.calls.append(("town", city, flag))
        self.current_map = city
        self.pos = (770, 610)
        return True


class FakeRouter:
    def build_route(self, dest_map, safe):
        return HAP_COC_ROUTE


class TestSmartRouteExecution(unittest.TestCase):
    def test_executor_navigates_and_verifies_each_gate(self):
        client = FakeClient()
        ok = execute_smart_route(client, HAP_COC_ROUTE, abort=lambda: False)
        self.assertTrue(ok)
        self.assertEqual(
            [call[1] for call in client.calls if call[0] == "gate"],
            [1, 17],
        )
        self.assertEqual(
            [call[4] for call in client.calls if call[0] == "gate"],
            [22000, 14821],
        )
        self.assertEqual(client.current_map, 14821)
        self.assertEqual(client.calls[-1], ("navigate", 1230, 470))

    def test_abort_stops_before_next_gate(self):
        client = FakeClient()
        ok = execute_smart_route(
            client,
            HAP_COC_ROUTE,
            abort=lambda: any(call[0] == "gate" for call in client.calls),
        )
        self.assertFalse(ok)
        self.assertEqual(
            [call[1] for call in client.calls if call[0] == "gate"],
            [1],
        )

    def test_unexpected_scene_stops_without_later_gate(self):
        client = FakeClient(wrong_scene=True)
        self.assertFalse(execute_smart_route(client, HAP_COC_ROUTE))
        self.assertEqual(
            [call[1] for call in client.calls if call[0] == "gate"],
            [1],
        )
        self.assertEqual(client._smart_route_failure, "unexpected_scene")

    def test_failed_gate_sends_no_later_gate(self):
        client = FakeClient(fail_gate=1)
        self.assertFalse(execute_smart_route(client, HAP_COC_ROUTE))
        self.assertEqual(
            [call[1] for call in client.calls if call[0] == "gate"],
            [1],
        )

    def test_client_wrapper_uses_route_city_and_flag(self):
        client = FakeClient()
        client.current_map = 12001
        with patch("bot.client._smart_world_router", return_value=FakeRouter()):
            ok = GameClient.follow_smart_route(client, 14821, (1230, 470))
        self.assertTrue(ok)
        self.assertIn(("town", 14001, 6), client.calls)
        self.assertNotIn(("town", 14821, 0), client.calls)


if __name__ == "__main__":
    unittest.main()
