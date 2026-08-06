import struct
import unittest
from unittest import mock

from bot import client as client_module
from bot.client import GameClient


class TestVantieuDispatchDecode(unittest.TestCase):
    def make_client(self):
        game = GameClient("user", "token")
        game._label = "hero"
        return game

    def test_0400_decodes_dispatch_effects(self):
        game = self.make_client()
        with mock.patch.object(client_module.config, "VANTIEU_DISPATCH_EFFECTS", {
            "1": {"doanh": "Huynh"},
            "6": {"he": "Dia"},
        }):
            game._on_vantieu(b"\x00" * 7 + bytes.fromhex("0400020106"))

        self.assertEqual(game.vantieu_req_code, "020106")
        self.assertEqual(game.vantieu_req, {"doanh": "Huynh", "he": "Dia"})

    def test_0300_keeps_slot_index_and_effects(self):
        game = self.make_client()
        start_ole = 50000.0
        end_ole = 50000.5
        body = (
            b"\x03\x00\x01"
            + bytes([2])
            + struct.pack("<d", start_ole)
            + struct.pack("<d", end_ole)
            + bytes([2, 7, 1, 6])
        )
        with mock.patch.object(client_module.config, "VANTIEU_DISPATCH_EFFECTS", {
            "1": {"doanh": "Huynh"},
            "6": {"he": "Dia"},
        }):
            game._on_vantieu(b"\x00" * 7 + body)

        self.assertEqual(game.vantieu_slots[2]["pet"], 7)
        self.assertEqual(game.vantieu_slots[2]["kind"], 2)
        self.assertEqual(game.vantieu_slots[2]["effect1"], 1)
        self.assertEqual(game.vantieu_slots[2]["effect2"], 6)
        self.assertEqual(game.vantieu_slots[2]["req"], {"doanh": "Huynh", "he": "Dia"})


class TestVantieuSlot2Flow(unittest.TestCase):
    def test_rolecount_dispatch_id_8_updates_server_counter(self):
        game = GameClient("user", "token")
        body = (
            b"\x01\x00"
            + struct.pack("<I", 1)
            + struct.pack("<Hii", 8, 2, 3)
        )

        game._apply_role_counts(body)

        self.assertEqual(game.vantieu_started, 2)
        self.assertEqual(game.vantieu_max, 3)

    def test_server_count_controls_dispatch(self):
        game = GameClient("user", "token")
        game._label = "hero"
        game.vantieu_started = 1
        game.vantieu_max = 3
        game.vantieu_roster = {3: "PetA"}
        sent_pets = []
        panel_calls = 0
        future_ole = 50000.0

        def fake_send(op, body):
            nonlocal panel_calls
            if op != 0x56:
                return
            if body == b"\x01\x00":
                panel_calls += 1
                game.vantieu_unlocked = 1
                if panel_calls == 1:
                    game.vantieu_slots = {}
                    game.vantieu_req_code = "020106"
                    game.vantieu_req = {"doanh": "Huynh", "he": "Dia"}
                else:
                    game.vantieu_slots = {1: {"end": future_ole, "pet": 3}}
                    game.vantieu_req_code = None
                    game.vantieu_req = None
            elif body.startswith(b"\x02\x00"):
                sent_pets.append(body[2])

        with mock.patch.object(game, "send", side_effect=fake_send), \
             mock.patch.object(client_module.time, "sleep"), \
             mock.patch.object(client_module.config, "VANTIEU_ENABLE", True), \
             mock.patch.object(client_module.config, "VANTIEU_PETS", []), \
             mock.patch.object(client_module.config, "VANTIEU_DISPATCH_EFFECTS", {"1": {}, "6": {}}), \
             mock.patch.object(client_module.config, "PET_HEDOANH", {
                 "PetA": {"doanh": "Huynh", "he": "Dia"},
             }):
            game.do_van_tieu()

        self.assertEqual(sent_pets, [3])
        self.assertEqual(game.vantieu_started, 2)

    def test_missing_server_count_does_not_start_new_dispatch(self):
        game = GameClient("user", "token")
        game._label = "hero"
        game.vantieu_started = None
        game.vantieu_roster = {3: "PetA"}
        sent_pets = []

        def fake_send(op, body):
            if op != 0x56:
                return
            if body == b"\x01\x00":
                game.vantieu_unlocked = 1
                game.vantieu_slots = {}
                game.vantieu_req = {"doanh": "Huynh", "he": "Dia"}
            elif body.startswith(b"\x02\x00"):
                sent_pets.append(body[2])

        with mock.patch.object(game, "send", side_effect=fake_send), \
             mock.patch.object(client_module.time, "sleep"), \
             mock.patch.object(client_module.config, "VANTIEU_ENABLE", True), \
             mock.patch.object(client_module.config, "VANTIEU_PETS", []), \
             mock.patch.object(client_module.config, "VANTIEU_DISPATCH_EFFECTS", {"1": {}, "6": {}}), \
             mock.patch.object(client_module.config, "PET_HEDOANH", {
                 "PetA": {"doanh": "Huynh", "he": "Dia"},
             }):
            game.do_van_tieu()

        self.assertEqual(sent_pets, [])

    def test_slot2_is_sent_when_slot1_is_running(self):
        game = GameClient("user", "token")
        game._label = "hero"
        game.vantieu_started = 0
        game.vantieu_max = 3
        game.vantieu_roster = {3: "PetA", 4: "PetB"}
        sent_pets = []
        panel_calls = 0
        future_ole = 50000.0

        def fake_send(op, body):
            nonlocal panel_calls
            if op != 0x56:
                return
            if body == b"\x01\x00":
                panel_calls += 1
                game.vantieu_unlocked = 2
                if panel_calls == 1:
                    game.vantieu_slots = {1: {"end": future_ole, "pet": 9}}
                    game.vantieu_req_code = "020106"
                    game.vantieu_req = {"doanh": "Huynh", "he": "Dia"}
                else:
                    game.vantieu_slots = {
                        1: {"end": future_ole, "pet": 9},
                        2: {"end": future_ole, "pet": 3},
                    }
                    game.vantieu_req_code = None
                    game.vantieu_req = None
            elif body.startswith(b"\x02\x00"):
                sent_pets.append(body[2])

        with mock.patch.object(game, "send", side_effect=fake_send), \
             mock.patch.object(client_module.time, "sleep"), \
             mock.patch.object(client_module.config, "VANTIEU_ENABLE", True), \
             mock.patch.object(client_module.config, "VANTIEU_PETS", []), \
             mock.patch.object(client_module.config, "VANTIEU_DISPATCH_EFFECTS", {"1": {}, "6": {}}), \
             mock.patch.object(client_module.config, "PET_HEDOANH", {
                 "PetA": {"doanh": "Huynh", "he": "Dia"},
                 "PetB": {"doanh": "Nguy", "he": "Thuy"},
             }):
            game.do_van_tieu()

        self.assertEqual(sent_pets, [3])
        self.assertGreaterEqual(panel_calls, 2)


if __name__ == "__main__":
    unittest.main()
