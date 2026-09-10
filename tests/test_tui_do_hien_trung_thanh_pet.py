"""TUI DO - dong "Chi so" cua pet phai co DO TRUNG THANH.

User chot 07/09: "trong tui do, cho chi so pet, m them do trung thanh cua con pet do vao".

Bot da doc san: `client.pet_faith[pid]` (byte +27 cua ban ghi trong goi pet list `0x0f`), va
`run_party_digioi.TRUNG_THANH_CANH_BAO = 40` la nguong canh bao dang dung o bang chinh - dung lai
cung mot nguong de hai cho khong noi khac nhau.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src(ten="gui.py"):
    with io.open(os.path.join(ROOT, ten), encoding="utf-8") as fh:
        return fh.read()


class TestHienTrungThanh(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find('phan.append("★ đang xuất chiến")')
        self.assertGreater(i, 0, "khong tim thay dong chi so pet")
        self.khoi = s[max(0, i - 1400):i + 200]

    def test_co_hien_trung_thanh(self):
        self.assertIn("Trung thành", self.khoi)

    def test_doc_tu_pet_faith_cua_client(self):
        """Doc THANG tu client - khong bat acc bao cao, khong tu tinh lai."""
        self.assertIn('getattr(c, "pet_faith", None)', self.khoi)

    def test_tra_pid_theo_carried_pets(self):
        """`pet_faith` khoa theo pet_id, con `who` la followIndex 1..4 -> phai tra qua carried_pets."""
        self.assertIn("carried_pets", self.khoi)
        self.assertIn("int(who) - 1", self.khoi)

    def test_canh_bao_khi_thap(self):
        self.assertIn("TRUNG_THANH_CANH_BAO", self.khoi)

    def test_dung_CHUNG_nguong_voi_bang_chinh(self):
        """Hai cho hien hai nguong khac nhau thi user doc ra hai su that khac nhau."""
        r = _src("run_party_digioi.py")
        i = r.find("TRUNG_THANH_CANH_BAO = ")
        self.assertGreater(i, 0)
        self.assertNotIn("40)", self.khoi.replace('getattr(ctrl, "TRUNG_THANH_CANH_BAO", 40)', ""),
                         "hardcode nguong rieng thay vi dung hang so chung")

    def test_thieu_du_lieu_thi_KHONG_hien_bua(self):
        """Acc chua nhan goi 0x0f -> khong co pet_faith. Hien '0' la noi sai (0 = phan boi)."""
        self.assertIn("if _tt is not None:", self.khoi)


if __name__ == "__main__":
    unittest.main()
