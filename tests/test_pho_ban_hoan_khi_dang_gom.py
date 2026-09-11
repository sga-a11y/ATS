"""DIEU PHOI RA LENH GOM -> PHO BAN TO DOI PHAI HOAN, nhu moi viec khac.

User 11/09: "p6, deo thay lap pt di PB luon".

CA THAT (party 6, 09:32):

    09:32:23 [party 6] gen 3: viec=gom - party dang o 2 MAP khac nhau [12001, 21001]
    09:32:23 [party 6] REFORM gen -> 1 - dieu phoi: ... -> gom ve cung map/kenh
    09:32:24 [ttnnam] Boss the gioi: HOAN (login, truoc pho ban doi) - dieu phoi dang ra lenh gom
    09:32:25 [ttmot]  (LEADER) pho ban doi lv20: khong phai ca party deu con luot -> bo qua
    09:32:30 [ttmot]  (LEADER) CA party (5 nguoi) chua xong o5 -> PHO BAN TO DOI LV20
    09:32:30 [ttmot]  (LEADER) === PHO BAN TO DOI LV20: tao + moi 4 member ===

Dong 09:32:24 cho thay co `party_dang_gom` DA CO va DA CHAY DUNG - boss the gioi doc no va hoan.
Viec vat (cat do / ban Noi Dat) cung doc no. Rieng duong pho ban to doi thi chua ai noi cho biet,
nen no chay tiep ngay giua lenh gom.

Vao PB la ca party bi keo vao INSTANCE rieng: lenh gom dang chay bi bo giua chung, acc nao chua kip
vao thi ket lai ben ngoai -> lech map -> dieu phoi lai ra lenh gom -> vong lai.

KHONG THEM CO MOI: dung dung co `party_dang_gom(pidx)` ma cac duong khac dang dung.
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


class TestPhoBanDocLenhDieuPhoi(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.than = _than(self.src, "def _handle_o5_team(")
        self.ma = _ma(self.than)

    def test_co_cua_hoan_khi_dang_gom(self):
        self.assertIn("party_dang_gom(pidx)", self.ma,
                      "duong pho ban to doi khong doc lenh dieu phoi -> chay giua luc dang gom")

    def test_cua_dung_TRUOC_moi_buoc_tao_PB(self):
        """Tao PB la keo ca party vao instance - khong hoan tac duoc."""
        i_cua = self.ma.find("party_dang_gom(pidx)")
        self.assertGreater(i_cua, 0)
        for _moc in ("do_team_dungeon", "PHO BAN TO DOI LV20", "o5_state"):
            i = self.ma.find(_moc)
            if i > 0:
                self.assertLess(i_cua, i, "cua hoan phai dung truoc '%s'" % _moc)

    def test_hoan_thi_RA_LUON(self):
        i = self.ma.find("party_dang_gom(pidx)")
        khoi = self.ma[i:i + 400]
        self.assertIn("return", khoi)

    def test_GHI_LY_DO_khi_hoan(self):
        """Bot tu biet va tu ghi ly do - khong de nguoi doc phai doan vi sao PB khong chay."""
        self.assertIn("pho ban to doi: HOAN", self.than)

    def test_dung_chung_co_voi_cac_duong_khac(self):
        """Khong duoc de ra co rieng: mot co, mot cho dat (`dat_party_dang_gom`), nhieu cho doc."""
        self.assertIn("dat_party_dang_gom(pidx, viec in", self.src)
        self.assertGreaterEqual(self.src.count("party_dang_gom("), 2)


class TestCoGomVanDuocDatDung(unittest.TestCase):
    """Co chi bat khi dieu phoi THUC SU dang dieu party (gom / moi / dong bo), khong phai luc nao
    cung bat - neu khong thi PB khong bao gio chay duoc."""

    def test_co_bat_theo_viec_cap_party(self):
        src = _src()
        i = src.find("dat_party_dang_gom(pidx, viec in")
        self.assertGreater(i, 0)
        dong = src[i:i + 200]
        for _v in ("VIEC_GOM", "VIEC_MOI", "VIEC_DONG_BO"):
            self.assertIn(_v, dong)
        self.assertNotIn("VIEC_LAM", dong, "VIEC_LAM ma bat co thi PB/viec vat khong bao gio chay")


if __name__ == "__main__":
    unittest.main()
