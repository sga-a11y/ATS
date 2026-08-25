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

import bot.client as _bc
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


def _nhan(c, pkt):
    """Bom goi qua DUNG duong dispatch that, KHONG goi thang handler.

    Bai hoc: ban test dau tien goi thang _on_route_dialog nen VAN XANH trong khi duong that hong.
    Duong that hong o HAI cho: (1) cho goi con loc `sub == 01`, (2) - nang hon - handler nam
    trong _observe_npc40_packet, ma ham do mo dau bang `if not self._npc40_started: return` nen
    khi qua cong KHONG BAO GIO chay. Test phai di tu _dispatch moi thay duoc.
    """
    c._dispatch(0x14, pkt)


def _bot():
    c = Client.__new__(Client)
    c._label = "test"
    c.current_map = 63000
    c._in_scene_gate = True
    c._gate_choice_pending = False
    c._gate_choice_try = 0
    c._gate_event_logged = 0
    c._gate_choice_sent_at = 0.0
    c._gate_choice_last = None
    c._gate_choice_key = (63000, 10)
    # bang nho o cap MODULE (co y: song qua relogin) -> moi bai test phai tu don,
    # khong thi bai truoc do het ma se lam bai sau do sai.
    c._npc40_last_dialog = None
    c._npc40_prompt_pending = False
    c._npc40_prompt_pending_at = 0.0
    # Cac observer anh em can nhieu trang thai khong lien quan -> cho rong. VAN di qua _dispatch
    # that de bai test con bat duoc loi "handler nam nham trong ham chi chay khi lam 40 NPC".
    for _ten in ("_observe_team_dungeon_packet", "_observe_npc40_packet", "_observe_mob_packet",
                 "_track_battle_packet"):
        setattr(c, _ten, lambda *a, **k: None)
    c.sent = []
    c.send = lambda op, pl: c.sent.append((op, pl.hex()))
    return c


class TestGateEventChoice(unittest.TestCase):
    def setUp(self):
        _bc._GATE_CHOICE_STATE.pop((63000, 10), None)

    def test_goi_thoai_khong_bi_tra_loi_nham(self):
        """resultType 1 = thoai -> KHONG duoc bam chon (day la loi cu)."""
        c = _bot()
        _nhan(c, _pkt(1, Client.EVENT_RESULT_TALK))
        self.assertFalse(c._gate_choice_pending)
        self.assertFalse(c._send_gate_choice())
        self.assertEqual(c.sent, [])

    def test_bat_buoc_chon_o_moi_sub_tu_1_den_6(self):
        """resultType 6 den tren BAT KY sub nao trong 1..6 deu phai bat duoc."""
        for sub in range(1, 7):
            c = _bot()
            _nhan(c, _pkt(sub, Client.EVENT_RESULT_INTERACT))
            self.assertTrue(c._gate_choice_pending, "sub %d bi bo sot" % sub)

    def test_tra_loi_dung_goi_C020_009(self):
        c = _bot()
        _nhan(c, _pkt(3, Client.EVENT_RESULT_INTERACT))
        self.assertTrue(c._send_gate_choice())
        self.assertEqual(c.sent, [(0x14, "090014")])   # 0x14 sub09 + ma 20 (=0x14) CO

    def test_leo_thang_khi_server_hoi_lai(self):
        """Server hoi lai = ma vua roi sai -> thu ma khac, khong bam mai mot ma."""
        c = _bot()
        codes = []
        for _ in range(5):
            _nhan(c, _pkt(1, Client.EVENT_RESULT_INTERACT))
            if c._send_gate_choice():
                codes.append(int(c.sent[-1][1][4:6], 16))
        self.assertEqual(codes, [20, 30, 31, 40])

    def test_ngoai_cong_thi_khong_dung_toi(self):
        """Hop thoai NPC nhiem vu/40NPC co duong rieng - tra bua o day la bam lung tung."""
        c = _bot()
        c._in_scene_gate = False
        _nhan(c, _pkt(1, Client.EVENT_RESULT_INTERACT))
        self.assertFalse(c._gate_choice_pending)


class TestGateChoiceHocMa(unittest.TestCase):
    """Chon SAI ma -> server NGAT KET NOI. Luot thu phai song qua lan dang nhap lai."""

    def setUp(self):
        _bc._GATE_CHOICE_STATE.pop((63000, 10), None)

    def test_luot_thu_song_qua_relogin(self):
        """Log 17:44: ma 20 sai -> server da -> client bi tao lai. Neu dem o client thi lan sau
        lai do ma 20 -> ket VINH VIEN. Phai tien sang ma tiep theo."""
        ma = []
        for _ in range(3):          # 3 lan "chay", moi lan mot client MOI
            c = _bot()
            _bc._GATE_CHOICE_STATE.setdefault((63000, 10), _bc._GATE_CHOICE_STATE.get((63000, 10))
                                              or {"try": 0, "ok": None})
            _nhan(c, _pkt(1, Client.EVENT_RESULT_INTERACT))
            c._send_gate_choice()
            ma.append(int(c.sent[-1][1][4:6], 16))
        self.assertEqual(ma, [20, 30, 31], "moi lan chay phai tien MOT buoc")

    def test_ma_dung_duoc_ghi_nho(self):
        c = _bot()
        _nhan(c, _pkt(1, Client.EVENT_RESULT_INTERACT))
        c._send_gate_choice()                      # thu ma 20
        _bc._GATE_CHOICE_STATE[(63000, 10)]["ok"] = 30   # gia su 30 la ma dung
        c2 = _bot()
        _bc._GATE_CHOICE_STATE[(63000, 10)] = {"try": 1, "ok": 30}
        _nhan(c2, _pkt(1, Client.EVENT_RESULT_INTERACT))
        c2._send_gate_choice()
        self.assertEqual(int(c2.sent[-1][1][4:6], 16), 30, "phai dung thang ma da biet")


class TestGateChoiceThuTuGoi(unittest.TestCase):
    """Server ngat ket noi neu SAI THU TU goi - neo lai bang goi that."""

    def setUp(self):
        _bc._GATE_CHOICE_STATE.pop((63000, 10), None)

    def test_khong_duoc_gui_next_ngay_sau_khi_chon(self):
        """Log 17:19:45 (goi that): 0x14 0600 roi 0x14 090014 -> "su kien vi pham (ma 5)" -> da.

        `0x14 06` la <事件下一步>. Bam "buoc tiep" trong luc server dang cho CHON, hoac ngay sau
        khi vua chon, deu bi coi la vi pham.
        """
        c = _bot()
        _nhan(c, _pkt(1, Client.EVENT_RESULT_INTERACT))
        self.assertFalse(c._gate_next_blocked())   # chua chon -> chua chan
        self.assertTrue(c._send_gate_choice())
        self.assertTrue(c._gate_next_blocked())    # vua chon -> PHAI chan 0x14 06

    def test_het_chan_sau_vai_giay(self):
        import time as _t
        c = _bot()
        c._gate_choice_sent_at = _t.time() - 10.0
        self.assertFalse(c._gate_next_blocked())


if __name__ == "__main__":
    unittest.main()
