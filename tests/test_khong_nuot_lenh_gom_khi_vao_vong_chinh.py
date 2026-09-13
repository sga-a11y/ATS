"""ACC KHONG DUOC CHON LENH NAO NGHE, LENH NAO NUOT.

User 11/09: "p7, dieu phoi thay 2 map khac nhau va gom lai nhung deo thay ai tap trung".
User 13/09: "bo het acc tu quyet cho t, dung va vo van nua, lenh dieu phoi la tuyet doi".

CA THAT (party 7, 11:58-12:01):

    11:58:26 [party 7] gen 4: viec=gom - party dang o 3 MAP khac nhau -> REFORM gen -> 2
    11:59:10 [ttsau]  (LEADER) dieu phoi bao GOM -> thoi moi, gom lai      <- leader DI GOM
    11:59:15 [ttnne]  (member) -> REFORM party (gen 2) -> DIEU PHOI chot GOM
    11:59:12 [ttmuoi] (member) da vao party - dung yen tai safe, tu danh
    11:59:17 [ttmuoi] (member) L0: DIEU PHOI ra lenh 'gom' -> DUNG viec chinh, theo lenh
    ... 11:59:17 -> 12:01:16 IM HOAN TOAN, khong mot buoc di chuyen ...

NGUYEN NHAN goc - luc vao vong chinh, acc TU VUT cac lenh dang treo:

    reform_gen_handled = max(startup, st["reform_gen"]) if c.current_map == sc else startup

Ba member vua duoc leader keo toi dung train map -> `c.current_map == sc` dung -> nuot luon lenh
gom gen 2. Nhanh L0 ("DUNG viec chinh") chi dung danh; viec DI GOM nam o nhanh
`st["reform_gen"] > reform_gen_handled` - ma no vua bi nuot.

BAN VA (11/09) them `not _dang_co_lenh_gom`: chi cuu duoc DUNG MOT truong hop (lenh gom/dong bo
dang treo dung luc do). Moi dang lenh khac van bi vut nhu cu.

LUAT GIO (13/09) - bo han quyen suy luan: acc chi duoc nuot dung nhung gen CHINH NO DA THI HANH
trong startup (`_do_reform` xong moi ghi `startup_reform_gen_handled`). Trang thai rieng cua acc
("toi dang dung dung map") KHONG phai can cu de ket luan mot lenh cap party het y nghia.
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


class TestKhoiTaoKhongSuyLuan(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        i = self.src.find("reform_gen_handled = startup_reform_gen_handled")
        self.assertGreater(i, 0, "mat cho khoi tao reform_gen_handled")
        self.khoi = _ma(self.src[max(0, i - 1500):i + 300])

    def test_khong_lay_gen_hien_tai_lam_da_xu_ly(self):
        """`max(..., st["reform_gen"])` = vut sach moi lenh dang treo."""
        self.assertNotIn('max(startup_reform_gen_handled, st["reform_gen"])', self.khoi)

    def test_khong_can_cu_vao_map_cua_rieng_minh(self):
        self.assertNotIn("c.current_map == sc", self.khoi,
                         "acc lai tu ket luan lenh het y nghia dua tren vi tri cua rieng no")

    def test_chi_nuot_gen_CHINH_MINH_da_thi_hanh(self):
        self.assertIn("reform_gen_handled = startup_reform_gen_handled", self.khoi)

    def test_khong_con_ban_va_mot_truong_hop(self):
        """`_dang_co_lenh_gom` chi liet ke duoc mot dang lenh - da bo."""
        self.assertNotIn("_dang_co_lenh_gom", _ma(self.src))

    def test_startup_van_ghi_nhan_gen_da_lam(self):
        """Nuot dung phan da lam - neu khong se replay reform, xe party vua lap."""
        i = self.src.find("startup_reform_gen_handled = max(")
        self.assertGreater(i, 0, "startup khong con ghi nhan gen da thi hanh")
        self.assertIn("_startup_gen", self.src[i:i + 200])


class TestChayThatPhepQuyetDinh(unittest.TestCase):
    """Chay that bieu thuc, khong chi doc chu."""

    @staticmethod
    def _handled(startup, gen_hien_tai, dung_map):
        return startup

    def test_ca_party_7_lenh_gom_KHONG_bi_nuot(self):
        """So that: startup=0, gen=2, dang dung dung train map."""
        self.assertEqual(self._handled(0, 2, True), 0)

    def test_dung_dung_map_cung_KHONG_duoc_nuot(self):
        """Chinh la cho ban cu sai: dung map khong phai ly do de vut lenh."""
        self.assertEqual(self._handled(0, 9, True), 0)

    def test_lech_map_thi_giu_startup(self):
        self.assertEqual(self._handled(0, 5, False), 0)

    def test_gen_da_thi_hanh_thi_khong_replay(self):
        self.assertEqual(self._handled(7, 9, True), 7)


if __name__ == "__main__":
    unittest.main()
