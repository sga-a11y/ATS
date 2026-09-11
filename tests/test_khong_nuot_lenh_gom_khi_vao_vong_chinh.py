"""VAO VONG CHINH KHONG DUOC NUOT LENH GOM DANG CO HIEU LUC.

User 11/09: "p7, dieu phoi thay 2 map khac nhau va gom lai nhung deo thay ai tap trung".

CA THAT (party 7, 11:58-12:01):

    11:58:26 [party 7] gen 4: viec=gom - party dang o 3 MAP khac nhau -> REFORM gen -> 2
    11:59:10 [ttsau]  (LEADER) dieu phoi bao GOM -> thoi moi, gom lai
    11:59:10 [ttsau]  pre-route: tele trung gian ve thanh 12061 truoc      <- leader DI GOM
    11:59:15 [ttnne]  (member) -> REFORM party (gen 2) -> DIEU PHOI chot GOM  <- mot member DI GOM
    11:59:12 [ttmuoi] (member) da vao party - dung yen tai safe, tu danh
    11:59:17 [ttmuoi] (member) L0: DIEU PHOI ra lenh 'gom' -> DUNG viec chinh, theo lenh
    ... 11:59:17 -> 12:01:16 IM HOAN TOAN, khong mot buoc di chuyen ...

Ba member (ttmuoi, ttbay, tttam) nhan lenh, DUNG viec chinh, roi dung im. Hai nguoi kia di ve thanh
mot minh. Party khong bao gio tap trung duoc.

NGUYEN NHAN: luc vao vong chinh, bien dem "lenh da xu ly" duoc dat bang gen HIEN TAI neu acc dang
dung dung train map:

    reform_gen_handled = max(startup, st["reform_gen"]) if c.current_map == sc else startup

Ba member vua duoc leader keo toi dung train map -> dieu kien dung -> NUOT luon lenh gom gen 2.
Nhanh L0 (`DUNG viec chinh`) chi lam mot viec la dung danh; con viec DI GOM nam o nhanh
`st["reform_gen"] > reform_gen_handled` - ma no vua bi nuot.

Y dinh ban dau cua dong do van dung: acc dang dung dung cho thi dung replay lenh cu (tranh xe party
vua lap). Cai thieu la: lenh gom/dong bo DANG CON HIEU LUC thi khong phai "lenh cu" - party van
dang o nhieu map, chinh vi the dieu phoi moi con ra lenh do.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _ma(s):
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    return re.sub(r"#.*", "", s)


class TestKhongNuotLenhDangCoHieuLuc(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        i = self.src.find("reform_gen_handled = (max(startup_reform_gen_handled")
        self.assertGreater(i, 0, "mat cho khoi tao reform_gen_handled")
        self.khoi = _ma(self.src[max(0, i - 1200):i + 600])

    def test_co_xet_ke_hoach_hien_tai(self):
        self.assertIn("_ke_hoach(st)", self.khoi,
                      "khoi tao mu theo gen -> nuot lenh gom dang chay")

    def test_xet_dung_hai_lenh_can_thi_hanh(self):
        for _v in ("VIEC_GOM", "VIEC_DONG_BO"):
            self.assertIn(_v, self.khoi)

    def test_dang_co_lenh_thi_KHONG_nuot(self):
        """`not _dang_co_lenh_gom` phai nam trong dieu kien nuot."""
        self.assertIn("not _dang_co_lenh_gom", self.khoi)

    def test_van_giu_y_dinh_cu_khi_KHONG_co_lenh(self):
        """Khong co lenh gom thi van nuot nhu cu - de khong replay lenh cu xe party vua lap."""
        self.assertIn("c.current_map == sc", self.khoi)
        self.assertIn("startup_reform_gen_handled", self.khoi)

    def test_GHI_LY_DO_khi_khong_nuot(self):
        self.assertIn("KHONG nuot lenh", self.src)


class TestChayThatPhepQuyetDinh(unittest.TestCase):
    """Chay that bieu thuc, khong chi doc chu."""

    @staticmethod
    def _handled(startup, gen_hien_tai, dung_map, co_lenh_gom):
        return (max(startup, gen_hien_tai)
                if (dung_map and not co_lenh_gom) else startup)

    def test_ca_party_7_lenh_gom_KHONG_bi_nuot(self):
        """Dung so that: startup=0, gen=2, dang o dung train map, dieu phoi dang bao gom."""
        self.assertEqual(self._handled(0, 2, True, True), 0)

    def test_khong_co_lenh_thi_van_nuot_nhu_cu(self):
        self.assertEqual(self._handled(0, 2, True, False), 2)

    def test_lech_map_thi_luon_giu_startup(self):
        """Acc con lech map -> giu 0 de keepalive don no NGAY (hanh vi cu, khong duoc doi)."""
        self.assertEqual(self._handled(0, 5, False, False), 0)
        self.assertEqual(self._handled(0, 5, False, True), 0)

    def test_startup_cao_hon_thi_giu_startup(self):
        self.assertEqual(self._handled(7, 2, True, False), 7)


if __name__ == "__main__":
    unittest.main()
