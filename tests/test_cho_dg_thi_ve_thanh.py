"""CON ACC DANG TRONG DI GIOI -> may acc xong truoc VE THANH dung cho, khong dung o bai train.

User chot 31/08 (party 7): "1 dua dang trong di gioi, 4 dua con lai dung cho quai danh la qua ngu
ngoc, m sua lai la co dua trong di gioi thi bon con lai neu xong di gioi roi thi ve dung o thanh".

Vi sao: safe cua bai train KHONG phai cho dung lau - quai van lang toi (map 23821: safe (990,490)
cach diem quai gan nhat 398, safe cu (950,1090) chi cach 172). Cho DG co the ca chuc phut.

Barrier "cho ca party xong DG" la CHO KHONG GIOI HAN (`cho khong gioi han | CON THIEU: ...`), nen
dung nham cho la an dan ca buoi.
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


class TestChoDGThiVeThanh(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _ve_cho_cho_pha_train(")
        self.assertGreater(i, 0)
        j = s.find("\n        def _finish_digioi_train_after_dg", i)
        self.assertGreater(j, i)
        self.khoi = s[i:j]
        self.than = re.sub(r"#.*", "", self.khoi)

    def test_co_kiem_acc_con_trong_DI_GIOI(self):
        self.assertIn("config.DIGIOI_MAP_ID", self.than,
                      "khong kiem ai con trong DG -> dung o bai train cho quai danh")
        self.assertIn("_con_trong_dg", self.than)

    def test_con_nguoi_trong_DG_thi_VE_THANH(self):
        i = self.than.find("if _con_trong_dg:")
        self.assertGreater(i, 0)
        khoi = self.than[i:i + 400]
        self.assertIn("_go_town_safe(c, label)", khoi, "phai ve thanh")
        self.assertIn("return", khoi, "ve thanh roi phai dung, khong roi xuong nhanh ra safe bai")

    def test_kiem_TRUOC_khi_chon_safe_bai_train(self):
        i_kiem = self.than.find("_con_trong_dg = []")
        i_safe = self.than.find("_ds = [tuple(map(int, p))")
        self.assertGreater(i_kiem, 0)
        self.assertGreater(i_safe, 0)
        self.assertLess(i_kiem, i_safe, "chon safe bai train TRUOC thi chot ve thanh vo nghia")

    def test_KHONG_ai_trong_DG_thi_van_giu_luat_cu(self):
        """User 27/08: "login vao va da dung o map roi ma no van ve thanh" - het DG thi dung o
        safe bai train, KHONG bay ve thanh roi bo cong len lai."""
        self.assertIn("dang dung san o safe %s cua bai train %s -> DUNG YEN", self.khoi)
        self.assertIn("dang o bai train %s -> ra safe %s dung cho, ", self.khoi)

    def test_acc_da_tat_thi_khong_tinh(self):
        self.assertIn('not getattr(_uc, "running", False)', self.than)

    def test_loi_doc_khong_lam_sap(self):
        self.assertIn("except Exception as e:", self.than)


if __name__ == "__main__":
    unittest.main()
