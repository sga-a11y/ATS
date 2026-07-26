import inspect
import unittest
from unittest import mock

from bot import client as client_module


class TestSocketLifecycle(unittest.TestCase):
    def test_connected_socket_uses_timeout_only_for_connect(self):
        opener = getattr(client_module, "_open_game_socket", None)
        self.assertIsNotNone(opener)
        sock = mock.Mock()

        with mock.patch.object(
            client_module.socket, "create_connection", return_value=sock
        ) as create:
            result = opener("127.0.0.1", 6614)

        self.assertIs(result, sock)
        create.assert_called_once_with(("127.0.0.1", 6614), timeout=15)
        sock.settimeout.assert_called_once_with(None)

    def test_stale_recv_thread_cannot_close_new_session(self):
        parameters = list(
            inspect.signature(client_module.GameClient._recv_loop).parameters
        )
        self.assertEqual(parameters, ["self", "sock"])

        game = client_module.GameClient("user", "token")
        old_sock = mock.Mock()
        old_sock.recv.return_value = b""
        game.sock = mock.Mock()
        game.running = True
        game.server_closed = False

        game._recv_loop(old_sock)

        self.assertTrue(game.running)
        self.assertFalse(game.server_closed)
        old_sock.recv.assert_not_called()


if __name__ == "__main__":
    unittest.main()
