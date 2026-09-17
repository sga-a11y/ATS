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
        E.thi_hanh(c, E.VIEC_VE_MAP, lambda: True, dich=18822, la_thanh=_la_thanh)
        self.assertIn(("scene_route", 18000, 18822), c.da_goi)
        self.assertNotIn(("smart_route", 18822), c.da_goi,
                         "quay ve thanh di lai -> teleport -> ROI DOI -> party vo")

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
