# -*- coding: utf-8 -*-
"""KHONG CO ROUTE VAN PHAI GOM (L0) - engine moi phai dung dung hai fallback cua flow cu.

`_thanh_tap_ket_dich` rong la chuyen BINH THUONG khi thanh gan bai train chua mo het:
`_pick_start_city` chi xet thanh CA PARTY deu mo, khong co ung vien nao thi tra None.

Tra None thang ra thi `_o_thanh_di_qua` cung tat theo ("chua biet dich -> khong ket luan"), party
lap doi ngay tai thanh dang dung, roi leader di duong -> `follow_smart_route` TU chon thanh khac
(router khong biet acc da mo thanh nao) -> teleport -> ROI DOI -> party tan.

Ca that 17/09 party 44 (user: "p44 thay moi dua 1 thanh, bon o Hoi Ke thay bao o cung pt, leader
thi o thanh khac"), lap 101 lan (`reform g=101`):
    08:05:06 gen 418: du doi, cung map/kenh -> DI TRAIN map 15457 (con o [18021] Hoi Ke)
    08:05:06 [tpmot] smart route 15457: city=15021      <- Tho Xuan, KHONG phai Hoi Ke
    08:05:06 [tpmot] Teleport: dang o to doi (4 member) -> ROI DOI truoc
    08:05:07 gen 419: viec=gom - party dang o 2 MAP khac nhau [12061, 18021]

Flow cu (`_do_reform`, nhanh "khong co smart/legacy route -> VAN GOM") dung:
    `_thanh_dong_acc_nhat` -> thanh dang co nhieu acc nhat (it phai di chuyen nhat)
    `_gather_city`         -> thanh GAN NHAT ma CA PARTY da mo
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


class TestThanhDichGoiHamChung(unittest.TestCase):
    def setUp(self):
        self.than = _than("_thanh_dich_engine_moi")
        self.chung = _than("chot_thanh_tap_ket")

    def test_engine_moi_GOI_ham_chung(self):
        self.assertIn("chot_thanh_tap_ket(", self.than,
                      "engine moi tu chon thanh -> lech voi thanh router dung")

    def test_ham_chung_van_giu_hai_fallback_cua_flow_cu(self):
        for _f in ("_thanh_dong_acc_nhat(", "_gather_city("):
            self.assertIn(_f, self.chung,
                          "thieu %s - flow cu van gom duoc khi khong co route" % _f)

    def test_ham_chung_uu_tien_thanh_CUA_ROUTE(self):
        """Phai gom ve dung thanh ma duong di xuat phat, khong thi gom xong leader lai teleport
        di noi khac - ma teleport bat buoc ROI DOI."""
        i_sr = self.chung.index("build_smart_route(")
        i_fb = self.chung.index("_thanh_dong_acc_nhat(")
        self.assertLess(i_sr, i_fb, "fallback dat truoc thanh cua route")


if __name__ == "__main__":
    unittest.main()


class TestThanhGanBaiCHUA_MO(unittest.TestCase):
    """Thanh cua route CHUA MO -> gom o thanh khac roi leader KEO DI BO toi do.

    `follow_smart_route` bat dau bang `go_to_town(route["city"])`, ma thanh chua mo thi
    `go_to_town` bo cuoc ngay ("thanh %s CHUA MO tele -> bo qua ngay") - acc nam lai thanh cu.
    Flow cu xu bang `_activate_nghiep_fallback` + `_reform_via_nghiep`:
        elif fc and c.city_unlocked(fc) is False:
            _activate_nghiep_fallback("thanh %s CHUA MO tele voi acc nay" % fc)
        ...
        c.follow_smart_scene_route(c.current_map, fc, None, abort=_ab, flee=not _full)

    Ca that 17/09 party 45 (user: "day la truong hop thanh gan bai train chua duoc mo nen can phai
    di mo thanh do truoc"):
        09:44:00 chdumot@15021(L) chduhai@18021 chduba@18021 chdubon@18021 chdunam@18021
    Leader mo Tho Xuan nen toi duoc, bon member chua mo nen ket o Hoi Ke, roster 0/4 mai.
    """

    def test_chuyen_diem_gom_khi_co_acc_CHUA_MO(self):
        than = _than("_thanh_dich_engine_moi")
        self.assertIn("_party_city_unlocked(", than, "khong kiem thanh da mo chua")
        self.assertIn("_gather_city(", than, "khong chuyen diem gom sang thanh ca party da mo")

    def test_co_buoc_DI_BO_toi_thanh_chua_mo(self):
        import io as _io
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "bot", "party_engine.py")
        with _io.open(p, encoding="utf-8") as fh:
            eng = fh.read()
        self.assertIn("follow_smart_scene_route(", eng,
                      "thieu buoc keo di bo -> acc chua mo thanh nam lai thanh cu vinh vien")
        i_bo = eng.index("follow_smart_scene_route(")
        i_rt = eng.index("follow_smart_route(", eng.index("if viec == VIEC_VE_MAP:"))
        self.assertLess(i_bo, i_rt, "phai di bo TRUOC khi chay route ra bai")

    def test_chi_NGUOI_KEO_lam_buoc_di_bo(self):
        """Member trong party TU FOLLOW qua cong (game keo theo leader)."""
        import io as _io
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "bot", "party_engine.py")
        with _io.open(p, encoding="utf-8") as fh:
            eng = fh.read()
        self.assertIn("_duoc_di_duong(", eng)
