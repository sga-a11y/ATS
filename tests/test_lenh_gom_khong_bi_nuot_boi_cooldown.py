"""LENH GOM KHONG DUOC BIEN MAT VI TRUNG COOLDOWN.

User 13/09: "party 35 thay lech map ma ko gom map lai duoc" -> "t thay van co dong lenh gom lai
ma" -> "the la dieu phoi lai ngu a".

Dung, lan nay LOI O DIEU PHOI (khong phai acc tu quyet).

`_dieu_phoi_thi_hanh` truoc day mo dau bang:

    if not doi or _viec not in (VIEC_GOM, VIEC_DONG_BO):
        return

`doi` = ke hoach VUA DOI o nhip nay. Nghia la lenh gom chi duoc phat dung MOT nhip - nhip ke
hoach doi. Nhip do ma trung `KE_HOACH_GOM_COOLDOWN` (180s) thi hai dong `return` ben duoi nuot
lenh, IM LANG, khong mot dong log. Va ke hoach sau do van la 'gom' nen khong con DOI nua ->
`not doi` chan tu cua -> KHONG BAO GIO phat lai.

CA THAT (party 35):

    12:22:47 [party 35] REFORM gen -> 2 ... -> dieu_phoi_gom_luc = 12:22:47
    12:23:26 [party 35] gen 7: viec=gom - party dang o 2 MAP khac nhau [56001, 56103]
             (khong co dong "REFORM gen ->" nao theo sau: lenh bi nuot)
    12:26:35 [dvsau] (LEADER) chua du member (2/4) NHUNG dv608 o map 56103 (leader 56001) ...
    12:27:35 / 12:28:38 / 12:29:38   y het nhau, khong ai di dau

GIO: con lech thi NHIP NAO CUNG XET; cooldown chi de khong ra lenh dam len nhau, va khi phai cho
thi PHAI NOI RA.
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class _Nen(unittest.TestCase):
    PARTY = 34      # party 35

    def setUp(self):
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)

    def tearDown(self):
        R._party_state.pop(self.PARTY, None)

    def _gom(self, doi=True, ly_do="party dang o 2 MAP khac nhau [56001, 56103]"):
        R._dieu_phoi_thi_hanh(self.PARTY, self.st,
                              {"viec": R.VIEC_GOM, "ly_do": ly_do}, doi)


class TestKhongNuotLenh(_Nen):
    def test_ra_lenh_duoc_lan_dau(self):
        _g0 = self.st["reform_gen"]
        self._gom()
        self.assertGreater(self.st["reform_gen"], _g0, "lenh gom dau tien khong duoc phat")

    def test_TRONG_cooldown_thi_CHO_chu_khong_vut_lenh(self):
        self._gom()
        _g = self.st["reform_gen"]
        self._gom()                       # ngay sau -> trong cooldown
        self.assertEqual(self.st["reform_gen"], _g, "ra lenh dam len dot gom dang chay")

    def test_HET_cooldown_thi_RA_LENH_LAI_du_ke_hoach_KHONG_doi(self):
        """Cot loi cua party 35: `doi=False` ma van con lech -> phai ra lenh lai."""
        self._gom()
        _g = self.st["reform_gen"]
        self.st["dieu_phoi_gom_luc"] = time.time() - R.KE_HOACH_GOM_COOLDOWN - 1
        self.st["reform_bump_luc"] = 0.0          # khoang lang bump khong dinh vao phep thu nay
        self._gom(doi=False)
        self.assertGreater(self.st["reform_gen"], _g,
                           "ke hoach khong DOI nua -> lenh gom bi chan vinh vien (bug party 35)")

    def test_nhip_dau_tien_TRUNG_cooldown_van_cuu_duoc(self):
        """Dung chuoi party 35: lenh truoc luc 12:22:47, gen moi luc 12:23:26 (39s sau)."""
        self._gom()
        _g = self.st["reform_gen"]
        self.st["dieu_phoi_gom_luc"] = time.time() - 39.0
        self._gom(doi=True)                       # nhip ke hoach DOI - bi cooldown nuot
        self.assertEqual(self.st["reform_gen"], _g)
        # ... nhung sau khi het cooldown, nhip thuong (doi=False) phai ra lenh duoc
        self.st["dieu_phoi_gom_luc"] = time.time() - R.KE_HOACH_GOM_COOLDOWN - 1
        self.st["reform_bump_luc"] = 0.0
        self._gom(doi=False)
        self.assertGreater(self.st["reform_gen"], _g, "party ket vinh vien nhu ca that")

    def test_viec_khac_thi_khong_dung_toi(self):
        _g = self.st["reform_gen"]
        R._dieu_phoi_thi_hanh(self.PARTY, self.st, {"viec": R.VIEC_LAM, "ly_do": ""}, True)
        R._dieu_phoi_thi_hanh(self.PARTY, self.st, {"viec": R.VIEC_MOI, "ly_do": ""}, True)
        self.assertEqual(self.st["reform_gen"], _g)


class TestKhongImLANG(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        i = self.src.find("def _dieu_phoi_thi_hanh(pidx, st, kh, doi):")
        self.assertGreater(i, 0)
        j = self.src.find("\ndef ", i + 10)
        self.than = self.src[i:j]

    def test_khong_con_chan_theo_doi(self):
        self.assertNotIn("if not doi or _viec not in", self.than,
                         "lenh gom lai chi song dung mot nhip")

    def test_phai_LOG_khi_cho_cooldown(self):
        self.assertIn("CHO them", self.than, "nuot lenh im lang -> khong the truy bang log")

    def test_log_co_chan_spam(self):
        """Vong chay moi 2s - in moi nhip la ngap log."""
        self.assertIn("gom_cho_log_luc", self.than)


class TestLogKhongNOI_DOI(unittest.TestCase):
    """Log hua mot viec ma than ham chi `pass` -> doc log tuong dang co lenh gom chay.

    User 13/09 doc dung nhung dong nay: "t thay van co dong lenh gom lai ma".
    """

    def setUp(self):
        self.src = _src()

    def test_bi_van_khoi_train_map_khong_hua_reform(self):
        i = self.src.find("BI VAN khoi train map")
        self.assertGreater(i, 0)
        self.assertNotIn("yeu cau CA PARTY reform", self.src[i:i + 300])

    def test_leader_mat_party_khong_hua_gom(self):
        i = self.src.find("MAT PARTY giua chung (%d/%d)")
        self.assertGreater(i, 0)
        self.assertNotIn("GOM LAI", self.src[i:i + 300],
                         "leader khong gom (dung), nhung log van noi la co")

    def test_leader_khong_moi_mu_khong_hua_gom(self):
        i = self.src.find("chua du member (%d/%d) NHUNG %s")
        self.assertGreater(i, 0)
        self.assertIn("CHO DIEU PHOI", self.src[i:i + 300])

    def test_khong_con_khoi_khoa_rong(self):
        """`with st["lock"]: pass` = tan du cua hanh dong da bi rut ruot. Co 16 cho nhu the, va
        nhieu cho LOG van hua viec ("yeu cau CA PARTY reform", "-> gom lai") -> doc log tuong
        party dang duoc gom."""
        self.assertNotIn("ACC KHONG RA LENH GOM (L1) - dieu phoi tu nhan ra", self.src)

    def test_khong_con_log_hua_hao(self):
        _ma = re.sub(r"#.*", "", self.src)      # chu thich duoc phep nhac lai cau cu de giai thich
        for _cau in ("yeu cau CA PARTY reform", "yeu cau REFORM lai ngay", "yeu cau REFORM ngay"):
            self.assertNotIn(_cau, _ma, "log con hua mot viec khong ai lam: " + _cau)


if __name__ == "__main__":
    unittest.main()
