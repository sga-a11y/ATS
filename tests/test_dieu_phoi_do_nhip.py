"""DIEU PHOI phai BAO khi chinh no bi tre nhip.

Do dac 13/09 (user: "dang chay la 250 acc day, m thu do xem dieu phoi quet kip ko"), 50 party x 5:

    dieu phoi chay mot minh              16 ms/vong   (0.33 ms moi party)
    250 luong acc CHO socket             15 ms        kip
    250 luong acc ban vua                61 ms        kip
    250 luong acc ban nhieu            2334 ms        TRE hon nhip 2s
    250 luong acc ban lien tuc         4668 ms        TRE nang (dinh 6.3s)

Ket luan: SO PARTY khong bao gio la van de - 500 party van chua toi 200ms. Cai lam dieu phoi tre
la GIL: luong nay phai xep hang voi 250 luong acc. Nen TACH MOI PARTY MOT LUONG DIEU PHOI khong
giup gi, con them 50 luong nua vao dung cai hang dang tac.

Da xay ra that (L10, p5 13:15-13:20): mot vong nong cua acc `continue` khong ngu -> 8.000 vong/
giay -> bo doi luong dieu phoi -> ke hoach dong bang 5 phut o `viec=gom` du party da chung kenh.
Luc do khong co gi bao; phai doc log acc moi lan ra.

Dieu phoi la luong DUY NHAT ra lenh cho ca bot: no tre bao nhieu giay = ca bot mu bay nhieu giay.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestCoDongHo(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        i = self.src.find("def _dieu_phoi_loop():")
        self.assertGreater(i, 0)
        j = self.src.find("\ndef ", i + 10)
        self.than = self.src[i:j]

    def test_do_khoang_cach_giua_hai_nhip(self):
        self.assertIn("DIEU PHOI TRE NHIP", self.than,
                      "khong do nhip -> dieu phoi bi bo doi ma khong ai biet")

    def test_do_thoi_gian_QUET(self):
        """Hai trieu chung khac nhau: bi doi CPU (giua hai nhip) vs co party keo dai vong quet."""
        self.assertIn("quet %d party mat", self.than)

    def test_nguong_lon_hon_nhip(self):
        """Canh bao duoi nhip = spam moi vong."""
        self.assertGreater(R.DIEU_PHOI_TRE_CANH_BAO_SEC, R.KE_HOACH_NHIP / 2)

    def test_nguong_quet_lau_cao_hon_muc_do_duoc_rat_nhieu(self):
        """16ms do duoc; nguong 1s = gap 60 lan -> khong bao oan."""
        self.assertGreaterEqual(R.DIEU_PHOI_QUET_LAU_SEC, 0.5)

    def test_khong_spam_log(self):
        """Tre nhip thuong keo dai nhieu vong lien -> phai co cua chong spam."""
        self.assertIn("_bao_tre_luc", self.than)
        self.assertIn("> 60.0", self.than)


class TestVanLaMOT_LUONG(unittest.TestCase):
    """Mot cho quyet (L1). Do dac cho thay tach ra khong giai quyet gi."""

    def setUp(self):
        self.src = _src()

    def test_chi_mot_luong_dieu_phoi(self):
        self.assertIn('name="dieu-phoi"', self.src)
        self.assertEqual(self.src.count("target=_dieu_phoi_loop"), 1,
                         "co hon mot luong dieu phoi -> hai cho cung ra lenh cho mot party")

    def test_loi_mot_party_khong_giet_ca_vong(self):
        i = self.src.find("def _dieu_phoi_loop():")
        j = self.src.find("\ndef ", i + 10)
        self.assertIn("DIEU PHOI loi (bo qua nhip nay)", self.src[i:j])


class TestQuetHetMoiParty(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_khong_bo_sot_party_nao(self):
        i = self.src.find("def _dieu_phoi_loop():")
        j = self.src.find("\ndef ", i + 10)
        than = re.sub(r"#.*", "", self.src[i:j])
        self.assertIn("for pidx in range(so_party):", than)
        self.assertNotIn("break", than, "thoat giua chung = party phia sau khong duoc quet")

    def test_moi_party_mot_so_rieng(self):
        """Khong lan party: state, acc, dong ho lech deu khoa theo pidx."""
        i = self.src.find("def _dieu_phoi_loop():")
        j = self.src.find("\ndef ", i + 10)
        than = self.src[i:j]
        for _k in ("_acc_song(pidx)", "_pstate(pidx)", "lech_tu[pidx]", "lech_tu.get(pidx)"):
            self.assertIn(_k, than, _k)


if __name__ == "__main__":
    unittest.main()
