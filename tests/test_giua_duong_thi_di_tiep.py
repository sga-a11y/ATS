# -*- coding: utf-8 -*-
"""DANG O GIUA DUONG thi DI TIEP TU DAY, khong quay ve thanh di lai tu dau.

`follow_smart_route` LUON bat dau bang `go_to_town(route["city"])`, tuc quay ve THANH cua route -
ma teleport bat buoc ROI DOI (client game chan tele khi con trong doi). Nen chi can viec `ve_map`
bi giao lai MOT lan giua chuyen di la leader lon nguoc ve thanh va party vo.

Ca that 17/09 party 51 (user: "p51, leader va member lai lech map"):
    20:43:24 gen 15: du doi, cung map/kenh -> DI TRAIN map 18822 (con o [18001])  <- ca party o thanh
    20:43:38 gen 16: ...                                          (con o [18000]) <- da qua 1 cong
    20:44:00 [mhmmot] PARTY: b441273a ROI doi -> roster con 0 nguoi               <- leader roi doi
    20:44:02 [mhmmot] Teleport -> city 12001                                      <- quay NGUOC
    20:44:04 [mhmmot] Teleport -> city 18001
    20:44:13 gen 19: viec=gom - party dang o 2 MAP khac nhau [18000, 18001]

`follow_smart_scene_route` la duong DI BO tu map hien tai - chinh ham flow cu dung de keo party
qua cong (`_reform_via_nghiep`).
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as E


class _Cli:
    def __init__(self, map_id):
        self.current_map = map_id
        self.running = True
        self._label = "test"
        self.da_goi = []

    def follow_smart_scene_route(self, src, dest, safe, abort=None, flee=True):
        self.da_goi.append(("scene_route", src, dest))
        return True

    def build_smart_route(self, dest, safe):
        self.da_goi.append(("build", dest))
        return {"city": 18001, "flag": 9}

    def follow_smart_route(self, dest, safe, abort=None, flee=True):
        self.da_goi.append(("smart_route", dest))
        return True


def _la_thanh(m):
    return int(m) in (12001, 18001, 18021)


class TestGiuaDuongThiDiTiep(unittest.TestCase):
    def test_o_map_giua_duong_thi_DI_BO_TIEP(self):
        c = _Cli(18000)                     # 18000 = map thuong, dang tren duong toi bai
        c._pe_dang_di_route = True          # DA xuat phat tu thanh route (co do `ve_map` bat len)
        E.thi_hanh(c, E.VIEC_VE_MAP, lambda: True, dich=18822, la_thanh=_la_thanh)
        self.assertIn(("scene_route", 18000, 18822), c.da_goi)
        self.assertNotIn(("smart_route", 18822), c.da_goi,
                         "quay ve thanh di lai -> teleport -> ROI DOI -> party vo")

    def test_VUA_LOGIN_o_map_la_thi_TELEPORT_chu_khong_di_bo(self):
        """Ca that 21/09 party 21: login tai 21814 (Trai Pham Thanh), bai train 21844 (Dam lay
        Tang Khau) - ca hai deu KHONG phai thanh. Di bo thang sang la keo ca party loi bo qua ca
        vung map; flow cu teleport ve thanh TRUNG GIAN (Trac Quan/Ng.Thanh) roi thanh TAP KET.
        User: "sao no ko tele ve thanh gan nhat roi di ma no lap party tu trai pham thanh 3 roi
        keo den bai train"."""
        c = _Cli(21814)                     # vua login, CHUA xuat phat -> khong co co
        E.thi_hanh(c, E.VIEC_VE_MAP, lambda: True, dich=21844, la_thanh=_la_thanh)
        self.assertNotIn(("scene_route", 21814, 21844), c.da_goi,
                         "di bo thang tu map la -> loi bo qua ca vung map")
        self.assertIn(("smart_route", 21844), c.da_goi,
                      "phai di duong route (co `pre_route_town_hop` -> thanh trung gian)")

    def test_di_xong_thi_HA_co(self):
        """Khong ha thi lan sau vua login da tuong dang giua chuyen -> lai di bo thang."""
        c = _Cli(18001)
        E.thi_hanh(c, E.VIEC_VE_MAP, lambda: True, dich=18822, la_thanh=_la_thanh)
        self.assertFalse(getattr(c, "_pe_dang_di_route", False))

    def test_o_THANH_thi_van_di_duong_binh_thuong(self):
        c = _Cli(18001)                     # dang o thanh -> route tu thanh la dung
        E.thi_hanh(c, E.VIEC_VE_MAP, lambda: True, dich=18822, la_thanh=_la_thanh)
        self.assertIn(("smart_route", 18822), c.da_goi)
        self.assertNotIn(("scene_route", 18001, 18822), c.da_goi)

    def test_di_bo_khong_duoc_thi_VAN_quay_ve_thanh(self):
        """L0: khong duoc de acc dung im chi vi khong co duong bo."""
        c = _Cli(18000)
        c.follow_smart_scene_route = lambda *a, **k: False
        E.thi_hanh(c, E.VIEC_VE_MAP, lambda: True, dich=18822, la_thanh=_la_thanh)
        self.assertIn(("smart_route", 18822), c.da_goi)

    def test_khong_biet_thanh_hay_khong_thi_giu_hanh_vi_cu(self):
        c = _Cli(18000)
        E.thi_hanh(c, E.VIEC_VE_MAP, lambda: True, dich=18822)      # la_thanh=None
        self.assertIn(("smart_route", 18822), c.da_goi)


if __name__ == "__main__":
    unittest.main()
