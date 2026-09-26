import time
import threading
import unittest
from unittest import mock

import bot.client as client_module
from bot.client import (
    GameClient,
    _PARTY_ENTITIES,
    _register_party_client,
)


def _switch_result(result):
    return b"\xc0\x91\x0a\x00\x00\x00\x07\x02\x00" + bytes([result])


class TestChannelSwitch(unittest.TestCase):
    def tearDown(self):
        if hasattr(client_module, "_PARTY_CLIENTS"):
            client_module._PARTY_CLIENTS.clear()
        _PARTY_ENTITIES.clear()

    def make_client(self):
        game = GameClient("user", "token")
        game._label = "hero"
        game.running = True
        return game

    def test_switch_channel_waits_for_ack_and_scene(self):
        game = self.make_client()
        # Kenh hien tai da TUOI -> `kenh_that()` khong phai hoi lai server (khong sinh goi 0x0c),
        # de assert duoi day van do dung MOT goi 0x07 nhu truoc.
        game.current_channel = 1
        game.current_channel_at = time.time()

        with mock.patch.object(game, "send") as send:
            def receive(_op, _payload):
                game._on_channel_switch_result(_switch_result(0))
                game._note_current_channel(50, "0x0c")
            send.side_effect = receive
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
        game._note_current_channel(50, "0x0c")

        with mock.patch.object(game, "send") as send:
            send.side_effect = lambda _op, _payload: game._on_channel_switch_result(_switch_result(1))
            self.assertTrue(game.switch_channel(50, wait=1.0, retries=1))

        self.assertEqual(game.current_channel, 50)

    def test_ack_alone_does_not_invent_current_channel(self):
        game = self.make_client()
        game._note_current_channel(12, "0x0c")
        with mock.patch.object(game, "send", side_effect=lambda *_:
                               game._on_channel_switch_result(_switch_result(0))):
            self.assertFalse(game.switch_channel(50, wait=0.01, retries=1))
        self.assertEqual(game.current_channel, 12)
        self.assertFalse(game.kenh_dang_chac())

    def test_scene_before_ack_is_not_overwritten_by_requested_target(self):
        game = self.make_client()
        def receive(*_):
            game._note_current_channel(19, "0x0c")
            game._on_channel_switch_result(_switch_result(0))
        with mock.patch.object(game, "send", side_effect=receive):
            self.assertFalse(game.switch_channel(50, wait=0.01, retries=1))
        self.assertEqual(game.current_channel, 19)
        self.assertTrue(game.kenh_dang_chac())

    def test_matching_scene_before_ack_succeeds(self):
        game = self.make_client()
        def receive(*_):
            game._note_current_channel(50, "0x0c")
            game._on_channel_switch_result(_switch_result(0))
        with mock.patch.object(game, "send", side_effect=receive):
            self.assertTrue(game.switch_channel(50, wait=0.01, retries=1))

    def test_same_channel_result_cannot_replace_different_scene_channel(self):
        game = self.make_client()
        game._note_current_channel(12, "0x0c")
        with mock.patch.object(game, "send", side_effect=lambda *_:
                               game._on_channel_switch_result(_switch_result(1))):
            self.assertFalse(game.switch_channel(50, wait=0.01, retries=1))
        self.assertEqual(game.current_channel, 12)

    def test_timeout_is_not_success_even_when_cached_channel_matches(self):
        game = self.make_client()
        game._note_current_channel(50, "0x0c")
        with mock.patch.object(game, "send"):
            self.assertFalse(game.switch_channel(50, wait=0.01, retries=1))
        self.assertFalse(game.kenh_dang_chac())

    def test_rejection_keeps_confirmed_scene_channel_certain(self):
        game = self.make_client()
        game._note_current_channel(12, "0x0c")
        with mock.patch.object(game, "send", side_effect=lambda *_:
                               game._on_channel_switch_result(_switch_result(4))):
            self.assertFalse(game.switch_channel(50, wait=0.01, retries=1))
        self.assertTrue(game.kenh_dang_chac())

    def test_late_ack_does_not_change_scene_channel_or_generation(self):
        game = self.make_client()
        game._chan_switch_target = 50
        game._note_current_channel(19, "0x0c")
        generation = game._channel_scene_generation
        game._on_channel_switch_result(_switch_result(0))
        self.assertEqual(game.current_channel, 19)
        self.assertEqual(game._channel_scene_generation, generation)

    def test_waits_for_scene_arriving_after_ack(self):
        game = self.make_client()
        game._note_current_channel(12, "0x0c")
        scene = threading.Timer(0.03, game._note_current_channel, args=(50, "0x0c"))
        def receive(*_):
            game._on_channel_switch_result(_switch_result(0))
            self.assertEqual(game.current_channel, 12)
            self.assertFalse(game.kenh_dang_chac())
            scene.start()
        try:
            with mock.patch.object(game, "send", side_effect=receive):
                self.assertTrue(game.switch_channel(50, wait=0.5, retries=1))
        finally:
            scene.cancel()
            if scene.ident is not None:
                scene.join()

    def test_matching_channel_in_different_map_does_not_complete_request(self):
        game = self.make_client()
        game.current_map = 49942
        def receive(*_):
            game.current_map = 12001
            game._note_current_channel(50, "0x0c")
            game._on_channel_switch_result(_switch_result(0))
        with mock.patch.object(game, "send", side_effect=receive):
            self.assertFalse(game.switch_channel(50, wait=0.01, retries=1))
        self.assertEqual(game.current_channel, 50)
        self.assertTrue(game.kenh_dang_chac())

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

    def test_zero_channel_from_scene_does_not_replace_known_channel(self):
        game = self.make_client()
        game.current_channel = 1

        game._note_current_channel(0, "0x0c")

        self.assertEqual(game.current_channel, 1)

    def test_refresh_current_channel_requests_scene_and_waits_for_positive_channel(self):
        game = self.make_client()

        with mock.patch.object(game, "send") as send:
            send.side_effect = lambda _op, _payload: game._note_current_channel(1, "0x0c")
            self.assertEqual(game.refresh_current_channel(wait=0.1), 1)

        send.assert_called_once_with(0x0c, b"\x01\x00")

    def test_invite_uses_live_bot_scene_when_leader_nearby_cache_is_stale(self):
        leader = self.make_client()
        leader.party_idx = 19
        leader.self_entity = bytes.fromhex("1111111111111111")
        leader.current_map = 12001
        leader.current_channel = 12
        leader.current_channel_at = time.time()

        member = self.make_client()
        member.party_idx = 19
        member.self_entity = bytes.fromhex("2222222222222222")
        member.current_map = 12001
        member.current_channel = 12
        member.current_channel_at = time.time()

        _register_party_client(19, leader.self_entity, leader)
        _register_party_client(19, member.self_entity, member)
        _PARTY_ENTITIES[19] = {leader.self_entity, member.self_entity}
        leader.entity_meta[member.self_entity] = {
            "nearby": True,
            "seen": 1.0,
            "scene_id": 12001,
            "instance_id": 12,
        }

        with mock.patch.object(leader, "invite_entity") as invite:
            self.assertEqual(leader.invite_members(gap=0), 1)

        invite.assert_called_once_with(member.self_entity)

    def test_invite_KHONG_moi_khi_LECH_KENH_that(self):
        leader = self.make_client()
        leader.party_idx = 19
        leader.self_entity = bytes.fromhex("1111111111111111")
        leader.current_map = 12001
        leader.current_channel = 12
        leader.current_channel_at = time.time()

        member = self.make_client()
        member.party_idx = 19
        member.self_entity = bytes.fromhex("2222222222222222")
        member.current_map = 12001
        member.current_channel = 13
        member.current_channel_at = time.time()

        _register_party_client(19, leader.self_entity, leader)
        _register_party_client(19, member.self_entity, member)
        _PARTY_ENTITIES[19] = {leader.self_entity, member.self_entity}

        # DOI LAI CHINH SACH (30/08): tung bo han so kenh vi hai gia tri NHO SAN hay lech oan.
        # Nhung bo han thi party nam rai nhieu kenh van duoc coi la du dieu kien moi - user kiem
        # chung tan mat: bot hien ca 5 nick party 3 o kenh 12, trong game la 12/12/12/2/1, moi
        # mai khong ai vao doi va khong mot ma tu choi nao. Nay HOI LAI SERVER (`kenh_that`) roi
        # moi so -> lech kenh THAT thi KHONG moi.
        with mock.patch.object(leader, "invite_entity") as invite:
            self.assertEqual(leader.invite_members(gap=0), 0)

        invite.assert_not_called()

    def test_invite_KHONG_moi_khi_lech_MAP_live(self):
        """Cong con lai sau khi bo so kenh: lech MAP thi van phai chan."""
        leader = self.make_client()
        leader.party_idx = 19
        leader.self_entity = bytes.fromhex("1111111111111111")
        leader.current_map = 12001
        leader.current_channel = 12

        member = self.make_client()
        member.party_idx = 19
        member.self_entity = bytes.fromhex("2222222222222222")
        member.current_map = 14821          # map KHAC
        member.current_channel = 12

        _register_party_client(19, leader.self_entity, leader)
        _register_party_client(19, member.self_entity, member)
        _PARTY_ENTITIES[19] = {leader.self_entity, member.self_entity}

        with mock.patch.object(leader, "invite_entity") as invite:
            self.assertEqual(leader.invite_members(gap=0), 0)
        invite.assert_not_called()

    def test_invite_KHONG_moi_khi_client_member_da_tat(self):
        leader = self.make_client()
        leader.party_idx = 19
        leader.self_entity = bytes.fromhex("1111111111111111")
        leader.current_map = 12001

        member = self.make_client()
        member.party_idx = 19
        member.self_entity = bytes.fromhex("2222222222222222")
        member.current_map = 12001
        member.running = False

        _register_party_client(19, leader.self_entity, leader)
        _register_party_client(19, member.self_entity, member)
        _PARTY_ENTITIES[19] = {leader.self_entity, member.self_entity}

        with mock.patch.object(leader, "invite_entity") as invite:
            self.assertEqual(leader.invite_members(gap=0), 0)
        invite.assert_not_called()

    def test_train_party_invites_whitelist_before_bot_members(self):
        leader = self.make_client()
        events = []
        leader.invite_whitelist_leaders = mock.Mock(
            side_effect=lambda gap=1.0: events.append(("whitelist", gap)) or 1
        )
        leader.invite_members = mock.Mock(
            side_effect=lambda gap=1.0: events.append(("bots", gap)) or 2
        )

        result = leader.invite_train_party_participants(gap=0)

        self.assertEqual(result, (1, 2))
        self.assertEqual(events, [("whitelist", 0), ("bots", 0)])

    def test_train_party_still_invites_bots_when_whitelist_invite_fails(self):
        leader = self.make_client()
        events = []
        leader.invite_whitelist_leaders = mock.Mock(side_effect=RuntimeError("scan failed"))
        leader.invite_members = mock.Mock(
            side_effect=lambda gap=1.0: events.append(("bots", gap)) or 2
        )

        result = leader.invite_train_party_participants(gap=0)

        self.assertEqual(result, (0, 2))
        self.assertEqual(events, [("bots", 0)])


if __name__ == "__main__":
    unittest.main()
