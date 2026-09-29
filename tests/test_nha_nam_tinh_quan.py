"""Nha Nam Tinh Quan (55002): khong phai thanh -> ve Bac Hai roi keo ca party di bo len.
Co acc chua mo Bac Hai -> keo ca lu di MO Bac Hai truoc, toi noi moi di tiep."""
import sys
import unittest
from unittest import mock

_argv = sys.argv
try:
    sys.argv = ["run_party_digioi.py"]
    import run_party_digioi as rp
finally:
    sys.argv = _argv


class TestNhaNamTinhQuan(unittest.TestCase):
    def setUp(self):
        self.pidx = 9201
        rp._party_state.pop(self.pidx, None)

    def tearDown(self):
        rp._party_state.pop(self.pidx, None)

    def test_da_mo_bac_hai_di_thang(self):
        with mock.patch.object(rp, "_party_city_unlocked", return_value=([], [])), \
             mock.patch.object(rp, "party_route_maps") as prm:
            rp._ra_lenh_di_nha_nam_tinh(self.pidx)
            rp._ra_lenh_di_nha_nam_tinh(self.pidx)     # lan 2 khong dat lai lenh
        prm.assert_called_once_with(self.pidx, 11011, 55002)

    def test_chua_mo_bac_hai_di_mo_truoc(self):
        with mock.patch.object(rp, "_party_city_unlocked", return_value=(["a"], [])), \
             mock.patch.object(rp, "_pick_start_city", return_value=18021), \
             mock.patch.object(rp, "party_route_maps") as prm:
            rp._ra_lenh_di_nha_nam_tinh(self.pidx)
        prm.assert_called_once_with(self.pidx, 18021, 11011)
        self.assertTrue(rp._pstate(self.pidx)["nha_nt_tiep"])

    def test_chua_biet_thi_cho(self):
        with mock.patch.object(rp, "_party_city_unlocked", return_value=([], ["a"])), \
             mock.patch.object(rp, "party_route_maps") as prm:
            rp._ra_lenh_di_nha_nam_tinh(self.pidx)
        prm.assert_not_called()

    def test_ve_thanh_tap_trung_khong_tele_55002(self):
        c = mock.Mock(current_map=12001)
        with mock.patch.object(rp, "_ra_lenh_di_nha_nam_tinh") as ra:
            self.assertFalse(rp._ve_thanh_tap_trung(c, self.pidx, "t", 55002, 1))
        c.go_to_town.assert_not_called()
        ra.assert_called_once()
        c.current_map = 55002
        self.assertTrue(rp._ve_thanh_tap_trung(c, self.pidx, "t", 55002, 1))

    def test_teleport_city_55002_chuyen_sang_di_bo(self):
        with mock.patch.object(rp, "party_go_nha_nam_tinh") as go:
            rp.party_teleport_city(self.pidx, 55002, 1)
        go.assert_called_once_with(self.pidx)
        self.assertIsNone(rp._pstate(self.pidx).get("cmd"))


if __name__ == "__main__":
    unittest.main()
