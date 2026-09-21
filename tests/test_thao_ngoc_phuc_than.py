# -*- coding: utf-8 -*-
"""NGOC PHUC THAN: mode event TAT HAN, va THAO TRUOC khi danh boss/PB.

User chot 21/09:
  * "mode event mac dinh cai su dung phuc than se tat: tick hay ko deu ko su dung, neu dang deo
     ngoc phuc than se thao ra"
  * "cac mode khac: neu co step danh boss the gioi, boss quan doan, PB don, PB doi thi truoc khi
     danh kiem tra xem co dang deo ngoc phuc than ko, neu dang deo thi thao ngoc ra"
  * "thao ra thoi day nhe, dung co tien tay vut bo"

Ngoc chi de an he so EXP luc train; deo vao boss/PB la dot ben ngoc khong duoc gi.
KHONG tu deo lai (user chon): vong `use_phuc_than_items` san co se tu deo lai o chu ky sau.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _than(src, dau, het="\n    def "):
    i = src.find(dau)
    return "" if i < 0 else src[i:src.find(het, i + 10)]


class _Cli:
    """Chi co thu `thao_ngoc_phuc_than` dung toi."""

    _label = "t"
    running = True

    def __init__(self, deo_tid=None, damage=0):
        self.equipped_items = ([{"id": deo_tid, "damage": damage}] if deo_tid else [])
        self.da_coi = []

    def unequip_item(self, fit_pos, follow=0):
        self.da_coi.append(int(fit_pos))
        return True

    thao_ngoc_phuc_than = C.GameClient.thao_ngoc_phuc_than
    _equipped_phuc_than_tid = C.GameClient._equipped_phuc_than_tid
    PHUC_THAN_FIT_POS = C.GameClient.PHUC_THAN_FIT_POS


class TestThaoNgoc(unittest.TestCase):
    def test_dang_deo_thi_COI_RA(self):
        c = _Cli(deo_tid=next(iter(C.PHUC_THAN_GEM_TIDS)))
        self.assertTrue(c.thao_ngoc_phuc_than("test"))
        self.assertEqual(c.da_coi, [6], "ngoc deo o vi tri 6 (dac biet) cua char")

    def test_KHONG_deo_thi_khong_lam_gi(self):
        c = _Cli()
        self.assertTrue(c.thao_ngoc_phuc_than())
        self.assertEqual(c.da_coi, [], "gui lenh coi khi khong deo -> goi thua, co the loi")

    def test_deo_do_KHAC_thi_khong_dung_toi(self):
        c = _Cli(deo_tid=0x1234)
        c.thao_ngoc_phuc_than()
        self.assertEqual(c.da_coi, [], "coi nham mon khac -> mat trang bi")


class TestKhongVutNgoc(unittest.TestCase):
    """User: "thao ra thoi day nhe, dung co tien tay vut bo". Thao xong ngoc nam TRONG TUI, ma bot
    co duong don tui - phai chac ngoc khong bi vut/ban/phan giai."""

    def test_ham_thao_KHONG_goi_lenh_vut(self):
        than = _than(_doc("bot", "client.py"), "    def thao_ngoc_phuc_than(")
        self.assertTrue(than)
        for cam in ("discard_item", "sell_", "decompose", "donate"):
            self.assertNotIn(cam, than, "ham thao lai di %s ngoc" % cam)

    def test_duong_VUT_RAC_chi_vut_NGOC_HU(self):
        """`DISCARD_JUNK_TIDS` phai KHONG chua ngoc that - chi Ngoc Hu (ngoc da hong)."""
        self.assertNotIn(C.BROKEN_PHUC_THAN_TID, C.PHUC_THAN_GEM_TIDS,
                         "ngoc hu bi tinh la ngoc that -> deo lai do hong")
        self.assertEqual(set(C.GameClient.DISCARD_JUNK_TIDS) & set(C.PHUC_THAN_GEM_TIDS), set(),
                         "duong vut rac se vut mat ngoc Phuc Than vua thao ra")

    def test_KHONG_tu_deo_lai(self):
        """User chon: de vong `use_phuc_than_items` tu lo. Deo lai ngay trong ham nay thi co luc
        deo lai khi con dang trong instance."""
        than = _than(_doc("bot", "client.py"), "    def thao_ngoc_phuc_than(")
        # `unequip_item(` co chua chuoi "equip_item(" -> phai kiem CO `self.`.
        self.assertNotIn("self.equip_item(", than)
        self.assertNotIn("_equip_phuc_than", than)


class TestModeEventTatHan(unittest.TestCase):
    def test_co_tat_nam_tren_CLIENT(self):
        self.assertIn("self.phuc_than_tat = False", _doc("bot", "client.py"),
                      "thieu khai bao mac dinh -> getattr moi noi, de sot")

    def test_dat_co_TRUOC_cua_re_engine_moi(self):
        """Dat sau cua re thi party engine moi khong bao gio duoc gan -> van dung Phuc Than."""
        s = _doc("run_party_digioi.py")
        i_co = s.find("c.phuc_than_tat = (")
        i_re = s.find("if dung_engine_moi(pidx):")
        self.assertGreater(i_co, 0, "mat cho dat co")
        self.assertLess(i_co, i_re, "dat SAU cua re -> engine moi diec")

    def test_dat_co_o_cho_chay_cho_MOI_ACC(self):
        """TUNG dat trong `lam_login_chores` - ham do CHI chay khi acc con viec vat login. Acc da
        xong chore thi co van False -> `use_phuc_than_items` DEO LAI ngoc vua thao.
        Ca that ttba 21/09: 20:28 thao (server xac nhan `Da coi do: vi tri 6`), 21:03 lai thao
        DUNG con ngoc do -> tuc da bi deo lai o giua."""
        s = _doc("run_party_digioi.py")
        # Than cua `lam_login_chores` KHONG duoc chua cho dat co (so vi tri thi vo nghia: ham do
        # dinh nghia truoc `run_account` trong file).
        i_chore = s.find("def lam_login_chores(")
        self.assertGreater(i_chore, 0)
        than_chore = s[i_chore:s.find("\ndef ", i_chore + 10)]
        self.assertNotIn("c.phuc_than_tat = (", than_chore,
                         "dat co trong `lam_login_chores` -> acc da xong chore la sot")
        # Phai nam trong `run_account`, GIUA "vao world" va cua re engine moi - doan do chay cho
        # MOI acc MOI lan login. (Cua so 800 ky tu khong du: khoi comment giai thich dai hon the.)
        i_co = s.find("c.phuc_than_tat = (")
        i_world = s.find('log.info("[%s] (%s) vao world."')
        i_re = s.find("if dung_engine_moi(pidx):")
        self.assertGreater(i_world, 0)
        self.assertLess(i_world, i_co, "dat TRUOC khi vao world -> chua co du lieu do dang mac")
        self.assertLess(i_co, i_re)

    def test_CHI_MOT_cho_dat_co(self):
        s = _doc("run_party_digioi.py")
        self.assertEqual(s.count("c.phuc_than_tat = ("), 1,
                         "hai cho dat co -> mot cho sua, cho kia quen")

    def test_mode_event_thi_THAO_ngoc_luon(self):
        s = _doc("run_party_digioi.py")
        i = s.find("c.phuc_than_tat = (")
        self.assertIn("thao_ngoc_phuc_than(", s[i:i + 500])

    def test_use_phuc_than_items_TU_CHAN(self):
        """Chan o TUNG NOI GOI (3 duong: login / keepalive engine cu / `_duy_tri` engine moi) thi
        som muon sot mot cai -> chan ngay trong ham."""
        than = _than(_doc("bot", "client.py"), "    def use_phuc_than_items(")
        self.assertTrue(than)
        i = than.find('getattr(self, "phuc_than_tat", False)')
        self.assertGreater(i, 0, "ham khong tu chan -> tick tat van dung")
        self.assertLess(i, than.find("USE_LOGIN_ITEMS"), "chan SAU khi da dung item thi vo nghia")


class TestThaoTruocKhiDanh(unittest.TestCase):
    """Bon duong: boss the gioi, boss Quan Doan, PB don, PB to doi (leader + member)."""

    @classmethod
    def setUpClass(cls):
        cls.src = _doc("bot", "client.py")

    def _co_thao(self, dau):
        than = _than(self.src, dau)
        self.assertTrue(than, "mat ham %r" % dau)
        return "thao_ngoc_phuc_than(" in than

    def test_boss_the_gioi(self):
        self.assertTrue(self._co_thao("    def do_world_boss(self"))

    def test_boss_quan_doan(self):
        self.assertTrue(self._co_thao("    def do_legion_boss(self"))

    def test_PB_don(self):
        self.assertTrue(self._co_thao("    def do_daily_dungeon(self"))

    def test_PB_to_doi_LEADER_o_cua_vao_CHUNG(self):
        """Dat o `do_team_dungeon` (cua chung) chu khong tung ham lv20/50/80/110 - moi level mot
        ham rieng, dat trong tung ham la som muon sot mot cai."""
        self.assertTrue(self._co_thao("    def do_team_dungeon(self, level"))

    def test_PB_to_doi_MEMBER_thao_luc_nhan_moi(self):
        """Member KHONG di qua `do_team_dungeon` (leader goi) -> thieu cho nay thi ca party thao
        con member van deo ngoc vao pho ban."""
        than = _than(self.src, "    def _on_dungeon(self")
        i = than.find("Nhan moi PHO BAN tu")
        self.assertGreater(i, 0)
        self.assertIn("thao_ngoc_phuc_than(", than[i:i + 400])

    def test_boss_QD_thao_SAU_cac_cua_bo_qua(self):
        """Thao roi moi phat hien het luot / con cooldown = mat cong deo lai."""
        than = _than(self.src, "    def do_legion_boss(self")
        i_thao = than.find("thao_ngoc_phuc_than(")
        self.assertGreater(i_thao, than.find("self.legion_boss_next and now < self.legion_boss_next"))

    def test_PB_don_thao_SAU_cua_da_xong(self):
        than = _than(self.src, "    def do_daily_dungeon(self")
        i_thao = than.find("thao_ngoc_phuc_than(")
        self.assertGreater(i_thao, than.find("DA XONG theo server"))


if __name__ == "__main__":
    unittest.main()
