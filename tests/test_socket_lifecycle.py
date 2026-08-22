import inspect
import unittest
from unittest import mock

from bot import client as client_module


class TestSocketLifecycle(unittest.TestCase):
    def test_socket_co_recv_timeout_de_bat_half_open(self):
        opener = getattr(client_module, "_open_game_socket", None)
        self.assertIsNotNone(opener)
        sock = mock.Mock()

        with mock.patch.object(
            client_module.socket, "create_connection", return_value=sock
        ) as create:
            result = opener("127.0.0.1", 6614)

        self.assertIs(result, sock)
        create.assert_called_once_with(("127.0.0.1", 6614), timeout=15)
        # TRUOC DAY settimeout(None) = recv block VO HAN. Do dung la cai bug: server half-open
        # (rot khong RST/FIN) -> recv treo mai mai -> acc dung hinh, supervisor khong biet de
        # relogin. Nay dat RECV_SOCK_TIMEOUT; _recv_loop bat socket.timeout roi so voi
        # RECV_DEAD_SECS de quyet dinh "coi nhu ROT".
        sock.settimeout.assert_called_once_with(client_module.RECV_SOCK_TIMEOUT)
        self.assertIsNotNone(client_module.RECV_SOCK_TIMEOUT, "quay lai block vo han")
        self.assertLess(client_module.RECV_SOCK_TIMEOUT, client_module.RECV_DEAD_SECS,
                        "recv timeout phai NGAN hon nguong coi-nhu-rot, khong thi khong bao gio "
                        "kip kiem tra")

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
