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
import struct
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


class _CfgMixin:
    def setUp(self):
        import bot.client as bc
        self._cu = bc.config
        bc.config = _Cfg()

    def tearDown(self):
        import bot.client as bc
        bc.config = self._cu


class TestGoiTheDoi(_CfgMixin, unittest.TestCase):
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

    def test_nhan_ra_da_mo_ke_ca_khi_so_dan_khong_khop(self):
        """Tui ao tung lech (goi giam mang so luong) -> moc so sanh "nhan duoc do" sai.

        Dau hieu THE BI TRU khong dinh loi do, phai du de ket luan la server DA an the -
        khong thi bot bao that bai trong khi the da mat (log 10:02).
        """
        c = _bot({0x7de7: 2, 0x7d65: 999})

        def _send_chi_tru_the(op, pl):
            c.sent.append((op, pl.hex()))
            c.bag_counts[0x7de7] -= 1        # KHONG cong dan -> gia lap tui ao lech
        c.send = _send_chi_tru_the
        self.assertTrue(c.open_exchange_card(0x7de7, 1))


class TestTuMoDeDuDan(_CfgMixin, unittest.TestCase):
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


class TestChiMoKhiDU(_CfgMixin, unittest.TestCase):
    """User: "neu mo Boi duong toa ky ma DU thi mo ra de nang cap".

    Bug that (log 10:04): thieu 142, chi co 17 the (17*5 = 85 - khong bao gio du) -> bot van mo
    HET 17 the, mat trang. Toi da bo mat chu "ma du" trong yeu cau cua user.
    """

    def test_mo_cung_khong_du_thi_KHONG_mo(self):
        c = _bot({0x7d65: 8, 0x7de7: 17})
        sau = c._mount_open_cards_for(0x7d65, thieu=142, dang_co=8)
        self.assertEqual(c.sent, [], "mo cung khong du -> phai giu the lai")
        self.assertEqual(sau, 8)
        self.assertEqual(c.bag_counts[0x7de7], 17, "khong duoc mat the nao")

    def test_vua_du_thi_mo(self):
        """thieu 85, co 17 the x5 = 85 -> DUNG du -> mo."""
        c = _bot({0x7d65: 15, 0x7de7: 17})
        c._mount_open_cards_for(0x7d65, thieu=85, dang_co=15)
        self.assertEqual(len(c.sent), 17)

    def test_thieu_mot_chut_cung_khong_mo(self):
        """thieu 86, co 17 the x5 = 85 -> THIEU 1 -> khong mo cai nao."""
        c = _bot({0x7d65: 14, 0x7de7: 17})
        c._mount_open_cards_for(0x7d65, thieu=86, dang_co=14)
        self.assertEqual(c.sent, [])


class TestGoiGiamMangSoLuong(unittest.TestCase):
    """`S:023-009 <背包減少物品> +索引(1) +數量(4)` - goi MANG so luong, khong phai luon 1.

    Bug that (log 10:02): nang cap thu cuoi an 100 dan nhung bot chi tru 1 -> tui ao lech 99
    (bot tuong con 102 trong khi that su con 3) -> vong sau tinh "thieu" sai, roi mo the ma khong
    nhan ra la da mo -> MAT THE.
    """

    @staticmethod
    def _goi_giam(slot, n):
        """c0 91 [len][..][0x17][09 00][slot][so luong i32]"""
        than = bytes([0x17]) + b"\x09\x00" + bytes([slot]) + struct.pack("<i", n)
        return b"\xc0\x91" + b"\x00\x00" + b"\x00\x00" + than

    def _bot_tui(self, slot, tid, n):
        c = GameClient.__new__(GameClient)
        c._label = "test"
        c.bag_slots = {slot: [tid, n]}
        c.bag_counts = {tid: n}
        c._pending_confirm_slot = None
        c._use_confirmed = False
        for ten in ("_observe_team_dungeon_packet", "_observe_npc40_packet",
                    "_observe_mob_packet", "_track_battle_packet", "_on_route_dialog"):
            setattr(c, ten, lambda *a, **k: None)
        return c

    def test_tru_dung_so_luong_trong_goi(self):
        c = self._bot_tui(3, 0x7d65, 103)
        c._dispatch(0x17, self._goi_giam(3, 100))
        self.assertEqual(c.bag_counts[0x7d65], 3, "phai tru 100, khong phai tru 1")
        self.assertEqual(c.bag_slots[3][1], 3)

    def test_tru_1_van_dung(self):
        c = self._bot_tui(3, 0x7d65, 10)
        c._dispatch(0x17, self._goi_giam(3, 1))
        self.assertEqual(c.bag_counts[0x7d65], 9)

    def test_khong_am(self):
        c = self._bot_tui(3, 0x7d65, 5)
        c._dispatch(0x17, self._goi_giam(3, 99))
        self.assertEqual(c.bag_counts[0x7d65], 0)


if __name__ == "__main__":
    unittest.main()
