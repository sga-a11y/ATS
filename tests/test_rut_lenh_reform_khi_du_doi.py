"""DIEU PHOI ra lenh thi DIEU PHOI RUT LENH khi lenh da dat muc dich.

User 13/09: "party 1 bi cai lon gi ma gom du pt, 1 luc sau lai huy pt roi pt lai" ->
"ro rang dieu phoi ra lenh ngu thi phai sua dieu phoi".

`_bump_reform` la lenh "doi hong, lap lai di". Doi du roi thi lenh do CHET - nhung truoc day
khong ai thu no ve, no nam cho duoc thi hanh THEM LAN NUA, va lan do pha dung cai party vua lap.

CA THAT party 1 (thbay = leader, 4 member):
    23:19:02 [party 1] REFORM gen -> 2 - chung kenh roi ma doi khong du -> lap lai party
    23:19:33 [thbay] (LEADER) moi 4 member theo entity ...
    23:19:33 PARTY: 7c5dd8f8 vao doi -> roster 1 nguoi
    23:19:34 PARTY: c45ad8f8 vao doi -> roster 2 nguoi
    23:19:36 PARTY: dc5ad8f8 vao doi -> roster 3 nguoi
    23:19:44 PARTY: 0c1dd3f8 vao doi -> roster 4 nguoi
    23:19:49 [thbay] (LEADER) DU PARTY (4/4 member join)        <- LENH DA DAT MUC DICH
    23:19:50 [thbay] (LEADER) reform pending -> BO QUA keo ra spot, de keepalive REFORM
    23:19:55 [thbay] (LEADER) -> REFORM party (gen 2)           <- PHA party vua lap
    23:19:55 [thbay] reform gen 2: bao CA PARTY ra diem tap ket truoc khi lap lai party

Leader lam DUNG lenh - loat moi 23:19:33 chinh la noi dung cua gen 2. Nhung viec moi do chay trong
vong moi cua leader, khong cham vao `reform_gen_handled` (chi vong chinh ghi), nen quay ve vong
chinh no van thay `reform_gen 2 > handled 1` -> lam lai tu dau -> lap vinh vien.

CACH SUA (user chot): DIEU PHOI rut lenh. KHONG de acc tu ket luan "minh vua lam xong cai ma lenh
muon" - do la mo lai cua acc tu quyet (L1). Acc chi DOC `reform_gen_thoa`.
"""
from __future__ import annotations

import io
import os
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _src_engine():
    """LUAT cap party da chuyen vao engine (21/09) - `party_engine.quyet_dinh_cap_party`."""
    with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
        return fh.read()


class TestChiRutONhanhDUDOI(unittest.TestCase):
    """Rut nham luc con lech map/kenh/thieu nguoi = nuot lenh dang can."""

    def setUp(self):
        self.src = _src()
        pe = _src_engine()
        i = pe.find("def quyet_dinh_cap_party(")
        self.assertGreater(i, 0, "mat quyet_dinh_cap_party")
        self.than = pe[i:]
        # Phan THI HANH (ghi `reform_gen_thoa` that su) van o `run_party_digioi`.
        k = self.src.find("def _thi_hanh_hieu_ung(")
        self.assertGreater(k, 0, "mat _thi_hanh_hieu_ung")
        self.thi_hanh = self.src[k:self.src.find("\ndef ", k + 10)]

    def test_co_ghi_reform_gen_thoa(self):
        self.assertIn("hu.rut_reform = True", self.than,
                      "dieu phoi khong rut lenh reform -> lenh chet van duoc thi hanh lai")
        self.assertIn('st["reform_gen_thoa"] = _rg', self.thi_hanh)

    def test_rut_nam_trong_nhanh_DU_DOI(self):
        """Phai nam SAU `else:` cuoi chuoi bac - tuc du doi + cung map + cung kenh."""
        _else = self.than.find("# DU DOI, CUNG MAP+KENH -> hai buoc cuoi")
        self.assertGreater(_else, 0, "mat nhanh else 'DU DOI, CUNG MAP+KENH'")
        _rut = self.than.find("hu.rut_reform = True")
        self.assertGreater(_rut, _else,
                           "rut lenh NGOAI nhanh du doi -> nuot ca lenh gom/dong bo dang can")

    def test_chi_rut_DUNG_MOT_LAN(self):
        """Rut o hai cho = chac chan co cho rut nham nhanh chua xong viec."""
        self.assertEqual(self.than.count("hu.rut_reform = True"), 1,
                         "co nhieu hon mot cho rut lenh reform trong dieu phoi")

    def test_moi_bac_chan_cua_CHUOI_deu_dung_truoc_cho_rut(self):
        """Ba bac cua chuoi (gom map / dong bo kenh / moi) phai nam TRUOC cho rut.

        (Cac cho gan `viec = VIEC_GOM` SAU do la phep khac - dam chan o thanh / dung hinh - va
        chung tu bump gen MOI, khong bi moc rut che.)
        """
        _rut = self.than.find("hu.rut_reform = True")
        self.assertGreater(_rut, 0)
        for _bac in ('ly_do = "cung map/kenh nhung DOI chua du',
                     "gom kenh truoc khi moi",
                     "dang o thanh DI NGANG QUA"):
            i = self.than.find(_bac)
            self.assertGreater(i, 0, "mat bac %r" % _bac)
            self.assertLess(i, _rut, "bac %r nam SAU cho rut -> rut khi viec chua xong" % _bac)


class TestAccCHIDOC(unittest.TestCase):
    """Acc khong duoc tu ket luan lenh da xong - chi doc con so dieu phoi ghi (L1)."""

    def setUp(self):
        self.src = _src()

    def test_vong_chinh_doc_reform_gen_thoa_TRUOC_khi_thi_hanh(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        with mock.patch.dict(R._party_state, {}, clear=True):
            st = R._pstate(0)
            st["reform_gen"] = 3
            st["reform_gen_thoa"] = 3
            self.assertFalse(R._reform_cho_xu(st, 0))

    def test_acc_khong_tu_GHI_reform_gen_thoa(self):
        """Chi dieu phoi duoc ghi. Acc ghi = acc tu quyet lenh nao con song."""
        # Cho DUY NHAT duoc ghi gio la `_thi_hanh_hieu_ung` (thi hanh `HieuUng` ma
        # `party_engine.quyet_dinh_cap_party` tra ve).
        i = self.src.find("def _thi_hanh_hieu_ung(")
        j = self.src.find("\ndef ", i + 10)
        ngoai = self.src[:i] + self.src[j:]
        self.assertNotIn('st["reform_gen_thoa"] =', ngoai,
                         "co cho NGOAI dieu phoi ghi reform_gen_thoa")


class TestHanhVi(unittest.TestCase):
    """Mo phong con so: lenh da rut thi khong thi hanh lai, lenh moi hon van chay."""

    @staticmethod
    def _can_lam(st, handled):
        _thoa = int(st.get("reform_gen_thoa", 0) or 0)
        if _thoa > handled:
            handled = _thoa
        return int(st.get("reform_gen", 0) or 0) > handled, handled

    def test_lenh_da_rut_thi_khong_lam_lai(self):
        st = {"reform_gen": 2, "reform_gen_thoa": 2}
        lam, _h = self._can_lam(st, 1)
        self.assertFalse(lam, "party du roi van reform lai -> pha chinh party vua lap")

    def test_lenh_MOI_sau_khi_rut_van_phai_chay(self):
        """Doi tan LAN NUA -> dieu phoi bump gen 3 -> phai thi hanh, khong bi lenh rut che mat."""
        st = {"reform_gen": 3, "reform_gen_thoa": 2}
        lam, _h = self._can_lam(st, 2)
        self.assertTrue(lam)

    def test_chua_rut_thi_van_chay_nhu_cu(self):
        st = {"reform_gen": 2}
        lam, _h = self._can_lam(st, 1)
        self.assertTrue(lam)

    def test_rut_khong_ha_moc_da_xu_ly(self):
        st = {"reform_gen": 5, "reform_gen_thoa": 2}
        lam, h = self._can_lam(st, 4)
        self.assertTrue(lam)
        self.assertEqual(h, 4, "moc da xu ly bi ha xuong -> thi hanh lai lenh cu")


class TestBumpVanNguyenVen(unittest.TestCase):
    """Rut lenh khong duoc lam hong `_bump_reform` (gen phai TANG, khong lui)."""

    def test_bump_van_tang_gen(self):
        st = {"lock": threading.RLock(), "pidx": 0, "reform_gen": 7, "reform_gen_thoa": 7}
        with st["lock"]:
            _g = R._bump_reform(st, "test", uu_tien=True)
        self.assertEqual(_g, 8)
        self.assertEqual(st["reform_gen"], 8)
        self.assertEqual(st["reform_gen_thoa"], 7, "bump khong duoc dong vao moc rut")


if __name__ == "__main__":
    unittest.main()
