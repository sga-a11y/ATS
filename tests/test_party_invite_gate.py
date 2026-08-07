import unittest
from unittest import mock

from bot import client as client_module
from bot.client import GameClient, _register_party_entity


def _party_invite(entity):
    return b"\xc0\x91\x00\x00\x00\x00\x0d\x09\x00" + entity


def _dungeon_invite(invite_id=b"\x01\x00\x00\x00", leader=b"\x22" * 8, name=""):
    encoded = name.encode("utf-16-le")
    body = b"\x0f\x00" + invite_id + b"\x01\x00" + leader + bytes([len(encoded)]) + encoded
    return b"\xc0\x91\x00\x00\x00\x00\x2f" + body


class TestPartyInviteGate(unittest.TestCase):
    def setUp(self):
        client_module._PARTY_ENTITIES.clear()
        client_module._PARTY_JOINED.clear()

    def tearDown(self):
        client_module._PARTY_ENTITIES.clear()
        client_module._PARTY_JOINED.clear()

    def make_client(self):
        game = GameClient("user", "token")
        game.party_idx = 19
        game.self_entity = b"\x11" * 8
        game.running = True
        return game

    def test_normal_party_invite_waits_until_client_is_ready(self):
        game = self.make_client()
        leader = b"\x22" * 8
        _register_party_entity(19, leader)

        with mock.patch.object(game, "send") as send:
            game._on_party(_party_invite(leader))
            send.assert_not_called()

            setter = getattr(game, "set_party_invite_ready", lambda _ready: None)
            setter(True)

        send.assert_called_once_with(0x0D, b"\x08\x00\x01" + leader)

    def test_dungeon_invite_still_works_while_normal_party_is_not_ready(self):
        game = self.make_client()

        with (
            mock.patch.object(client_module.config, "leaders_for", return_value=[]),
            mock.patch.object(client_module.threading, "Timer"),
            mock.patch.object(game, "send") as send,
        ):
            game._on_dungeon(_dungeon_invite())

        send.assert_called_once_with(0x2F, b"\x03\x00\x01\x00\x00\x00\x00")


if __name__ == "__main__":
    unittest.main()
