"""MOI BUMP REFORM LA MOT LENH ABORT CA PARTY - KHONG DUOC RA HAI LENH LIEN TIEP.

User 11/09: "party 19, deu leader 1 noi member 1 noi, kha nang lai bi cai loi dang di ra bai thi
member tele ve thanh, leader thi ngu van di 1 minh".

CA THAT (party 19, 08:04 - hai lenh cach nhau BON giay):

    08:04:21 [party 19] gen 19: viec=gom - party o 2 MAP khac nhau [12001, 21001]
    08:04:21 [party 19] REFORM gen -> 3 (bump tai :9531) - gom ve cung map/kenh
    08:04:19 [quanmot] (LEADER) pre-route: tele trung gian ve thanh 12001 truoc
    08:04:23 [quanmot] (LEADER) Da ve thanh 12001 -> Teleport -> city 21001 (flag 13)
    08:04:25 [party 19] gen 20: viec=moi - cung map/kenh nhung DOI chua du
    08:04:25 [party 19] REFORM gen -> 4 (bump tai :9807) - lap lai party
    08:04:25 [vumot]   (member) ABORT di duong reform: reform_gen 3 -> 4 (acc khac bump)
    08:04:25 [quantam] (member) ABORT di duong reform: reform_gen 3 -> 4 (acc khac bump)

Leader vua tele qua 12001 roi 21001, nen co DUNG MOT NHIP ca party bi doc la "cung map". Dieu phoi
tuong da gom xong -> ra lenh lap party -> lenh do ABORT chinh hai member dang tren duong. Leader di
tiep mot minh.

CAC COOLDOWN SAN CO KHONG PHU DUOC CHO NAY:
    `KE_HOACH_GOM_COOLDOWN`   chan gom -> gom
    `LAP_LAI_PARTY_COOLDOWN`  chan lap -> lap
Chuoi gom -> lap party thi khong ai chan. Nen han phai nam o CHINH `_bump_reform` - noi duy nhat
moi lenh deu di qua - chu khong phai o tung nhanh goi.
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


class TestBumpCoKhoangLang(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.than = _than(self.src, "def _bump_reform(")
        self.ma = _ma(self.than)

    def test_co_hang_khoang_lang(self):
        self.assertIn("REFORM_BUMP_CACH_TOI_THIEU_SEC = ", self.src)

    def test_han_du_dai_cho_mot_chuyen_tele(self):
        """Leader tele ve thanh roi tele ra bai mat ~10-20s. Han ngan hon la khong chan duoc gi."""
        m = re.search(r"REFORM_BUMP_CACH_TOI_THIEU_SEC = ([0-9.]+)", self.src)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(float(m.group(1)), 20.0)

    def test_bump_som_thi_KHONG_tang_gen(self):
        """Tang gen roi moi kiem la da ABORT xong - kiem vo nghia."""
        i_chan = self.ma.find("REFORM_BUMP_CACH_TOI_THIEU_SEC")
        i_tang = self.ma.find('st["reform_gen"] = st.get("reform_gen", 0) + 1')
        self.assertGreater(i_chan, 0, "mat cua chan trong _bump_reform")
        self.assertGreater(i_tang, 0)
        self.assertLess(i_chan, i_tang, "phai kiem TRUOC khi tang reform_gen")

    def test_bump_bi_bo_qua_van_GHI_LY_DO(self):
        """Bot phai tu ghi ly do khi khong lam - khong de nguoi doc phai doan."""
        self.assertIn("BO QUA bump reform", self.than)

    def test_ghi_lai_moc_moi_lan_bump_that(self):
        self.assertIn('st["reform_bump_luc"] = time.time()', self.ma)


class TestChayThat(unittest.TestCase):
    """Chay that phep chan, khong chi doc chu."""

    @staticmethod
    def _bump(st, now, han):
        """Mo phong dung thu tu trong code: kiem truoc, tang sau."""
        truoc = st.get("reform_bump_luc", 0.0)
        if truoc and now - truoc < han:
            return st.get("reform_gen", 0), False
        st["reform_bump_luc"] = now
        st["reform_gen"] = st.get("reform_gen", 0) + 1
        return st["reform_gen"], True

    def test_hai_lenh_cach_4_giay_thi_lenh_hai_bi_bo(self):
        """Dung ca party 19: gom luc t=0, lap party luc t=4."""
        st = {}
        g1, ok1 = self._bump(st, 1000.0, 30.0)
        g2, ok2 = self._bump(st, 1004.0, 30.0)
        self.assertTrue(ok1)
        self.assertFalse(ok2, "lenh thu hai phai bi bo - no ABORT member dang di duong")
        self.assertEqual(g1, g2, "gen KHONG duoc tang -> member khong bi abort")

    def test_lenh_dau_tien_luon_di_qua(self):
        self.assertEqual(self._bump({}, 1000.0, 30.0), (1, True))

    def test_qua_han_thi_bump_binh_thuong(self):
        st = {}
        self._bump(st, 1000.0, 30.0)
        g, ok = self._bump(st, 1031.0, 30.0)
        self.assertTrue(ok)
        self.assertEqual(g, 2)

    def test_party_hong_that_van_duoc_cuu_sau_han(self):
        """Chan khong duoc bien thanh 'khong bao gio bump nua' (L0: party hong phai gom BANG DUOC)."""
        st = {}
        n = 0
        for t in range(1000, 1200, 5):        # thu bump moi 5 giay trong 200 giay
            if self._bump(st, float(t), 30.0)[1]:
                n += 1
        self.assertGreaterEqual(n, 6, "van phai cuu duoc party, chi la thua hon")


if __name__ == "__main__":
    unittest.main()
