# -*- coding: utf-8 -*-
"""PHA DI GIOI: acc chua vao DG ma dang o BAI QUAI -> VE THANH truoc, dung dung do.

User chot 22/09: "dang pha DG neu log vao thi ve thanh cho t, dung dung bai quai nua".

Login lai giua bai train la bi keo tran NGAY -> moi thu phia sau deu ket:
  - vao DG: `enter_di_gioi` bi tran chan;
  - ho phu: `_ho_phu_engine_moi` bo qua vi `c.in_combat()`.

Ca that 22/09 party 1 (user: "thang sga005 log vao bi danh luon deo kip dung DG phu a"):
    07:30:35 [nasau]  Di Gioi Ho Phu - con 1 phut (<15), da gui lenh dung     <- o map 49942 (DG)
    07:30:37 [baybay] Di Gioi Ho Phu - con 2 phut (<15), da gui lenh dung     <- o map 49942 (DG)
    07:41:08 [nanam]  BATTLE SEND g=1 t=1 ...                                 <- o 56802 (bai train)
    (nanam = sga005: KHONG mot dong ho phu nao)
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as PE

THANH = 12001
BAI_QUAI = 56802
MAP_DG = 49942


def _acc(u, map_id, trong_dg=False, con_gio=True):
    return PE.AnhAcc(u, song=True, map_id=map_id, kenh=1, so_member=4,
                     trong_dg=trong_dg, con_gio_dg=con_gio)


def _quyet(accs, thanh_dich=THANH):
    anh = PE.AnhParty(0, accs, can_bao_nhieu=len(accs) - 1, pha=PE.PHA_DG,
                      thanh_dich=thanh_dich)
    return PE.quyet_dinh(anh)


class TestVeThanhTruocKhiVaoDG(unittest.TestCase):
    def test_dang_o_BAI_QUAI_thi_VE_THANH(self):
        ket = _quyet([_acc("a", BAI_QUAI)])
        self.assertEqual(ket["a"], PE.VIEC_VE_THANH,
                         "dung o bai quai la bi keo tran -> khong vao DG / khong dung ho phu duoc")

    def test_DA_O_THANH_thi_VAO_DG_luon(self):
        self.assertEqual(_quyet([_acc("a", THANH)])["a"], PE.VIEC_DI_GIOI)

    def test_DA_TRONG_DG_thi_khong_dong_toi(self):
        ket = _quyet([_acc("a", MAP_DG, trong_dg=True)])
        self.assertNotEqual(ket["a"], PE.VIEC_VE_THANH)
        self.assertNotEqual(ket["a"], PE.VIEC_DI_GIOI)

    def test_CHUA_CHOT_thanh_dich_thi_VAO_DG_nhu_cu(self):
        """Khong biet ve dau thi dung ra lenh rong (L3) - van vao DG nhu truoc."""
        self.assertEqual(_quyet([_acc("a", BAI_QUAI)], thanh_dich=None)["a"], PE.VIEC_DI_GIOI)

    def test_HET_GIO_DG_thi_khong_bi_keo_ve_thanh(self):
        """Het gio thi nhanh khac lo (nghi / thoat), khong phai viec cua cua nay."""
        ket = _quyet([_acc("a", BAI_QUAI, con_gio=False)])
        self.assertNotEqual(ket["a"], PE.VIEC_VE_THANH)

    def test_moi_acc_xet_RIENG(self):
        """Dua da o thanh thi vao DG, dua con o bai thi ve thanh - khong bat ca lu theo mot dua."""
        ket = _quyet([_acc("a", THANH), _acc("b", BAI_QUAI)])
        self.assertEqual(ket["a"], PE.VIEC_DI_GIOI)
        self.assertEqual(ket["b"], PE.VIEC_VE_THANH)



class TestHetGioMaConHoPhu(unittest.TestCase):
    """HET GIO ma CON HO PHU -> van con viec o DG, KHONG duoc dung im.

    Giu pha DG khi con ho phu (user chot 22/09) tro thanh CAI BAY neu acc het gio nhan
    `VIEC_NGHI`: no dung im TAI CHO - ma cho do la BAI QUAI - va vi khong duoc giao
    `VIEC_DI_GIOI` nen cung KHONG AI goi ho phu -> ket vinh vien.

    Ca that 22/09 party 1 (user: "van dung o bai cho quai danh"):
        09:00:36 pha=digioi  nanam@56802(L) ... tuyet@12003
        09:08:57 ENGINE: sga008 -> nghi
    """

    def test_het_gio_con_ho_phu_o_BAI_QUAI_thi_VE_THANH(self):
        a = PE.AnhAcc("a", song=True, map_id=BAI_QUAI, kenh=1, so_member=4,
                      con_gio_dg=False, con_ho_phu=True)
        ket = PE.quyet_dinh(PE.AnhParty(0, [a], can_bao_nhieu=0, pha=PE.PHA_DG,
                                        thanh_dich=THANH))
        self.assertEqual(ket["a"], PE.VIEC_VE_THANH, "dung im o bai quai -> quai danh chet")

    def test_het_gio_con_ho_phu_DA_O_THANH_thi_VAO_DG(self):
        """Vao DG la duong goi ho phu - phai duoc giao, khong thi ho phu nam mai trong tui."""
        a = PE.AnhAcc("a", song=True, map_id=THANH, kenh=1, so_member=4,
                      con_gio_dg=False, con_ho_phu=True)
        ket = PE.quyet_dinh(PE.AnhParty(0, [a], can_bao_nhieu=0, pha=PE.PHA_DG,
                                        thanh_dich=THANH))
        self.assertEqual(ket["a"], PE.VIEC_DI_GIOI)

    def test_het_gio_VA_HET_ho_phu_thi_nghi_nhu_cu(self):
        a = PE.AnhAcc("a", song=True, map_id=BAI_QUAI, kenh=1, so_member=4,
                      con_gio_dg=False, con_ho_phu=False)
        ket = PE.quyet_dinh(PE.AnhParty(0, [a], can_bao_nhieu=0, pha=PE.PHA_DG,
                                        thanh_dich=THANH))
        self.assertEqual(ket["a"], PE.VIEC_NGHI)

    def test_mot_dua_het_gio_nhung_con_ho_phu_KHONG_lam_ca_party_dung_im(self):
        """`_co_dua_het_gio` cung phai xet ho phu - khong thi ca party trong DG bi bat NGHI."""
        accs = [PE.AnhAcc("a", song=True, map_id=MAP_DG, kenh=1, so_member=4,
                          trong_dg=True, con_gio_dg=True),
                PE.AnhAcc("b", song=True, map_id=MAP_DG, kenh=1, so_member=4,
                          trong_dg=True, con_gio_dg=False, con_ho_phu=True)]
        ket = PE.quyet_dinh(PE.AnhParty(0, accs, can_bao_nhieu=0, pha=PE.PHA_DG,
                                        thanh_dich=THANH))
        self.assertNotEqual(ket["a"], PE.VIEC_NGHI)


if __name__ == "__main__":
    unittest.main()
