"""VAO PARTY roi KHONG co nghia la duoc dung yen danh o BAT CU DAU.

Doan "member da vao party" truoc day khong he kiem MAP: vao doi xong la `flee_mode = False` +
`combat_ready()` + log "dung yen tai safe, tu danh" - ke ca khi acc dang o map KHAC han leader va
dieu phoi dang ra lenh gom.

Ca that 07/09 party 1 (user: "leader ve Giang Lang roi ma 4 dua kia van o map khac, dieu phoi ngu
vai lon" / "dieu phoi ra lenh thi cac acc phai theo lenh chu"):

    18:54:23 [xGAx] (LEADER) reform: CHO ca party ve Giang Lăng (1/5) - THIEU:
             minhminhmq[map=12003] brubb46677[map=21836] tuyetdo[map=21836] chihao188[map=12003]
    18:54:33 [minh] (member) da vao party - dung yen tai safe, tu danh      <- map 12003
    18:56:22 [brub] (member) da vao party - dung yen tai safe, tu danh      <- map 21836

Leader phai EP RELOGIN tung dua de "cuu party" (94s roi 201s) - cach thu va cham.

Lenh cua dieu phoi khong co gia tri neu acc tu cho phep minh dung yen o cho khac. Sai map thi giu
`flee_mode` va di theo lenh gom; vong chinh + dieu phoi (VIEC_GOM / reform) lo viec keo ve.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestKiemMapTruocKhiDanh(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("_sai_map = bool(train_on_map and sc")
        self.assertGreater(i, 0, "vao party xong van khong kiem map")
        self.khoi = s[i:i + 1800]

    def test_sai_map_thi_GIU_flee(self):
        i = self.khoi.find("if _sai_map:")
        self.assertGreater(i, 0)
        nhanh = self.khoi[i:self.khoi.find("else:", i)]
        self.assertIn("c.flee_mode = True", nhanh)

    def test_sai_map_thi_KHONG_bat_combat(self):
        """`combat_ready()` = bat quai aggro. Bat o map sai = dam quai mot minh giua duong gom."""
        i = self.khoi.find("if _sai_map:")
        nhanh = self.khoi[i:self.khoi.find("else:", i)]
        self.assertNotIn("combat_ready()", nhanh)

    def test_DUNG_map_thi_van_danh_binh_thuong(self):
        """Khong duoc lam hong duong dung: dung map thi van bo flee + bat combat nhu cu."""
        i = self.khoi.find("else:")
        nhanh = self.khoi[i:i + 900]
        self.assertIn("c.flee_mode = False", nhanh)
        self.assertIn("combat_ready()", nhanh)

    def test_khong_log_nham_la_dang_dung_yen_danh(self):
        """Log "dung yen tai safe, tu danh" trong khi dang bi keo di la doc log ra sai su that."""
        self.assertIn("if not _sai_map:", self.khoi)

    def test_van_giu_nhanh_KHONG_co_bot_leader(self):
        s = _src()
        self.assertIn("KHONG co bot-leader -> dung yen tai safe", s)


class TestKhongDungContinue(unittest.TestCase):
    def test_khong_dung_continue_trong_nhanh_nay(self):
        """`continue` o day de nhay nham vong (doan nay nam sau mot vong `while` da ket thuc).
        Dung if/else ro rang thay vi dieu khien luong bang continue."""
        s = _src()
        i = s.find("_sai_map = bool(train_on_map and sc")
        j = s.find("KHONG co bot-leader -> dung yen tai safe", i)
        self.assertGreater(j, i)
        for d in s[i:j].splitlines():
            self.assertNotEqual(d.strip(), "continue", d)


if __name__ == "__main__":
    unittest.main()
