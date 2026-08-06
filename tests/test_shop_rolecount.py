import unittest
from unittest import mock

from bot.client import GameClient


class TestShopRoleCount(unittest.TestCase):
    def make_client(self):
        game = GameClient("user", "token")
        game._label = "hero"
        return game

    def test_role_count_updates_shop_counters(self):
        game = self.make_client()

        game._apply_role_counts(bytes.fromhex(
            "010003000000"
            "56040300000003000000"
            "16000100000001000000"
            "2b000100000001000000"
        ))

        self.assertEqual(game.role_counts[0x0456], (3, 3))
        self.assertEqual(game.shop_ho_phu_count, 3)
        self.assertEqual(game.shop_ho_phu_max, 3)
        self.assertEqual(game.role_counts[0x0016], (1, 1))
        self.assertEqual(game.shop_bao_hop_count, 1)
        self.assertEqual(game.shop_bao_hop_max, 1)
        self.assertEqual(game.role_counts[0x002b], (1, 1))
        self.assertEqual(game.shop_thien_chau_count, 1)
        self.assertEqual(game.shop_thien_chau_max, 1)

    def test_buy_ho_phu_uses_remaining_server_count(self):
        game = self.make_client()
        game.shop_ho_phu_count = 1
        game.shop_ho_phu_max = 3

        with mock.patch.object(game, "send") as send:
            game.buy_di_gioi_ho_phu()

        send.assert_called_once_with(0x42, bytes.fromhex("0100010103018cff2400020000"))
        self.assertEqual(game.shop_ho_phu_count, 3)

    def test_buy_ho_phu_skips_when_server_count_is_full(self):
        game = self.make_client()
        game.shop_ho_phu_count = 3
        game.shop_ho_phu_max = 3

        with mock.patch.object(game, "send") as send:
            game.buy_di_gioi_ho_phu()

        send.assert_not_called()

    def test_buy_bao_hop_skips_when_server_count_is_full(self):
        game = self.make_client()
        game.shop_bao_hop_count = 1
        game.shop_bao_hop_max = 1
        game.xu = 2_000_000

        with mock.patch.object(game, "send") as send:
            game.buy_trieu_goi_bao_hop(1_000_000)

        send.assert_not_called()

    def test_buy_bao_hop_uses_server_count(self):
        game = self.make_client()
        game.shop_bao_hop_count = 0
        game.shop_bao_hop_max = 1
        game.xu = 2_000_000

        with mock.patch.object(game, "send") as send:
            game.buy_trieu_goi_bao_hop(1_000_000)

        send.assert_called_once_with(0x42, bytes.fromhex("01000101030754b560ea010000"))
        self.assertEqual(game.shop_bao_hop_count, 1)
        self.assertEqual(game.xu, 1_940_000)

    def test_buy_hop_thien_chau_sends_shop_slot(self):
        game = self.make_client()

        with mock.patch.object(game, "send") as send:
            game.buy_hop_thien_chau()

        send.assert_called_once_with(0x42, bytes.fromhex("0100010103068ab62700010000"))

    def test_buy_hop_thien_chau_skips_when_server_count_is_full(self):
        game = self.make_client()
        game.shop_thien_chau_count = 1
        game.shop_thien_chau_max = 1

        with mock.patch.object(game, "send") as send:
            game.buy_hop_thien_chau()

        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
