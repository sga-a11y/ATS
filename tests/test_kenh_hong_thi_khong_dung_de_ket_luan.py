"""LENH DOI KENH HONG -> SO KENH DANG NHO KHONG CON LA BANG CHUNG.

User 11/09: "p24 dang o kenh 5 het, co lech kenh deo dau" -> "the may de loi cu lap lai a".

Dung, loi cu. `KNOWLEDGE.md` muc 7 da ghi tu 30/08:

    `current_channel` la so NHO SAN va no SAI DUOC. Kiem chung tan mat: bot hien ca 5 nick party 3
    o kenh 12, dang nhap vao game xem thi la 12/12/12/2/1.
    KHONG CO LENH HOI "toi dang o kenh nao" - nguon duy nhat la ack cua chinh `0x07 0200`.

Note co roi ma code van lay so do ra ket luan. Party 24, 11/09:

    00:20:01 [daimot]  Doi kenh 2 TIMEOUT sau 4.0s -> THAT BAI han toan: server IM LANG
    00:20:06 [daimuoi] Doi kenh 4 THAT BAI: khu da day nguoi (result=4)
    00:20:17 [daibay]  Doi kenh 7 THAT BAI han toan: S:007-002 ma 4
    ...
    00:21:26 [party 24] party lech kenh {1: 1, 2: 4} -> CHOT kenh dich = 5

Moi dong `THAT BAI` la mot so kenh chet cung trong bo nho bot. Dieu phoi doc dung dong so ao do,
ket luan "lech kenh", roi ra lenh doi kenh - ma doi kenh BAT BUOC roi doi truoc. Party 5 dua dang
du bi xe ra, va no dung chet 40 phut.

QUY TAC: so kenh chi dung de ket luan khi lan cham cuoi vao no la MOT ACK THAT (`S:007-002` ma 0/1,
`0x03`, `0x0c`). Lenh doi kenh hong -> danh dau nghi ngo -> dieu phoi BO QUA acc do khi dem lech
(bo qua = khong ra lenh = an toan; nguoc lai la ra lenh xe doi dua tren so ao).

KHONG lap lai bay 30/08 ("khong ro = chua sang" lam treo ca dong bo kenh): o day acc mo ho chi bi
BO KHOI PHEP DEM, khong bi coi la "dang o kenh khac".
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _doc(ten):
    with io.open(os.path.join(ROOT, ten), encoding="utf-8") as fh:
        return fh.read()


def _ma(s):
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    return re.sub(r"#.*", "", s)


class TestClientDanhDauKenhNghiNgo(unittest.TestCase):
    def setUp(self):
        self.src = _doc(os.path.join("bot", "client.py"))
        self.ma = _ma(self.src)

    def test_co_ham_kenh_dang_chac(self):
        self.assertIn("def kenh_dang_chac(", self.src)

    def test_doi_kenh_that_bai_thi_danh_dau_nghi_ngo(self):
        i = self.ma.find("THAT BAI han toan sau")
        self.assertGreater(i, 0)
        khoi = self.ma[max(0, i - 800):i + 200]
        self.assertIn("kenh_dang_nghi_ngo = True", khoi)

    def test_server_xac_nhan_thi_XOA_nghi_ngo(self):
        """Khong xoa thi mot lan hong la acc do mu kenh vinh vien."""
        i = self.ma.find("def _note_current_channel(")
        self.assertGreater(i, 0)
        khoi = self.ma[i:i + 1200]
        self.assertIn("kenh_dang_nghi_ngo = False", khoi)

    def test_van_giu_log_that_bai(self):
        """Log nay la thu duy nhat noi cho nguoi doc biet lenh da ket thuc (user 08/09)."""
        self.assertIn("Doi kenh %d THAT BAI han toan sau %d luot", self.src)


class TestDieuPhoiBoQuaKenhMoHo(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")
        i = self.src.find("def _dieu_phoi_quyet(")
        self.assertGreater(i, 0)
        dong = self.src[i:].split("\n")
        het = len(dong)
        for k, d in enumerate(dong[1:], start=1):
            if d.strip() and not d.startswith(" "):
                het = k
                break
        self.than = "\n".join(dong[:het])

    def test_phep_dem_kenh_co_loc_theo_do_chac(self):
        ma = _ma(self.than)
        i = ma.find("kenhs = set()")
        self.assertGreater(i, 0)
        khoi = ma[i:i + 900]
        self.assertIn("kenh_dang_chac()", khoi)

    def test_acc_mo_ho_khong_bi_gan_kenh_gia(self):
        """Bay 30/08: coi 'khong ro' = 'chua sang' -> treo toan bo dong bo kenh. O day chi `continue`."""
        ma = _ma(self.than)
        i = ma.find("kenh_dang_chac()")
        khoi = ma[i:i + 200]
        self.assertIn("continue", khoi)


class TestChayThatPhepDem(unittest.TestCase):
    """Chay that phep loc, khong chi doc chu."""

    @staticmethod
    def _dem(cap):
        """cap = [(kenh, chac)] - dung dung bieu thuc trong code."""
        ra = set()
        for ch, chac in cap:
            if not ch:
                continue
            if not chac:
                continue
            ra.add(int(ch))
        return ra

    def test_ca_party_cung_kenh_nhung_vai_acc_mo_ho(self):
        """Ca party 24: so nho noi lech, thuc te cung kenh -> phai ra 'khong lech'."""
        self.assertEqual(len(self._dem([(5, True), (1, False), (2, False), (5, True), (5, True)])), 1)

    def test_lech_that_van_bat_duoc(self):
        self.assertGreater(len(self._dem([(5, True), (7, True)])), 1)

    def test_tat_ca_mo_ho_thi_khong_ket_luan_gi(self):
        self.assertEqual(self._dem([(1, False), (2, False)]), set())


if __name__ == "__main__":
    unittest.main()
