"""Login vao ma DANG DUNG TREN MAP TRAIN -> ra safe TRUOC khi lam viec vat.

Viec vat dau phien rat dai (thanh tuu, diem danh, qua 14 ngay, qua ban be, donate quan doan,
thu cuoi, van tieu, boss QD, nhiem vu hang ngay...) - dung giua bai quai ma lam thi an dan ca
loat, va toa do/HP lech het truoc khi vao pha train.

Chot cu la `_early_mode == "train"` -> mode DG+Train o pha `digioi` BI BO QUA HOAN TOAN du no
dang dung ngay tren bai quai (party 11, 31/08 09:25: `MODE=digioi start_city=23821`, khong he co
dong "ve safe truoc login chores"). Dieu kien dung la DANG DUNG TREN MAP TRAIN.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestRaSafeTruocViecVat(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("_login_safe_done = False")
        self.assertGreater(i, 0, "mat buoc ra safe truoc login chores")
        self.khoi = s[i:i + 1600]
        self.than = re.sub(r"#.*", "", self.khoi)
        self.src = s

    def test_dieu_kien_la_DANG_O_MAP_TRAIN(self):
        self.assertIn("_early_tm is not None and login_map == _early_sc", self.than,
                      "van chot theo mode -> DG+Train o pha digioi khong duoc ra safe")

    def test_KHONG_con_chot_theo_mode(self):
        i = self.than.find("_login_safe_done = False")
        j = self.than.find("_safe0 = _nearest_safe(")
        self.assertGreater(j, i)
        khuc = self.than[i:j]
        self.assertNotIn('if _early_mode == "train" and _early_tm is not None:\n            c.flee_mode = True\n            if login_map', khuc,
                         "van long viec ra safe trong nhanh mode==train")

    def test_van_giu_flee_cho_mode_train(self):
        """Mode train van phai bat flee_mode ngay tu dau nhu cu."""
        self.assertIn('if _early_mode == "train" and _early_tm is not None:', self.than)
        self.assertIn("c.flee_mode = True", self.than)

    def test_di_bang_flee(self):
        self.assertIn("c.navigate_to(*_safe0, flee=True)", self.than,
                      "di ra safe ma dung lai danh tung bay quai = vo nghia")

    def test_CHAY_TRUOC_login_chores(self):
        """Thu tu la ca van de: ra safe phai xong TRUOC khi goi bat ky viec vat nao."""
        i_safe = self.src.find("_login_safe_done = True")
        for viec in ("c.claim_achievements()", "c.claim_checkin()", "c.claim_mail()",
                     "c.claim_friend_gifts()"):
            j = self.src.find(viec)
            self.assertGreater(j, 0, "khong tim thay %s" % viec)
            self.assertLess(i_safe, j, "%s chay TRUOC buoc ra safe" % viec)

    def test_loi_khi_ra_safe_KHONG_chan_login(self):
        self.assertIn("except Exception as e:", self.than)
        self.assertIn("loi ve safe ngay sau login (bo qua)", self.than)


if __name__ == "__main__":
    unittest.main()
