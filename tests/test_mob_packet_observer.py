import json
import os
import struct
import tempfile
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

    def test_16_forwards_slot_based_monster_movement(self):
        body = b"\x02\x00" + struct.pack("<HHH", 15, 3990, 2490)
        self.client.begin_mob_observation(self.observer)

        self.client._dispatch(0x16, frame(0x16, body))

        self.assertEqual(
            self.observer.calls,
            [("move", b"\x16\x02\x0f\x00\x00\x00\x00\x00", 11013, 3990, 2490)],
        )

    def test_rich_0c_alone_does_not_mark_entity_as_player(self):
        entity = b"player00"
        prefix = b"\x00\x00" + entity + struct.pack("<HHH", 11013, 410, 1050)
        body = prefix + bytes(40 - len(prefix))
        self.client.begin_mob_observation(self.observer)

        self.client._dispatch(0x0C, frame(0x0C, body))

        self.assertEqual(self.observer.calls, [])

    def test_0f_companion_list_marks_owner_as_player(self):
        entity = b"player00"
        self.client.begin_mob_observation(self.observer)

        self.client._dispatch(0x0F, frame(0x0F, b"\x07\x00" + entity + bytes(20)))

        self.assertEqual(self.observer.calls, [("player", entity)])

    def test_27_guild_list_marks_every_entity_as_player(self):
        first = b"player00"
        second = b"player01"

        def guild_record(entity):
            name = "PhaoThu".encode("utf-16le")
            return entity + bytes(4) + bytes([len(name)]) + name

        self.client.begin_mob_observation(self.observer)
        self.client._dispatch(
            0x27,
            frame(0x27, b"\x09\x00" + guild_record(first) + guild_record(second)),
        )

        self.assertEqual(
            self.observer.calls,
            [("player", first), ("player", second)],
        )

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

    def test_raw_capture_ignores_packets_until_target_map_after_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "probe.jsonl")
            self.client.current_map = 20000
            self.client.arm_mob_packet_capture(20801, path=path)

            before = frame(0x14, b"\x01\x00")
            self.client._dispatch(0x14, before)
            self.client._capture_mob_packet(0x14, before)

            body = (b"\x00\x00" + self.client.self_entity + bytes(11)
                    + struct.pack("<HHH", 20801, 4110, 2510))
            arrival = frame(0x03, body)
            self.client._dispatch(0x03, arrival)
            self.client._capture_mob_packet(0x03, arrival)

            after = frame(0x06, b"\x01\x00" + b"monster1" + b"\x03"
                          + struct.pack("<HH", 4050, 2430))
            self.client._dispatch(0x06, after)
            self.client._capture_mob_packet(0x06, after)
            saved_path, count = self.client.finish_mob_packet_capture()

            self.assertEqual(saved_path, path)
            self.assertEqual(count, 2)
            with open(path, encoding="utf-8") as fh:
                records = [json.loads(line) for line in fh]
            self.assertEqual([record["opcode"] for record in records], [3, 6])
            self.assertTrue(all(record["map_id"] == 20801 for record in records))
            self.assertEqual(records[0]["packet"], arrival.hex())

    def test_raw_capture_stops_at_packet_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "probe.jsonl")
            self.client.current_map = 20801
            self.client.arm_mob_packet_capture(20801, path=path, max_packets=1)
            pkt = frame(0x14, b"\x01\x00")

            self.client._capture_mob_packet(0x14, pkt)
            self.client._capture_mob_packet(0x14, pkt)
            _saved_path, count = self.client.finish_mob_packet_capture()

            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
