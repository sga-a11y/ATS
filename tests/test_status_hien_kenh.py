# -*- coding: utf-8 -*-
"""Cot "Kenh" tren bang phai hien kenh THAT cua tung acc.

Truoc day lay st["channel"] = kenh party CHON: bi clear moi vong sync nen cot gan nhu luon "-",
va giong het nhau moi acc. Hau qua: vu lech kenh (log 17:25 - leader kenh 2, member kenh 1) nhin
tren bang khong ra, phai doc log moi biet.
"""
import unittest


class TestStatusHienKenh(unittest.TestCase):
    def _lay_kenh(self, kenh_that, kenh_party):
        import run_party_digioi as R
        st = {"channel": kenh_party}
        c = type("C", (), {"current_channel": kenh_that})()
        # dung DUNG bieu thuc trong account_status (neo lai de doi code la test do)
        return getattr(c, "current_channel", None) or st.get("channel")

    def test_uu_tien_kenh_that_cua_acc(self):
        self.assertEqual(self._lay_kenh(2, None), 2)
        self.assertEqual(self._lay_kenh(1, 5), 1, "kenh that phai thang kenh party chon")

    def test_chua_doc_duoc_thi_lui_ve_kenh_party(self):
        self.assertEqual(self._lay_kenh(None, 5), 5)

    def test_bieu_thuc_con_nguyen_trong_account_status(self):
        """Neo THANG vao ma nguon: doi bieu thuc ma quen test thi bai nay do."""
        import io
        src = io.open("run_party_digioi.py", encoding="utf-8").read()
        self.assertIn('"channel": getattr(c, "current_channel", None) or st.get("channel"),', src)


if __name__ == "__main__":
    unittest.main()
