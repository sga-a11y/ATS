# -*- coding: utf-8 -*-
"""TAO PHONG PB: phai DOC `S:047-002` roi hay moi member.

`S:047-002 <創建房間結果> +結果(1)` ve cho LEADER (`Dungeon.ReciveCreateDungeon`,
`_lua_dec/Logic/Dungeon.lua:460`). Ma != 0 thi client goi `ClearRoomData()` - PHONG KHONG TON TAI.
Bang ma (client `:463`): 0 thanh cong · 1 khong co ma pho ban · 2 khong du cap · 3 dang o trong
phong PB roi · 4 het luot · 5 khong duoc to doi · 6 phong day · 7 het cho.

Bot bo qua goi nay toi 22/09: ban `0x2f 0100` + `0x2f 0200`, `sleep(1.0)`, roi MOI LUON. Tao hong
=> moi vao phong KHONG TON TAI => cho du 40 giay => `SERVER moi cong nhan 0/4` => huy => lam lai,
vinh vien.

Ca that 22/09 party 50 (user: "lap pt roi dung o Ng Thanh"), lv110:
    22:37:59 (LEADER) === PHO BAN TO DOI LV110: tao + moi 4 member ===
    22:38:01 (LEADER) phong PB: moi 4 member theo entity:
             ['a65d1be6:dakhai:12061/k1', 'a95d1be6:daknam:12061/k1',
              'a75d1be6:dakba:12061/k1', 'a85d1be6:dakbon:12061/k1']
    22:38:45 (LEADER) lv110 member ready 0/4 sau 40.1s -> HUY phong, relogin ca party
Entity DUNG HET - dung map, dung kenh, client con song, da thay tan mat - ma phia member KHONG
MOT DONG nao. Party 21 (19:56 -> 20:02+, lv20) y het.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


def _than(s, dau):
    i = s.find(dau)
    assert i > 0, "mat %r" % dau
    return s[i:s.find("\n    def ", i + 10)]


class TestDocGoiKetQuaTaoPhong(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_CO_xu_ly_sub_0x02(self):
        than = _than(self.src, "def _on_dungeon(")
        self.assertIn("sub == 0x02", than, "khong doc S:047-002 -> khong biet phong co tao duoc khong")

    def test_ma_loi_ghi_DU_theo_client(self):
        """Thieu mot ma la lan sau lai phai mo nguoc client de tra."""
        than = _than(self.src, "def _on_dungeon(")
        for _s in ("無此副本編號", "等級不符", "已在副本房間中", "次數用盡",
                   "不可組隊", "人數已滿", "暫無可用空間"):
            self.assertIn(_s, than, "thieu ma loi %s" % _s)

    def test_ma_KHAC_0_thi_log_CANH_BAO(self):
        than = _than(self.src, "def _on_dungeon(")
        self.assertIn("TAO PHONG HONG", than)


class TestChoKetQuaRoiMoiMoi(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_co_ham_cho_rieng(self):
        self.assertIn("def _cho_tao_phong_pb(", self.src)

    def test_CA_HAI_duong_tao_phong_deu_cho(self):
        """lv20 co duong rieng (`_do_team_dungeon_lv20_inner`), lv50/80/110 dung
        `_create_team_dungeon_room` - sot mot duong la duong do van dot 40s moi vong."""
        for _dau in ("def _do_team_dungeon_lv20_inner(", "def _create_team_dungeon_room("):
            than = _than(self.src, _dau)
            self.assertIn("_cho_tao_phong_pb(", than, "%s khong cho ket qua tao phong" % _dau)
            i_cho = than.find("_cho_tao_phong_pb(")
            i_moi = than.find("_invite_team_dungeon_participants(")
            self.assertGreater(i_moi, 0)
            self.assertLess(i_cho, i_moi, "%s moi member TRUOC khi biet phong co tao duoc khong" % _dau)

    def test_xoa_ket_qua_CU_truoc_khi_gui(self):
        """Khong xoa thi doc phai ket qua cua luot truoc -> ket luan sai ca hai chieu."""
        for _dau in ("def _do_team_dungeon_lv20_inner(", "def _create_team_dungeon_room("):
            than = _than(self.src, _dau)
            i_xoa = than.find("self._pb_tao_phong_kq = None")
            i_gui = than.find('self.send(0x2f, b"\\x02\\x00"')
            if i_gui < 0:
                i_gui = than.find('self.send(0x2f, bytes.fromhex("0200010001"))')
            self.assertGreater(i_xoa, 0, "%s khong xoa ket qua cu" % _dau)
            self.assertLess(i_xoa, i_gui, "%s xoa SAU khi gui -> nuot mat ket qua" % _dau)

    def test_SERVER_IM_LANG_thi_VAN_MOI(self):
        """KNOWLEDGE.md muc 7: coi "khong tra loi" la "hong" da tung treo ca dong bo kenh (30/08).
        Khong bien mot phep do moi thanh cua chan."""
        than = _than(self.src, "def _cho_tao_phong_pb(")
        i_none = than.find("if _kq is None:")
        self.assertGreater(i_none, 0, "khong xu ly truong hop server im lang")
        self.assertIn("return True", than[i_none:i_none + 400],
                      "server im lang ma coi la hong -> chan het PB")

    def test_ma_khac_0_thi_BO_VONG(self):
        than = _than(self.src, "def _cho_tao_phong_pb(")
        i = than.find("if _kq != 0:")
        self.assertGreater(i, 0)
        self.assertIn("return False", than[i:i + 600], "biet phong hong ma van moi tiep")


class TestKnowledgeDaGhi(unittest.TestCase):
    def test_KNOWLEDGE_co_bang_ma(self):
        with io.open(os.path.join(ROOT, "KNOWLEDGE.md"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("S:047-002", s, "phat hien moi ma khong ghi vao KNOWLEDGE.md")
        self.assertIn("創建房間結果", s)


if __name__ == "__main__":
    unittest.main()
