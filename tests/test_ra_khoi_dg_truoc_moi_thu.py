"""`go_to_town`: RA KHOI DI GIOI truoc MOI nhanh `return False`.

Hai nhanh bo cuoc som ("khong phai thanh teleport" / "thanh CHUA MO tele") nam TRUOC buoc ra DG
-> acc KET LAI TRONG DI GIOI vinh vien. DG co gio va day quai; doi thanh khac cung khong ai keo
no ra vi ham da return roi.

Log 01/09 party 49 (gclmmot/gclmhai/gclmba/gclmbon/gclmnam), xong DG luc 09:41:04:
    09:41:04 go_to_town: thanh 12061 CHUA MO tele -> bo qua ngay (khong spam)
    09:41:09 (member) KHONG co bot-leader -> dung yen tai safe (kenh 4)
roi ca 5 acc dung im o (870,740) TRONG map 49942 (user: "sao mai no ko chiu di ra ngoai DG").
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRaKhoiDGTruoc(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("    def go_to_town(")
        self.assertGreater(i, 0)
        self.khoi = s[i:s.find("\n    def ", i + 10)]
        self.than = re.sub(r"#.*", "", self.khoi)

    def test_goi_exit_di_gioi(self):
        self.assertIn("self.exit_di_gioi()", self.than)

    def test_chay_TRUOC_moi_nhanh_bo_cuoc(self):
        i_dg = self.than.find("self.exit_di_gioi()")
        self.assertGreater(i_dg, 0)
        for nhanh in ('is_teleport_city', 'self.city_unlocked(city_id) is False'):
            i = self.than.find(nhanh)
            self.assertGreater(i, 0, "mat nhanh %s" % nhanh)
            self.assertLess(i_dg, i, "ra DG chay SAU nhanh '%s' -> ket trong DG" % nhanh)

    def test_CHI_goi_MOT_LAN(self):
        """Truoc day co doan thu hai o giua ham; de ca hai la di ra 2 lan."""
        self.assertEqual(self.than.count("self.exit_di_gioi()"), 1)

    def test_van_giu_chot_KHONG_teleport_khi_van_o_DG(self):
        """Ra khong duoc thi van phai chan teleport (goi vo ich + spam)."""
        self.assertIn("go_to_town: VAN dang o Di Gioi", self.khoi)

    def test_van_giu_chot_instance(self):
        self.assertIn("in_instance_map(self.current_map)", self.than)


if __name__ == "__main__":
    unittest.main()
