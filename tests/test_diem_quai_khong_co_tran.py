"""Party dung tai diem quai 240s khong vao tran -> bao "Chu y" (user chot 30/09).

Ca that party 7 + 9, map 23802 diem (290,2390): diem khong co quai, bot DUNG HINH -> gom ve
thanh -> lai chon dung diem do, lap tu 16:23 toi sang hom sau ma khong ai biet.
"""
import os
import sys
import threading
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_party_digioi as rp  # noqa: E402


def _hu():
    return SimpleNamespace(het_lech_tu=None, o_thanh_tu=None, doi_pha_train=False,
                           xoa_nhip_acc=True, rut_reform=False, reset_joined=False,
                           dang_gom=True, nguoi_keo="*")


class DiemQuaiKhongCoTran(unittest.TestCase):
    def setUp(self):
        rp.party_diem_quai_canh_bao.clear()
        self._orig = rp._map_train_dich
        rp._map_train_dich = lambda pidx, st: 23802

    def tearDown(self):
        rp._map_train_dich = self._orig
        rp.party_diem_quai_canh_bao.clear()

    def _chay(self, pos, map_id=23802, pha="train"):
        st = {"lock": threading.Lock(), "mob_spot": (290, 2390)}
        song = [("a", SimpleNamespace(current_map=map_id, pos=pos))]
        anh = SimpleNamespace(pha=pha, leader_acc=None, co_leader_dang_song=True)
        rp._thi_hanh_hieu_ung(8, st, song, _hu(), rp.VIEC_GOM, anh)

    def test_dung_tai_diem_quai_thi_bao_va_dem_lan(self):
        self._chay((300, 2380))
        self._chay((300, 2380))
        items = rp.diem_quai_canh_bao_items(8)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["map"], 23802)
        self.assertEqual(items[0]["diem"], [290, 2390])
        self.assertEqual(items[0]["lan"], 2)
        rp.diem_quai_canh_bao_bo_qua(8)
        self.assertEqual(rp.diem_quai_canh_bao_items(8), [])

    def test_con_o_safe_hoac_khac_map_khong_bao(self):
        self._chay((910, 590))                  # dang o safe, chua ra diem quai
        self._chay((300, 2380), map_id=23801)   # chua toi map train
        self._chay((300, 2380), pha="dg")
        self.assertEqual(rp.diem_quai_canh_bao_items(8), [])


if __name__ == "__main__":
    unittest.main()
