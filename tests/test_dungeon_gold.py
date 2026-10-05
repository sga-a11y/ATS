"""Gold from client protocol and login capture; ticket balance guard (05/10)."""
import struct
import unittest
from unittest import mock
from bot.client import GameClient
from tests.test_quest_hoi_thoai_capture import _frames
from pathlib import Path


def packet(op, body):
    return b'\xc0\x91' + struct.pack('<H', len(body) + 7) + b'\x00\x00' + bytes([op]) + body


class TestDungeonGold(unittest.TestCase):
    def client(self, gold=None):
        c = GameClient.__new__(GameClient)
        c._label = 'gold-test'
        c.nguyen_bao = gold
        c.nguyen_bao_khoa = None
        c.bag_slots = {}
        c._dungeon_tier = lambda: 3
        return c

    def test_login_capture_balance(self):
        path = Path(__file__).resolve().parents[1] / 'captures/tsm_login_20260929.pcap'
        rows = [b for k, op, b in _frames(path) if k == 'S' and op == 35 and b[:2] == b'\x05\x00']
        self.assertEqual(rows, [bytes.fromhex('05006400000000000000')])
        c = self.client()
        c._observe_gold(35, packet(35, rows[0]))
        self.assertEqual((c.nguyen_bao, c.nguyen_bao_khoa), (100, 0))

    def test_server_balance_replaces_previous_amount_including_zero(self):
        c = self.client(100)
        for value in (9, 0, 30):
            c._observe_gold(35, packet(35, b'\x05\x00' + struct.pack('<II', value, 50)))
            self.assertEqual(c.nguyen_bao, value)
            self.assertEqual(c.nguyen_bao_khoa, 50)

    def test_short_or_unrelated_packets_do_not_invent_zero(self):
        c = self.client()
        c._observe_gold(35, packet(35, b'\x05\x00\x01'))
        c._observe_gold(26, packet(26, b'\x04\x00' + struct.pack('<I', 9000)))
        self.assertIsNone(c.nguyen_bao)

    def test_legacy_point_and_shop_update(self):
        c = self.client()
        c._observe_gold(35, packet(35, b'\x04\x00' + struct.pack('<ii', 2, 34) + b'\x00'*8))
        self.assertEqual(c.nguyen_bao, 234)
        c._observe_gold(23, packet(23, b'\x4c\x00' + struct.pack('<HiiB', 123, 10, 224, 1)))
        self.assertEqual(c.nguyen_bao, 224)

    def buy(self, gold, price=10, kind=1):
        c = self.client(gold)
        def reply(op, body):
            if body[:2] == b'\x01\x00':
                c._dg_query = b'\x01\x00\x0d\x00' + bytes([kind]) + struct.pack('<I', price)
            else:
                c._dg_query = b'\x02\x00\x0d\x00\x01'
        c.send = mock.Mock(side_effect=reply)
        result = c.buy_dungeon_ticket()
        buys = [call for call in c.send.call_args_list if call.args[1][:2] == b'\x02\x00']
        return result, buys

    def test_less_than_ten_does_not_send_purchase(self):
        for gold in (0, 9):
            self.assertEqual(self.buy(gold), (False, []))

    def test_exact_price_and_unknown_balance_keep_existing_purchase_path(self):
        for gold in (10, 100, None):
            result, buys = self.buy(gold)
            self.assertTrue(result)
            self.assertEqual(len(buys), 1)

    def test_server_quote_is_used_and_free_ticket_is_not_blocked(self):
        self.assertEqual(self.buy(10, price=20), (False, []))
        self.assertTrue(self.buy(0, price=0, kind=254)[0])
