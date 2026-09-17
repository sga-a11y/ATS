# -*- coding: utf-8 -*-
"""`_thanh_tap_ket_dich` KHONG duoc cache ket qua "chua biet" (None).

`_pick_start_city` tra None khi chua thanh nao CA PARTY mo di toi duoc. Ma `city_unlocked` tra
None ("chua biet") suot luc acc vua login chua nhan co nhiem vu (`mark_flags`), con
`_party_unlocked_cities` thi BO QUA thanh nao con acc chua biet - nen None phan lon la TRANG THAI
TAM THOI luc party dang len.

Cache lai thi no dong bang CA BUOI: `_thanh_tap_ket_dich` rong -> `_o_thanh_di_qua` tat theo
("chua biet dich -> khong ket luan") -> party lap doi ngay tai thanh dang dung, roi leader di
duong, `follow_smart_route` TU chon thanh khac (router khong biet acc da mo thanh nao) ->
teleport -> ROI DOI -> party tan -> gom lai -> lap.

Ca that 17/09 party 44 (`reform g=101`, tuc quay 101 lan) va party 45:
    08:49:26 [party 45] gen 14: du doi, cung map/kenh -> DI TRAIN map 15457 (con o [18021])
    08:49:26 [chdumot] Teleport -> city 12061       <- leader di, party 4/4 tan ngay
    08:49:27 [party 45] gen 15: viec=gom - party dang o 2 MAP khac nhau [12061, 18021]
"""
from __future__ import annotations

import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "run_party_digioi.py")


def _than(ten):
    with io.open(SRC, encoding="utf-8") as fh:
        s = fh.read()
    i = s.index("def %s(" % ten)
    return s[i:s.index(chr(10) + "def ", i + 10)]


class TestKhongDongBangChuaBiet(unittest.TestCase):
    def setUp(self):
        self.than = _than("_thanh_tap_ket_dich")

    def test_chi_cache_khi_CHOT_DUOC(self):
        self.assertIn("if _tp:", self.than,
                      "cache ca None -> party khong co thanh tap ket suot ca buoi")
        i_if = self.than.index("if _tp:")
        i_cache = self.than.index('st["thanh_tap_ket_cache"] = (_train, _tp)')
        self.assertLess(i_if, i_cache, "phep gan cache phai nam TRONG nhanh chot duoc")

    def test_van_cache_khi_da_chot(self):
        """Van phai cache: `_pick_start_city` goi router, ma vong dieu phoi chay moi 2 giay."""
        self.assertIn('st["thanh_tap_ket_cache"] = (_train, _tp)', self.than)
        self.assertIn('_cu = st.get("thanh_tap_ket_cache")', self.than)


if __name__ == "__main__":
    unittest.main()


class TestMotNguonThanhTapKet(unittest.TestCase):
    """DIEM GOM ma engine dang keo party ve THANG TUYET DOI trong `_thanh_tap_ket_dich`.

    Do la thanh MA CA PARTY DANG DUOC KEO VE, va la thanh cua CHINH ROUTE se di.
    `_pick_start_city` tinh theo tieu chi KHAC ("thanh gan bai nhat ma CA PARTY deu da mo") nen ra
    thanh khac - the la hai ben danh nhau: mot ben keo party ve thanh A, ben kia
    (`_o_thanh_di_qua`) bao "A chi la thanh di ngang, chua toi B" va cam lap party o A.

    Ca that 17/09 party 44+45 (user: "p44 p45 thay van dung o Tho xuan"):
        19:28:49 REFORM gen -> 6 - dang o thanh DI NGANG QUA 15021, chua toi thanh tap ket 18021
    Engine keo ca party ve 15021 (thanh cua route), con `_o_thanh_di_qua` doi 18021 - khong ai dua
    party toi 18021 ca, nen no dung im o Tho Xuan.
    """

    def setUp(self):
        self.than = _than("_thanh_tap_ket_dich")

    def test_uu_tien_diem_gom_engine_dang_keo_ve(self):
        self.assertIn('st.get("diem_gom_hien_tai")', self.than,
                      "khong doc diem gom dang dung -> hai nguon danh nhau")
        i_rp = self.than.index('st.get("diem_gom_hien_tai")')
        i_pick = self.than.index("_pick_start_city(")
        self.assertLess(i_rp, i_pick, "route_plan phai duoc xet TRUOC _pick_start_city")

    def test_van_giu_duong_du_phong(self):
        """Chua co `route_plan` (party vua len) thi van phai tinh duoc bang `_pick_start_city`."""
        self.assertIn("_pick_start_city(", self.than)
