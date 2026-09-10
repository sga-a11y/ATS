"""SAFE BI QUAI DANH -> BAO vao o "Chu y", KHONG tu doi safe, KHONG tu quet lai map.

Diem safe la cho DUNG NGHI giua cac tran. No duoc HOC bang
`nearest_walkable_outside(clearance=200, max_path=600)` - tuc chi cach cac VET TUAN TRA DA QUAN SAT
DUOC 200 don vi, ma lan quet co the chua thay het duong quai di. Hoc sai thi acc dung do chiu tran
vo han, khong co gi phat hien ra.

Ca that 07/09 party 3, map 21852 (Trai Di Lang2):
    safe[2] = (2090, 1170)      mob[2] = (1830, 1250)      cach nhau 272
    ca 5 acc login ve dung safe do -> 147 luot `combat=True` tai (2090,1170) trong 19 phut,
    vi tri chi dao dong 20 don vi - khong he chay di dau.

User chot 07/09: "t doi diem safe do sang toa do khac roi, m ko can scan lai map, chi can them cai
la neu dung o safe ma van bi danh qua nhieu thi m ban thong bao cho tao de tao tu check lai, chu t
deo tin may scan lai la on" + "ban thong bao la cho vao cai CHU Y ay nhe" + "tinh nang chung cho
tat ca cac map nhe".

=> Bot CHI DEM va BAO. Khong tu doi safe, khong tu rescan.
"""
from __future__ import annotations

import io
import os
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _src(ten):
    with io.open(os.path.join(ROOT, ten), encoding="utf-8") as fh:
        return fh.read()


class TestDemTranTaiSafe(unittest.TestCase):
    U = "acc_test_safe"
    SAFE = [2090, 1170]

    def setUp(self):
        R.account_safe_canh_bao.pop(self.U, None)

    tearDown = setUp

    def _danh(self, n, pos=None, safe=None, map_id=21852):
        for _ in range(n):
            R._ghi_nhan_tran_tai_safe(self.U, map_id, pos or self.SAFE, safe or self.SAFE)

    def test_duoi_nguong_thi_CHUA_bao(self):
        self._danh(R.SAFE_DANH_NGUONG - 1)
        rec = R.account_safe_canh_bao[self.U]
        self.assertEqual(rec["so_tran"], R.SAFE_DANH_NGUONG - 1)
        self.assertFalse(rec["lan_bao"], "bao som -> user bi lam phien vi vai tran binh thuong")

    def test_qua_nguong_thi_BAO(self):
        self._danh(R.SAFE_DANH_NGUONG)
        rec = R.account_safe_canh_bao[self.U]
        self.assertGreater(rec["lan_bao"], 0)
        self.assertEqual(rec["safe"], self.SAFE)
        self.assertEqual(rec["map"], 21852)

    def test_danh_o_XA_safe_thi_khong_tinh(self):
        """Tran o BAI QUAI la binh thuong - chi dem tran xay ra NGAY TAI cho nghi."""
        self._danh(R.SAFE_DANH_NGUONG * 2, pos=[1830, 1250])
        self.assertNotIn(self.U, R.account_safe_canh_bao)

    def test_doi_safe_thi_dem_LAI_TU_DAU(self):
        self._danh(R.SAFE_DANH_NGUONG - 1)
        R._ghi_nhan_tran_tai_safe(self.U, 21852, [500, 500], [500, 500])
        self.assertEqual(R.account_safe_canh_bao[self.U]["so_tran"], 1)

    def test_doi_MAP_thi_dem_LAI_TU_DAU(self):
        self._danh(R.SAFE_DANH_NGUONG - 1)
        R._ghi_nhan_tran_tai_safe(self.U, 23872, self.SAFE, self.SAFE)
        self.assertEqual(R.account_safe_canh_bao[self.U]["so_tran"], 1)

    def test_qua_CUA_SO_thoi_gian_thi_dem_lai(self):
        """Vai tran roi rac trong ca buoi khong phai la 'safe hong'."""
        self._danh(R.SAFE_DANH_NGUONG - 1)
        R.account_safe_canh_bao[self.U]["tu_luc"] = time.time() - R.SAFE_DANH_CUA_SO - 5
        R._ghi_nhan_tran_tai_safe(self.U, 21852, self.SAFE, self.SAFE)
        self.assertEqual(R.account_safe_canh_bao[self.U]["so_tran"], 1)

    def test_thieu_du_lieu_thi_bo_qua(self):
        for a in ((None, self.SAFE, self.SAFE), (21852, None, self.SAFE),
                  (21852, self.SAFE, None)):
            R._ghi_nhan_tran_tai_safe(self.U, *a)
        self.assertNotIn(self.U, R.account_safe_canh_bao)

    def test_bo_qua_thi_xoa_canh_bao(self):
        self._danh(R.SAFE_DANH_NGUONG)
        R.safe_canh_bao_bo_qua(self.U)
        self.assertNotIn(self.U, R.account_safe_canh_bao)


class TestKHONG_tu_sua(unittest.TestCase):
    """User chot: chi BAO. Tu doi safe / tu rescan la lam trai y."""

    def test_khong_tu_doi_safe(self):
        s = _src("run_party_digioi.py")
        i = s.find("def _ghi_nhan_tran_tai_safe(")
        than = s[i:s.find("\ndef ", i + 10)]
        for cam in ("train_safes[", "save_learned_regions", "rally_point\"] ="):
            self.assertNotIn(cam, than, cam)

    def test_khong_tu_danh_dau_rescan(self):
        s = _src("run_party_digioi.py")
        i = s.find("def _ghi_nhan_tran_tai_safe(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertNotIn("rescan", than)


class TestVaoOChuY(unittest.TestCase):
    def test_GUI_lay_tu_safe_canh_bao_items(self):
        g = _src("gui.py")
        i = g.find("def _party_notify_items(")
        self.assertGreater(i, 0)
        self.assertIn("ctrl.safe_canh_bao_items(pidx)", g[i:i + 1600])

    def test_GUI_co_dong_hien_thi_va_nut_bo_qua(self):
        g = _src("gui.py")
        i = g.find('if it.get("_safe_danh"):')
        self.assertGreater(i, 0, "khong co dong hien trong o Chu y")
        khoi = g[i:i + 1600]
        self.assertIn("ctrl.safe_canh_bao_bo_qua(", khoi)
        self.assertIn("ĐIỂM SAFE BỊ QUÁI ĐÁNH", khoi)

    def test_xep_vao_loai_CAN_LAM_NGAY(self):
        g = _src("gui.py")
        i = g.find("NOTIFY_CAM = (")
        self.assertGreater(i, 0)
        self.assertIn("_safe_danh", g[i:i + 120])


class TestDemTheoCANH_LEN(unittest.TestCase):
    def test_khong_dem_moi_nhip(self):
        """Mot tran keo dai nhieu nhip keepalive - dem moi nhip thi vai tran da vuot nguong."""
        s = _src("run_party_digioi.py")
        i = s.rfind("_ghi_nhan_tran_tai_safe(username,")   # CHO GOI, khong phai dinh nghia
        self.assertGreater(i, 0)
        khoi = s[max(0, i - 700):i]
        self.assertIn("if _bt_now and not _bt_truoc:", khoi)


if __name__ == "__main__":
    unittest.main()
