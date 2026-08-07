import unittest
from unittest import mock

from bot.client import GameClient


def _switch_result(result):
    return b"\xc0\x91\x0a\x00\x00\x00\x07\x02\x00" + bytes([result])


class TestChannelSwitch(unittest.TestCase):
    def make_client(self):
        game = GameClient("user", "token")
        game._label = "hero"
        game.running = True
        return game

    def test_switch_channel_waits_for_success_ack(self):
        game = self.make_client()

        with mock.patch.object(game, "send") as send:
            send.side_effect = lambda _op, _payload: game._on_channel_switch_result(_switch_result(0))
            self.assertTrue(game.switch_channel(50, wait=1.0, retries=1))

        send.assert_called_once_with(0x07, b"\x02\x00\x32\x00")
        self.assertEqual(game.current_channel, 50)

    def test_switch_channel_does_not_set_channel_on_failure(self):
        game = self.make_client()
        game.current_channel = 12

        with mock.patch.object(game, "send") as send:
            send.side_effect = lambda _op, _payload: game._on_channel_switch_result(_switch_result(4))
            self.assertFalse(game.switch_channel(50, wait=1.0, retries=1))

        self.assertEqual(game.current_channel, 12)

    def test_switch_channel_same_channel_ack_is_success(self):
        game = self.make_client()

        with mock.patch.object(game, "send") as send:
            send.side_effect = lambda _op, _payload: game._on_channel_switch_result(_switch_result(1))
            self.assertTrue(game.switch_channel(50, wait=1.0, retries=1))

        self.assertEqual(game.current_channel, 50)

    def test_switch_channel_timeout_keeps_old_channel(self):
        game = self.make_client()
        game.current_channel = 12

        with mock.patch.object(game, "send"):
            self.assertFalse(game.switch_channel(50, wait=0.01, retries=1))

        self.assertEqual(game.current_channel, 12)

    def test_parse_channel_from_player_appear_uses_variable_name_length(self):
        game = self.make_client()
        game.self_entity = bytes.fromhex("0102030405060708")
        name = "hero".encode("utf-16-le")
        body = bytearray(64)
        body[0:2] = b"\x00\x00"
        body[2:10] = game.self_entity
        body[21:23] = (12831).to_bytes(2, "little")
        body[23:25] = (470).to_bytes(2, "little")
        body[25:27] = (1210).to_bytes(2, "little")
        body[46] = len(name)
        body[47:47 + len(name)] = name
        body[47 + len(name):49 + len(name)] = (50).to_bytes(2, "little")
        pkt = b"\xc0\x91\x00\x00\x00\x00\x03" + bytes(body)

        self.assertEqual(game._parse_channel_from_03(pkt), 50)


if __name__ == "__main__":
    unittest.main()
