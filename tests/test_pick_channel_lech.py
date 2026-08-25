# -*- coding: utf-8 -*-
"""pick_best_channel: het kenh de tach thi GOM ca party ve kenh cua leader.

Bug that (log 17:25, user chi ra): kenh da full nen server khong con liet ke kenh nao de chuyen
sang -> `cand` rong. Truoc day bot hieu nham cai do la "ca party dang cung kenh" va tra 0 (giu
nguyen), trong khi thuc te leader o kenh 2 con 4 member o kenh 1 -> leader moi VO HAN, khong ai
thay loi moi.

Dung ra: het cho de tach thi gom NGUOC LAI ve kenh cua leader - leader dang o do san nen chac
chan vao duoc.
"""
import unittest

from bot.client import GameClient


class _Set:
    def wait(self, _t):
        return True

    def clear(self):
        pass

    def set(self):
        pass


def _bot(channels, current):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.running = True
    c.channels = dict(channels)
    c.current_channel = current
    c.switched = []
    c._chan_event = _Set()
    c.request_channel_list = lambda: None

    def _sw(ch):
        c.switched.append(ch)
        c.current_channel = ch
        return True
    c.switch_channel = _sw
    return c


class TestPickChannelLech(unittest.TestCase):
    def test_het_kenh_de_tach_thi_gom_ve_kenh_leader(self):
        """Canh log 17:25: khong con kenh trong, leader o kenh 2 -> ca party ve kenh 2."""
        c = _bot({1: (50, 50)}, current=2)
        r = c.pick_best_channel(need=5)
        self.assertEqual(r, 2, "phai bao kenh CUA LEADER cho ca party, KHONG bao 0 (giu nguyen)")
        self.assertEqual(c.switched, [], "leader dang o kenh do roi -> khong tu chuyen")

    def test_chua_biet_kenh_thi_khong_doan(self):
        c = _bot({1: (50, 50)}, current=None)
        self.assertEqual(c.pick_best_channel(need=5), 0)
        self.assertEqual(c.switched, [])

    def test_con_kenh_du_cho_thi_van_tach_nhu_cu(self):
        """Khong duoc pha hanh vi cu: con kenh trong thi van chuyen sang kenh it nguoi."""
        c = _bot({1: (50, 50), 3: (2, 50), 4: (9, 50)}, current=1)
        r = c.pick_best_channel(need=5)
        self.assertEqual(r, 3, "kenh it nguoi nhat MA du cho")
        self.assertEqual(c.switched, [3])


if __name__ == "__main__":
    unittest.main()
