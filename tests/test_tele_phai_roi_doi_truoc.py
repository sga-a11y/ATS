"""TELE PHAI THOAT TO DOI TRUOC - y het client game.

`_lua_dec/UI/UITeleport.lua:673` chan tele o BA dieu kien, va client KHONG gui goi nao khi dinh:

    function UITeleport.CheckTeleport()
      if Role.player.war ~= EWar.None then ... return true; end        -- dang danh
      if SceneManager.sceneId == 10701 then ... return true; end       -- scene cam
      if not Team.IsAlone(Role.playerId) then ... return true; end     -- DANG TO DOI
      return false;
    end

Bot cheo hai dieu dau (state.in_battle + cac guard instance/Di Gioi/pho ban) nhung THIEU cai thu
ba, nen no gui MU. Server im lang bo qua -> vong `go_to_town` ban lai moi 2s toi het deadline.

Ca that 07/09 [dieumot] - cung mot acc, cung mot thanh, khac moi chuyen da roi doi hay chua:
    00:04:21  Roi/giai tan party cu
    00:04:21  Teleport -> city 12001
    00:04:25  Da ve thanh 12001               <-- 4 giay, 2 goi
    00:04:53  PARTY: goi 0x0d sub=11          <-- da lai vao to doi
    00:05:05  Ve thanh 12001 ...
    00:05:05..00:05:43  Teleport -> city 12001  x19 goi
    00:05:45  Da ve thanh 12001               <-- 40 giay
Ca log: 4758 goi teleport, phan lon la ban lai -> chinh la nguon spam sinh `ma 13`.

Roi doi dat trong `teleport()` chu KHONG phai `go_to_town()`: co nhieu duong goi tele
(`pre_route_town_hop`, route train, NPC40, mua HP/SP...), dat o ham cuoi cung thi khong sot duong
nao. Mat nguoi thi dieu phoi gom lai - dung L0.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _than(ten, *p):
    s = _src(*(p or ("bot", "client.py")))
    i = s.find("    def %s(" % ten)
    assert i > 0, ten
    j = s.find(os.linesep.join(["", "    def "]), i + 10)
    if j < 0:
        j = s.find("\n    def ", i + 10)
    return s[i:j if j > 0 else len(s)]


class _Gia:
    """Ban sao toi thieu cua GameClient cho ham teleport()."""

    _label = "gia"

    def __init__(self, members):
        self.party_members = list(members)
        self.da_roi_doi = 0
        self.da_gui = []
        self._self_map_change_at = 0.0

    def leave_party(self):
        self.da_roi_doi += 1
        self.party_members = []

    def send(self, opcode, payload):
        self.da_gui.append((opcode, payload, self.da_roi_doi))


def _chay_teleport(c, city, flag=0):
    from bot import client as C
    return C.GameClient.teleport(c, city, flag)


class TestRoiDoiTruocKhiTele(unittest.TestCase):
    def test_dang_to_doi_thi_ROI_DOI_roi_moi_gui(self):
        c = _Gia([b"\x01\x02\x03\x04", b"\x05\x06\x07\x08"])
        self.assertTrue(_chay_teleport(c, 12001, 0))
        self.assertEqual(c.da_roi_doi, 1, "gui tele ma khong roi doi -> server bo qua")
        self.assertEqual(len(c.da_gui), 1)
        self.assertEqual(c.da_gui[0][2], 1, "roi doi phai xay ra TRUOC khi gui goi tele")

    def test_khong_o_doi_thi_KHONG_goi_roi_doi(self):
        """Roi doi mu la gui goi thua, va `leave_party` khi roster rong con tu log canh bao."""
        c = _Gia([])
        self.assertTrue(_chay_teleport(c, 12001, 0))
        self.assertEqual(c.da_roi_doi, 0)
        self.assertEqual(len(c.da_gui), 1)

    def test_roi_doi_loi_thi_VAN_tele(self):
        """Khong duoc de mot ngoai le cua leave_party nuot luon lenh ve thanh."""
        c = _Gia([b"\x01\x02\x03\x04"])
        c.leave_party = lambda: (_ for _ in ()).throw(RuntimeError("dut ket noi"))
        self.assertTrue(_chay_teleport(c, 12001, 0))
        self.assertEqual(len(c.da_gui), 1)


class TestDatDungCho(unittest.TestCase):
    def test_o_teleport_chu_khong_phai_go_to_town(self):
        """Co nhieu duong goi tele; dat o `go_to_town` la sot cac duong con lai."""
        t = _than("teleport")
        self.assertIn("leave_party()", t, "chua roi doi trong teleport()")
        i = t.find("leave_party()")
        j = t.find("self.send(")
        self.assertGreater(j, 0)
        self.assertLess(i, j, "roi doi phai dung TRUOC khi gui goi tele")

    def test_van_giu_cac_guard_cu_cua_go_to_town(self):
        """Cac guard nay tung sinh ra tu ca hong that (pho ban to doi / Di Gioi / instance) -
        bo di la spam tele quay lai."""
        g = _than("go_to_town")
        for m in ("_team_dungeon_until", "in_di_gioi()", "in_instance_map("):
            self.assertIn(m, g, m)


if __name__ == "__main__":
    unittest.main()
