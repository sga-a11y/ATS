# -*- coding: utf-8 -*-
"""BAN NOI DAT: di bang `navigate_to` (tu tim duong), khong replay tung buoc.

User 21/09: "m cu doi thanh smart route nhu di Tien trang cho dong bo".

Cai bay da mac phai khi lam viec nay - va la ly do bai test nay ton tai:
  T tuong `0x14 08 00 0a 00` giua duong la CONG CHUYEN MAP, roi ket luan "world_nav thieu canh
  12061 cong 10 nen khong smart route duoc". SAI. User chi ra: "cai nay co phai la cong khong nhi,
  no chay thang chu co chuyen map dau".

Hai bang chung KHONG DOI MAP, ca hai deu neo o duoi:
  1. Toa do truoc/sau cong LIEN MACH ((410,750) -> (606,698)), trong khi qua cong that thi toa do
     NHAY sang he khac (xem `TRAC_HPSP_ROUTE`: (90,1670) -> gate -> (1310,590)).
  2. `sell_noi_dat` KHONG co buoc quay ve, con `buy_hp_sp` BAT BUOC co `_ve_thanh_sau_mua_hpsp`.
     Ai doi map thi nguoi do phai quay ve.

Vi cung mot map nen o day KHONG dung `follow_smart_scene_route` (do la phan di GIUA cac map) -
chi `navigate_to` la du.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestDiBangTuTimDuong(unittest.TestCase):
    def setUp(self):
        s = _doc("bot", "client.py")
        i = s.find("    def sell_noi_dat(self")
        self.assertGreater(i, 0, "mat ham `sell_noi_dat`")
        self.than = s[i:s.find("\n    def ", i + 10)]
        # Bo CHU THICH: than ham nay co noi ro "khong can follow_smart_scene_route", bat theo
        # ca chu thich thi chinh cau giai thich lai lam test do.
        self.lenh = "\n".join(d for d in self.than.split("\n") if not d.strip().startswith("#"))

    def test_KHONG_con_replay_tung_buoc(self):
        for ten in ("NOI_DAT_NPC_ROUTE_PRE", "NOI_DAT_NPC_ROUTE_POST",
                    "_move_noi_dat_npc_step"):
            self.assertNotIn(ten, self.lenh, "van con replay tung buoc: %s" % ten)

    def test_di_bang_navigate_to_toi_HAI_MOC(self):
        self.assertIn("navigate_to(*self.NOI_DAT_CONG_POS", self.than)
        self.assertIn("navigate_to(*self.NOI_DAT_NPC_POS", self.than)
        self.assertLess(self.than.find("NOI_DAT_CONG_POS"), self.than.find("NOI_DAT_NPC_POS"),
                        "toi NPC truoc roi moi toi cong -> nguoc duong")

    def test_VAN_gui_goi_mo_cong_o_GIUA(self):
        """Chuoi packet da xac minh tu capture that; bo di la danh cuoc khong can thiet."""
        i = self.than.find('self.send(0x14, b"\\x08\\x00\\x0a\\x00")')
        self.assertGreater(i, 0, "mat goi mo cong")
        self.assertLess(self.than.find("NOI_DAT_CONG_POS"), i, "gui goi mo cong TRUOC khi toi cong")
        self.assertGreater(self.than.find("NOI_DAT_NPC_POS"), i)

    def test_VAN_giu_HAN_GIO(self):
        """Ham nay chay trong `pre_route_town_hop` nen CA PARTY dung cho - qua han phai bo, di
        tiep. `navigate_to` co the ket rat lau neu bi danh giua duong."""
        self.assertIn("NOI_DAT_HAN_GIO", self.than)
        self.assertIn("abort=_abort", self.than, "khong truyen abort -> han gio vo nghia")

    def test_KHONG_dung_follow_smart_scene_route(self):
        """Ca duong nam trong CUNG map -> goi ham di giua cac map la tra None ngay (map nguon ==
        map dich khong co canh nao), bot dung im."""
        self.assertNotIn("follow_smart_scene_route", self.lenh)


class TestKhongDoiMap(unittest.TestCase):
    """Hai bang chung cho ket luan "cong 10 khong doi map". Sau nay ai sua lai thanh "cong that"
    thi phai pha mot trong hai cai nay truoc."""

    def setUp(self):
        self.src = _doc("bot", "client.py")

    def test_ban_noi_dat_KHONG_co_buoc_quay_ve(self):
        i = self.src.find("    def sell_noi_dat(self")
        than = self.src[i:self.src.find("\n    def ", i + 10)]
        self.assertNotIn("go_to_town", than, "phai quay ve = da doi map = ket luan tren sai")

    def test_mua_hpsp_THI_CO_quay_ve(self):
        """Doi chung: duong that su doi map thi bat buoc co buoc quay ve."""
        i = self.src.find("    def buy_hp_sp(self")
        than = self.src[i:self.src.find("\n    def ", i + 10)]
        self.assertIn("_ve_thanh_sau_mua_hpsp()", than)

    def test_toa_do_hai_ben_cong_LIEN_MACH(self):
        """Cach nhau ~200 don vi = di bo tiep. Qua cong that thi nhay hang nghin don vi."""
        import re
        m = {}
        for ten in ("NOI_DAT_CONG_POS", "NOI_DAT_NPC_POS"):
            g = re.search(r"%s = \((\d+), (\d+)\)" % ten, self.src)
            self.assertTrue(g, "mat hang so %s" % ten)
            m[ten] = (int(g.group(1)), int(g.group(2)))
        dx = abs(m["NOI_DAT_NPC_POS"][0] - m["NOI_DAT_CONG_POS"][0])
        dy = abs(m["NOI_DAT_NPC_POS"][1] - m["NOI_DAT_CONG_POS"][1])
        self.assertLess(max(dx, dy), 1000, "hai moc o hai he toa do khac nhau -> co doi map that")


if __name__ == "__main__":
    unittest.main()
