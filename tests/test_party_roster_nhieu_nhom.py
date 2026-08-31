"""`S:013-006 <隊伍資料>` chua NHIEU party trong MOT goi.

Client duyet het goi (`protocolTable[13][6]`):
    while data.length > 0 do
      local leaderId = data:ReadInt64(); local count = data:ReadByte()
      for i = 1, count do Team.AddMember(leaderId, data:ReadInt64(), false) end
    end
Goi phat theo MAP nen cac party khac cung map di CHUNG mot goi. Bot truoc day chi doc NHOM DAU
roi `return` neu minh khong o trong do -> party cua minh nam nhom thu 2 tro di la MAT TRANG CA
GOI -> leader khong bao gio thay roster.

Party 15 (27/08): roster cuoi cung 08:48:44, sau do 35 phut leader dem `roster server=0 nguoi`
trong khi member van accept deu moi vong -> ket vinh vien.

Cung file nay kiem 3 goi party ma bot TRUOC DAY DIEC hoan toan:
    S:013-005 <玩家加入隊伍>  - server bao tung nguoi vao doi
    S:013-010 <邀請組隊結果>  - dong y / tu choi / khong phan hoi
    S:013-013 <組隊訊息>      - LY DO khong lap duoc doi (1..8)
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402

TA = b"\xaa" * 8
LEADER = b"\xbb" * 8
BAN1, BAN2 = b"\xc1" * 8, b"\xc2" * 8
LA_LEADER, LA_MEM = b"\xd1" * 8, b"\xd2" * 8


def _goi(sub: int, than: bytes) -> bytes:
    n = len(than) + 9
    return bytes([0xC0, 0x91, n & 0xFF, n >> 8, 0, 0, 0x0D, sub, 0]) + than


def _nhom(leader: bytes, members) -> bytes:
    return leader + bytes([len(members)]) + b"".join(members)


def _bot(self_entity=TA, party_idx=7001):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.self_entity = self_entity
    c.party_idx = party_idx
    c.party_members = []
    c.party_leader = None
    c.auto_accept_party = True
    c.party_invite_ready = True
    c._pending_party_invites = {}
    c.entity_names = {}
    import types
    c.state = types.SimpleNamespace(my_atype=0, self_slot=None)
    return c


class TestRosterNhieuNhom(unittest.TestCase):
    def setUp(self):
        import bot.client as m
        m.reset_party_joined(7001)

    tearDown = setUp

    def test_party_minh_o_NHOM_THU_HAI_van_doc_duoc(self):
        """Day la ca lam party 15 ket 35 phut."""
        c = _bot()
        than = _nhom(LA_LEADER, [LA_LEADER, LA_MEM]) + _nhom(LEADER, [LEADER, TA, BAN1])
        c._on_party(_goi(0x06, than))
        self.assertEqual(c.party_leader, LEADER, "bo ca goi vi party minh khong o nhom dau")
        self.assertEqual(c.party_members, [LEADER, TA, BAN1])

    def test_party_minh_o_nhom_dau_van_dung(self):
        c = _bot()
        than = _nhom(LEADER, [LEADER, TA]) + _nhom(LA_LEADER, [LA_LEADER, LA_MEM])
        c._on_party(_goi(0x06, than))
        self.assertEqual(c.party_members, [LEADER, TA])

    def test_KHONG_lay_roster_cua_party_LA(self):
        c = _bot()
        than = _nhom(LA_LEADER, [LA_LEADER, LA_MEM])
        c._on_party(_goi(0x06, than))
        self.assertEqual(c.party_members, [], "ghi de roster bang party cua nguoi khac")

    def test_minh_LA_LEADER_o_nhom_sau(self):
        c = _bot(self_entity=LEADER)
        than = _nhom(LA_LEADER, [LA_LEADER, LA_MEM]) + _nhom(LEADER, [LEADER, TA, BAN1])
        c._on_party(_goi(0x06, than))
        self.assertEqual(c.party_leader, LEADER)
        self.assertEqual(len(c.party_members), 3)

    def test_goi_cut_khong_lam_sap(self):
        c = _bot()
        than = _nhom(LEADER, [LEADER, TA])[:-3]      # thieu byte giua chung
        c._on_party(_goi(0x06, than))                # khong duoc no


class TestGoiTruocDayBiDiec(unittest.TestCase):
    def setUp(self):
        import bot.client as m
        m.reset_party_joined(7001)

    tearDown = setUp

    def test_S013_005_nguoi_vao_doi(self):
        c = _bot()
        c.party_leader = LEADER
        c.party_members = [LEADER, TA]
        c._on_party(_goi(0x05, LEADER + BAN1))
        self.assertIn(BAN1, c.party_members, "bo qua goi bao NGUOI VAO DOI")

    def test_S013_005_cua_party_LA_thi_bo_qua(self):
        c = _bot()
        c.party_leader = LEADER
        c.party_members = [LEADER, TA]
        c._on_party(_goi(0x05, LA_LEADER + LA_MEM))
        self.assertEqual(c.party_members, [LEADER, TA])

    def test_S013_005_khong_them_TRUNG(self):
        c = _bot()
        c.party_leader = LEADER
        c.party_members = [LEADER, TA, BAN1]
        c._on_party(_goi(0x05, LEADER + BAN1))
        self.assertEqual(c.party_members.count(BAN1), 1)

    def test_co_bang_ma_ly_do_that_bai(self):
        """8 ma cua S:013-013 - ma 7/8 = dang trong nhom PHO BAN, ly do rat de gap voi bot."""
        self.assertEqual(GameClient.PARTY_MSG[7], "MINH dang trong nhom PHO BAN")
        self.assertEqual(GameClient.PARTY_MSG[8], "NGUOI KIA dang trong nhom PHO BAN")
        self.assertEqual(set(GameClient.PARTY_MSG), set(range(1, 9)))

    def test_co_bang_ket_qua_loi_moi(self):
        self.assertEqual(GameClient.PARTY_INVITE_RESULT,
                         {1: "DONG Y", 2: "TU CHOI", 3: "KHONG PHAN HOI"})

    def test_hai_goi_do_KHONG_lam_sap(self):
        c = _bot()
        c._on_party(_goi(0x0a, bytes([1, 4]) + "Abc".encode("utf-16-le")))
        c._on_party(_goi(0x0d, bytes([8])))
        c._on_party(_goi(0x0d, bytes([99])))     # ma la


if __name__ == "__main__":
    unittest.main()
