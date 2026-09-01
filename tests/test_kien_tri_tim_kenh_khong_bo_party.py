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


class TestPickerKienTri(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("if r is None:   # co kenh nhung khong kenh nao du cho ca party")
        self.assertGreater(i, 0)
        self.khoi = s[i:i + 1400]

    def test_KHONG_con_cho_cung_60s(self):
        self.assertNotIn("time.sleep(60)", self.khoi)

    def test_thu_lai_moi_10_15s_NGAU_NHIEN(self):
        """Co dinh 60s thi cham; co dinh bat ky con lam moi party hoi lai cung nhip roi cung nhay
        vao dung mot kenh vua trong ra."""
        self.assertIn("random.uniform(10.0, 15.0)", self.khoi)

    def test_van_giu_3s_trong_30s_dau(self):
        self.assertIn("3.0 if time.time() - t0 <= 30", self.khoi)

    def test_bao_NHIP_TIM_moi_vong_cho(self):
        self.assertIn("_nhip_cho_kenh(st)", self.khoi)

    def test_KHONG_gom_ca_party_ve_kenh_leader(self):
        """User chot: don cung khong du cho, chi lam ca lu chen vao mot kenh dang day."""
        self.assertNotIn("current_channel", self.khoi)

    def test_picker_bao_nhip_moi_vong_lap_sync(self):
        s = _src()
        i = s.find("_nhip_cho_kenh(st)   # con song va con dang tim kenh")
        self.assertGreater(i, 0, "picker khong bao nhip o dau vong lap -> member cat oan")


class TestMemberChoTheoNhip(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("CHO_KENH_CAP = 90.0")
        self.assertGreater(i, 0)
        self.khoi = s[i:i + 3000]

    def test_han_do_theo_NHIP_TIM_khong_theo_dong_ho(self):
        self.assertIn('float(st.get("kenh_nhip") or 0.0)', self.khoi)
        self.assertIn("time.time() - max(_t_cho_kenh, _nhip) > CHO_KENH_CAP", self.khoi)

    def test_ca_HAI_cho_cat_deu_dung_nhip(self):
        """Co hai cho member bo cho (vong ngoai + vong `channel_ready.wait`); bo sot mot cho la
        van cat oan nhu cu."""
        self.assertEqual(self.khoi.count("if _het_kien_nhan():"), 2)
        self.assertNotIn("time.time() - _t_cho_kenh > CHO_KENH_CAP", self.khoi)

    def test_VAN_con_han_khi_picker_chet_han(self):
        """Bo han hoan toan = quay lai bug party 14 (member treo 11 phut cho picker da chet)."""
        self.assertIn("CHO_KENH_CAP = 90.0", self.khoi)
        self.assertIn("return False", self.khoi)

    def test_van_thoat_duoc_khi_HET_GIO_DG(self):
        self.assertIn("_finish_digioi_train_if_time_over", self.khoi)


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
