# -*- coding: utf-8 -*-
"""Bam lenh tui do luc DANG TRONG TRAN -> xep hang, het tran moi gui.

User 26/08: "may lenh dung item/trang bi, m them cai la neu click khi dang trong battle thi bot
de end battle moi gui di".

Client that CUNG chan: Item.UnEquip / Item.Use deu co
    if FightField.conIdx ~= FightField.GetPlayerIdx() then ShowCenterMessage(22595); return
tuc trong tran CHI doi do duoc khi TOI LUOT MINH. Gui bua giua tran thi server nuot lenh.
"""
import io
import os
import unittest

from bot.client import GameClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class _St:
    def __init__(self, in_battle):
        self.in_battle = in_battle


def _bot(in_battle):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.state = _St(in_battle)
    c._bag_queue = []
    return c


class TestXepHang(unittest.TestCase):
    def test_dang_danh_thi_XEP_HANG_khong_gui(self):
        c = _bot(True)
        goi = []
        self.assertTrue(c.queue_bag_cmd("Cởi ra", lambda: goi.append(1)))
        self.assertEqual(goi, [], "dang danh ma van gui la sai")
        self.assertEqual(len(c._bag_queue), 1)

    def test_ngoai_tran_thi_KHONG_xep_hang(self):
        c = _bot(False)
        self.assertFalse(c.queue_bag_cmd("Cởi ra", lambda: None))
        self.assertEqual(c._bag_queue, [])

    def test_het_tran_thi_gui_DUNG_THU_TU(self):
        c = _bot(True)
        goi = []
        c.MOUNT_GAP = 0
        for t in ("a", "b", "c"):
            c.queue_bag_cmd(t, lambda t=t: goi.append(t))
        c.state.in_battle = False
        c._flush_bag_queue()
        self.assertEqual(goi, ["a", "b", "c"])
        self.assertEqual(c._bag_queue, [], "xa xong phai rong")

    def test_mot_lenh_loi_KHONG_chan_lenh_sau(self):
        c = _bot(True)
        goi = []

        def _no():
            raise RuntimeError("hong")
        c.queue_bag_cmd("hong", _no)
        c.queue_bag_cmd("ok", lambda: goi.append("ok"))
        c._flush_bag_queue()
        self.assertEqual(goi, ["ok"])

    def test_xa_rong_thi_khong_lam_gi(self):
        c = _bot(False)
        c._flush_bag_queue()          # khong duoc no


class TestKhongBamMotNhanh(unittest.TestCase):
    """`in_battle` duoc HA o NHIEU cho (ket tran that, bo chay, doi map, reset...).

    Bam vao mot nhanh la kieu loi da mac nhieu lan trong repo nay (vd doi pha DG co 5 duong thoat,
    toi chi va 1). Nen ngoai moc nhanh o mot cho, phai co LUOI AN TOAN chay dinh ky.
    """

    def test_co_luoi_an_toan_o_vong_heartbeat(self):
        s = _doc("bot", "client.py")
        self.assertIn("if self._bag_queue and not self.state.in_battle:", s)
        self.assertIn("LUOI AN TOAN cho hang doi lenh tui do", s)

    def test_van_co_moc_nhanh_khi_ket_tran(self):
        s = _doc("bot", "client.py")
        self.assertIn("self._flush_bag_queue()     # lenh tui do user bam giua tran", s)


class TestGuiBaoRo(unittest.TestCase):
    def test_gui_kiem_tra_TRUOC_khi_gui(self):
        s = _doc("gui.py")
        self.assertIn("if self.c.queue_bag_cmd(text, fn):", s)

    def test_bao_ro_cho_user_biet(self):
        """Khong bao thi user tuong bam hut roi bam lai may lan."""
        s = _doc("gui.py")
        self.assertIn("def _done_queued", s)
        self.assertIn("sẽ gửi ngay khi đánh xong", s)


class TestTenChiSoDayDu(unittest.TestCase):
    """Ma 25/26 = HP/SP - ItemData.GetAttrText -> TextData_C.dat 20346='HP:' 20347='SP:'.

    User 26/08: "item hoi phuc dang ghi la 25/26, hinh nhu la HP/SP nhi" - dung, va truoc do UI
    hien "chỉ số 25 +104" vi thieu ten trong bang.
    """

    def test_co_ma_25_26(self):
        s = _doc("gui.py")
        i = s.find("_ITEM_ATTR = {")
        khoi = s[i:i + 420]
        self.assertIn('25: "HP"', khoi)
        self.assertIn('26: "SP"', khoi)

    def test_co_ma_trung_thanh(self):
        s = _doc("gui.py")
        self.assertIn('64: "Trung thành"', s)


if __name__ == "__main__":
    unittest.main()
