"""Server DA LOAT ca party -> gian nhip login, khong de 5 acc vao trong 6 giay.

Do tren party.log 31/08 (party 1, 38 lan rot ca ngay):
  - 6 lan CA PARTY rot trong CUNG MOT GIAY: 16:41:07 va 17:45:48 (4 acc), 17:55:30 (3 acc),
    13:37:40 va 16:48:47 (2 acc) - deu `ma 61` (thong bao rieng cua server).
  - 2 chum `ma 90` (DANG NHAP QUA THUONG XUYEN) ngay sau do: 15:09:36-42 va 17:09:53-59, moi chum
    5 acc login lot trong 6 giay.
Nhanh gian cu CHI chay khi `forced` (bot tu ep ca party relogin). Server da loat thi
`forced=False`, moi acc dung chung `wait = 5` -> vao cung luc -> dinh 90 -> backoff
`30 * attempt` (toi 300s) cho CA 5 acc.
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


class TestGianLogin(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("wait = 1 if forced else (5 if attempt <= 3")
        self.assertGreater(i, 0, "mat cong thuc backoff relogin")
        self.than = re.sub(r"#.*", "", s[i:i + 2200])
        self.src = s

    def test_KHONG_con_chi_gian_khi_forced(self):
        self.assertNotIn("if forced:\n            try:\n                _order = ", self.than,
                         "van chi gian khi bot tu ep -> server da loat thi ca party van vao cung luc")

    def test_dau_hieu_la_NHIEU_ACC_DANG_ROT(self):
        self.assertIn('len(st["reconnecting"])', self.than,
                      "khong dem so acc dang rot thi khong biet la bi da loat")
        self.assertIn("_dang_rot >= 2", self.than)

    def test_buoc_gian_cho_server_da_loat_LON_HON_forced(self):
        m = re.search(r"_gian_buoc = (\d+) if forced else \((\d+) if _dang_rot >= 2 else 0\)",
                      self.than)
        self.assertIsNotNone(m, "cong thuc buoc gian doi dang - kiem lai")
        forced_buoc, loat_buoc = int(m.group(1)), int(m.group(2))
        self.assertEqual(forced_buoc, 3, "nhanh forced dang chay tot, khong doi")
        self.assertGreater(loat_buoc, forced_buoc,
                           "5 acc trong 6s DA dinh ma 90 -> buoc 3s van qua sat")

    def test_trai_du_de_5_acc_khong_lot_trong_6_giay(self):
        m = re.search(r"else \((\d+) if _dang_rot >= 2 else 0\)", self.than)
        buoc = int(m.group(1))
        self.assertGreater(buoc * 1, 6, "acc thu hai phai cach acc dau hon 6s")

    def test_thu_tu_theo_VI_TRI_trong_party(self):
        """Cach duy nhat khong dung nhau ma khong can khoa: moi acc mot cho co dinh."""
        self.assertIn("_order.index(username)", self.than)
        self.assertIn("party_accounts(pidx)", self.than)

    def test_acc_dau_tien_KHONG_bi_gian(self):
        self.assertIn("if _them:", self.than, "acc index 0 phai vao ngay, khong cong them gi")

    def test_KHONG_dung_toi_backoff_ma_90(self):
        """`30 * attempt` cho ma 90 la luat rieng - gian nhip khong duoc de len."""
        i = self.src.find("_cause == DISCONNECT_RATE_LIMIT")
        self.assertGreater(i, 0)
        self.assertIn("wait = max(wait, min(30 * attempt, 300))", self.src[i:i + 300])

    def test_co_LOG_khi_gian(self):
        self.assertIn("relogin HANG LOAT", self.src,
                      "gian im lang -> lan sau doc log khong hieu vi sao acc vao muon")


if __name__ == "__main__":
    unittest.main()
