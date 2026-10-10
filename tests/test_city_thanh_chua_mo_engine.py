"""Mode CITY, thanh dich CHUA MO: ENGINE quyet di tu dau, khong acc nao tu quyet.

Ca that party 21, 09/10/2026 - chon Thien Thuy (24001, khu Luong Chau VTC vua mo), ca 5 acc chua mo:

    11:37:55..58 dieu906..910 relogin -> tao worker MOI
    11:38:00 [dieubay] go_to_town: thanh 24001 CHUA MO tele -> bo qua ngay (khong spam)
    11:38:00 [dieubay] thanh 24001 CHUA MO tele va KHONG thanh nao ca party da mo di toi do duoc
             -> dung tai cho                                   <- dieuchin/dieumuoi CON DANG LOGIN
    11:42:14 [party 21] ENGINE: 'city' giao lai 80 lan lien tiep cho dieu907 ...

Dem tren log: 307 lan `go_to_town: thanh 24001 CHUA MO`, 1 lan "dung tai cho", 0 lan ra lenh DI MAP.
Doi chung cung party 11:19: login du -> `thanh xuat phat = Truong Sa ... ca party deu da mo`.
Router tu 24001 that ra co duong: Truong An (14001) 7 cong.

Hai loi chong nhau: (1) viec cap party nam trong luong ACC (`_ve_thanh_tap_trung`), acc login xong
truoc chot cho ca party; (2) danh dau "da ra lenh" TRUOC khi chon duoc thanh -> chon hong la khoa
ca phien. Gio engine quyet (`_engine_city_decisions`), chua du du lieu ca party thi chua chot, va
khong khoa vinh vien.
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

_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import run_party_digioi as rpd          # noqa: E402
finally:
    sys.argv = _argv

from tests.party_engine_scenarios import account, snapshot   # noqa: E402

PIDX = 9321
DICH = 24001
P21 = ["dieusau", "dieubay", "dieutam", "dieuchin", "dieumuoi"]


def _anh(chua_login=()):
    return snapshot([account(u, map_id=23803, so_member=0, song=u not in chua_login) for u in P21])


class _Base(unittest.TestCase):
    def setUp(self):
        rpd._party_state.pop(PIDX, None)
        self.lenh = []
        self._patches = [
            mock.patch.object(rpd, "party_route_maps",
                              side_effect=lambda p, a, b: self.lenh.append((a, b))),
            mock.patch.object(rpd, "_pick_start_city", return_value=14001),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        rpd._party_state.pop(PIDX, None)

    def chay(self, anh, mo=((), ())):
        with mock.patch.object(rpd, "_party_city_unlocked", return_value=mo):
            return rpd._engine_city_decisions(PIDX, anh, {u: "city" for u in P21}, DICH)


class TestCaParty21(_Base):
    def test_con_acc_dang_login_thi_CHUA_CHOT_va_KHONG_KHOA(self):
        """11:38:00: dieuchin/dieumuoi chua login xong -> khong ra lenh, khong danh dau gi."""
        out = self.chay(_anh(chua_login=("dieuchin", "dieumuoi")),
                        mo=(["dieusau", "dieubay", "dieutam"], []))
        self.assertEqual(self.lenh, [])
        self.assertEqual(set(out.values()), {"nghi"}, "dang cho thi khong giao `city` (lenh rong)")
        self.assertIsNone(rpd._pstate(PIDX).get("city_lenh"), "chua chot thi khong duoc khoa")

    def test_login_du_thi_ENGINE_ra_lenh_DI_MAP(self):
        self.chay(_anh(chua_login=("dieuchin", "dieumuoi")), mo=(["dieusau"], []))
        out = self.chay(_anh(), mo=(P21, []))
        self.assertEqual(self.lenh, [(14001, DICH)])
        self.assertEqual(set(out.values()), {"nghi"}, "di bo theo lenh route, khong tele le")

    def test_chua_biet_co_nhiem_vu_thi_chua_chot(self):
        out = self.chay(_anh(), mo=(["dieusau"], ["dieuchin"]))
        self.assertEqual(self.lenh, [])
        self.assertEqual(set(out.values()), {"nghi"})

    def test_ca_party_da_mo_thi_tele_thang(self):
        out = self.chay(_anh(), mo=([], []))
        self.assertEqual(self.lenh, [])
        self.assertEqual(set(out.values()), {"city"})

    def test_acc_dang_login_khong_chan_khi_ca_party_da_mo(self):
        out = self.chay(_anh(chua_login=("dieumuoi",)), mo=([], []))
        self.assertEqual(out["dieusau"], "city")


class TestKhongKhoaVinhVien(_Base):
    def test_ra_lenh_MOT_lan_trong_nhip(self):
        for _ in range(5):
            self.chay(_anh(), mo=(P21, []))
        self.assertEqual(len(self.lenh), 1, "moi giay ra lenh lai thi route bi khoi dong lai mai")

    def test_khong_co_duong_thi_THU_LAI_sau_nhip(self):
        """Ca P21 cu: chon hong mot lan la dung im ca phien. Gio phai thu lai."""
        with mock.patch.object(rpd, "_pick_start_city", return_value=None):
            self.chay(_anh(), mo=(P21, []))
        self.assertEqual(self.lenh, [])
        rpd._pstate(PIDX)["city_lenh"]["luc"] = time.time() - rpd.CITY_LENH_LAI_SEC - 1
        self.chay(_anh(), mo=(P21, []))
        self.assertEqual(self.lenh, [(14001, DICH)])

    def test_route_xong_van_chua_toi_thi_ra_lenh_lai(self):
        self.chay(_anh(), mo=(P21, []))
        rpd._pstate(PIDX)["city_lenh"]["luc"] = time.time() - rpd.CITY_LENH_LAI_SEC - 1
        self.chay(_anh(), mo=(["dieumuoi"], []))
        self.assertEqual(len(self.lenh), 2)

    def test_khong_ai_can_ve_thanh_thi_khong_dung_gi(self):
        with mock.patch.object(rpd, "_party_city_unlocked") as hoi:
            out = rpd._engine_city_decisions(PIDX, _anh(), {u: "nghi" for u in P21}, DICH)
        hoi.assert_not_called()
        self.assertEqual(set(out.values()), {"nghi"})


class TestNhaNamTinh(_Base):
    def test_khong_tele_duoc_nen_luon_ra_lenh_qua_Bac_Hai(self):
        with mock.patch.object(rpd, "_party_city_unlocked", return_value=([], [])):
            out = rpd._engine_city_decisions(PIDX, _anh(), {u: "city" for u in P21},
                                             rpd.NHA_NAM_TINH_QUAN)
        self.assertEqual(self.lenh, [(rpd.BAC_HAI, rpd.NHA_NAM_TINH_QUAN)])
        self.assertEqual(set(out.values()), {"nghi"})

    def test_chua_biet_Bac_Hai_thi_cho_khong_khoa(self):
        with mock.patch.object(rpd, "_party_city_unlocked", return_value=([], ["dieusau"])):
            rpd._engine_city_decisions(PIDX, _anh(), {u: "city" for u in P21},
                                       rpd.NHA_NAM_TINH_QUAN)
        self.assertEqual(self.lenh, [])
        self.assertIsNone(rpd._pstate(PIDX).get("city_lenh"))


class TestAccKhongTuQuyet(unittest.TestCase):
    """Luong ACC (`_ve_thanh_tap_trung`) chi tele - khong chon thanh, khong ra lenh route."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _ve_thanh_tap_trung(")
        self.than = src[i:src.find("\ndef ", i + 10)]

    def test_khong_goi_ra_lenh_hay_chon_thanh(self):
        for cam in ("party_route_maps", "_ra_lenh_di_mo_thanh", "_ra_lenh_di_nha_nam_tinh",
                    "_pick_start_city", "_party_city_unlocked"):
            self.assertNotIn(cam + "(", self.than, "acc lai tu quyet viec cap party: " + cam)

    def test_engine_goi_cho_mode_city(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _engine_mode_decisions(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertIn("_engine_city_decisions(pidx, anh, result", than)


if __name__ == "__main__":
    unittest.main()
