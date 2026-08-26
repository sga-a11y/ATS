# -*- coding: utf-8 -*-
"""The doi (Exchange, specialAbility 219) + tu mo de du dan nang cap thu cuoi.

Crack client:
  - `Logic_Item.lua:1999-2035`: item co specialAbility == EItemUseKind.Exchange (219) KHONG dung
    goi dung item thuong, ma gui `C:090-001 <兌換> +兌換物品ID(2) +選取數量(1) <<+選取索引(1)>>`
    = opcode 0x5a sub01. So muc phai chon = itemData.elementValue.
  - `Data_ExchangeData.lua` + `DataManager.OnLoadExchange`: danh sach muc nam trong
    Data/Exchange_C.dat, client KHONG nhan qua mang -> bot phai tra bang (exchange.json).

Vi du cua user (neo thang vao bai test):
    "dang co 33/50 -> thieu 17 -> dang co 10 cai Boi duong toa ky -> mo 4 cai de lay 20"
"""
import unittest

from bot.client import GameClient


class _Cfg:
    """config gia - chi co bang EXCHANGE."""
    EXCHANGE = {
        0x7de7: [{"i": 1, "id": 0x7d65, "n": 5, "ten": "Tang Cap Ky Don"},
                 {"i": 2, "id": 0xb22c, "n": 1, "ten": "Tui Toa Ky Dan"}],
    }


def _bot(bag):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.running = True
    c.bag_counts = dict(bag)
    c.sent = []
    c.MOUNT_GAP = 0.0
    c.EXCHANGE_ACK_WAIT = 0.3
    c._bag_slot_of = lambda tid: 7 if int(tid) in c.bag_counts else None
    c._mount_item_name = lambda tid: "0x%04x" % tid

    def _send(op, pl):
        c.sent.append((op, pl.hex()))
        # gia lap server: mo the -> tru 1 the, cong 5 dan
        if op == 0x5a:
            c.bag_counts[0x7de7] = c.bag_counts.get(0x7de7, 0) - 1
            c.bag_counts[0x7d65] = c.bag_counts.get(0x7d65, 0) + 5
    c.send = _send
    return c


class TestGoiTheDoi(unittest.TestCase):
    def setUp(self):
        import bot.client as bc
        self._cu = bc.config
        bc.config = _Cfg()

    def tearDown(self):
        import bot.client as bc
        bc.config = self._cu

    def test_goi_dung_dinh_dang_C090_001(self):
        c = _bot({0x7de7: 3})
        self.assertTrue(c.open_exchange_card(0x7de7, 1))
        op, hx = c.sent[-1]
        self.assertEqual(op, 0x5a)
        # sub01 + itemId u16 LE (e77d) + selectCount 01 + index 01
        self.assertEqual(hx, "0100" + "e77d" + "01" + "01")

    def test_index_2_gui_dung_index(self):
        c = _bot({0x7de7: 1})
        c.open_exchange_card(0x7de7, 2)
        self.assertTrue(c.sent[-1][1].endswith("0102"))

    def test_khong_co_the_trong_tui_thi_khong_gui(self):
        c = _bot({})
        self.assertFalse(c.open_exchange_card(0x7de7, 1))
        self.assertEqual(c.sent, [])

    def test_the_khong_co_trong_bang_thi_khong_gui(self):
        c = _bot({0x9999: 5})
        self.assertFalse(c.open_exchange_card(0x9999, 1))
        self.assertEqual(c.sent, [])


class TestTuMoDeDuDan(unittest.TestCase):
    def setUp(self):
        import bot.client as bc
        self._cu = bc.config
        bc.config = _Cfg()

    def tearDown(self):
        import bot.client as bc
        bc.config = self._cu

    def test_vi_du_cua_user_33_tren_50(self):
        """thieu 17, moi the duoc 5 -> mo 4 the (KHONG mo het 10)."""
        c = _bot({0x7d65: 33, 0x7de7: 10})
        sau = c._mount_open_cards_for(0x7d65, thieu=17, dang_co=33)
        self.assertEqual(len(c.sent), 4, "phai mo dung 4 the")
        self.assertEqual(sau, 53)
        self.assertEqual(c.bag_counts[0x7de7], 6, "con lai 6 the")

    def test_khong_mo_thua_khi_chia_het(self):
        """thieu 10, moi the 5 -> dung 2 the, khong phai 3."""
        c = _bot({0x7d65: 40, 0x7de7: 9})
        c._mount_open_cards_for(0x7d65, thieu=10, dang_co=40)
        self.assertEqual(len(c.sent), 2)

    def test_khong_du_the_thi_mo_het_the_co(self):
        c = _bot({0x7d65: 0, 0x7de7: 2})
        sau = c._mount_open_cards_for(0x7d65, thieu=50, dang_co=0)
        self.assertEqual(len(c.sent), 2)
        self.assertEqual(sau, 10)

    def test_khong_co_the_thi_khong_lam_gi(self):
        c = _bot({0x7d65: 33})
        sau = c._mount_open_cards_for(0x7d65, thieu=17, dang_co=33)
        self.assertEqual(c.sent, [])
        self.assertEqual(sau, 33)

    def test_khong_mo_the_cho_item_khac(self):
        """The nay khong ra item minh can -> khong duoc dung toi."""
        c = _bot({0x7de7: 10})
        c._mount_open_cards_for(0xdead, thieu=5, dang_co=0)
        self.assertEqual(c.sent, [])


if __name__ == "__main__":
    unittest.main()
