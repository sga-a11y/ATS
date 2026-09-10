"""VIEC VAT phai HOAN khi party dang gom - khong phai bo, chi la khong phai luc nay.

User VAN cho phep cat tien trang / ban Noi Dat (bat trong config). Van de la CHO LUC: hai viec do
deu keo acc sang map KHAC (12263 Chu tien trang, 12061 Nha buon) - dung luc ca party phai o mot cho.

Ca that 07/09 party 1, user: "leader bi chet va ve thanh, bot dieu phoi lam cai lon gi ma deo keo
pt chay lai di, thay reform vai lan moi duoc":

    18:03:33 [xGAx] (LEADER) BI VAN khoi train map (dang o 12003, vd chet) -> yeu cau CA PARTY reform
    18:03:37  ca party ve thanh
    18:03:45 [xGAx]   Tien trang: 3 mon can cat -> di NPC Chu tien trang (map 12263)
    18:03:45 [minh]   Ban Noi Dat: co 146 cai -> di NPC Nha buon Ng.Thanh
    18:03:46 [chihao] Tien trang: 2 mon can cat -> di NPC Chu tien trang (map 12263)
    18:03:51 [tuyet]  reform: cho leader lap duong toi map 21836 (15s)...
    18:03:52 [brub]   reform: cho leader lap duong toi map 21836 (15s)...

Leader vua ra lenh gom xong thi CHINH NO bo di cat do; hai member dung cho no lap duong. Party tu
mot cho thanh BON map [12001, 12061, 12263, 21011] -> dieu phoi lai ra lenh gom -> lap. Do la
"reform vai lan moi duoc".

HOAN chu khong BO: `pre_route_town_hop` chay lai MOI LAN di tu thanh ra train, va ca hai viec deu
tu kiem "con mon nao can lam khong" - nen lan sau party on dinh la lam binh thuong.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as CL   # noqa: E402


def _src(ten):
    with io.open(os.path.join(ROOT, ten), encoding="utf-8") as fh:
        return fh.read()


class TestCoGom(unittest.TestCase):
    PIDX = 8801

    def tearDown(self):
        CL.dat_party_dang_gom(self.PIDX, False)

    def test_bat_roi_tat(self):
        self.assertFalse(CL.party_dang_gom(self.PIDX))
        CL.dat_party_dang_gom(self.PIDX, True)
        self.assertTrue(CL.party_dang_gom(self.PIDX))
        CL.dat_party_dang_gom(self.PIDX, False)
        self.assertFalse(CL.party_dang_gom(self.PIDX))

    def test_party_khac_khong_anh_huong(self):
        CL.dat_party_dang_gom(self.PIDX, True)
        self.assertFalse(CL.party_dang_gom(self.PIDX + 1))

    def test_party_idx_None_an_toan(self):
        CL.dat_party_dang_gom(None, True)
        self.assertFalse(CL.party_dang_gom(None))


class TestChiDieuPhoiGhi(unittest.TestCase):
    def test_MOT_cho_ghi_duy_nhat(self):
        s = _src("run_party_digioi.py")
        ghi = [d for d in s.splitlines() if "dat_party_dang_gom(" in d and "import" not in d]
        self.assertEqual(len(ghi), 1, ghi)

    def test_cho_do_nam_trong_dieu_phoi(self):
        s = _src("run_party_digioi.py")
        i = s.find("dat_party_dang_gom(pidx,")
        self.assertGreater(i, 0)
        self.assertIn("def _dieu_phoi_quyet(", s[:i].rsplit("def ", 1)[0] + "def _dieu_phoi_quyet(")
        khoi = s[max(0, i - 600):i]
        self.assertIn("viec", khoi)

    def test_client_KHONG_tu_bat(self):
        s = _src("bot/client.py")
        sau = s.split("def dat_party_dang_gom")[-1]
        self.assertNotIn("dat_party_dang_gom(", sau, "client tu bat/tat co cua ca party")

    def test_bat_cho_ca_ba_lenh_gom(self):
        """GOM (ve cung map) · MOI (thieu doi) · DONG BO (lech kenh tai cho) - ca ba deu la luc
        party phai o mot cho."""
        s = _src("run_party_digioi.py")
        i = s.find("dat_party_dang_gom(pidx,")
        dong = s[i:i + 120]
        for m in ("VIEC_GOM", "VIEC_MOI", "VIEC_DONG_BO"):
            self.assertIn(m, dong, m)


class TestPreRouteHoan(unittest.TestCase):
    def setUp(self):
        s = _src("bot/client.py")
        i = s.find("def pre_route_town_hop(")
        self.assertGreater(i, 0)
        self.than = s[i:s.find("\n    def ", i + 10)]

    def test_hoan_khi_dang_gom(self):
        self.assertIn("party_dang_gom(self.party_idx)", self.than)

    def test_kiem_TRUOC_khi_lam_viec_vat(self):
        i = self.than.find("party_dang_gom(self.party_idx)")
        for m in ("self.sell_noi_dat()", "self.cat_do_tien_trang()"):
            self.assertGreater(self.than.find(m), i, "van lam %s roi moi kiem" % m)

    def test_VAN_tele_ve_thanh_trung_gian(self):
        """Hoan viec vat, KHONG hoan chuyen di - tele trung gian la mot phan cua duong gom."""
        i = self.than.find("party_dang_gom(self.party_idx)")
        self.assertGreater(self.than.find("self.go_to_town(city, flag)"), 0)
        self.assertLess(self.than.find("self.go_to_town(city, flag)"), i,
                        "bo luon buoc tele trung gian -> hong duong gom")

    def test_khong_XOA_tinh_nang(self):
        """User VAN cho phep lam viec vat - chi hoan. Hai loi goi phai con nguyen."""
        for m in ("self.sell_noi_dat()", "self.cat_do_tien_trang()"):
            self.assertIn(m, self.than, m)


if __name__ == "__main__":
    unittest.main()
