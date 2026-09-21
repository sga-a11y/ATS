# -*- coding: utf-8 -*-
"""MUA HP/SP di bang SMART ROUTE, khong replay tung buoc.

User 21/09 bao party 21 o thanh "di 1 buoc roi dung yen tam 10-15s". Hai viec khac nhau:
  1. Cho mu 8s moi buoc trong `_wait_combat_clear` - da sua rieng (xem
     `CHO_END_NEU_VUA_DANH_SEC`).
  2. Kieu di chuyen: "m cu doi thanh smart route nhu di Tien trang cho dong bo".

Route replay di CO DINH ~35 buoc boc tu capture: khong biet duong tat, va neu bi day lech vi tri
thi moi buoc sau deu sai. Smart route tinh duong tu vi tri THAT.

NEO QUAN TRONG - `HPSP_NPC_MAP` phai la map ma HAI CONG cua route replay dan toi. Doi hang so nay
thanh map khac la bot di nham cho ma KHONG bao loi gi (van "toi noi", chi la khong co NPC).
"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestDungSmartRoute(unittest.TestCase):
    def setUp(self):
        s = _doc("bot", "client.py")
        i = s.find("    def _run_trac_hpsp_route(self):")
        self.assertGreater(i, 0, "mat ham `_run_trac_hpsp_route`")
        self.than = s[i:s.find("\n    def ", i + 10)]

    def test_goi_smart_route_TRUOC(self):
        self.assertIn("follow_smart_scene_route(", self.than)
        self.assertLess(self.than.find("follow_smart_scene_route("),
                        self.than.find("for step in self.TRAC_HPSP_ROUTE"),
                        "replay chay truoc -> smart route thanh do thua")

    def test_toi_map_roi_di_TIEP_toi_NPC(self):
        """Smart route chi dua toi MAP; khong `navigate_to` thi dung o cua map, mo shop khong duoc
        (giong bai hoc `cat_do_tien_trang`)."""
        self.assertIn("navigate_to(*self.HPSP_NPC_POS", self.than)

    def test_replay_van_con_lam_DU_PHONG(self):
        """Smart route can `world_nav.json` + `Ground.mmg`; thieu file la khong co duong nao."""
        self.assertIn("for step in self.TRAC_HPSP_ROUTE", self.than)

    def test_du_phong_CHI_chay_khi_dang_o_Trac_Quan(self):
        """Smart route co the di duoc NUA DUONG roi ket. Replay bat dau tu spawn Trac Quan nen
        chay tu map khac = toa do sai ngay buoc dau -> `di chuyen QUA XA (ma 14)` -> dut ket noi."""
        i = self.than.find("for step in self.TRAC_HPSP_ROUTE")
        self.assertIn("self.current_map != self.TRAC_QUAN_CITY", self.than[:i])


class TestMapDichKhopVoiBangTimDuong(unittest.TestCase):
    """`HPSP_NPC_MAP` phai la map ma hai cong cua route replay dan toi - doi chieu voi chinh
    `world_nav.json` (bang tim duong cua game) chu khong tin hang so viet tay."""

    @classmethod
    def setUpClass(cls):
        with io.open(os.path.join(ROOT, "world_nav.json"), encoding="utf-8") as fh:
            cls.nav = json.load(fh)
        cls.src = _doc("bot", "client.py")

    def _hang_so(self, ten):
        i = self.src.find("    %s = " % ten)
        self.assertGreater(i, 0, "mat hang so %s" % ten)
        return eval(self.src[i:self.src.find("\n", i)].split("=", 1)[1].split("#")[0].strip())

    def _qua_cong(self, scene, door):
        for e in self.nav["edges"]:
            if int(e["scene"]) == int(scene) and int(e["door"]) == int(door):
                return int(e["target_scene"])
        return None

    def test_hai_cong_cua_replay_dan_dung_toi_HPSP_NPC_MAP(self):
        giua = self._qua_cong(12001, 1)          # gate "08000100"
        self.assertIsNotNone(giua, "world_nav mat canh 12001 cong 1")
        dich = self._qua_cong(giua, 5)           # gate "08000500"
        self.assertEqual(dich, self._hang_so("HPSP_NPC_MAP"),
                         "HPSP_NPC_MAP khong phai map ma route replay dan toi")

    def test_smart_route_TIM_DUOC_duong(self):
        """Thieu mot canh la `build_smart_scene_route` tra None -> bot dung im. Bai hoc cong 10
        cua Nghiep Thanh: cong CO THAT trong Eve.emg nhung game KHONG khai trong bang tim duong."""
        canh = {(int(e["scene"]), int(e["target_scene"])) for e in self.nav["edges"]}
        giua = self._qua_cong(12001, 1)
        self.assertIn((12001, giua), canh)
        self.assertIn((giua, self._hang_so("HPSP_NPC_MAP")), canh)


if __name__ == "__main__":
    unittest.main()
