"""DU party ma KHONG DANH -> hoi VI TRI HIEN TAI, dung sai cho thi ra diem quai.

Rule user (30/08): check vi sao no khong danh ->
    - khong du party  -> tim cach lap lai party   (nhanh cu, khong doi)
    - du party ma khong danh -> XEM VI TRI HIEN TAI

Su co party 3 (30/08 14:33-14:41+):
    14:33:44 (LEADER) DU PARTY (4/4 member join)
    14:33:45 (LEADER) reform pending (acc bi dump dungeon) -> BO QUA keo ra spot, de keepalive REFORM
    14:33:50..14:41  (LEADER) pos=(1520, 400) map=23821 combat=False   <- dung safe, khong danh gi

Ba lo hong nam canh nhau:
  1. `_start_training()` `return` giua chung nhung caller van gan `training_started = True`
     -> vong retry 60s (`if ... and not training_started`) KHONG BAO GIO chay.
  2. Chot bail so `st["reform_gen"]` voi `_rg_base` - moc chup TRUOC pho ban - nen mot khi da
     bump la dung MAI MAI; con reform that thi bi nuot ngay sau do (reform_gen_handled = gen
     hien tai vi leader dang dung dung map train). Khong ai cuu -> ket vinh vien.
  3. `flee_mode` bat len o nhanh "MAT PARTY -> GOM LAI" nhung khong cho nao ha xuong khi party
     day lai -> dung DUNG diem quai van bo chay.

Cach xu: bam VI TRI THAT thay vi co trang thai. KHONG ve thanh (ca party dang cung map+kenh, chi
thieu moi buoc di ra spot).
"""
from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import run_party_digioi as R
finally:
    sys.argv = _argv


def _doc(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestXaDiemQuai(unittest.TestCase):
    def test_dung_dung_spot_khong_phai_xa(self):
        self.assertFalse(R._xa_diem_quai((1200, 800), (1200, 800)))

    def test_trong_bien_do_jitter_khong_phai_xa(self):
        for d in (-10, 10):
            self.assertFalse(R._xa_diem_quai((1200 + d, 800 + d), (1200, 800)))

    def test_dung_o_safe_la_XA(self):
        """Party 3: safe (1520,400), diem quai o cho khac han."""
        self.assertTrue(R._xa_diem_quai((1520, 400), (1200, 800)))

    def test_chi_lech_mot_truc_van_la_xa(self):
        self.assertTrue(R._xa_diem_quai((1520, 800), (1200, 800)))

    def test_chua_biet_toa_do_thi_KHONG_keo_di(self):
        self.assertFalse(R._xa_diem_quai(None, (1200, 800)))
        self.assertFalse(R._xa_diem_quai((1200, 800), None))


class TestStartTrainingTraKetQua(unittest.TestCase):
    def setUp(self):
        s = _doc("run_party_digioi.py")
        i = s.find("def _start_training(")
        self.assertGreater(i, 0)
        j = s.find("\n            _joined = joined_member_count(pidx)", i)
        self.assertGreater(j, i)
        self.than = s[i:j]

    def test_nhan_co_ep_ra_spot(self):
        self.assertIn("def _start_training(ep_ra_spot=False):", self.than)

    def test_moi_return_deu_co_gia_tri(self):
        """`return` tran = None = caller khong phan biet duoc 'da train' voi 'bail'."""
        self.assertIsNone(re.search(r"^\s*return\s*$", self.than, re.M),
                          "con `return` tran trong _start_training")

    def test_bail_reform_tra_False(self):
        i = self.than.find("reform pending (acc bi dump dungeon)")
        self.assertGreater(i, 0)
        self.assertIn("return False", self.than[i:i + 400])

    def test_ep_ra_spot_bo_qua_chot_reform(self):
        i = self.than.find('if st["reform_gen"] > _rg_base')
        self.assertGreater(i, 0)
        self.assertIn("not ep_ra_spot", self.than[i:i + 120],
                      "khong bo duoc chot -> retry bail lai mai mai, leader ket o safe")

    def test_ket_thuc_tra_True(self):
        self.assertTrue(self.than.rstrip().endswith("return True"),
                        "roi khoi ham ma khong tra gi = None = caller tuong da bail")


class TestVongRetry60s(unittest.TestCase):
    def setUp(self):
        s = _doc("run_party_digioi.py")
        i = s.find("DU PARTY roi ma KHONG DANH")
        self.assertGreater(i, 0, "khong tim thay nhanh 'du party ma khong danh'")
        self.khoi = s[i:i + 4200]
        self.than = re.sub(r"#.*", "", self.khoi)   # chu thich hay lap lai chinh cau lenh
        self.src = s

    def test_lan_dau_gan_theo_ket_qua(self):
        self.assertIn("training_started = bool(_start_training())", self.src)
        self.assertNotIn("_start_training(); training_started = True", self.src)

    def test_bam_vi_tri_chu_khong_bam_training_started(self):
        i_pos = self.than.find("_xa_diem_quai(c.pos")
        self.assertGreater(i_pos, 0, "khong doi chieu vi tri hien tai voi diem quai")
        i_ts = self.than.find("not training_started")
        self.assertTrue(i_ts < 0 or i_pos < i_ts,
                        "van uu tien co trang thai training_started hon vi tri that")

    def test_xa_spot_thi_ep_ra_spot(self):
        i = self.than.find("_xa_diem_quai(c.pos")
        self.assertGreater(i, 0)
        self.assertIn("_start_training(ep_ra_spot=True)", self.than[i:i + 900])

    def test_KHONG_ve_thanh(self):
        """Rule user: cung map thi ra spot luon, ve thanh la sai."""
        self.assertNotIn("_bump_reform", self.than, "ve thanh gom lai = sai rule")
        self.assertNotIn("go_to_town", self.than)

    def test_dung_dung_spot_ma_con_flee_thi_TAT_flee(self):
        i = self.than.find("elif c.flee_mode:")
        self.assertGreater(i, 0, "dung dung diem quai ma bo chay thi khong tran nao xong")
        self.assertIn("c.flee_mode = False", self.than[i:i + 500])

    def test_dang_danh_thi_CHO_HET_TRAN_chu_KHONG_bo_qua_vong(self):
        """`elif not c.in_combat()` lam vong cuu nay KHONG BAO GIO chay: leader dung giua bai voi
        party da du ma chua duoc keo ra spot -> quai vao lien tuc -> vong nao cung bi bo qua.
        Party 44 (30/08) ket dung the 23 phut (21:19 "DU PARTY (4/4)" + "BO QUA keo ra spot"
        -> danh le toi 21:40)."""
        self.assertNotIn("elif not c.in_combat():", self.than,
                         "bo qua vong khi dang danh = khong bao gio cuu duoc")
        i = self.than.find("if c.in_combat():")
        self.assertGreater(i, 0)
        self.assertIn("_wait_combat_clear(", self.than[i:i + 300])
        self.assertLess(i, self.than.find("_xa_diem_quai(c.pos"),
                        "phai cho het tran TRUOC khi quyet dinh keo di")


if __name__ == "__main__":
    unittest.main()
