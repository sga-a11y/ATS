"""Thoat Di Gioi: uu tien SMART PATH toi cong, chuoi buoc capture chi la DU PHONG.

Chuoi 7 buoc co dinh replay tu `exit_new.pcap` xuat phat tu (738,648) va cho 2.0s MOI BUOC ->
14 giay chi de di mot doan ngan, va dung o cho khac thi di lung tung (user 01/09: "dang nhich 1
ty roi dung yen 1 luc roi nhich 1 ty").

Map Di Gioi 49942 CO du lieu trong Ground.mmg (da kiem: `find_world_path` tra duong) nen
`navigate_to` tu tim duong tu CHO DANG DUNG, chia doan 100px, cho 0.55s/buoc.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as CL          # noqa: E402
from bot.client import GameClient     # noqa: E402


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


class TestGroundMapCoDuLieuDiGioi(unittest.TestCase):
    def test_map_di_gioi_co_trong_ground_mmg(self):
        """Neu map DG khong co du lieu thi smart path vo dung - phai kiem, khong duoc doan."""
        from bot import config
        st = CL._ground_store()
        if st is None:
            self.skipTest("khong co Ground.mmg tren may nay")
        self.assertIsNotNone(st.map_fingerprint(config.DIGIOI_MAP_ID),
                             "Ground.mmg khong co map Di Gioi -> smart path khong dung duoc")

    def test_tim_duoc_duong_toi_cong(self):
        from bot import config
        st = CL._ground_store()
        if st is None:
            self.skipTest("khong co Ground.mmg tren may nay")
        duong = st.find_world_path(config.DIGIOI_MAP_ID, (738, 648), GameClient.DIGIOI_CONG_RA)
        self.assertTrue(duong, "khong tim duoc duong toi cong")


class TestUuTienSmartPath(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def exit_di_gioi(")
        self.assertGreater(i, 0)
        self.than = s[i:s.find("\n    def _di_bo_chuoi_buoc_ra_cong", i)]
        self.src = s

    def test_toa_do_cong_la_HANG_SO(self):
        """Truoc day (270,210) viet tay o 2 cho - sua mot cho la lech."""
        self.assertEqual(GameClient.DIGIOI_CONG_RA, (270, 210))
        self.assertIn("DIGIOI_CONG_RA", self.than)

    def test_GOI_navigate_to_TRUOC(self):
        i_nav = self.than.find("self.navigate_to(_cx, _cy")
        i_du_phong = self.than.find("_di_bo_chuoi_buoc_ra_cong")
        self.assertGreater(i_nav, 0, "khong dung smart path -> van nhich tung buoc nhu cu")
        self.assertGreater(i_du_phong, i_nav, "chuoi buoc capture phai la DU PHONG, chay SAU")

    def test_chuoi_buoc_cu_chi_chay_khi_smart_path_HONG(self):
        i = self.than.find("if _smart:")
        self.assertGreater(i, 0)
        khoi = self.than[i:i + 700]
        self.assertIn("else:", khoi)
        self.assertIn("_di_bo_chuoi_buoc_ra_cong(step_wait)", khoi)

    def test_di_bang_FLEE(self):
        """Dung lai danh tung bay quai giua duong ra = vo nghia."""
        self.assertIn("flee=True", self.than)

    def test_VAN_gui_du_chuoi_goi_qua_cong(self):
        """Toi noi roi van phai gui 0x14 08/0x0c/0x14 06 thi map moi doi."""
        for goi in ("08000100", "0100", "0600"):
            self.assertIn(goi, self.than, "thieu goi qua cong: %s" % goi)

    def test_KHONG_BO_CUOC_thu_toi_khi_ra_duoc(self):
        """User chot 01/09: "phai di ra bang duoc". Ket trong DG la ket VINH VIEN - DG co gio,
        day quai, khong luong nao khac keo acc ra ho. Bo cuoc sau 3 vong = acc nam do ca buoi."""
        self.assertNotIn("for _lan in range(3):", self.than,
                         "van bo cuoc sau 3 vong -> ket lai trong DG")
        self.assertIn("while self.running:", self.than)
        self.assertIn("self._left_di_gioi()", self.than)

    def test_CHI_dung_khi_acc_stop_hoac_rot(self):
        i = self.than.rfind("return False")
        self.assertGreater(i, 0)
        self.assertIn("stop/rot", self.than[max(0, i - 300):i],
                      "con duong thoat nao khac ngoai 'da ra' / 'acc dung'")

    def test_chua_ra_thi_BAM_POS_ve_o_di_duoc_roi_thu_lai(self):
        """Lap y het mot cach vo vong thi khong bao gio ra: pos dang nho co the nam NGOAI vung di
        duoc (dead-reckoning lech), luc do smart path khong tim noi duong."""
        self.assertIn("self._bam_o_di_duoc(self.pos or (_cx, _cy), (_cx, _cy))", self.than)

    def test_co_LOG_dinh_ky_khi_lau_khong_ra(self):
        """Vong vo han ma im lang thi nhin tu ngoai khong phan biet duoc voi treo."""
        self.assertIn("_lan % 5 == 0", self.than)
        self.assertIn("khong bo cuoc", self.than)

    def test_smart_path_LOI_thi_khong_lam_sap(self):
        self.assertIn("except Exception as e:", self.than)


class TestChuoiBuocDuPhong(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _di_bo_chuoi_buoc_ra_cong(")
        self.assertGreater(i, 0)
        self.than = s[i:s.find("\n    def ", i + 10)]

    def test_giu_nguyen_chuoi_tu_capture(self):
        self.assertIn("(738, 648)", self.than)
        self.assertIn("(390, 330)", self.than)

    def test_van_cho_het_tran_moi_move(self):
        """Client cung khong move giua tran; gui giua tran thi lech het chuoi."""
        self.assertIn("self._wait_combat_clear(idle=2.0, cap=120.0)", self.than)
        i_cho = self.than.find("_wait_combat_clear")
        i_move = self.than.find("self.move_to(")
        self.assertLess(i_cho, i_move)


if __name__ == "__main__":
    unittest.main()
