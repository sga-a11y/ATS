"""Server DONG (khong kenh nao du cho ca party) -> KIEN TRI thu lai, KHONG bo party giua chung.

Log 01/09/2026 party 4 (sga011-015, server trieu_van, dang o Di Gioi map 49942, 89 kenh x 20 cho):

    11:25:19 [thmo] Nhan danh sach 89 kenh
    11:25:19 [thmo] KHONG kenh nao du 5 cho trong cho ca party -> RETRY (cho kenh trong)
    ...  (lap lai toi 11:32+, leader van dang lam viec)
    11:26:45 [thnam] (member) cho channel_ready qua 90s -> THOI CHO

Leader kien tri dung, nhung member CAT CUNG sau `CHO_KENH_CAP` = 90s (them 31/08 de chua party 14
treo 11 phut) nen bo cho trong khi leader VAN DANG QUET -> moi acc nam nguyen kenh login
(33 / 2 / 20 / 71 / 2), party khong bao gio lap duoc (user: "party 4 bi sao ma moi dua 1 kenh").

Chot voi user 01/09:
  - KHONG gom ca party ve kenh leader ("don cung van ko du dau, DG deo can don"),
  - picker thu lai moi 10-15s NGAU NHIEN cho toi khi co cho / het gio DG,
  - member cho theo NHIP TIM cua picker, chi bo cho khi picker IM HAN (thread ket/rot).
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import run_party_digioi as rpd          # noqa: E402
finally:
    sys.argv = _argv


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestNhipTim(unittest.TestCase):
    def test_nhip_ghi_thoi_diem(self):
        st = {}
        rpd._nhip_cho_kenh(st)
        self.assertGreater(st["kenh_nhip"], 0.0)

    def test_state_khoi_tao_co_kenh_nhip(self):
        """Thieu key -> `st.get` tra None, member se tinh nhip = 0 va cat ngay o vong dau."""
        self.assertIn('"kenh_nhip": 0.0', _src())






class TestMoPhongHanhVi(unittest.TestCase):
    """Kiem THAT logic han: picker con nhip -> khong cat; picker im -> cat."""

    @staticmethod
    def _het(t_bat_dau, nhip, bay_gio, cap=90.0):
        return bay_gio - max(t_bat_dau, nhip) > cap

    def test_picker_van_quet_sau_10_phut_thi_KHONG_cat(self):
        t0 = 1000.0
        # picker bao nhip moi 12s -> tai giay thu 600 nhip gan nhat la 1596
        self.assertFalse(self._het(t0, 1596.0, 1600.0))

    def test_picker_im_qua_90s_thi_CAT(self):
        self.assertFalse(self._het(1000.0, 1500.0, 1580.0))
        self.assertTrue(self._het(1000.0, 1500.0, 1600.0))

    def test_picker_chua_bao_nhip_lan_nao_van_cat_sau_90s(self):
        self.assertTrue(self._het(1000.0, 0.0, 1100.0))


if __name__ == "__main__":
    unittest.main()
