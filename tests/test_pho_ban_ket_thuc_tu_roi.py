"""PHO BAN KET THUC (`S:047-012`) -> moi acc TU ROI, y het client game.

User hoi 07/09: "xong roi va leader an hoan thanh la ca pt bi day ra ngoai ma?" - tra crack client
thi NGUOC LAI: server KHONG day ai ra ca.

    S:047-012 <副本結束> +結果(1) +副本編號(2) +數量(1) <<+獎勵ID(2) +數量(4)>>
    protocolTable[47][12] = function(data) Dungeon.ReciveDungeonResult(data); end

`Logic/Dungeon.lua:783` - goi nay chi mang KET QUA + phan thuong; chinh cai NUT DONG bang ket qua
moi la lenh roi:

    UI.Open(UIResult, Role.player, title, "", "", reward, Dungeon.LeaveSinglePlayDungeon, result == 0);

    function Dungeon.LeaveSinglePlayDungeon()          -- Dungeon.lua:243
      sendBuffer:WriteInt64(Role.playerId);
      Network.Send(13, 4, sendBuffer);                 -- C:013-004
    end

Tuc MOI client tu roi. Bot thi `_on_dungeon()` CHI xu ly `sub == 0x0f` (loi moi) - khong doc goi
ket thuc, nen member khong he biet pho ban da xong va nam lai trong map instance.

Ca that 07/09 party 42:
    10:35:48 [luubmot] (LEADER) === PHO BAN TO DOI LV50 XONG -> roi pho ban ===
    10:40:39 [luubhai] go_to_town: DANG TRONG pho ban to doi (map=62012) -> khong teleport
    10:40:39 [luubhai] (member) reform: CHUA ve duoc Hội Kê (map=62012) -> nghi 10s thu lai
Gan 5 phut sau khi PB xong, member VAN o trong phong.

Day la viec moi acc TU LAM khi nhan goi CUA CHINH NO (giong client), khong phai viec dieu phoi -
dung L2: doc thang goi minh nhan duoc, khong cho ai bao.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient   # noqa: E402


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


def _goi_ket_thuc(ket_qua=0, dungeon_id=0x000E, thuong=()):
    """Dung goi S:047-012 y ta client: [0c 00][ket qua 1][pho ban 2][so thuong 1] + n*(id2 + sl4)."""
    b = b"\x0c\x00" + bytes([ket_qua]) + dungeon_id.to_bytes(2, "little") + bytes([len(thuong)])
    for tid, sl in thuong:
        b += tid.to_bytes(2, "little") + sl.to_bytes(4, "little")
    return b"\x00" * 7 + b


class _Gia:
    _label = "gia"

    def __init__(self):
        self.auto_accept_party = True
        self.party_idx = 0
        self.dungeon_complete = False
        self._pb_ket_thuc_luc = 0.0
        self.da_roi = 0

    def leave_single_dungeon(self):
        self.da_roi += 1
        return True

    def send(self, *_a, **_k):
        pass


class TestTuRoiKhiNhanGoiKetThuc(unittest.TestCase):
    def test_nhan_goi_thi_gui_lenh_roi(self):
        c = _Gia()
        GameClient._on_dungeon(c, _goi_ket_thuc())
        self.assertEqual(c.da_roi, 1, "khong tu roi -> ket lai trong map instance")
        self.assertTrue(c.dungeon_complete)
        self.assertGreater(c._pb_ket_thuc_luc, 0)

    def test_co_phan_thuong_van_doc_duoc(self):
        c = _Gia()
        GameClient._on_dungeon(c, _goi_ket_thuc(thuong=((0x1234, 3), (0x5678, 1))))
        self.assertEqual(c.da_roi, 1)

    def test_ket_qua_KHAC_0_cung_phai_roi(self):
        """`result == 0` chi doi mau nut trong client; du thang hay thua deu phai ra khoi phong."""
        c = _Gia()
        GameClient._on_dungeon(c, _goi_ket_thuc(ket_qua=1))
        self.assertEqual(c.da_roi, 1)

    def test_loi_khi_roi_KHONG_lam_dut_dispatch(self):
        c = _Gia()
        c.leave_single_dungeon = lambda: (_ for _ in ()).throw(OSError("socket dong"))
        GameClient._on_dungeon(c, _goi_ket_thuc())   # khong duoc nem ra ngoai
        self.assertTrue(c.dungeon_complete)

    def test_goi_cut_thi_bo_qua(self):
        c = _Gia()
        GameClient._on_dungeon(c, b"\x00" * 7 + b"\x0c\x00\x00")
        self.assertEqual(c.da_roi, 0)

    def test_khong_dung_nham_sub_khac(self):
        """Chi 0x0c moi la ket thuc. 0x0a (roi phong) / 0x0b (san sang) / 0x0d khong duoc coi la xong."""
        for sub in (0x0a, 0x0b, 0x0d):
            c = _Gia()
            GameClient._on_dungeon(c, bytes(7) + bytes([sub, 0]) + bytes(20))
            self.assertEqual(c.da_roi, 0, "sub 0x%02x" % sub)
            self.assertFalse(c.dungeon_complete, "sub 0x%02x" % sub)

class TestVienDanClient(unittest.TestCase):
    def test_co_ghi_ro_nguon(self):
        s = _src()
        i = s.find("if sub == 0x0c and len(body) >= 5:")
        self.assertGreater(i, 0)
        khoi = s[max(0, i - 1400):i]
        for m in ("S:047-012", "LeaveSinglePlayDungeon", "Dungeon.lua"):
            self.assertIn(m, khoi, m)

    def test_dung_dung_lenh_cua_client(self):
        """Client dong bang ket qua -> `Network.Send(13, 4, playerId)` = C:013-004 =
        `leave_single_dungeon`, KHONG phai C:047-010 (nut 'Thoat' cua UI to doi)."""
        s = _src()
        i = s.find("if sub == 0x0c and len(body) >= 5:")
        khoi = s[i:i + 900]
        self.assertIn("leave_single_dungeon()", khoi)


if __name__ == "__main__":
    unittest.main()
