"""`_party_tai_cho_xu_ly`: DOC LAI map/kenh sau vong cho rally, khong dung so doc tu truoc.

So kenh duoc doc o DAU ham, roi ham cho ca party ra diem tap ket (`_cho_ca_party_ve_rally`, cap
hang chuc giay). Trong lung do moi nguoi doi kenh xong het -> so cu thanh rac, nhung nhanh re van
chay theo so cu.

Log 31/08 (party 16), user chon kenh 1 bang lenh tay:
    09:57:33 (LEADER) bao CA PARTY ra diem tap ket ...   <- doc tinh hinh o day: member con kenh cu
    09:57:40 [chu702..705] Doi kenh OK -> 1              <- CA 5 acc da o kenh 1
    09:57:41 (LEADER) ca party DA o map train 21811 nhung LECH KENH -> chi sync kenh tai cho
    09:58:22 [chu701] Kenh it nguoi MA DU CHO ca party (5): kenh 2 -> chuyen sang
=> di nham nhanh "lech kenh" roi sync kenh TU CHON kenh 2, bo kenh user vua chon.
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


class TestDocLaiKenhSauKhiGom(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _party_tai_cho_xu_ly(")
        self.assertGreater(i, 0)
        j = s.find("\n        def ", i + 10)
        self.assertGreater(j, i)
        self.khoi = s[i:j]
        self.than = re.sub(r"#.*", "", self.khoi)

    def test_doc_tinh_hinh_la_ham_dung_lai_duoc(self):
        self.assertIn("def _doc_tinh_hinh():", self.than,
                      "van doc mot lan roi dung mai -> so kenh cu tha ho lam sai nhanh re")
        self.assertGreaterEqual(self.than.count("_doc_tinh_hinh()"), 2,
                                "chi goi 1 lan = khong he doc lai")

    def test_doc_LAI_SAU_vong_cho_rally(self):
        i_cho = self.than.find("_cho_ca_party_ve_rally(")
        i_lai = self.than.find("_tinh_moi = _doc_tinh_hinh()")
        i_re = self.than.find('if _tinh == "lech_kenh":')
        self.assertGreater(i_cho, 0)
        self.assertGreater(i_lai, i_cho, "doc lai phai SAU vong cho rally")
        self.assertGreater(i_re, i_lai, "doc lai phai TRUOC khi re nhanh lech_kenh")

    def test_KHONG_de_ep_doi_kenh_bi_doc_lai_xoa(self):
        """`ep_doi_kenh` la ket luan 'cung so kenh ma khong thay nhau' - doc lai chi ra 'cung_kenh'
        nhu cu, ghi de la quay ve dung kenh hong."""
        self.assertIn("if not ep_doi_kenh:", self.than)

    def test_lech_map_sau_khi_doc_lai_van_ve_thanh(self):
        i = self.than.find("_tinh_moi = _doc_tinh_hinh()")
        self.assertIn('if _tinh == "lech_map":', self.than[i:i + 700],
                      "doc lai ra lech_map ma van chay tiep tai cho")


if __name__ == "__main__":
    unittest.main()
