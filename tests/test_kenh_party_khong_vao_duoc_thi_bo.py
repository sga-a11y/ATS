"""Kenh CHOT cua party khong vao duoc (result 2/4) -> BO kenh do, chon lai.

Log 31/08 party 1 (13:33-13:49), `st["channel"] = 3`:
    13:48:08 [sieugaaa] Doi kenh 3 THAT BAI: khong co khu do de doi (result=2)
    13:48:09 [sieugaaa] (LEADER) tu kiem kenh: chua ve duoc kenh party 3 (nho san 1) -> van moi
    13:41:59 [minh]   (member) khong doi duoc sang kenh chung 3 (result=2) -> bao leader pick lai
    13:33:40 [tuyet]  (member) khong doi duoc sang kenh chung 3 (result=2) -> bao leader pick lai
    13:41:33 [chihao] (member) khong doi duoc sang kenh chung 3 (result=2) -> bao leader pick lai
Ba member sau do nam cho `channel_ready` (khong ai set lai) nen `party_invite_ready` khong mo,
chi con lap "Chua san sang vao party -> GIU loi moi"; leader moi 13s/lan suot 16 phut voi
`da join=1 | roster server=1`.

Kenh khong ton tai / da day thi cho mai cung khong vao duoc - phai bo va chon kenh khac.
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


class TestKenhPartyKhongVaoDuoc(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _leader_tu_kiem_kenh(")
        self.assertGreater(i, 0)
        j = s.find("\ndef _invite_party_participants(", i)
        self.assertGreater(j, i)
        self.khoi = s[i:j]
        self.than = re.sub(r"#.*", "", self.khoi)

    def test_phan_biet_ma_2_va_4(self):
        self.assertIn('_res = getattr(c, "_chan_switch_result", None)', self.than,
                      "khong doc ma loi -> coi moi that bai nhu nhau, giu ca kenh khong ton tai")
        self.assertIn("if _res in (2, 4):", self.than)

    def test_BO_kenh_hong_va_bao_dong_bo_lai(self):
        i = self.than.find("if _res in (2, 4):")
        khoi = self.than[i:i + 600]
        self.assertIn('st["channel"] = None', khoi, "khong bo kenh -> vong sau lai chot dung kenh do")
        self.assertIn('st["channel_ready"].clear()', khoi,
                      "khong clear -> member doc lai dung kenh hong cu")
        self.assertIn("_bump_reform(st)", khoi, "khong bao ai dong bo lai thi khong ai chon kenh moi")

    def test_loi_KHAC_thi_van_khong_chan_moi_party(self):
        """Timeout / loi tam thoi thi cu moi tiep, khong duoc dap kenh dang dung."""
        self.assertIn("else:", self.than)
        self.assertIn("van moi, vong sau kiem lai", self.khoi)


if __name__ == "__main__":
    unittest.main()
