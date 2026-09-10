"""MOT PARTY MOT KET LUAN. Chot kenh khong duoc tu ket luan lai tinh hinh party.

User 10/09: "khac map ma dieu phoi ngu toi ko nhan ra" -> "logic thi cuc ky don gian chi co vay:
check map truoc, lech map thi gom map, sau do check kenh, lech kenh thi gom kenh, du pt thi di
train".

Logic do CO SAN va DUNG trong `_dieu_phoi_quyet`. Cai hong la ben canh no: `_dieu_phoi_chot_kenh`
chup `song` MOT LAN NUA va TU di kiem map lai. Hai anh chup cach nhau vai tram ms -> hai ket luan
trai nguoc trong cung mot nhip.

CA THAT (party 6, 10/09 - party 7 y het, lech 6 giay):

    23:19:50  DIEU PHOI: ca party da chung kenh 1 nhung DOI chua du -> LAP LAI PARTY   <- chot kenh
    23:19:59  gen 25: viec=lam - con lech map [21001, 21002] -> chua lap party         <- ben quyet
    23:20:11  gen 26: viec=gom - party dang o 2 MAP khac nhau [12001, 21001]
    ...
    23:45:46  DIEU PHOI: ca party da chung kenh 1 nhung DOI chua du
              (taot001=4 taot002=4 taot003=3 taot004=2 taot005=1) -> LAP LAI PARTY
    23:46:34  gen 15: viec=gom - party dang o 3 MAP khac nhau [12001, 23001, 23811]

Dong `taot001=4 ... taot005=1` la roster DANG LEN - party dang duoc moi do dang thi bi `_bump_reform`
cat ngang -> giai tan -> moi lai tu dau. Tu 23:43 den 23:47 quay dung mot vong: gom -> lap lai ->
lech map -> gom lai, khong lan nao qua noi 4/5.

Bump reform la lenh ABORT moi acc dang di duong (L6/L7). Ra no giua vong gom = huy chinh viec minh
vua ra lenh.

`VIEC_MOI` la lenh DUY NHAT co nghia "da cung map + cung kenh, gio lap doi di". Moi viec khac
(`gom` / `dong_bo` / `lam`) deu co nghia CHUA den luot lap party.
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
    """Than mot ham cap module - neo theo THUT LE GIAM, khong theo cua so ky tu (L3i)."""
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


class TestChotKenhNhanKeHoach(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.than = _than(self.src, "def _dieu_phoi_chot_kenh(")

    def test_ham_nhan_ke_hoach_vua_quyet(self):
        """Khong tu suy ra tinh hinh - nhan thang ket luan cua `_dieu_phoi_quyet`."""
        self.assertRegex(self.than.split("\n")[0],
                         r"def _dieu_phoi_chot_kenh\(pidx, st, song, kh")

    def test_noi_goi_truyen_ke_hoach_CUNG_NHIP(self):
        """`kh` phai la ke hoach vua quyet o dong tren, khong phai doc lai tu `st`."""
        ma = _ma(self.src)
        i = ma.find("kh, ly_do, lech_tu[pidx] = _dieu_phoi_quyet(")
        self.assertGreater(i, 0)
        khoi = ma[i:i + 900]
        self.assertIn("_dieu_phoi_chot_kenh(pidx, st, song, kh)", khoi)

    def test_chi_LAP_LAI_PARTY_khi_viec_la_MOI(self):
        """Cua chan phai dung TRUOC `_bump_reform` - bump la lenh khong hoan tac duoc."""
        ma = _ma(self.than)
        i_cua = ma.find("!= VIEC_MOI")
        self.assertGreater(i_cua, 0, "khong con cua chan theo `viec` -> chot kenh lai nhay coc")
        i_bump = ma.find("_bump_reform(")
        self.assertGreater(i_bump, 0)
        self.assertLess(i_cua, i_bump, "cua chan phai dung TRUOC bump reform")

    def test_cua_chan_RA_LUON_khong_lam_gi_them(self):
        i = self.than.find("!= VIEC_MOI")
        khoi = _ma(self.than[i:i + 400])
        self.assertIn("return None", khoi)


class TestThuTuGomVanGiuNguyen(unittest.TestCase):
    """Thu tu user chot: lech map -> gom map; cung map ma lech kenh -> gom kenh; du thi train."""

    def setUp(self):
        self.than = _than(_src(), "def _dieu_phoi_quyet(")

    def test_lech_map_thi_KHONG_lap_party(self):
        i = self.than.find("con lech map %s -> chua lap party")
        self.assertGreater(i, 0, "mat nhanh 'lech map -> chua lap party'")

    def test_cung_map_ma_lech_kenh_thi_DONG_BO_TAI_CHO(self):
        """Lech kenh khong keo ca party ve thanh - doi kenh la xong."""
        self.assertIn("viec = VIEC_DONG_BO if len(maps) <= 1 else VIEC_GOM", _ma(self.than))

    def test_chi_khi_cung_map_cung_kenh_moi_ra_VIEC_MOI(self):
        ma = _ma(self.than)
        i_lech = ma.find("elif song and len(maps) > 1:")
        i_moi = ma.find("elif song and _thieu_doi(pidx, song):")
        self.assertGreater(i_lech, 0)
        self.assertGreater(i_moi, i_lech,
                           "nhanh lap party phai dung SAU nhanh lech map, khong thi no gianh truoc")


if __name__ == "__main__":
    unittest.main()
