"""DANG THI HANH THI GIU LENH, KHONG PHAI VUT LENH.

User 11/09: "di DG, thay bon no ko du pt" -> "truoc do da du party 5 dua va dang danh roi, sau do
tu nhien dieu phoi lam cai gi ma no hong pt" -> "lenh nay la cua dua nao dua ra".

Lenh la CUA DIEU PHOI (`DIEU PHOI GUI doi kenh ...` trong log), khong phai acc tu quyet.

CA THAT (party 24, 11/09 - MUOI lenh doi kenh trong 72 giay):

    00:21:26  {1:1, 2:4}       -> CHOT kenh dich = 5
    00:21:40  {2:2, 5:3}       -> CHOT kenh dich = 4
    00:21:46  {2:2, 4:3}       -> CHOT kenh dich = 5
    00:21:53  {2:2, 4:3}       -> CHOT kenh dich = 3
    00:21:59  {2:2, 4:1, 5:2}  -> CHOT kenh dich = 4
    00:22:07  {2:2, 4:1, 5:2}  -> CHOT kenh dich = 5
    00:22:13  {2:2, 4:1, 5:2}  -> CHOT kenh dich = 7
    00:22:19  {2:2, 5:3}       -> CHOT kenh dich = 5
    00:22:26  {2:2, 5:3}       -> CHOT kenh dich = 4
    00:22:38  {4:2, 5:3}       -> CHOT kenh dich = 5

Ba dong lien tiep la CUNG mot phan bo ma ba ket luan khac nhau. Moi lenh bat acc `leave_party()`
roi nhay kenh (server cam doi kenh khi con trong doi), nen party 5 dua DANG DU bi xe ra:

    00:21:27 [daimot] (LEADER) chua moi 4 member: ['...:lech kenh live 1!=5', ...]
    00:21:27 [daimot] (LEADER) Di Gioi moi 226s chua du party (0/4) -> MOI TIEP

Roi no dung chet 40 phut, va "5/5 acc DUNG HINH qua 240s" chi la HAU QUA cuoi chuoi.

NGUYEN NHAN: cua o `_dieu_phoi_chot_kenh` gop HAI ca can hai hanh dong khac han vao lam mot:

    doi DA DU      -> het viec that       -> XOA `kenh_dich`   (dung)
    dang doi kenh  -> lenh dang THI HANH  -> XOA `kenh_dich`   (SAI)

Xoa o ca thu hai = bo lenh giua chung. Nhip sau acc bay xong, `_dang_doi_kenh` tat, ma `cu` da la
None nen cua "DA CHOT ROI THI GIU" khong con gi de giu -> chot lai bang phan bo VUA DOI -> dich
khac -> ca party quay dau -> lap lai mai.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _than(src, dau):
    """Than ham cap module - neo theo THUT LE GIAM, khong theo cua so ky tu (L3i)."""
    i = src.find(dau)
    assert i > 0, dau
    dong = src[i:].split("\n")
    het = len(dong)
    for k, d in enumerate(dong[1:], start=1):
        if d.strip() and not d.startswith(" "):
            het = k
            break
    return "\n".join(dong[:het])


def _ma(s):
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    return re.sub(r"#.*", "", s)


class TestDangDoiKenhThiGiuDich(unittest.TestCase):
    def setUp(self):
        self.than = _than(_src(), "def _dieu_phoi_chot_kenh(")
        self.ma = _ma(self.than)

    def test_co_nhanh_GIU_dich_khi_dang_thi_hanh(self):
        self.assertIn("return int(st[\"kenh_dich\"])", self.ma,
                      "mat nhanh giu dich -> lenh doi kenh lai bi vut giua chung")

    def test_nhanh_GIU_dung_TRUOC_nhanh_XOA(self):
        """Thu tu quan trong: nhanh xoa cu van con `or _dang_doi_kenh(song)` trong dieu kien."""
        i_giu = self.ma.find("return int(st[\"kenh_dich\"])")
        i_xoa = self.ma.find("or _dang_doi_kenh(song)")
        self.assertGreater(i_giu, 0)
        self.assertGreater(i_xoa, 0)
        self.assertLess(i_giu, i_xoa, "nhanh giu phai chan truoc nhanh xoa")

    def test_chi_GIU_khi_that_su_dang_co_dich(self):
        """Khong co dich thi khong co gi de giu - phai di chot binh thuong."""
        i = self.ma.find("return int(st[\"kenh_dich\"])")
        dieu_kien = self.ma[max(0, i - 400):i]
        self.assertIn("st.get(\"kenh_dich\")", dieu_kien)
        self.assertIn("_dang_doi_kenh(song)", dieu_kien)

    def test_van_con_cua_DA_CHOT_THI_GIU(self):
        """Cua kien nhan cu la lop chan thu hai - khong duoc mat."""
        self.assertIn("KENH_DICH_KIEN_NHAN_SEC", self.ma)


class TestDauVetTinhCaDanhTaiCho(unittest.TestCase):
    """Danh tai cho cung la TIEN DO - DG dung mot cho ban Phuc Than, map/pos khong bao gio doi."""

    def setUp(self):
        self.than = _than(_src(), "def _dau_vet_acc(")

    def test_dau_vet_co_the_he_tran(self):
        self.assertIn("battle_tracker", self.than)
        self.assertIn("generation", self.than)

    def test_van_con_map_va_vi_tri(self):
        self.assertIn("current_map", self.than)
        self.assertIn("pos", self.than)


class TestKhongResyncPartyDangLanh(unittest.TestCase):
    """`resync_gen` chi lam duoc mot viec: bat moi member roi doi roi moi lai. Party DU + cung
    kenh thi do la dap doi dang lanh, khong phai chua treo."""

    def setUp(self):
        self.than = _than(_src(), "def _dieu_phoi_quyet(")

    def test_DG_party_du_va_cung_kenh_thi_khong_resync(self):
        ma = _ma(self.than)
        i = ma.find("_acc_dung_hinh(st, song, KE_HOACH_DUNG_HINH_SEC)")
        self.assertGreater(i, 0)
        khoi = ma[i:i + 900]
        self.assertIn("_thieu_doi(pidx, song)", khoi)
        self.assertIn("len(kenhs) <= 1", khoi)

    def test_van_giu_phat_hien_dung_hinh(self):
        """Chi bo CACH CHUA sai, khong bo phep do - party ket that van phai bat duoc."""
        self.assertIn("DUNG HINH qua", self.than)


if __name__ == "__main__":
    unittest.main()
