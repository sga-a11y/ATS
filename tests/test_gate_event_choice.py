# -*- coding: utf-8 -*-
"""Su kien cong (cau Gioi kieu): bot phai bat dung buoc CHON cua server.

Crack client (Logic_Event_EventManager.lua + Logic_Event_EventHandler.lua):
  - `S:020-001..006 <一般事件>` DEU vao chung EventManager.ReceiveCommonEvent -> SUB KHONG phai
    loai buoc. Loai buoc la `resultType`, byte thu 5 cua payload (offset +4).
  - EventHandler[1] = Thoai, [3] = Vao tran, [6] = TUONG TAC (server dung lai cho chon).
  - Chon gui `C:020-009 <事件選擇> +選擇碼(1)` = `0x14 09 <ma>`; 20=Co, 21=Khong, 30+i=danh sach,
    40=dong.

Bai hoc bo test nay neo: ban dau bot bat theo `sub == 01` va tra loi goi DAU TIEN -> tra loi vao
goi THOAI chu khong phai goi hoi -> ket o cong (log 16:46, cong idx=10 map 63000).
"""
import unittest

from bot.client import GameClient as Client


def _pkt(sub, result_type, extra=b""):
    """Dung goi S:020-<sub> voi resultType cho truoc (khop ReceiveCommonEvent)."""
    payload = bytes([
        0,           # +0 resultDiagnosis
        0, 0,        # +1 resultGroupNo u16
        0,           # +3 resultNo
        result_type,  # +4 resultType  <- thu bot phai doc
        0,           # +5 resultClass
        0, 0,        # +6 parameter u16
        0,           # +8 parameterStyle
        0, 0, 0, 0,  # +9 resultValue i32
        0, 0,        # +13 resultMeanNo u16
    ]) + extra
    return b"\xc0\x91" + b"\x00\x00" + b"\x00\x00" + b"\x14" + bytes([sub, 0]) + payload


def _bot():
    c = Client.__new__(Client)
    c._label = "test"
    c.current_map = 63000
    c._in_scene_gate = True
    c._gate_choice_pending = False
    c._gate_choice_try = 0
    c.sent = []
    c.send = lambda op, pl: c.sent.append((op, pl.hex()))
    return c


class TestGateEventChoice(unittest.TestCase):
    def test_goi_thoai_khong_bi_tra_loi_nham(self):
        """resultType 1 = thoai -> KHONG duoc bam chon (day la loi cu)."""
        c = _bot()
        c._on_route_dialog(_pkt(1, Client.EVENT_RESULT_TALK))
        self.assertFalse(c._gate_choice_pending)
        self.assertFalse(c._send_gate_choice())
        self.assertEqual(c.sent, [])

    def test_bat_buoc_chon_o_moi_sub_tu_1_den_6(self):
        """resultType 6 den tren BAT KY sub nao trong 1..6 deu phai bat duoc."""
        for sub in range(1, 7):
            c = _bot()
            c._on_route_dialog(_pkt(sub, Client.EVENT_RESULT_INTERACT))
            self.assertTrue(c._gate_choice_pending, "sub %d bi bo sot" % sub)

    def test_tra_loi_dung_goi_C020_009(self):
        c = _bot()
        c._on_route_dialog(_pkt(3, Client.EVENT_RESULT_INTERACT))
        self.assertTrue(c._send_gate_choice())
        self.assertEqual(c.sent, [(0x14, "090014")])   # 0x14 sub09 + ma 20 (=0x14) CO

    def test_leo_thang_khi_server_hoi_lai(self):
        """Server hoi lai = ma vua roi sai -> thu ma khac, khong bam mai mot ma."""
        c = _bot()
        codes = []
        for _ in range(4):
            c._on_route_dialog(_pkt(1, Client.EVENT_RESULT_INTERACT))
            if c._send_gate_choice():
                codes.append(int(c.sent[-1][1][4:6], 16))
        self.assertEqual(codes, [20, 30, 40])   # Co -> muc dau danh sach -> dong

    def test_ngoai_cong_thi_khong_dung_toi(self):
        """Hop thoai NPC nhiem vu/40NPC co duong rieng - tra bua o day la bam lung tung."""
        c = _bot()
        c._in_scene_gate = False
        c._on_route_dialog(_pkt(1, Client.EVENT_RESULT_INTERACT))
        self.assertFalse(c._gate_choice_pending)


if __name__ == "__main__":
    unittest.main()
