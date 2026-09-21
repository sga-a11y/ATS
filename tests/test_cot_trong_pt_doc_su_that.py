"""Cot "Trong PT" phai doc ROSTER THAT, khong doc so tu ghi cua bot.

Ca that 21/09 party 34 (user: "moi dua 1 kenh, nhung vi sao lai bao dang o trong pt"): bang hien
kenh 5/10/14/8/10 - moi acc mot kenh - ma cot "Trong PT" van tich xanh 4 dua.

Doi kenh la PHAI roi doi truoc (server tra `result=3` neu con trong doi - xem
`_prepare_channel_switch`), nen khac kenh thi chac chan KHONG con chung doi. Cot do dang noi
nguoc lai su that, va do la cot user nhin de biet party con nguyen hay khong.

Goc: `is_joined()` doc `_PARTY_JOINED` - SO TU GHI cua bot ("acc nay da bam accept"). So khong
tu xoa khi server da acc ra khoi doi. Cung mot bai hoc voi cot "Kenh" ngay ben tren trong cung
ham do, va voi `in_team_dungeon()` (sua 14/09): hoi TRANG THAI THAT, dung hoi moc/so bot ghi ra.
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


class TestDocRosterThat(unittest.TestCase):
    def setUp(self):
        s = _src()
        # Co HAI cho: khoi mac dinh (acc chua chay) va khoi that. Lay khoi THAT - no nam sau
        # `"log_label"` trong cung dict.
        j = s.find('"log_label":')
        self.assertGreater(j, 0)
        i = s.find('"in_party":', j)
        self.assertGreater(i, 0, "khong tim thay cot in_party")
        self.dong = s[i:i + 300]

    def test_doc_party_members_hoac_party_leader(self):
        self.assertIn("party_members", self.dong)
        self.assertIn("party_leader", self.dong)

    def test_KHONG_doc_so_is_joined(self):
        self.assertNotIn("is_joined(", self.dong,
                         "so tu ghi khong tu xoa khi server da acc ra khoi doi")

    def test_acc_tat_thi_KHONG_bao_dang_trong_pt(self):
        self.assertIn("if running else False", self.dong)


class TestCotKenhVanDocKenhThat(unittest.TestCase):
    """Cot ben canh da hoc dung bai nay tu truoc - giu lai de khong ai lui ve `st["channel"]`."""

    def test_kenh_doc_tu_client(self):
        s = _src()
        j = s.find('"log_label":')
        i = s.find('"channel":', j)
        self.assertGreater(i, 0)
        self.assertIn("current_channel", s[i:i + 200])


if __name__ == "__main__":
    unittest.main()
