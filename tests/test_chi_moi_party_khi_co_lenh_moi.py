"""MOI PARTY LA VIEC CO LENH, KHONG PHAI MAC DINH.

User 14/09: "m vua cai lon gi ma party4 lai lap party o Trac quan, code ngu vai lon".

`_nhip_moi_party` truoc day:
    if _kh and _kh.get("viec") == VIEC_GOM:
        return "gom"
    _invite_party_participants(...)          # con lai: MOI
tuc MOI la mac dinh, CHAN la ngoai le, va cua chan chi biet DUNG MOT lenh. Moi lenh khac
(`dong_bo`, `lam`, `di_train`, `ra_quai`) deu roi thang xuong moi party - ke ca khi dang dung o
cho khong duoc phep lap. Them lenh moi vao chuoi dieu phoi la lai lot them mot duong.

CA THAT party 4 (thmo = leader, map 12001 = Cua thanh Trac Quan):
    12:13:13 [party 4] gen 9: viec=gom - dang o thanh DI NGANG QUA 12001, chua toi thanh tap ket
                              21001 -> di tiep roi moi lap party
    12:13:14..40 [thmo] (LEADER) dieu phoi bao GOM (...) -> thoi moi, gom lai     <- chan DUNG
    12:13:43 [party 4] gen 10: viec=dong_bo - cung map nhung ['sga009','sga013'] KHONG THAY duoc
                               dong doi (khac instance du cung so kenh)
    12:13:45 [thmo] (LEADER) moi 4 member theo entity ...        <- cua khong biet lenh nay
    12:13:53 [thmo] (LEADER) DU PARTY (4/4 member join)          <- LAP PARTY TAI TRAC QUAN

Bac chan "thanh trung gian thi khong lap pt" (test_chi_lap_party_o_diem_tap_ket.py) van dung: no
DA ra lenh `gom` luc 12:13:13. Nhung 30 giay sau dieu phoi thay them chuyen khac nen doi lenh sang
`dong_bo`, va ngay khi lenh khong con dung chu `gom` thi leader moi party luon.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _than():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        s = fh.read()
    i = s.find("def _nhip_moi_party(")
    assert i > 0, "mat _nhip_moi_party"
    j = s.find("\n    def ", i + 10)
    return s[i:j if j > 0 else len(s)]


class TestChiMoiKhiCoLenhMOI(unittest.TestCase):
    def setUp(self):
        self.than = _than()

    def test_co_cua_chan_theo_LENH_DANG_KEO_DI(self):
        """Chi `gom` / `dong_bo` la "chua toi luot lap party" - hai lenh do dang keo acc di cho
        khac, moi luc do vo ich va dam vao chinh lenh.

        KHONG chan `lam`: no nghia "khong con gi phai xu ly o cap party -> cu lam viec cua minh",
        ma lap party CHINH LA viec cua leader. Ca that party 47/51, 14/09 (mode Di Gioi - dieu phoi
        ra `lam`): leader bi chan 13 phut, roster 0/4, 5 acc dung im o 49942.
        """
        self.assertIn("_viec in (VIEC_DONG_BO,)", self.than,
                      "cua chan sai loai lenh -> hoac lot het, hoac chan ca 'lam'")

    def test_cua_chan_dung_TRUOC_khi_gui_loi_moi(self):
        _cua = self.than.find("_viec != VIEC_MOI")
        _moi = self.than.find("_invite_party_participants(")
        self.assertGreater(_moi, 0, "mat buoc gui loi moi")
        self.assertLess(_cua, _moi, "cua chan dat SAU loi moi -> vo nghia")

    def test_van_giu_duong_GOM_rieng(self):
        """Caller phan biet 'gom' (phai di gom) voi 'cho' (chi la chua toi luot)."""
        self.assertIn('return "gom"', self.than)
        self.assertIn('return "cho"', self.than)

    def test_CHUA_CO_LENH_thi_van_moi(self):
        """Dieu phoi chua chay lan nao -> khong ai ra lenh, khong duoc dung im cho mai."""
        self.assertIn("if _kh is not None and _viec in (VIEC_DONG_BO,):", self.than,
                      "chua co ke hoach ma cung chan -> party khong bao gio hinh thanh")

    def test_lenh_LAM_thi_VAN_duoc_moi(self):
        """`lam` = party on, cu lam viec cua minh - ma lap party la viec cua leader."""
        i = self.than.find("if _kh is not None and _viec in (")
        self.assertGreater(i, 0)
        _dk = self.than[i:self.than.find(":", i)]
        self.assertNotIn("VIEC_LAM", _dk, "chan ca 'lam' -> party Di Gioi khong bao gio lap duoc")
        self.assertNotIn("VIEC_DI_TRAIN", _dk)
        self.assertNotIn("VIEC_RA_QUAI", _dk)

    def test_van_nghe_lenh_kenh_TRUOC(self):
        _nghe = self.than.find("_nghe_lenh_kenh()")
        self.assertGreater(_nghe, 0)
        self.assertLess(_nghe, self.than.find("_invite_party_participants("))

    def test_noi_ro_ly_do_khi_chua_toi_luot(self):
        """Khong noi ly do thi nhin log tuong leader treo."""
        self.assertIn("chua toi luot moi party: dieu phoi dang ra lenh", self.than)

    def test_khong_spam_log(self):
        """Vong nay chay lien tuc - log moi nhip la ngap file."""
        self.assertIn("moi_cho_log", self.than)


class TestCallerVanXuLyDUNG(unittest.TestCase):
    """Hai cho goi chi so `== "gom"`; gia tri moi ("cho") phai roi vao duong chay tiep binh thuong."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_van_du_hai_cho_goi(self):
        self.assertEqual(self.src.count("_nhip_moi_party(True) == \"gom\"")
                         + self.src.count("_nhip_moi_party(train_on_map) == \"gom\""), 2)

    def test_vong_moi_cua_leader_van_co_loi_ra(self):
        """'cho' keo dai -> sau 120s bump reform, khong ket vinh vien."""
        i = self.src.find('while joined_member_count(pidx) < st["n_members"]:')
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 1600]
        self.assertIn("time.time() - _inv_t0 > 120", khoi,
                      "vong moi mat loi ra -> leader cho lenh MOI vinh vien")


if __name__ == "__main__":
    unittest.main()
