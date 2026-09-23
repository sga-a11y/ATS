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

    def tearDown(self):
        client_module._PARTY_ENTITIES.clear()

    def make_client(self):
        game = GameClient("user", "token")
        game.party_idx = 19
        game.self_entity = b"\x11" * 8
        game.running = True
        return game

    def test_loi_moi_NGUOI_LA_thi_van_hoan_toi_khi_san_sang(self):
        """Nguoi ngoai party moi -> hoan lai nhu cu (khong bo dang lam de vao doi nguoi la)."""
        game = self.make_client()
        nguoi_la = b"\x33" * 8                 # KHONG dang ky vao party 19

        with mock.patch.object(game, "send") as send:
            game._on_party(_party_invite(nguoi_la))
            send.assert_not_called()

            setter = getattr(game, "set_party_invite_ready", lambda _ready: None)
            setter(True)

        send.assert_called_once_with(0x0D, b"\x08\x00\x01" + nguoi_la)

    def test_dang_lam_VIEC_VAT_thi_GIU_loi_moi(self):
        """User 14/09: "dang lam may cai viec vat do ko vao pt la dung, dang lam do ma vao pt roi
        bi keo di luon thi no hong viec vat"."""
        game = self.make_client()
        leader = b"\x22" * 8
        _register_party_entity(19, leader)
        with mock.patch.object(game, "dang_lam_viec_vat", return_value=True),              mock.patch.object(game, "send") as send:
            game._on_party(_party_invite(leader))
            send.assert_not_called()
        self.assertIn(bytes(leader), game._pending_party_invites)

    def test_RANH_ma_co_ket_False_thi_van_nhan(self):
        """Ca that 08/09 party 17: hai acc lap "GIU loi moi ... se accept sau viec vat" moi 6 giay
        suot 40 phut trong khi KHONG he lam viec vat nao - co `party_invite_ready` ket False vinh
        vien vi acc bi ABORT truoc khi toi dong gan co.

        Cho go: vong keepalive bat co khi acc DANG RANH (xem run_party_digioi, nhanh L0).
        """
        game = self.make_client()
        leader = b"\x22" * 8
        _register_party_entity(19, leader)
        with mock.patch.object(game, "dang_lam_viec_vat", return_value=False),              mock.patch.object(game, "send") as send:
            game._on_party(_party_invite(leader))      # co van False -> GIU
            self.assertIn(bytes(leader), game._pending_party_invites)
            game.set_party_invite_ready(True)          # keepalive thay acc ranh -> mo cong
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
