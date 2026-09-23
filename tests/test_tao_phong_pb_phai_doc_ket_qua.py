# -*- coding: utf-8 -*-
"""TAO PHONG PB: phai DOC `S:047-002` roi hay moi member.

`S:047-002 <創建房間結果> +結果(1)` ve cho LEADER (`Dungeon.ReciveCreateDungeon`,
`_lua_dec/Logic/Dungeon.lua:460`). Ma != 0 thi client goi `ClearRoomData()` - PHONG KHONG TON TAI.
Bang ma lay tu nhanh `if result == N` THAT (`Dungeon.lua:486-514`), KHONG lay tu comment o `:463`
(comment do chi liet ke toi 7, ghi sai ma 7, va thieu ma 8/9):
    0 thanh cong · 1 khong co ma pho ban · 2 khong du cap · 3 dang o trong phong PB roi ·
    4 het luot · 5 DANG O TRONG TO DOI · 6 phong day · 7 phong khong ton tai · 8 dang trong tran ·
    9 ma dau dang dung

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
        """DU CA 9 MA, lay tu nhanh `if result == N` THAT (_lua_dec/Logic/Dungeon.lua:486-514).

        Ban 22/09 chep theo COMMENT o `:463` cua chinh client - comment do chi liet ke toi 7 va
        ghi sai ma 7 la `暫無可用空間` (dung la `該房間不存在`), lai thieu han ma 8 `戰鬥中` va
        ma 9. Thieu ma la lan sau lai phai mo nguoc client de tra.
        """
        than = _than(self.src, "def _on_dungeon(")
        for _s in ("無此副本編號", "等級不符", "已在副本房間中", "次數用盡",
                   "不可組隊", "人數已滿", "該房間不存在", "戰鬥中", "魔豆正在使用中"):
            self.assertIn(_s, than, "thieu ma loi %s" % _s)
        self.assertNotIn("暫無可用空間", than, "van giu ma 7 SAI chep tu comment :463")

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



class TestThoatToDoiTruocKhiLapPhong(unittest.TestCase):
    """MA 5 `不可組隊` = DANG O TRONG TO DOI thi server KHONG CHO tao phong.

    Cung luat voi doi kenh (`S:007-002` ma 3 `組隊不可換分區`) va voi vao nha (`HouseManager`
    ma 10 dung chung thong bao 10316).

    Ban 22/09 chi don PHONG PB cu (`C:047-010`), KHONG don TO DOI (`C:013-004`) -> party thuong con
    nguyen -> moi lan tao phong deu an ma 5, lap 1 lan/giay.

    Ca that 23/09 party 45 (user: "party 45 co dua ko vao phong PB"):
        12:19:01 [party 45] roster leader=3/4                   <- DANG o to doi
        12:19:01 [chdumot] TAO PHONG HONG (S:047-002 ket qua=5: 不可組隊)
    Doi chung cung phut, party 43 vua ra khoi pho ban nen to doi TAN THEO:
        12:20:03 [tonqhai]  -> da ra khoi pho ban (map 62013 -> 12061)
        12:20:03 [party 43] roster leader=0/4                   <- KHONG o to doi nao
        12:20:04 [tonqmot]  Phong PB: TAO PHONG OK
    """

    def setUp(self):
        self.src = _src()
        self.than = _than(self.src, "def _don_truoc_khi_tao_phong(")

    def test_co_ham_don_rieng(self):
        self.assertIn("def _don_truoc_khi_tao_phong(", self.src)

    def test_don_CA_HAI_thu(self):
        self.assertIn("leave_team_dungeon(", self.than, "khong don PHONG PB cu")
        self.assertIn("leave_party()", self.than, "khong don TO DOI -> van an ma 5")

    def test_ra_khoi_PHONG_truoc_roi_moi_ROI_DOI(self):
        self.assertLess(self.than.find("leave_team_dungeon("), self.than.find("leave_party()"),
                        "roi doi truoc thi con ket trong phong PB")

    def test_CHO_server_xac_nhan_roster_rong(self):
        """Gui `0x2f 0200` ngay sau `C:013-004` thi server chua xu xong -> van ma 5."""
        self.assertIn("party_members", self.than, "khong cho roster ve rong")
        self.assertIn("time.sleep(", self.than)

    def test_KHONG_dem_theo_gia_tri_tra_ve_cua_leave_team_dungeon(self):
        """Ham do tra True CA O NHANH "coi nhu da o ngoai" (khong gui goi nao) - dem theo no thi
        log in "don 5 acc" ngay duoi 5 dong "KHONG gui C:047-010" (ban 22/09)."""
        self.assertNotIn("_don += 1", self.than)
        self.assertNotIn("don %d acc ra khoi phong PB CU", self.src)

    def test_CA_HAI_duong_tao_phong_deu_don(self):
        for _dau in ("def _do_team_dungeon_lv20_inner(", "def _create_team_dungeon_room("):
            _t = _than(self.src, _dau)
            self.assertIn("_don_truoc_khi_tao_phong(", _t, "%s khong thoat to doi truoc" % _dau)
            self.assertLess(_t.find("_don_truoc_khi_tao_phong("),
                            _t.find("_cho_tao_phong_pb("),
                            "%s don SAU khi tao phong" % _dau)


class TestKnowledgeDaGhi(unittest.TestCase):
    def test_KNOWLEDGE_co_bang_ma(self):
        with io.open(os.path.join(ROOT, "KNOWLEDGE.md"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("S:047-002", s, "phat hien moi ma khong ghi vao KNOWLEDGE.md")
        self.assertIn("創建房間結果", s)


if __name__ == "__main__":
    unittest.main()
