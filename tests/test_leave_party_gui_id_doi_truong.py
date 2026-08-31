"""`C:013-004 <離開隊伍>`: KHONG o party thi KHONG DUOC GUI; co o thi gui ID **ĐỘI TRƯỞNG**.

Client (Logic/Team.lua:138):
    function Team.Leave()
      if this.members[Role.playerId] == nil then return end   -- KHONG o party -> KHONG gui
      sendBuffer:WriteInt64(this.members[Role.playerId]);     -- members[minh] = leaderId
      Network.Send(13, 4, sendBuffer);
    end

Bot tung sai HAI lan o day:
  1. gui `self_entity` thay vi ID doi truong (leader tinh co dung vi self == leader);
  2. gui MU luc roster local RONG (nhanh "don party ma") - NGUOC HAN dong guard cua client -
     va con gui THEM goi thu hai kem ID cua minh, cai client khong bao gio lam.

Ban 013-004 mu vao party MINH KHONG O lam server NGUNG gui loi moi cua party do toi minh.
Tuong quan 3/3 party trong log 30/08, khong sai mot truong hop nao:
    party 3  16:55  baybay + hoathap GUI leave -> khong vao noi; laochin + batbat khong gui -> vao ngay
    party 11 15:50  luu0077/0101/008 GUI leave -> khong vao noi; luuchin khong gui -> vao CA 5 vong
    party 2  15:17  nasau            GUI leave -> khong vao noi; 3 dua con lai       -> vao binh thuong
Dua DUY NHAT khong gui goi nay luon la dua DUY NHAT vao duoc doi.
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
CHU = b"\x22" * 8


def _bot(self_entity=TOI, party_leader=None, party_members=None, team_of=None):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.self_entity = self_entity
    c.party_leader = party_leader
    c.party_members = list(party_members or [])
    c.team_of = dict(team_of or {})
    c.team_of_at = time.time() if team_of else 0.0
    c.gui = []
    c.send = lambda op, body: c.gui.append((op, bytes(body)))
    return c


class TestKhongOPartyThiKhongGui(unittest.TestCase):
    """Dong guard cua client. Gui mu = tu bit duong nhan loi moi cua chinh party do."""

    def test_roster_server_va_local_deu_rong_thi_IM(self):
        c = _bot(party_leader=CHU, party_members=[])
        c.leave_party()
        self.assertEqual(c.gui, [], "gui mu -> server ngung gui loi moi toi minh")

    def test_caller_doan_doi_truong_ma_CHUA_TUNG_thay_roster_thi_IM(self):
        """Nhanh 'don party ma': caller chi doan doi truong party minh MUON vao."""
        c = _bot(party_leader=None, party_members=[])
        c.leave_party(leader_entity=CHU)
        self.assertEqual(c.gui, [])

    def test_khong_biet_gi_thi_IM(self):
        c = _bot()
        c.leave_party()
        self.assertEqual(c.gui, [])

    def test_van_XOA_roster_local_du_khong_gui(self):
        c = _bot(party_leader=CHU, party_members=[])
        c.leave_party()
        self.assertEqual(c.party_members, [])


class TestCoOPartyThiGuiDung(unittest.TestCase):
    def test_MEMBER_gui_ID_DOI_TRUONG(self):
        c = _bot(party_leader=CHU, party_members=[CHU, TOI])
        c.leave_party()
        self.assertEqual(c.gui, [(protocol.OP_PLAYER_STATE, b"\x04\x00" + CHU)])

    def test_CHI_MOT_goi(self):
        """Client chi gui mot goi; goi thu hai kem ID cua minh la bot tu bia ra."""
        c = _bot(party_leader=CHU, party_members=[CHU, TOI])
        c.leave_party()
        self.assertEqual(len(c.gui), 1)

    def test_LEADER_van_giai_tan_duoc(self):
        c = _bot(self_entity=CHU, party_leader=CHU, party_members=[CHU, TOI])
        c.leave_party()
        self.assertEqual(c.gui, [(protocol.OP_PLAYER_STATE, b"\x04\x00" + CHU)])

    def test_ROSTER_SERVER_thang_caller_doan(self):
        """Ket trong party LA: caller doan doi truong party minh MUON vao -> sai truong."""
        c = _bot(team_of={TOI: CHU})
        c.leave_party(leader_entity=b"\x99" * 8)
        self.assertEqual(c.gui[0][1][2:], CHU)

    def test_roster_server_CU_thi_khong_tin(self):
        c = _bot(team_of={TOI: CHU})
        c.team_of_at = time.time() - (GameClient.TEAM_OF_MAX_AGE + 5)
        c.leave_party()
        self.assertEqual(c.gui, [], "roster cu ma van gui = gui mu")

    def test_caller_doan_duoc_dung_khi_DA_tung_thay_roster(self):
        """Da tung nhan roster (party_leader) = co that mot party dinh toi minh."""
        c = _bot(party_leader=b"\x99" * 8, party_members=[])
        c.leave_party(leader_entity=CHU)
        self.assertEqual(c.gui[0][1][2:], CHU)

    def test_KHONG_xoa_party_leader(self):
        c = _bot(party_leader=CHU, party_members=[CHU, TOI])
        c.leave_party()
        self.assertEqual(c.party_leader, CHU)

    def test_chua_co_entity_thi_khong_gui(self):
        c = _bot(self_entity=None, party_members=[CHU])
        c.leave_party()
        self.assertEqual(c.gui, [])


if __name__ == "__main__":
    unittest.main()
