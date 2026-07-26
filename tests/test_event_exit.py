import struct
import unittest
from unittest import mock

from bot import protocol
from bot.client import GameClient


def self_spawn(entity, map_id, x, y):
    body = b"\x00\x00" + entity + bytes(11) + struct.pack("<HHH", map_id, x, y)
    return protocol.build_packet(0x03, body)


class TestServerPositionRefresh(unittest.TestCase):
    def setUp(self):
        self.client = GameClient("user", "token")
        self.client.self_entity = b"self0000"
        self.client.current_map = 10991
        self.client.pos = (910, 290)
        self.client.running = True

    def test_self_spawn_updates_position_and_generation(self):
        before = self.client._position_generation
        self.client._dispatch(
            0x03,
            self_spawn(self.client.self_entity, 10991, 900, 300),
        )
        self.assertEqual(self.client.pos, (900, 300))
        self.assertEqual(self.client._position_generation, before + 1)

    def test_other_entity_does_not_update_position_generation(self):
        before = self.client._position_generation
        self.client._dispatch(0x03, self_spawn(b"other000", 10991, 100, 100))
        self.assertEqual(self.client.pos, (910, 290))
        self.assertEqual(self.client._position_generation, before)

    def test_scene_request_fresh_spawn_avoids_relogin(self):
        def answer_scene(opcode, payload):
            self.assertEqual((opcode, payload), (0x0C, b"\x01\x00"))
            self.client._dispatch(
                0x03,
                self_spawn(self.client.self_entity, 10991, 880, 320),
            )

        with mock.patch.object(self.client, "send", side_effect=answer_scene), \
             mock.patch.object(self.client, "relogin") as relogin:
            self.assertTrue(
                self.client.refresh_server_position(10991, request_timeout=0.1)
            )
        relogin.assert_not_called()
        self.assertEqual(self.client.pos, (880, 320))

    def test_scene_timeout_keeps_known_position_without_relogin(self):
        with mock.patch.object(self.client, "send"), \
             mock.patch.object(self.client, "relogin") as relogin_mock:
            self.assertTrue(
                self.client.refresh_server_position(10991, request_timeout=0.0)
            )
        relogin_mock.assert_not_called()
        self.assertEqual(self.client.pos, (910, 290))

    def test_scene_timeout_without_known_position_fails_without_relogin(self):
        self.client.pos = None
        with mock.patch.object(self.client, "send"), \
             mock.patch.object(self.client, "relogin") as relogin_mock:
            self.assertFalse(
                self.client.refresh_server_position(10991, request_timeout=0.0)
            )
        relogin_mock.assert_not_called()

    def test_fresh_spawn_on_different_map_fails(self):
        def answer_scene(_opcode, _payload):
            self.client._dispatch(
                0x03,
                self_spawn(self.client.self_entity, 12003, 170, 780),
            )

        with mock.patch.object(self.client, "send", side_effect=answer_scene), \
             mock.patch.object(self.client, "relogin") as relogin:
            self.assertFalse(
                self.client.refresh_server_position(10991, request_timeout=0.1)
            )
        relogin.assert_not_called()


class TestSmartEventExit(unittest.TestCase):
    def setUp(self):
        self.client = GameClient("user", "token")
        self.client.running = True
        self.client.current_map = 10991
        self.client.pos = (910, 290)
        self.event = {
            "exit": {
                "out_map": 12003,
                "steps": [
                    {"move": [1, 2], "flag": 5},
                    {"gate": 99, "x": 3, "y": 4},
                ],
            }
        }

    def test_exit_resyncs_then_uses_smart_scene_route_and_ignores_steps(self):
        def finish_route(
            source_map,
            dest_map,
            safe=None,
            abort=None,
            flee=True,
            refresh_position=True,
        ):
            self.assertEqual(
                (source_map, dest_map, safe, flee, refresh_position),
                (10991, 12003, None, True, False),
            )
            self.client.current_map = 12003
            return True

        with mock.patch.object(
            self.client,
            "refresh_server_position",
            return_value=True,
        ) as refresh, mock.patch.object(
            self.client,
            "follow_smart_scene_route",
            side_effect=finish_route,
        ) as route, mock.patch.object(
            self.client,
            "_exit_event_gate",
        ) as captured_gate, mock.patch.object(
            self.client,
            "_route_move",
        ) as captured_move, mock.patch.object(
            self.client,
            "_wait_combat_clear",
            return_value=True,
        ), mock.patch(
            "bot.client.time.sleep",
        ):
            self.assertTrue(self.client.exit_event(self.event))
        refresh.assert_called_once_with(10991)
        route.assert_called_once()
        captured_gate.assert_not_called()
        captured_move.assert_not_called()

    def test_exit_stops_when_position_refresh_fails(self):
        self.event["exit"]["steps"] = []
        with mock.patch.object(
            self.client,
            "refresh_server_position",
            return_value=False,
        ) as refresh, mock.patch.object(
            self.client,
            "follow_smart_scene_route",
        ) as route:
            self.assertFalse(self.client.exit_event(self.event))
        refresh.assert_called_once_with(10991)
        route.assert_not_called()

    def test_exit_requires_router_to_reach_exact_out_map(self):
        self.event["exit"]["steps"] = []
        with mock.patch.object(
            self.client,
            "refresh_server_position",
            return_value=True,
        ), mock.patch.object(
            self.client,
            "follow_smart_scene_route",
            return_value=False,
        ) as route:
            self.assertFalse(self.client.exit_event(self.event))
        route.assert_called_once_with(
            10991, 12003, safe=None, flee=True, refresh_position=False
        )
        self.assertEqual(self.client.current_map, 10991)


class TestSmartSceneRoute(unittest.TestCase):
    def setUp(self):
        self.client = GameClient("user", "token")
        self.client.running = True
        self.client.current_map = 18021
        self.client.pos = (2730, 1030)

    def test_refreshes_server_position_before_building_route(self):
        route = {
            "dest_map": 21011,
            "safe": None,
            "legs": [],
        }

        def refresh(_source_map):
            self.client.pos = (270, 590)
            return True

        with mock.patch.object(
            self.client,
            "refresh_server_position",
            side_effect=refresh,
        ) as refresh_mock, mock.patch.object(
            self.client,
            "build_smart_scene_route",
            return_value=route,
        ) as build, mock.patch(
            "bot.client.execute_smart_route",
            return_value=True,
        ):
            self.assertTrue(
                self.client.follow_smart_scene_route(18021, 21011)
            )

        refresh_mock.assert_called_once_with(18021)
        build.assert_called_once_with(18021, 21011, None)
        self.assertEqual(self.client.pos, (270, 590))


if __name__ == "__main__":
    unittest.main()
