import struct
import unittest
from unittest import mock

from bot import protocol
from bot.client import GameClient
from bot.mob_scanner import MobScanSession


class RecordingObserver:
    def __init__(self):
        self.calls = []

    def observe_spawn(self, entity, map_id, x, y, now):
        self.calls.append(("spawn", entity, map_id, x, y))

    def observe_move(self, entity, map_id, x, y, now):
        self.calls.append(("move", entity, map_id, x, y))

    def mark_player(self, entity):
        self.calls.append(("player", entity))


def frame(opcode, body):
    return protocol.build_packet(opcode, body)


class TestMobPacketObserver(unittest.TestCase):
    def setUp(self):
        self.client = GameClient("user", "token")
        self.client.current_map = 11013
        self.client.self_entity = b"self0000"
        self.observer = RecordingObserver()

    def test_07_forwards_initial_entity_position(self):
        entity = b"monster1"
        body = b"\x00\x00" + entity + struct.pack("<HHH", 11013, 430, 930)
        self.client.begin_mob_observation(self.observer)

        self.client._dispatch(0x07, frame(0x07, body))

        self.assertEqual(
            self.observer.calls,
            [("spawn", entity, 11013, 430, 930)],
        )

    def test_06_forwards_entity_movement_on_current_map(self):
        entity = b"monster1"
        body = b"\x01\x00" + entity + b"\x03" + struct.pack("<HH", 530, 830)
        self.client.begin_mob_observation(self.observer)

        self.client._dispatch(0x06, frame(0x06, body))

        self.assertEqual(
            self.observer.calls,
            [("move", entity, 11013, 530, 830)],
        )

    def test_rich_0c_marks_player_entity(self):
        entity = b"player00"
        prefix = b"\x00\x00" + entity + struct.pack("<HHH", 11013, 410, 1050)
        body = prefix + bytes(40 - len(prefix))
        self.client.begin_mob_observation(self.observer)

        self.client._dispatch(0x0C, frame(0x0C, body))

        self.assertEqual(self.observer.calls, [("player", entity)])

    def test_real_session_excludes_self_and_party_entities(self):
        party = b"party000"
        session = MobScanSession(11013, self.client.self_entity, {party})
        session.begin_station(0.0)
        self.client.begin_mob_observation(session)
        for entity in (self.client.self_entity, party):
            body = b"\x01\x00" + entity + b"\x03" + struct.pack("<HH", 530, 830)
            self.client._dispatch(0x06, frame(0x06, body))

        self.assertEqual(session.candidate_count(), 0)

    def test_short_packets_do_not_call_observer(self):
        self.client.begin_mob_observation(self.observer)
        for opcode in (0x06, 0x07, 0x0C):
            self.client._dispatch(opcode, frame(opcode, b"\x00"))

        self.assertEqual(self.observer.calls, [])

    def test_end_only_clears_matching_observer(self):
        other = RecordingObserver()
        self.client.begin_mob_observation(self.observer)
        self.client.end_mob_observation(other)
        body = b"\x01\x00" + b"monster1" + b"\x03" + struct.pack("<HH", 530, 830)

        self.client._dispatch(0x06, frame(0x06, body))

        self.assertEqual(len(self.observer.calls), 1)
        self.client.end_mob_observation(self.observer)
        self.client._dispatch(0x06, frame(0x06, body))
        self.assertEqual(len(self.observer.calls), 1)

    def test_get_ground_store_uses_shared_client_singleton(self):
        sentinel = object()
        with mock.patch("bot.client._ground_store", return_value=sentinel):
            self.assertIs(self.client.get_ground_store(), sentinel)


if __name__ == "__main__":
    unittest.main()
