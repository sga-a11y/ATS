"""MEMBER TRONG PARTY TU DI THEO LEADER -> `pos` cua member lac, phai bam theo leader.

Client that lam client-side, KHONG co goi nao bao (Logic/Team.lua:176 `AddMember`):
    Role.players[roleId]:Teleport(leader.position);
    Role.players[roleId]:UpdateSpeed(leader.speed);

Va server KHONG echo lai lenh move cua chinh minh - da do bang so tren log 30/08:
184 goi `0x06` DA GUI, 0 goi `S:006-001` nhan ve mang entity cua chinh minh (45 goi nhan ve deu
la cua nguoi khac). Client that cung vay: `MoveController.SendMove` GUI toa do len, con
`Role.player.position` la bien LOCAL.

=> Khong co cach hoi vi tri. Nhung vi tri THAT cua member thi suy ra duoc: no bam theo leader, ma
client cua leader nam CUNG TIEN TRINH.

Hau qua khi khong lam:
  - laochin (party 3, 30/08 23:33) bao pos=(990,480) dung rally, combat=True lien tuc, trong khi
    3 member cung cho combat=False suot -> thuc te no o diem quai;
  - 4 acc party 6 gui move tu pos cu -> `di chuyen QUA XA (ma 14)` -> dut ket noi cung mot giay.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as CL  # noqa: E402
from bot.client import GameClient  # noqa: E402

CHU = b"\xaa" * 8
TOI = b"\x11" * 8


def _cli(entity, pos, map_id=23821, running=True):
    c = GameClient.__new__(GameClient)
    c._label = "test-" + entity.hex()[:4]
    c.self_entity = entity
    c.party_idx = 77
    c.party_leader = None
    c.party_members = []
    c.pos = pos
    c.current_map = map_id
    c.running = running
    c._position_generation = 0
    c._pos_valid_for_map = None
    c._cho_bam_leader = False
    return c


class TestTheoLeaderSuaPos(unittest.TestCase):
    def setUp(self):
        CL._PARTY_CLIENTS.pop(77, None)
        self.lead = _cli(CHU, (810, 990))
        self.mem = _cli(TOI, (2150, 1810))
        self.mem.party_leader = CHU
        self.mem.party_members = [CHU, TOI]
        self.mem._cho_bam_leader = True      # vua vao doi (Team.AddMember)
        CL._register_party_client(77, CHU, self.lead)
        CL._register_party_client(77, TOI, self.mem)

    def tearDown(self):
        CL._PARTY_CLIENTS.pop(77, None)

    def test_member_lay_vi_tri_LEADER(self):
        self.assertTrue(self.mem._theo_leader_sua_pos())
        self.assertEqual(self.mem.pos, (810, 990))

    def test_bao_cho_navigate_biet_pos_da_doi(self):
        gen = self.mem._position_generation
        self.mem._theo_leader_sua_pos()
        self.assertGreater(self.mem._position_generation, gen)
        self.assertEqual(self.mem._pos_valid_for_map, 23821)

    def test_CHI_bam_MOT_LAN_dung_luc_vao_doi(self):
        """Client teleport member toi cho leader DUNG MOT LAN, trong `AddMember` (Team.lua:176);
        sau do member tu di bang chan cua no. Bam moi lan `navigate_to` la DAP toa do THAT.

        Log 31/08 party 1 (15:17:06): 4 member vua qua cong toi (3970,1210) - toa do DUNG - bi ghi
        de thanh (1237,543) cua leader (lech 2800); goi ngay sau gui tu goc sai -> CA 4 dinh
        `SERVER NGAT KET NOI: ma la 47` cung mot giay.
        """
        self.assertTrue(self.mem._theo_leader_sua_pos())
        self.mem.pos = (3970, 1210)          # vd: tu qua cong, toa do nay la THAT
        self.assertFalse(self.mem._theo_leader_sua_pos(), "bam lan hai = dap toa do that")
        self.assertEqual(self.mem.pos, (3970, 1210))

    def test_CHUA_vao_doi_thi_KHONG_bam(self):
        self.mem._cho_bam_leader = False
        self.assertFalse(self.mem._theo_leader_sua_pos())
        self.assertEqual(self.mem.pos, (2150, 1810))

    def test_co_bat_khi_CHINH_MINH_vao_doi(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("vao doi (leader=%s) -> roster %d nguoi")
        self.assertGreater(i, 0)
        khoi = src[i:i + 900]
        self.assertIn("if _ai == self.self_entity and _ai != _lead:", khoi,
                      "bat co cho ca nguoi khac vao doi -> bam nham")
        self.assertIn("self._cho_bam_leader = True", khoi)

    def test_LECH_IT_thi_giu_nguyen(self):
        """Member di sau leader vai chuc don vi la binh thuong, dung giat toa do lien tuc."""
        self.mem.pos = (830, 1000)
        self.assertFalse(self.mem._theo_leader_sua_pos())
        self.assertEqual(self.mem.pos, (830, 1000))

    def test_LEADER_khong_tu_sua_theo_chinh_minh(self):
        self.lead.party_leader = CHU
        self.lead.party_members = [CHU, TOI]
        self.assertFalse(self.lead._theo_leader_sua_pos())
        self.assertEqual(self.lead.pos, (810, 990))

    def test_KHONG_o_party_thi_khong_dung_toi(self):
        self.mem.party_members = []
        self.assertFalse(self.mem._theo_leader_sua_pos())
        self.assertEqual(self.mem.pos, (2150, 1810))

    def test_leader_KHAC_MAP_thi_khong_lay(self):
        self.lead.current_map = 12001
        self.assertFalse(self.mem._theo_leader_sua_pos())

    def test_leader_da_tat_thi_khong_lay(self):
        self.lead.running = False
        self.assertFalse(self.mem._theo_leader_sua_pos())


class TestApVaoLuong(unittest.TestCase):
    def _doc(self, *p):
        with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
            return fh.read()

    def test_navigate_to_sua_pos_TRUOC_khi_tinh_duong(self):
        s = self._doc("bot", "client.py")
        i = s.find("def navigate_to(")
        than = s[i:i + 6000]
        i_sua = than.find("self._theo_leader_sua_pos()")
        i_path = than.find("_ground_store()")
        self.assertGreater(i_sua, 0, "khong sua pos -> smart path tinh tu diem xuat phat SAI")
        self.assertGreater(i_path, 0)
        self.assertLess(i_sua, i_path, "sua SAU khi tinh duong thi vo nghia")

    def test_kiem_da_ra_rally_cung_sua_pos(self):
        s = self._doc("run_party_digioi.py")
        for ten in ("def _da_toi():", "def _vi_sao_chua_san_sang("):
            i = s.find(ten)
            self.assertGreater(i, 0, ten)
            khoi = re.sub(r"#.*", "", s[i:i + 3400])
            self.assertIn("_theo_leader_sua_pos()", khoi,
                          "%s van doc pos cu -> ket luan 'da ra diem tap ket' oan" % ten)

    def test_KHONG_con_khang_dinh_server_echo_pos(self):
        """Da do: 184 goi gui / 0 goi nhan ve cua chinh minh."""
        s = self._doc("bot", "client.py")
        self.assertNotIn("VI TRI THAT do SERVER cap", s)
        i = s.find("def _theo_leader_sua_pos(")
        self.assertGreater(i, 0)


if __name__ == "__main__":
    unittest.main()
