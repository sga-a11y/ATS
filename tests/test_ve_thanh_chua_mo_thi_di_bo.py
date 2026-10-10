"""Mode CITY chon thanh CHUA MO tele -> ra lenh DI MAP: ca party lap doi va KEO nhau di bo.

Log 01/09/2026 party 48 (dt901-905) va 49 (gclm*): ra khoi Di Gioi ve map 12003 (quang truong Trac
Quan) roi nam im ca tieng:

    10:07:00 [dtbon] Da THOAT Di Gioi -> map 12003 (sau 1 lan, 8s)
    10:07:05 [dtmot] (member) TAP TRUNG ve thanh 12061 (flag 2) (dung o 12003 -> ve lai)
    10:07:05 [dtmot] go_to_town: thanh 12061 CHUA MO tele -> bo qua ngay (khong spam)

Acc chua mo diem dich chuyen Nghiep Thanh -> `go_to_town` bo cuoc ngay (dung, tele khong bao gio an)
nhung mode city KHONG co buoc du phong nao => dung im (user: "party 48 49 no ko ve thanh, no dung
yen o quang truong, t chon Ng thanh ma" / "cho ca pt di tu thanh gan nhat da mo den nhe").

Ban dau sua bang cach cho MOI ACC tu di bo -> hong ngay: cong co hoi thoai (cau Gioi kieu, map
63000 cong 10) chi MOT nguoi tra loi duoc, 5 acc di le thi moi acc tu bam mot ma va ket ca lu o cau
(log 11:31-11:35, user: "leader chon thoi, lien quan me gi den 5 acc" / "m dang cho di le a").

Chot: dung LAI co che da co va da chay tot - lenh "DI MAP AAA -> BBB" (`party_route_maps` ->
`_do_manual_route`): gom ca party ve thanh xuat phat, lap party TAM (party khong co chu PT thi
picker dong vai leader), LEADER KEO qua tung cong con member follow, den noi thi giai tan. Y het
cach mode train xu ly "thanh gan bai chua mo" (`_reform_via_nghiep`).
"""
from __future__ import annotations

import io
import os
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


class _Bot:
    """Bot gia: tele CHI an voi thanh trong `mo`."""

    def __init__(self, map_id=12003, mo=(12001,)):
        self.current_map = map_id
        self._mo = set(mo)
        self.da_tele = []

    def go_to_town(self, city_id, flag=0, **kw):
        self.da_tele.append(int(city_id))
        if int(city_id) in self._mo:
            self.current_map = int(city_id)
            return True
        return False

    def city_unlocked(self, city_id):
        return int(city_id) in self._mo


class TestDiBoKhiThanhChuaMo(unittest.TestCase):
    """Luong ACC chi tele. Thanh chua mo -> ENGINE ra lenh DI MAP, acc khong tu ra (tu 09/10, ca
    party 21: acc ra lenh luc ca party chua login xong -> khoa ca phien). Xem
    `tests/test_city_thanh_chua_mo_engine.py`."""

    def setUp(self):
        self._route = rpd.party_route_maps
        self.lenh = []
        rpd.party_route_maps = lambda pidx, a, b: self.lenh.append((pidx, a, b))

    def tearDown(self):
        rpd.party_route_maps = self._route

    def test_thanh_DA_MO_thi_tele_thang_khong_ra_lenh(self):
        c = _Bot(map_id=12003, mo=(12001, 12061))
        self.assertTrue(rpd._ve_thanh_tap_trung(c, 0, "t", 12061, 2))
        self.assertEqual(c.current_map, 12061)
        self.assertEqual(self.lenh, [], "thanh da mo ma van keo di bo -> cham vo ich")

    def test_thanh_CHUA_MO_thi_acc_KHONG_tu_ra_lenh(self):
        c = _Bot(map_id=12003, mo=(12001,))
        self.assertFalse(rpd._ve_thanh_tap_trung(c, 0, "t", 12061, 2))
        self.assertEqual(self.lenh, [], "viec cap party la cua engine")

    def test_tele_that_bai_vi_LY_DO_KHAC_thi_KHONG_ra_lenh(self):
        """Thanh DA MO ma tele khong an = dang bi battle chan -> `go_to_town` da lap du roi."""
        c = _Bot(map_id=12003, mo=(12061,))
        c.go_to_town = lambda cid, flag=0, **kw: False
        self.assertFalse(rpd._ve_thanh_tap_trung(c, 0, "t", 12061, 2))
        self.assertEqual(self.lenh, [])


class TestDungLaiCoCheDaCo(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_dung_LENH_DI_MAP_chu_khong_tu_di_bo(self):
        i = self.src.find("def _ra_lenh_di_mo_thanh(")
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("party_route_maps(pidx, xuat_phat, dest_city)", than)
        self.assertNotIn("follow_smart_scene_route", than,
                         "tu di bo = moi acc tu tra loi cong hoi thoai -> ket ca lu o cau Gioi kieu")

    def test_ca_hai_cho_mode_city_deu_goi(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot

        client = NS()
        with mock.patch.dict(R.config.PARTY_CONFIG, {0: {"mode": "city", "start_city_id": 100, "city_flag": 3}}, clear=True), \
                mock.patch.object(R, "_event_cua_party", return_value={}), \
                mock.patch.object(R, "_ve_thanh_tap_trung", return_value=True) as move:
            self.assertTrue(R._engine_mode_action(0, client, "city", lambda: True))
        self.assertEqual(move.call_args.args[0:2], (client, 0))
        self.assertEqual(move.call_args.args[3:], (100, 3))

    def test_khong_con_goi_go_to_town_tron_trong_mode_city(self):
        self.assertNotIn('if c.go_to_town(sc, city_flag) and c.current_map == getattr(', self.src)


if __name__ == "__main__":
    unittest.main()
