"""`S:007-001 <分區列表>` phai parse DUNG `count` cua server, khong doan.

Client that (`_lua_dec/Common/protocal.lua:1059`):

    protocolTable[7][1] = function(data)
      local count = data:ReadByte();
      if count <= 0 then ShowCenterMessage(string.Get(10135)); return; end
      for i = 1, count do
        aeraData.index          = data:ReadUInt16();
        aeraData.currentPlayers = data:ReadUInt16();
        aeraData.maxPlayers     = data:ReadUInt16();
      end

Ban cu BO QUA `count`, duyet het buffer roi loc bang phong doan `0 < ch < 1000 and cap > 0`:
goi thieu byte -> im lang nhan mot bang NGAN; goi thua -> nhet block rac vao.

Bang thieu kenh chinh la thu khien dieu phoi "khong chot lai kenh khac" - no chi thay may kenh
dau (deu day) va khong biet con kenh trong phia sau. Bang chung 08/09, CUNG mot server ma so kenh
doc ra nhay lung tung:

    545 lan "Nhan danh sach 9 kenh" · 256 lan "14 kenh" · 129 lan "62 kenh" · ... "5 kenh"

User: "deo can ghi nho kenh day, m phai lay duoc chinh xac ket qua tra ve".
"""
from __future__ import annotations

import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient   # noqa: E402


def _gia():
    c = GameClient.__new__(GameClient)
    c._label = "gia"
    c.channels = {}
    c._ds_kenh_nhan_luc = 0.0
    import threading as _th
    c._chan_event = _th.Event()
    return c


def _goi(chans, count=None, cat=0):
    """header(6) + op(1) + '01 00'(2) + count(1) + count*(ch,cur,cap).

    `count` khac None -> co tinh khai bao SAI so voi so block that (goi bi cat).
    `cat` -> bo bot ngan ay byte cuoi (goi TCP bi cat giua chung).
    """
    than = b"".join(struct.pack("<HHH", ch, cur, cap) for ch, cur, cap in chans)
    if cat:
        than = than[:-cat]
    return bytes(6) + b"\x07" + b"\x01\x00" + bytes([count if count is not None else len(chans)]) + than


class TestParseDungCount(unittest.TestCase):
    def test_doc_du_moi_kenh(self):
        c = _gia()
        ds = [(i, i, 20) for i in range(1, 63)]      # 62 kenh nhu server that
        GameClient._on_channel_list(c, _goi(ds))
        self.assertEqual(len(c.channels), 62)
        self.assertEqual(c.channels[62], (62, 20))

    def test_goi_THIEU_BYTE_thi_BO_ca_goi(self):
        """Nhan bang ngan = tuong server chi co may kenh -> khong bao gio chot ra kenh con trong."""
        c = _gia()
        c.channels = {9: (1, 20)}
        GameClient._on_channel_list(c, _goi([(i, 5, 20) for i in range(1, 63)], cat=100))
        self.assertEqual(c.channels, {9: (1, 20)}, "nhan bang thieu thay vi giu bang cu")

    def test_goi_THUA_BYTE_thi_KHONG_nhet_rac(self):
        c = _gia()
        pkt = _goi([(1, 5, 20), (2, 6, 20)]) + b"\xff\xff\x01\x00\x14\x00"
        GameClient._on_channel_list(c, pkt)
        self.assertEqual(sorted(c.channels), [1, 2])

    def test_count_0_thi_khong_dung_bang_rong(self):
        """Client: count <= 0 -> ShowCenterMessage roi return, KHONG xoa danh sach dang co."""
        c = _gia()
        c.channels = {3: (1, 20)}
        GameClient._on_channel_list(c, _goi([], count=0))
        self.assertEqual(c.channels, {3: (1, 20)})

    def test_count_0_van_DANH_THUC_nguoi_dang_cho(self):
        """Cau tra loi (KHONG CO KENH NAO) da co ngay - de nguoi hoi ngoi het timeout la phi."""
        c = _gia()
        GameClient._on_channel_list(c, _goi([], count=0))
        self.assertTrue(c._chan_event.is_set())

    def test_KENH_DANG_O_luon_co_trong_danh_sach(self):
        """Client tu them chinh instance minh dang o neu server khong liet ke:
            if not table.Contains(UIServerArea.instances, SceneManager.instanceId) then
              aeraData.index = SceneManager.instanceId; table.insert(...)
        Server khong liet ke kenh minh dang dung (thuong vi no DAY) khong co nghia kenh do khong
        ton tai."""
        c = _gia()
        c.current_channel = 27
        GameClient._on_channel_list(c, _goi([(1, 5, 20), (2, 6, 20)]))
        self.assertIn(27, c.channels)

    def test_kenh_dang_o_KHONG_bia_suc_chua(self):
        """Client them vao KHONG kem current/maxPlayers. Bia so = chot kenh bang so tu nghi ra."""
        c = _gia()
        c.current_channel = 27
        GameClient._on_channel_list(c, _goi([(1, 5, 20)]))
        self.assertEqual(c.channels[27], (None, None))

    def test_kenh_dang_o_CO_trong_goi_thi_giu_so_that(self):
        c = _gia()
        c.current_channel = 2
        GameClient._on_channel_list(c, _goi([(1, 5, 20), (2, 6, 20)]))
        self.assertEqual(c.channels[2], (6, 20))

    def test_suc_chua_KHONG_RO_thi_khong_lam_no_ham_chot(self):
        """`(None, None)` di qua `_bang_kenh` / `_kenh_trong_cho_ca_party` / `pick_best_channel`."""
        from unittest import mock
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        c = _gia()
        c.current_channel = 27
        GameClient._on_channel_list(c, _goi([(1, 5, 20)]))
        self.assertEqual(R._bang_kenh([("a", c)]), {1: (5, 15)})
        self.assertIsNone(R._kenh_trong_cho_ca_party(0, {}, [("a", c)] * 30, set()))

    def test_so_kenh_LON_van_doc_het(self):
        """`0 < ch < 1000` cua ban cu la phong doan - kenh so lon deu bi vut."""
        c = _gia()
        GameClient._on_channel_list(c, _goi([(1200, 3, 20), (5, 1, 20)]))
        self.assertIn(1200, c.channels)

    def test_dong_dau_LUC_NHAN(self):
        """Dieu phoi doc moc nay de biet bang da moi chua (khong chot bang bang cu/rong)."""
        c = _gia()
        GameClient._on_channel_list(c, _goi([(1, 2, 20)]))
        self.assertGreater(c._ds_kenh_nhan_luc, 0.0)


class TestVienDanCrackClient(unittest.TestCase):
    def test_co_ghi_nguon(self):
        import io
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def _on_channel_list")
        self.assertGreater(i, 0)
        khoi = s[i:i + 2600]
        for m in ("protocal.lua", "count", "ReadUInt16"):
            self.assertIn(m, khoi, m)


if __name__ == "__main__":
    unittest.main()
