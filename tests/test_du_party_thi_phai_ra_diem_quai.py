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






if __name__ == "__main__":
    unittest.main()
