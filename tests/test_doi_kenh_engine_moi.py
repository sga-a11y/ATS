# -*- coding: utf-8 -*-
"""LENH DOI KENH TAY phai chay duoc tren CA HAI ENGINE.

User 21/09: "party 1, t bam doi kenh ma no deo doi". Log chung minh lenh CO toi engine, engine CO
giao viec, nhung viec khong lam gi:

    18:58:20 >>> PARTY 1: lenh DOI KENH -> 2
    18:58:20 [party 1] ENGINE: sga005..tuyetdo -> lenh_tay
    18:58:22 [party 1] ENGINE: sga005..tuyetdo -> train      <- 2 giay sau ve train

Nhanh `channel` cua `_lenh_tay_engine_moi` chi `return _lam_xong()` voi ly do "dieu phoi lo bang
`kenh_dich`". Nhung `_engine_chot_kenh` nam trong `_dieu_phoi_loop`, ma vong do BO QUA party
dung engine moi (cua chan so 1) -> khong ai lo ca.

Khong ai thay cho toi khi `PARTY_ENGINE_MOI_TU` ha xuong 1 (21/09): luc do MOI party chay engine
moi va nut doi kenh chet han.

FLOW user chot 21/09 (viet vao `documents/CORE_FLOW.md`):

    chay ve safe gan nhat -> thoat party -> chuyen sang kenh duoc chon -> lap lai party
    -> chay ra lai diem quai
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _than(src, dau, het="\ndef "):
    i = src.find(dau)
    return "" if i < 0 else src[i:src.find(het, i + 10)]


class TestKhongConNuotLenh(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")
        self.than = _than(self.src, "def _lenh_tay_engine_moi(")
        self.assertTrue(self.than, "mat `_lenh_tay_engine_moi`")
        i = self.than.find('if kind == "channel":')
        self.assertGreater(i, 0, "mat nhanh channel")
        self.khoi = self.than[i:i + 1600]

    def test_nhanh_channel_THAT_SU_doi_kenh(self):
        self.assertIn("doi_kenh_theo_lenh_tay(", self.khoi,
                      "van danh dau 'da xong' ma khong doi kenh")

    def test_KHONG_do_cho_dieu_phoi_cu(self):
        """`_engine_chot_kenh` khong bao gio chay cho party engine moi."""
        _lenh = "\n".join(d for d in self.khoi.split("\n") if not d.strip().startswith("#"))
        i = _lenh.find('if kind == "channel":')
        j = _lenh.find("doi_kenh_theo_lenh_tay(")
        self.assertGreater(j, i, "return truoc khi kip doi kenh")
        self.assertNotIn("return _lam_xong()", _lenh[i:j], "van return khong khi giua chung")


class TestDungChungMotHAM(unittest.TestCase):
    """Chep doi la som muon lech: ban engine cu da duc ket ~10 ca that (thu tu ra safe/giai tan,
    ghim kenh, kien tri 5 phut, bo som khi kenh day...)."""

    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_co_ham_module_level(self):
        self.assertIn("def doi_kenh_theo_lenh_tay(", self.src)

    def test_ENGINE_CU_cung_goi_ham_do(self):
        than = _than(self.src, "def run_account(")
        self.assertIn("_dang_ky_engine_moi(", than)
        self.assertNotIn("doi_kenh_theo_lenh_tay(", than)
        self.assertNotIn("def _do_manual_cmd", than)

    def test_chi_MOT_ban_xu_ly_lenh_doi_kenh_TAY(self):
        """Dem theo `kenh_ghim` - dau hieu RIENG cua duong LENH TAY (vong sync kenh khong ghim).

        Dem `switch_channel(ch, theo_lenh=True)` thi bat nham ca nhanh retry sync kenh cua member
        (`run_account`, "chua vao party -> retry chuyen kenh") - viec khac han.
        """
        self.assertEqual(self.src.count('st["kenh_ghim"] = ch or None'), 1,
                         "hai ban xu ly lenh doi kenh tay -> mot cho sua, cho kia quen")


class TestDungFlowUserChot(unittest.TestCase):
    """chay ve safe -> thoat party -> doi kenh -> lap lai party -> ra lai diem quai."""

    def setUp(self):
        src = _doc("run_party_digioi.py")
        self.than = _than(src, "def doi_kenh_theo_lenh_tay(")
        self.assertTrue(self.than)
        self.lenh = "\n".join(d for d in self.than.split("\n") if not d.strip().startswith("#"))
        self.src = src

    def test_1_ra_safe_TRUOC(self):
        i_safe = self.lenh.find('_safe("lenh doi kenh tay")')
        i_tan = self.lenh.find("c.leave_party()")
        self.assertGreater(i_safe, 0, "khong ra safe -> doi kenh giua bay quai")
        self.assertLess(i_safe, i_tan, "giai tan truoc khi ra safe -> party tan giua bai")

    def test_2_thoat_party_TRUOC_khi_doi_kenh(self):
        i_tan = self.lenh.find("c.leave_party()")
        i_doi = self.lenh.find("c.switch_channel(ch,")
        self.assertLess(i_tan, i_doi, "con trong doi thi server tu choi doi kenh (result=3)")

    def test_3_doi_xong_CHECK_LAI_da_o_safe_chua(self):
        i_doi = self.lenh.find("c.switch_channel(ch,")
        self.assertIn('_safe("sau khi doi kenh', self.lenh[i_doi:],
                      "kenh moi cho do co the day quai ma party vua tan")

    def test_4_ENGINE_MOI_co_duong_ra_safe_that(self):
        """Truyen `ra_safe=None` thi buoc 1 bi bo, acc doi kenh ngay giua bay quai."""
        self.assertIn("def _ra_safe_engine_moi(", self.src)
        than = _than(self.src, "def _ra_safe_engine_moi(")
        self.assertIn("navigate_to(", than)
        self.assertIn("_wait_combat_clear(", than, "ra safe giua tran -> khong di duoc")
        self.assertIn("rally_point", than, "khong dung diem gom cua party")

    def test_4b_XAC_NHAN_da_toi_safe(self):
        """`navigate_to` khong tu kiem -> phai doc lai toa do (user chot 30/08)."""
        than = _than(self.src, "def _ra_safe_engine_moi(")
        self.assertIn('getattr(c, "pos", None)', than)

    def test_5_lap_lai_party_va_ra_diem_quai_do_ENGINE_lo(self):
        """Hai buoc cuoi KHONG nam trong ham doi kenh: xong lenh tay, engine quay lai chu trinh
        binh thuong -> thay party thieu -> `lap_party` -> `ra_spot`. Neo lai de khong ai nhet
        them vao ham doi kenh (lam hai lan = dap party vua lap)."""
        self.assertNotIn("invite_members(", self.than)
        self.assertNotIn("VIEC_RA_SPOT", self.than)

    def test_GHIM_kenh_de_picker_khong_keo_di(self):
        self.assertIn('st["kenh_ghim"]', self.lenh)


if __name__ == "__main__":
    unittest.main()
