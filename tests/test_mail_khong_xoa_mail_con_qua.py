"""Nhan qua mail: TUI DAY thi GIU mail lai, khong duoc xoa -> lam Y CLIENT.

Bot truoc day gui `53 01` (nhan) cho TAT CA mail roi `53 02` (xoa) cho TAT CA ngay sau do, khong
he doi xac nhan. Tui do DAY -> server tu choi cho nhan -> bot van xoa -> MAT QUA
(user 01/09: "neu nhan qua fail do tui do full thi sau do m van xoa mail lam mat qua").

Client (`_lua_dec/UI/UIMail.lua`) tach bach hai viec:

    OnClick_TakeAll()      -- C:083-001
        if v.state < EMailState.Take and table.maxn(v.contents) > 0
    OnClick_RemoveEmpty()  -- C:083-002
        if v.state == EMailState.Take or (v.state == EMailState.Read and table.maxn(v.contents) <= 0)

`EMailState = {Unread = 0, Read = 1, Take = 2}` (Logic/Social.lua), va state chi len `Take` khi
SERVER xac nhan qua `S:083-002 <領取信件> +數量(4) <<+信件ID(4)>>` (protocal.lua:13147).
Tuc client KHONG BAO GIO xoa mail con qua chua nhan duoc.
"""
from __future__ import annotations

import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient           # noqa: E402


def _mid(n):
    return struct.pack("<I", n)


class _Bot:
    """Client gia: chi giu phan can cho `claim_mail`."""

    MAIL_CHUA_DOC = GameClient.MAIL_CHUA_DOC
    MAIL_DA_DOC = GameClient.MAIL_DA_DOC
    MAIL_DA_NHAN = GameClient.MAIL_DA_NHAN
    claim_mail = GameClient.claim_mail.__wrapped__ if hasattr(
        GameClient.claim_mail, "__wrapped__") else GameClient.claim_mail

    def __init__(self, mails, server_cho_nhan=()):
        self.running = True
        self._label = "t"
        self._mail_ids = list(mails)
        self._mail_taken = set()
        self._cho_nhan = {bytes(m) for m in server_cho_nhan}
        self.goi = []

    def send(self, op, payload):
        self.goi.append((op, payload))
        if op != 0x53:
            return
        sub, body = payload[0], payload[2:]
        n = int.from_bytes(body[0:4], "little")
        ids = [body[4 + i * 4:8 + i * 4] for i in range(n)]
        if sub == 0x01:      # server chi XAC NHAN nhung mail no cho nhan (tui con cho)
            self._mail_taken |= {i for i in ids if i in self._cho_nhan}

    def _ds(self, sub):
        """Danh sach mailid trong goi 0x53 sub nay (rong neu khong gui)."""
        for op, pl in self.goi:
            if op == 0x53 and pl[0] == sub:
                n = int.from_bytes(pl[2:6], "little")
                return [pl[6 + i * 4:10 + i * 4] for i in range(n)]
        return []


class TestTuiDayThiGiuMail(unittest.TestCase):
    def test_nhan_duoc_HET_thi_xoa_het(self):
        b = _Bot([(_mid(1), 0, 2), (_mid(2), 0, 1)], server_cho_nhan=[_mid(1), _mid(2)])
        b.claim_mail()
        self.assertEqual(b._ds(0x01), [_mid(1), _mid(2)])
        self.assertEqual(b._ds(0x02), [_mid(1), _mid(2)])

    def test_TUI_DAY_thi_KHONG_XOA_mail_con_qua(self):
        """Loi that: nhan fail ma van xoa -> mat qua."""
        b = _Bot([(_mid(1), 0, 2), (_mid(2), 0, 1)], server_cho_nhan=[_mid(1)])
        b.claim_mail()
        self.assertEqual(b._ds(0x02), [_mid(1)], "xoa ca mail chua nhan duoc -> MAT QUA")

    def test_khong_nhan_duoc_MAIL_NAO_thi_khong_gui_lenh_xoa(self):
        b = _Bot([(_mid(1), 0, 2)], server_cho_nhan=[])
        b.claim_mail()
        self.assertEqual(b._ds(0x02), [])

    def test_mail_RONG_van_duoc_xoa(self):
        """Mail khong co dinh kem thi khong co gi de mat -> don di cho sach hom thu."""
        b = _Bot([(_mid(9), 0, 0)])
        b.claim_mail()
        self.assertEqual(b._ds(0x01), [], "mail rong ma van doi nhan qua")
        self.assertEqual(b._ds(0x02), [_mid(9)])

    def test_mail_rong_duoc_DANH_DAU_DA_DOC_truoc_khi_xoa(self):
        """Client chi xoa mail rong khi no o trang thai Read (OnClick_RemoveEmpty)."""
        b = _Bot([(_mid(9), 0, 0)])
        b.claim_mail()
        self.assertEqual(b._ds(0x03), [_mid(9)])

    def test_mail_DA_NHAN_tu_truoc_thi_xoa_khong_can_nhan_lai(self):
        b = _Bot([(_mid(5), GameClient.MAIL_DA_NHAN, 3)])
        b.claim_mail()
        self.assertEqual(b._ds(0x01), [], "mail da nhan roi ma con doi nhan lai")
        self.assertEqual(b._ds(0x02), [_mid(5)])

    def test_khong_co_mail_thi_khong_gui_gi(self):
        b = _Bot([])
        b.claim_mail()
        self.assertEqual(b.goi, [])


class TestDocGoiMail(unittest.TestCase):
    """S:083-001 <新增信件> +數量(4) <<+信件ID(4) +時間(8) +狀態(1) +L(2) +內容(L) +附件數量(1) ...>>"""

    @staticmethod
    def _c():
        c = GameClient.__new__(GameClient)
        c._label = "t"
        c._mail_ids = []
        c._mail_taken = set()
        for ten in ("_observe_team_dungeon_packet", "_observe_npc40_packet",
                    "_observe_mob_packet", "_track_battle_packet"):
            setattr(c, ten, lambda *a, **k: None)
        return c

    @staticmethod
    def _goi_list(mailid, state, n_qua, tieu_de=b"ab"):
        rec = (struct.pack("<I", mailid) + struct.pack("<d", 46000.5) + bytes([state])
               + struct.pack("<H", len(tieu_de)) + tieu_de + bytes([n_qua])
               + b"\x01" + b"\x00" * 4)
        return (b"\xc0\x91\x00\x00\x00\x00\x53\x01\x00"
                + struct.pack("<I", 1) + rec)

    def test_doc_dung_state_va_so_dinh_kem(self):
        c = self._c()
        c._dispatch(0x53, self._goi_list(7, 2, 3))
        self.assertEqual(c._mail_ids, [(struct.pack("<I", 7), 2, 3)])

    def test_mail_khong_dinh_kem_doc_ra_0(self):
        c = self._c()
        c._dispatch(0x53, self._goi_list(8, 1, 0))
        self.assertEqual(c._mail_ids[0][2], 0)

    def test_S083_002_ghi_nhan_mail_DA_NHAN(self):
        """Day la goi DUY NHAT chung minh qua da vao tui."""
        c = self._c()
        pkt = (b"\xc0\x91\x00\x00\x00\x00\x53\x02\x00"
               + struct.pack("<I", 2) + _mid(3) + _mid(4))
        c._dispatch(0x53, pkt)
        self.assertEqual(c._mail_taken, {_mid(3), _mid(4)})

    def test_goi_cut_khong_lam_sap(self):
        c = self._c()
        c._dispatch(0x53, b"\xc0\x91\x00\x00\x00\x00\x53\x02\x00\x05")
        self.assertEqual(c._mail_taken, set())


if __name__ == "__main__":
    unittest.main()
