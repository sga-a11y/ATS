"""`S:007-002` ma 3 <組隊不可換分區> = SERVER TU NOI minh dang o party -> phai roi that.

Luat "khong co bang chung thi KHONG gui 013-004" la dung va phai giu (gui mu vao party minh khong
o lam server NGUNG gui loi moi cua party do toi minh). Nhung ma 3 KHONG PHAI la doan mu: chinh
server vua khang dinh. Do la bang chung manh hon ca roster - roster chi la thu bot tu nho.

Khong co lenh hoi roster (`protocal.lua` chi co C:013-001/003/004/005/006/007/008/009/010/015),
nen doi truong phai doan la CHINH MINH: leader thi `members[minh] == minh`, con member ma roster
rong thi day la party MA - gui gi cung khong lam hong them.

Log 31/08 party 7 (14:45-14:55): ttsau bi ma 3, moi lan deu
    Doi kenh N bi TU CHOI: DANG TO DOI (ma 3) -> roi party roi thu lai
    KHONG o party nao (roster server + local deu rong) -> KHONG gui 013-004
lap 67 luot, quet het kenh 2,3,4,... khong bao gio doi duoc kenh -> party khong gom lai duoc.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402

TOI = b"\x11" * 8


def _bot():
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.self_entity = TOI
    c.party_idx = 0
    c.party_leader = None
    c.party_members = []
    c.team_of = {}
    c.team_of_at = 0.0
    c.da_gui = []
    c.send = lambda op, body: c.da_gui.append((op, body))
    return c


class TestMa3ThiTinServer(unittest.TestCase):
    def test_roster_rong_MA_server_bao_ma3_thi_VAN_GUI(self):
        c = _bot()
        c.leave_party(server_bao_dang_o_party=True)
        self.assertEqual(len(c.da_gui), 1, "server bao dang to doi ma van khong gui -> ket vong lap")
        _op, body = c.da_gui[0]
        self.assertEqual(body[:2], b"\x04\x00")
        self.assertEqual(body[2:], TOI, "khong biet doi truong -> gui ID cua chinh minh")

    def test_roster_rong_va_KHONG_co_ma3_thi_VAN_KHONG_GUI(self):
        """Luat cu phai con nguyen: gui mu la server ngung gui loi moi toi minh."""
        c = _bot()
        c.leave_party()
        self.assertEqual(c.da_gui, [], "gui mu khi khong co bang chung nao")

    def test_CHI_gui_MOT_goi(self):
        c = _bot()
        c.leave_party(server_bao_dang_o_party=True)
        self.assertEqual(len(c.da_gui), 1, "client khong bao gio gui hai goi 013-004")

    def test_nhanh_ma3_cua_switch_channel_co_bat_co(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("DANG TO DOI (ma 3) -> roi party roi thu lai")
        self.assertGreater(i, 0)
        self.assertIn("self.leave_party(server_bao_dang_o_party=True)", s[i:i + 400],
                      "nhanh ma 3 khong bat co -> van bi guard chan, quet kenh vo han")




class TestMa3ThiDungQuetKenh(unittest.TestCase):
    """Ma 3 la loi PARTY, khong dinh gi toi kenh -> kenh nao cung tra dung ma 3.

    `pick_best_channel` coi "khong doi duoc kenh N" la "thu kenh khac", nen mot lan bi ma 3 la no
    dot het danh sach kenh, moi kenh 2 luot ack. Party 7 (31/08 14:45-14:55): quet kenh 2,3,4,...
    67 luot trong 10 phut, khong bao gio thoat.
    """

    def _src(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            return fh.read()

    def test_dung_quet_khi_gap_ma_3(self):
        s = self._src()
        i = s.find("def pick_best_channel(")
        self.assertGreater(i, 0)
        than = s[i:s.find("\n    def ", i + 10)]
        i_thu = than.find("if self.switch_channel(best[0]):")
        self.assertGreater(i_thu, 0)
        khoi = than[i_thu:i_thu + 900]
        self.assertIn('getattr(self, "_chan_switch_result", None) == 3', khoi,
                      "khong phan biet ma 3 -> quet het kenh mot cach vo ich")
        i_ma3 = khoi.find('== 3')
        i_khac = khoi.find("thu kenh khac neu co")
        self.assertLess(i_ma3, i_khac, "kiem ma 3 phai TRUOC nhanh 'thu kenh khac'")

    def test_tra_None_de_caller_thu_lai_sau(self):
        s = self._src()
        i = s.find("def pick_best_channel(")
        than = s[i:s.find("\n    def ", i + 10)]
        i_ma3 = than.find('getattr(self, "_chan_switch_result", None) == 3')
        khoi = than[i_ma3:i_ma3 + 800]
        self.assertIn("return None", khoi,
                      "tra 0 la 'ca party da cung kenh' - sai han y nghia, party se khong dong bo")
    def test_bao_CA_PARTY_roi_party_chu_khong_de_leader_tu_xoay(self):
        """Party la cua CA LU: con acc nao trong doi thi server van coi leader la dang to doi.
        Leader tu roi roi thu lai khong go duoc - phai bao ca party cung roi + dong bo kenh."""
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find('if r is None and getattr(c, "_chan_switch_result", None) == 3:')
        self.assertGreater(i, 0, "picker khong he phan biet ma 3 -> cho vong sau mai")
        khoi = s[i:i + 1200]
        self.assertIn("_bump_reform(st)", khoi,
                      "khong bao ca party thi chi minh leader roi - server van chan")
        self.assertIn("return False", khoi, "phai thoat vong sync de di theo reform gen moi")
        i_thuong = s.find("if r is None:   # co kenh nhung khong kenh nao du cho ca party")
        self.assertGreater(i_thuong, i, "nhanh ma 3 phai kiem TRUOC nhanh 'cho kenh trong'")


if __name__ == "__main__":
    unittest.main()
