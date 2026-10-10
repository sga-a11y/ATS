# -*- coding: utf-8 -*-
"""Pha TRAIN ma acc dang trong Di Gioi -> VE THANH truoc, khong gom kenh trong DG.

Ca that 10/10 party 25: ca 5 acc login vao dang o DG 49942, mode train. Dieu phoi ra
`dong_bo` (cung map lech kenh [1, 4, 5]) -> 232 lan giao `doi_kenh`, 0 lan thanh cong,
chi ra khoi DG khi `DUNG HINH qua 240s`. Engine cu: login sai map (ke ca DG) -> ca party ve
thanh roi keo toi map train.
"""
import unittest
from unittest import mock

from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot

DG = 49942


class TestPhaTrainTrongDg(unittest.TestCase):

    def test_ca_party_trong_dg_lech_kenh_thi_ve_thanh_khong_doi_kenh(self):
        accs = [account("a", map_id=DG, kenh=1, trong_dg=True, so_member=0),
                account("b", map_id=DG, kenh=4, trong_dg=True, so_member=0),
                account("c", map_id=DG, kenh=5, trong_dg=True, so_member=0)]
        kq = E.quyet_dinh(snapshot(accs, can_bao_nhieu=2, map_dich=DG, thanh_dich=14001,
                                   dp_viec=E.DP_DONG_BO))
        self.assertEqual(set(kq.values()), {E.VIEC_VE_THANH})

    def test_mot_acc_trong_dg_thi_chi_acc_do_ve_thanh(self):
        accs = [account("a", map_id=14001, kenh=1),
                account("b", map_id=DG, kenh=1, trong_dg=True)]
        kq = E.quyet_dinh(snapshot(accs, thanh_dich=14001, dp_viec=E.DP_GOM))
        self.assertEqual(kq["b"], E.VIEC_VE_THANH)
        self.assertNotEqual(kq.get("a"), E.VIEC_VE_THANH)   # da o thanh tap ket -> de yen

    def test_dang_danh_trong_dg_thi_cho_het_tran(self):
        accs = [account("a", map_id=DG, trong_dg=True, dang_danh=True),
                account("b", map_id=DG, trong_dg=True)]
        kq = E.quyet_dinh(snapshot(accs, thanh_dich=14001, dp_viec=E.DP_DONG_BO))
        self.assertEqual(kq["a"], E.VIEC_NGHI)
        self.assertEqual(kq["b"], E.VIEC_VE_THANH)

    def test_pha_dg_khong_dung_toi(self):
        accs = [account("a", map_id=DG, trong_dg=True, con_gio_dg=True),
                account("b", map_id=DG, trong_dg=True, con_gio_dg=True)]
        kq = E.quyet_dinh(snapshot(accs, pha=E.PHA_DG, thanh_dich=14001))
        self.assertNotIn(E.VIEC_VE_THANH, kq.values())

    def test_mode_stand_city_khong_dung_toi(self):
        accs = [account("a", map_id=DG, trong_dg=True),
                account("b", map_id=DG, trong_dg=True)]
        kq = E.quyet_dinh(snapshot(accs, pb_tai_cho=True, thanh_dich=14001))
        self.assertNotIn(E.VIEC_VE_THANH, kq.values())

    def test_ve_thanh_chua_chot_thanh_ma_trong_dg_thi_van_ra_khoi_dg(self):
        c = mock.Mock()
        c.in_di_gioi.return_value = True
        self.assertFalse(E.thi_hanh(c, E.VIEC_VE_THANH, lambda: True, dich=None))
        c.exit_di_gioi.assert_called_once()

    def test_ve_thanh_chua_chot_thanh_ngoai_dg_thi_lenh_rong(self):
        c = mock.Mock()
        c.in_di_gioi.return_value = False
        self.assertFalse(E.thi_hanh(c, E.VIEC_VE_THANH, lambda: True, dich=None))
        c.exit_di_gioi.assert_not_called()


if __name__ == "__main__":
    unittest.main()
