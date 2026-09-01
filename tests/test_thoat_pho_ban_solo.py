"""PHO BAN SOLO thoat bang `C:013-004` voi ID CUA CHINH MINH (khac roi party).

Client (`_lua_dec/Logic/Dungeon.lua:243`):
    function Dungeon.LeaveSinglePlayDungeon()
      sendBuffer:WriteInt64(Role.playerId);   -- ID CUA CHINH MINH
      Network.Send(13, 4, sendBuffer);        -- C:013-004
    end
`Team.Leave` cung goi 013-004 nhung gui `members[playerId]` = ID DOI TRUONG. Hai duong khac nhau,
cung mot opcode.

BUG 01/09: buoc thoat dungeon truoc dung `leave_party()`. Sau khi them guard "khong o party thi
KHONG gui 013-004" (chong gui mu -> server ngung gui loi moi toi minh), pho ban SOLO khong co
party nao -> guard chan -> bot KHONG BAO GIO ra khoi map 62001:
    08:19:43 [vuhai] Dungeon HOAN THANH -> nhan thuong + ra
    08:19:43 [vuhai] KHONG o party nao (roster server + local deu rong) -> KHONG gui 013-004
roi `go_to_town` spam "Teleport -> city 12001" moi 2 giay hon 100 giay, va ca 4 acc dinh
`SERVER NGAT KET NOI: gui goi lien tuc qua nhanh (ma 13)`.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import protocol                  # noqa: E402
from bot.client import GameClient         # noqa: E402

TOI = b"\x11" * 8
CHU = b"\x22" * 8


def _bot():
    c = GameClient.__new__(GameClient)
    c._label = "t"
    c.self_entity = TOI
    c.party_idx = 0
    c.party_leader = None
    c.party_members = []
    c.team_of = {}
    c.team_of_at = 0.0
    c.sent = []
    c.send = lambda op, b: c.sent.append((op, bytes(b)))
    return c


class TestThoatPhoBanSolo(unittest.TestCase):
    def test_gui_ID_CUA_CHINH_MINH(self):
        c = _bot()
        self.assertTrue(c.leave_single_dungeon())
        self.assertEqual(c.sent, [(protocol.OP_PLAYER_STATE, b"\x04\x00" + TOI)])

    def test_KHONG_bi_guard_cua_leave_party_chan(self):
        """Guard "khong o party thi khong gui" la cua `leave_party`; duong solo phai di rieng."""
        c = _bot()
        c.leave_party()
        self.assertEqual(c.sent, [], "roi party khi khong o party nao -> van phai bi chan")
        c.leave_single_dungeon()
        self.assertEqual(len(c.sent), 1, "thoat dungeon solo bi chan -> ket trong map 62001")

    def test_KHAC_leave_party_o_cho_gui_ID_nao(self):
        c = _bot()
        c.party_leader = CHU
        c.party_members = [CHU, TOI]
        c.leave_party()
        c.leave_single_dungeon()
        self.assertEqual(c.sent[0][1], b"\x04\x00" + CHU, "roi party phai gui ID DOI TRUONG")
        self.assertEqual(c.sent[1][1], b"\x04\x00" + TOI, "thoat solo phai gui ID CUA MINH")

    def test_chua_biet_entity_thi_KHONG_gui(self):
        c = _bot()
        c.self_entity = None
        self.assertFalse(c.leave_single_dungeon())
        self.assertEqual(c.sent, [])

    def test_dungeon_solo_dung_ham_nay(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("Dungeon HOAN THANH -> nhan thuong + ra")
        self.assertGreater(i, 0)
        khoi = s[i:i + 1600]
        self.assertIn("self.leave_single_dungeon()", khoi)
        self.assertNotIn("self.leave_party()", khoi, "quay lai leave_party = bi guard chan lai")


class TestKhongTeleportTrongInstance(unittest.TestCase):
    """`go_to_town` co chot cho pho ban TO DOI + Di Gioi, nhung THIEU pho ban SOLO (map 62001)
    -> spam teleport toi khi server da vi `ma 13`."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def go_to_town(")
        self.assertGreater(i, 0)
        self.than = s[i:s.find("\n    def ", i + 10)]

    def test_co_chot_cho_MOI_instance(self):
        self.assertIn("in_instance_map(self.current_map)", self.than,
                      "chi chot pho ban TO DOI -> pho ban solo lot qua, spam teleport")

    def test_chot_TRA_VE_ngay_chu_khong_lap_tiep(self):
        i = self.than.find("in_instance_map(self.current_map)")
        khoi = self.than[i:i + 500]
        self.assertIn("return False", khoi)

    def test_van_giu_cac_chot_cu(self):
        self.assertIn("_team_dungeon_until", self.than)
        self.assertIn("self.in_di_gioi()", self.than)


if __name__ == "__main__":
    unittest.main()
