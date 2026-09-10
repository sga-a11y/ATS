"""ACC KHAC DANG CHI VAO MINH = co that mot party dang song -> phai giai tan duoc.

`leave_party()` chi gui `C:013-004` khi co BANG CHUNG dang o party. Ba bang chung cu deu doc tu
SO CUA RIENG MINH (roster server con tuoi / roster local / server vua bao "dang to doi"). Nhung bot
dieu khien CA PARTY trong MOT tien trinh, nen roster cua BON KIA cung la du lieu cua bot - va mot
acc noi "toi o party cua X" la bang chung co that mot party dang song voi X lam doi truong.

Ca that 08/09 party 2 (user: "p2, sao ko moi vao pt dc") - 14 phut, 7 vong, khong lan nao vao duoc:

    16:34:22 [gaha] PARTY: e6a1d6f8 vao doi (leader=b59fd6f8) -> roster 1 nguoi
    16:36:36 [gaha] (member) roster SERVER noi minh DA o party cua LEADER b59fd6f8
    16:48:17 [gamo] KHONG o party nao (roster server + local deu rong) -> KHONG gui 013-004
    16:49:38 [gamo] (LEADER) moi 4 member ... | da join=0 | roster server=0 nguoi

`b59fd6f8` CHINH LA `gamo`. Bon member deu o party do no lam doi truong, con no thi tin so nho rong
cua minh va TU CHOI giai tan -> party MA giu cham 4 nguoi, va server khong gui loi moi toi nguoi da
co doi nen `gamo` moi mai vo ich.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as client_module          # noqa: E402
from bot.client import GameClient           # noqa: E402


def _gia(label, ent, party_idx=2):
    c = GameClient.__new__(GameClient)
    c._label = label
    c.party_idx = party_idx
    c.self_entity = ent
    c.running = True
    c.party_members = []
    c.party_leader = None
    c.da_gui = []
    c.send = lambda op, pl: c.da_gui.append((op, pl))
    c._doi_truong_dang_ket = lambda: None       # roster SERVER rong
    return c


class TestRosterChiDoiTheoSERVER(unittest.TestCase):
    """Roster chi doi khi SERVER bao - y het client (`protocal.lua:1694`):

        protocolTable[13][4] = function(data)      -- S:013-004 <玩家離開隊伍>
          local roleId = data:ReadInt64();
          Team.RemoveMember(roleId);

    Bot truoc day lam NGUOC ca hai dau: gui `C:013-004` xong XOA SO NGAY (khong cho xac nhan), con
    khi NHAN `S:013-004` thi chi lay toa do, khong xoa ai. Do la cho de ra "party ma" - thu bot TU
    BIA (user 08/09: "cai party ma nay la bot tu bia ra day chu, game client thi member thoat het
    hoac leader giai tan la pt giai tan roi").
    """

    LEADER = b"\xb5\x9f\xd6\xf8\x80\x8d\x00\x00"
    MINH = b"\x11" * 8
    KHAC = b"\x22" * 8

    def _c(self):
        c = _gia("gia", self.MINH)
        c.party_leader = self.LEADER
        c.party_members = [self.LEADER, self.KHAC]
        c.party_idx = 2
        c._label = "gia"
        c.pos = (500, 600)                  # `_on_party` sub04 resync toa do
        c._position_generation = 0
        c._pos_valid_for_map = None
        c.current_map = 23001
        return c

    def _goi(self, ai):
        # `_on_party` doc `sub = pkt[7]`; ID o pkt[9:17], roi X/Y 2B moi cai
        return bytes(7) + b"\x04\x00" + ai + (500).to_bytes(2, "little") + (600).to_bytes(2, "little")

    def _nhan(self, c, ai):
        GameClient._on_party(c, self._goi(ai))

    def test_GUI_lenh_KHONG_tu_xoa_roster(self):
        c = self._c()
        c._doi_truong_dang_ket = lambda: self.LEADER
        GameClient.leave_party(c)
        self.assertEqual(len(c.da_gui), 1, "phai gui 013-004")
        self.assertTrue(c.party_members, "tu xoa roster luc GUI -> tu lam mu minh, de ra party ma")

    def test_nhan_S013_004_CHINH_MINH_thi_roster_rong(self):
        c = self._c()
        self._nhan(c, self.MINH)
        self.assertEqual(c.party_members, [])
        self.assertIsNone(c.party_leader)

    def test_nhan_S013_004_NGUOI_KHAC_thi_chi_bo_nguoi_do(self):
        c = self._c()
        self._nhan(c, self.KHAC)
        self.assertEqual(c.party_members, [self.LEADER])

    def test_DOI_TRUONG_roi_thi_doi_GIAI_TAN(self):
        """Luat game: leader giai tan thi party tan."""
        c = self._c()
        self._nhan(c, self.LEADER)
        self.assertEqual(c.party_members, [])
        self.assertIsNone(c.party_leader)

    def test_nguoi_ngoai_doi_khong_lam_gi(self):
        c = self._c()
        self._nhan(c, b"\x99" * 8)
        self.assertEqual(c.party_members, [self.LEADER, self.KHAC])


class TestGiaiTanPartyMa(unittest.TestCase):
    LEADER = b"\xb5\x9f\xd6\xf8\x80\x8d\x00\x00"
    MEMBER = b"\xe6\xa1\xd6\xf8\x80\x8d\x00\x00"

    def setUp(self):
        client_module._PARTY_CLIENTS.clear()

    def tearDown(self):
        client_module._PARTY_CLIENTS.clear()

    def _dat(self, *cs):
        with client_module._PARTY_LOCK:
            client_module._PARTY_CLIENTS[2] = {c._label: c for c in cs}

    def test_member_chi_vao_minh_thi_GUI_013_004(self):
        lead = _gia("gamo", self.LEADER)
        mem = _gia("gaha", self.MEMBER)
        mem.party_leader = self.LEADER          # member noi: doi truong cua toi la gamo
        self._dat(lead, mem)
        GameClient.leave_party(lead)
        self.assertEqual(len(lead.da_gui), 1, "van tu choi giai tan -> party ma giu cham member")
        op, pl = lead.da_gui[0]
        self.assertEqual(pl, b"\x04\x00" + self.LEADER)

    def test_KHONG_ai_chi_vao_minh_thi_van_KHONG_gui(self):
        """Gui mu la server ngung gui loi moi toi minh - giu nguyen hanh vi cu."""
        lead = _gia("gamo", self.LEADER)
        mem = _gia("gaha", self.MEMBER)
        mem.party_leader = b"\x99" * 8          # o party cua NGUOI KHAC
        self._dat(lead, mem)
        GameClient.leave_party(lead)
        self.assertEqual(lead.da_gui, [])

    def test_acc_DA_TAT_thi_khong_tinh(self):
        lead = _gia("gamo", self.LEADER)
        mem = _gia("gaha", self.MEMBER)
        mem.party_leader = self.LEADER
        mem.running = False
        self._dat(lead, mem)
        GameClient.leave_party(lead)
        self.assertEqual(lead.da_gui, [])

    def test_khong_tu_chi_vao_chinh_minh(self):
        """`party_leader` cua chinh minh tro toi minh (party 1 nguoi) khong phai bang chung."""
        lead = _gia("gamo", self.LEADER)
        lead.party_leader = self.LEADER
        self._dat(lead)
        GameClient.leave_party(lead)
        self.assertEqual(lead.da_gui, [])

    def test_ba_bang_chung_cu_van_chay_TRUOC(self):
        """Bang chung moi chi la duong lui - roster that van uu tien."""
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("_chu = self._doi_truong_dang_ket()")
        j = s.find("ACC KHAC TRONG CUNG PARTY DANG CHI VAO MINH", i)
        self.assertGreater(j, i, "bang chung moi dat truoc roster server")
        for m in ("self.party_members", "server_bao_dang_o_party"):
            self.assertIn(m, s[i:j], m)


if __name__ == "__main__":
    unittest.main()
