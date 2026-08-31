"""Doc `S:013-006` cho CA CAC PARTY KHAC -> biet minh dang ket trong party NAO.

Client Lua (Logic/Team.lua):
    protocolTable[13][6] -> AddMember(leaderId, roleId) cho MOI nhom trong goi
    AddMember: `this.members[roleId] = leaderId`          -- ban do entity -> doi truong
    Team.Leave: `sendBuffer:WriteInt64(this.members[Role.playerId])`   -- doi truong party MINH O
    Team.Invite: chi gui `C:013-007 邀請組隊` khi `IsAlone(roleId)`;
                 nguoi da o party -> gui `C:013-001 要求組隊` (KHONG phai 007)

Bot truoc day `break` ngay khi thay nhom cua minh -> vut het cac nhom khac -> khong biet:
  - MINH dang ket trong party cua ai  -> gui 013-004 kem ID doi truong DOAN (party minh muon
    vao) -> sai truong -> server bo qua -> ket vinh vien.
  - NGUOI KIA da o party chua -> cu ban 013-007 vao ho -> server nuot im lang, KHONG ma loi.

Party 2 (30/08 15:16-15:23): nasau f4d0d7f8 cung map 21851, cung kenh 3 (co ack 0x07 hai ben),
leader sga001 moi lai moi 5 giay suot 6 phut, `da join=3 | roster server=3`, khong mot ma tu
choi nao. Kenh/map deu dung -> khong phai loi dong bo kenh.
"""
from __future__ import annotations

import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402
from bot import protocol  # noqa: E402

TOI = b"\x11" * 8
CHU_A = b"\xaa" * 8      # doi truong party LA (minh dang ket trong day)
CHU_B = b"\xbb" * 8      # doi truong party minh MUON vao
NGUOI = b"\xcc" * 8


def _bot(self_entity=TOI):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.self_entity = self_entity
    c.party_idx = 0
    c.party_leader = None
    c.party_members = []
    c.team_of = {}
    c.team_of_at = 0.0
    c.state = type("S", (), {"my_atype": 0, "self_slot": 0})()
    c.gui = []
    c.send = lambda op, body: c.gui.append((op, bytes(body)))
    return c


def _goi_roster(*nhom):
    """0x0d sub=06: << [leader 8B][count 1B][member 8B]*count >>"""
    body = b"\x0d" + b"\x06\x00"      # [opcode 0x0d][sub 06 00] -> leader bat dau o offset 9
    for lead, mems in nhom:
        body += lead + bytes([len(mems)]) + b"".join(mems)
    return b"\xc0\x91" + (len(body) + 6).to_bytes(2, "little") + b"\x00\x00" + body


class TestDocMoiNhom(unittest.TestCase):
    def test_ghi_ca_nhom_KHONG_co_minh(self):
        c = _bot()
        c._on_party(_goi_roster((CHU_B, [NGUOI]), (CHU_A, [TOI])))
        self.assertEqual(c.team_of.get(NGUOI), CHU_B, "vut mat nhom cua nguoi khac")
        self.assertEqual(c.team_of.get(TOI), CHU_A)

    def test_nhom_cua_minh_o_CUOI_goi_van_doc_duoc(self):
        c = _bot()
        c._on_party(_goi_roster((CHU_B, [NGUOI]), (CHU_A, [TOI])))
        self.assertEqual(c.party_leader, CHU_A)
        self.assertEqual(c.party_members, [TOI])

    def test_doi_truong_cung_duoc_ghi(self):
        c = _bot()
        c._on_party(_goi_roster((CHU_A, [TOI])))
        self.assertEqual(c.team_of.get(CHU_A), CHU_A)


class TestBietMinhKetODau(unittest.TestCase):
    def test_tra_ID_doi_truong_party_dang_o(self):
        c = _bot()
        c._on_party(_goi_roster((CHU_A, [TOI])))
        self.assertEqual(c._doi_truong_dang_ket(), CHU_A)

    def test_roster_QUA_CU_thi_khong_tin(self):
        """S:013-006 phat lien tuc theo map; roster cu = da roi map/kenh do tu lau."""
        c = _bot()
        c._on_party(_goi_roster((CHU_A, [TOI])))
        c.team_of_at = time.time() - (GameClient.TEAM_OF_MAX_AGE + 5)
        self.assertIsNone(c._doi_truong_dang_ket())

    def test_chua_co_roster_thi_None(self):
        self.assertIsNone(_bot()._doi_truong_dang_ket())


class TestLeavePartyGuiDungParty(unittest.TestCase):
    def test_ROSTER_thang_caller_doan(self):
        """Day la ca ket that: caller doan doi truong party minh MUON vao (CHU_B)."""
        c = _bot()
        c._on_party(_goi_roster((CHU_A, [TOI])))
        c.leave_party(leader_entity=CHU_B)
        self.assertEqual(c.gui[0], (protocol.OP_PLAYER_STATE, b"\x04\x00" + CHU_A),
                         "van gui ID party minh MUON vao -> server bo qua -> ket vinh vien")

    def test_khong_co_roster_nao_thi_KHONG_GUI(self):
        """Xem `test_leave_party_gui_id_doi_truong`: gui mu = server ngung gui loi moi toi minh."""
        c = _bot()
        c.leave_party(leader_entity=CHU_B)
        self.assertEqual(c.gui, [])

    def test_da_tung_thay_roster_thi_dung_caller(self):
        c = _bot()
        c.party_leader = b"\x99" * 8
        c.leave_party(leader_entity=CHU_B)
        self.assertEqual(c.gui[0][1][2:], CHU_B)

    def test_doi_truong_party_MOT_MINH_van_gui_ID_minh(self):
        c = _bot()
        c._on_party(_goi_roster((TOI, [TOI])))
        c.leave_party()
        self.assertEqual(c.gui[0][1][2:], TOI)


class TestNhanRaNguoiDangOPartyKhac(unittest.TestCase):
    def test_nguoi_o_party_khac(self):
        c = _bot()
        c._on_party(_goi_roster((CHU_B, [NGUOI]), (CHU_A, [TOI])))
        self.assertEqual(c.dang_o_party_khac(NGUOI), CHU_B)

    def test_nguoi_CUNG_party_thi_khong_tinh(self):
        c = _bot()
        c._on_party(_goi_roster((CHU_A, [TOI, NGUOI])))
        self.assertIsNone(c.dang_o_party_khac(NGUOI))

    def test_nguoi_chua_o_party_nao(self):
        c = _bot()
        c._on_party(_goi_roster((CHU_A, [TOI])))
        self.assertIsNone(c.dang_o_party_khac(NGUOI))

    def test_roster_cu_thi_khong_ket_luan(self):
        c = _bot()
        c._on_party(_goi_roster((CHU_B, [NGUOI]), (CHU_A, [TOI])))
        c.team_of_at = time.time() - (GameClient.TEAM_OF_MAX_AGE + 5)
        self.assertIsNone(c.dang_o_party_khac(NGUOI))


class TestMemberTuGo(unittest.TestCase):
    def test_retry_doc_roster_server_chu_khong_chi_local(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("elif not is_joined(pidx, c.self_entity):")
        self.assertGreater(i, 0)
        khoi = s[i:i + 2600]
        self.assertIn("_doi_truong_dang_ket()", khoi,
                      "chi tin party_members local -> ket ma van tuong minh dang ranh")
        i_ket = khoi.find("_ket_party_la or not getattr(c,")
        self.assertGreater(i_ket, 0, "roster server phai MO them duong go, khong bi local chan")


if __name__ == "__main__":
    unittest.main()
