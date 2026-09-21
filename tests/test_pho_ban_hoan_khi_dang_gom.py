"""PHO BAN TO DOI **KHONG** HOAN THEO LENH DIEU PHOI (doi 17/09) - y het boss the gioi / PB don.

## Truoc day: CO hoan (11/09)

User 11/09: "p6, deo thay lap pt di PB luon". Ca that (party 6, 09:32):

    09:32:23 [party 6] gen 3: viec=gom - party dang o 2 MAP khac nhau [12001, 21001]
    09:32:24 [ttnnam] Boss the gioi: HOAN (login, truoc pho ban doi) - dieu phoi dang ra lenh gom
    09:32:30 [ttmot]  (LEADER) === PHO BAN TO DOI LV20: tao + moi 4 member ===

Luc do boss the gioi da biet hoan con duong PB to doi thi chua, nen no chay giua lenh gom.

## Gio: KHONG hoan nua

Chinh cua hoan do lai la thu giet PB to doi. Do tren log 17/09:

    1762 lan `pho ban to doi: HOAN`   /   33 lan `=== PHO BAN TO DOI LV20 ===`

98% so lan bi hoan - dung cai da xay ra voi boss the gioi va PB don, va da duoc xu 14/09 bang
cach BO CUA HOAN (khi do: 2739 lan `Boss the gioi: HOAN`, 3224 lan `Dungeon: HOAN`, o 1 chi
14/152 acc sang duoc). Ly do giong het: viec nay chay o login chores, ma luc moi login ca party
dung moi dua mot noi -> dieu phoi LUON dang ra lenh gom/moi -> hoan -> va vi chi chay MOT LAN,
mat luot CA NGAY.
User 17/09 (khi thay engine moi danh duoc PB don ma khong danh PB doi): "flow cu co hoan nua dau,
m bia ra a".

## Vi sao gio an toan (ba ly do da viet san cho boss the gioi)

  * dieu phoi KHONG con tinh acc dang viec vat / `VIEC_DAILY` vao phep do lech map/kenh
  * loi moi party duoc GIU lai den khi acc xong viec
  * PB to doi keo CA PARTY vao cung mot instance, va ca party deu dang lam daily cung luc - khac
    han canh mot acc bo di danh boss mot minh
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

    def test_KHONG_con_cua_hoan(self):
        """1762 lan HOAN / 33 lan danh duoc (log 17/09) - cua hoan giet luon tinh nang."""
        self.assertNotIn("party_dang_gom(pidx)", self.ma,
                         "cua hoan dat dung vao luc LUON DANG GOM -> mat luot PB doi ca ngay")

    def test_van_GHI_RO_vi_sao_bo(self):
        """Doi hanh vi nguoc lai voi ca that 11/09 thi phai de lai ly do ngay tai cho."""
        self.assertIn("KHONG HOAN THEO LENH DIEU PHOI NUA", self.than)
        self.assertIn("14/09", self.than, "phai dan lai lan bo cua hoan cho boss the gioi / PB don")

    def test_boss_the_gioi_va_PB_don_cung_KHONG_hoan(self):
        """Ba duong nay phai cung mot luat - khong duoc moi duong mot kieu."""
        self.assertIn("KHONG HOAN THEO LENH DIEU PHOI NUA", self.src)

    def test_co_party_dang_gom_VAN_con_cho_viec_vat(self):
        """Bo cua o PB to doi KHONG co nghia xoa ca co: cat do / ban Noi Dat van phai hoan khi gom
        (chung keo acc sang map KHAC mot minh, khac han PB to doi keo CA party vao instance)."""
        self.assertIn("dat_party_dang_gom(pidx, hu.dang_gom)", self.src)
        self.assertIn("party_dang_gom(", self.src)


class TestCoGomVanDuocDatDung(unittest.TestCase):
    """Co chi bat khi dieu phoi THUC SU dang dieu party (gom / moi / dong bo), khong phai luc nao
    cung bat - neu khong thi PB khong bao gio chay duoc."""

    def test_co_bat_theo_viec_cap_party(self):
        """Luat gio o `party_engine.quyet_dinh_cap_party`: `hu.dang_gom` chi bat khi dieu phoi
        THUC SU dang dieu party (gom / moi / dong bo)."""
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            pe = fh.read()
        i = pe.find("hu.dang_gom = viec in")
        self.assertGreater(i, 0, "mat cho bat co 'party dang gom'")
        dong = pe[i:i + 200]
        for _v in ("DP_GOM", "DP_MOI", "DP_DONG_BO"):
            self.assertIn(_v, dong)
        self.assertNotIn("DP_LAM", dong, "DP_LAM ma bat co thi PB/viec vat khong bao gio chay")


if __name__ == "__main__":
    unittest.main()
