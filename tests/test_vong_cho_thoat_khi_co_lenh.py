"""ACC KHONG CO VONG TU CHO CAP PARTY NAO NUA.

User 13/09: "bo het acc tu quyet cho t, dung va vo van nua, lenh dieu phoi la tuyet doi"
         -> "van cho acc tu quyet ma ko theo dieu phoi".

Cau thu hai la sau khi t thu hai cach VA:
  1. de nguyen vong cho, gan them cua thoat khi `reform_gen` doi;
  2. de nguyen vong cho, chuyen viec DEM sang cho dieu phoi (`st["cho_daily"]`).
Ca hai deu sai cung mot kieu: acc VAN DUNG YEN CHO, chi doi nguoi dat dieu kien. Cai phai bo la
HANH DONG TU CHO, khong phai do dai hay chu so hu cua no.

HAI VONG DA XOA (13/09), deu cua LEADER:

  a) barrier login-dailies: `while True` cho den khi `dailies_done >= min(expected, _con_cho)`.
     Party 48, 08/09 (user: "bon no ko lap pt"):
       06:52:36 [dtmot] (LEADER) CHO ca party xong daily (2/5, reconnecting=0)...
       06:53:37 [dtmot] (LEADER) CHO ca party xong daily (2/5, reconnecting=0)...
       06:52:51 [party 48] viec=moi - DOI chua du (dt901=4 dt902=0 dt903=0 dt904=4 dt905=0)

  b) `while _dem_san_sang(pidx) < st["n_members"]`: leader tu dinh nghia "du san sang" roi cho,
     VA trong luc cho con tu goi `_do_reform(to_spot=False)` moi khi qua `READY_WAIT_REFORM_SEC`
     / `READY_WAIT_SPLIT_SEC` - tu chon ca thoi diem gom.

GIO: leader MOI luon. Thieu nguoi / lech map / lech kenh la viec dieu phoi doc moi 2 giay va ra
lenh theo dung chuoi user chot: gom map -> gom kenh -> moi -> di train -> ra diem quai.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _ma(s):
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    return re.sub(r"#.*", "", s)


class TestKhongConVongTuCho(unittest.TestCase):
    def setUp(self):
        self.ma = _ma(_src())

    def test_khong_con_barrier_daily(self):
        self.assertNotIn('st["dailies_done"] + len(', self.ma,
                         "leader lai tu dem va tu cho ca party xong daily")

    def test_khong_con_vong_cho_member_san_sang(self):
        self.assertNotIn('while _dem_san_sang(pidx) < st["n_members"]:', self.ma)

    def test_khong_thay_bang_cua_thoat(self):
        """Ban va thu nhat: giu vong, them loi ra theo `reform_gen`. Van la vong cho."""
        self.assertNotIn("_co_lenh_moi", self.ma)

    def test_khong_thay_bang_co_cua_dieu_phoi(self):
        """Ban va thu hai: giu vong, de dieu phoi dem ho. Van la vong cho."""
        self.assertNotIn("cho_daily", self.ma)
        self.assertNotIn("_con_lam_daily", self.ma)

    def test_khong_con_nguong_tu_gom_khi_lech_map(self):
        """`READY_WAIT_SPLIT_SEC` = leader tu chon luc nao gom party lech map."""
        self.assertNotIn("READY_WAIT_SPLIT_SEC", self.ma)


class TestLeaderMoiLuon(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_moi_ngay_khong_cho_du_san_sang(self):
        i = self.src.find("member san sang -> MOI (theo entity)")
        self.assertGreater(i, 0, "mat moc leader di moi party")
        self.assertIn("dieu phoi gom", self.src[i:i + 300],
                      "khong ghi ro thieu nguoi thi ai lo")

    def test_khong_tu_reform_trong_luc_moi(self):
        """Doan tu luc vao nhanh leader den luc goi moi: khong duoc tu ra lenh gom."""
        i = self.src.find("(LEADER) toi train map theo party NHUNG chi con")
        j = self.src.find("member san sang -> MOI (theo entity)", i)
        self.assertGreater(j, i)
        self.assertNotIn("_do_reform", _ma(self.src[i:j]),
                         "leader lai tu ra lenh gom truoc khi moi")


class TestChuoiLenhVanDuBac(unittest.TestCase):
    """Xoa vong cho thi chuoi cua dieu phoi phai con nguyen - do la thu thay the no."""

    def setUp(self):
        self.src = _src()

    def test_du_bon_bac(self):
        i_map = self.src.find("elif song and len(maps) > 1:")
        i_kenh = self.src.find("elif song and len(kenhs) > 1 and _thieu_doi(pidx, song):")
        i_moi = self.src.find("elif song and _thieu_doi(pidx, song):")
        for _t, _i in (("gom map", i_map), ("gom kenh", i_kenh), ("moi", i_moi)):
            self.assertGreater(_i, 0, "mat bac " + _t)
        self.assertLess(i_map, i_kenh)
        self.assertLess(i_kenh, i_moi)

    def test_khong_chen_dieu_kien_phu_truoc_bac_moi(self):
        """Chen them dieu kien vao bac MOI = dung lai cai vong cho duoi dang khac."""
        i = self.src.find("elif song and _thieu_doi(pidx, song):")
        self.assertEqual(self.src[i:i + 40].strip(),
                         "elif song and _thieu_doi(pidx, song):")


if __name__ == "__main__":
    unittest.main()
