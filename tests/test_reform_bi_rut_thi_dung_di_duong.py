# -*- coding: utf-8 -*-
"""LENH REFORM BI RUT -> vong di duong phai DUNG NGAY, khong di tiep.

`_do_reform` di duong trong mot vong `while not _ab()`. `_ab()` truoc day chi bat ba thu:
party da dung · client chet · `reform_gen` bi acc KHAC bump. Lenh bi DIEU PHOI RUT
(`reform_gen_thoa`, L16) thi gen KHONG tang -> vong cu chay tiep cho mot lenh khong con ton tai.

VA NO KHONG TU DUNG LAI DUOC: rut lenh xong viec thanh `lam` -> dieu phoi chot
`nguoi_keo = leader` -> bon con lai dam vao cua chan teleport trong `GameClient.go_to_town`
(`KHONG roi doi ... dieu phoi giao viec di duong cho 'X'`) va ban lai moi 2 giay, mai mai.
Engine thi thay chung "dang ban" nen khong giao viec moi -> ca party dung hinh.

Ca that 22/09 party 1 (user: "du part va dang danh, tu nhien no dung lai va lam cai gi do"):
    21:35:35 [party 1] REFORM gen -> 4 ... -> gom ve cung map/kenh
    21:35:36 [party 1] RUT lenh reform gen 4 - da du doi (...), cung map [56802] kenh [1]
    21:35:36 [nasau]   pre-route: tele trung gian ve thanh 12001 truoc (2 thanh da mo)
    21:35:36 [nasau]   Teleport toi thanh 12061: KHONG roi doi (4 member) - dieu phoi giao viec
                       di duong cho 'sga005'
    ... lap moi 2 giay ...
    21:35:35 [party 1] 5/5 acc DUNG HINH qua 240s: ['sga005','sga006','sga007','sga008','tuyetdo']

Dem viec engine giao trong 400 nhip cuoi: sga005/sga007 nhan 136 lan `train`, con
sga006/sga008/tuyetdo chi 41 lan - ba dua ket trong vong di duong cua lenh da bi rut.

DUNG LAI TAI CHO LA DUNG: lenh chi bi rut khi party DA du doi, cung map, cung kenh - tuc khong
con gi phai gom. Engine giao `train` o nhip ke tiep.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _than_ab():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        s = fh.read()
    i = s.find("def _ab(_seen=[]):")
    assert i > 0, "mat ham abort cua _do_reform"
    j = s.find("\n            plan_ready", i)
    assert j > i, "khong tim duoc cuoi ham _ab"
    return s[i:j]


class TestAbortKhiLenhBiRut(unittest.TestCase):
    def setUp(self):
        self.than = _than_ab()

    def test_CO_hoi_reform_gen_thoa(self):
        self.assertIn("reform_gen_thoa", self.than,
                      "khong hoi 'lenh con hieu luc khong' -> di tiep cho lenh da bi rut")

    def test_so_voi_gen_DANG_THI_HANH(self):
        """`thoa >= _g0` - rut dung gen minh dang chay thi phai dung, khong phai chi gen sau."""
        self.assertIn('int(st.get("reform_gen_thoa", 0) or 0) >= _g0', self.than)

    def test_VAN_GIU_ba_cua_cu(self):
        """Them cua moi khong duoc lam mat ba cua da co."""
        self.assertIn("_stopped()", self.than, "mat cua 'party da dung'")
        self.assertIn("not c.running", self.than, "mat cua 'client khong con chay'")
        self.assertIn('st["reform_gen"] > _g0', self.than, "mat cua 'acc khac bump gen'")
        self.assertIn("_keo_bi_tut_nguoi()", self.than, "mat cua 'nguoi keo tut lai'")

    def test_NOI_RO_ly_do_trong_log(self):
        """`_ab` co hop dong rieng: bat thi phai noi VI SAO (1 lan/reform)."""
        self.assertIn("DA BI RUT", self.than, "abort cam thi lan sau lai mo nguoc ca vong di duong")
        self.assertIn("ABORT di duong reform", self.than)


class TestTaiLieuKhongMAU_THUAN(unittest.TestCase):
    """`_reform_cho_xu` co docstring CAM dung no o cho abort. Cua moi la ngoai le co ly do, nen
    docstring do phai ghi lai - khong thi nguoi sau doc tai lieu se go cua nay ra."""

    def test_docstring_ghi_ngoai_le(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def _reform_cho_xu(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn("KHONG dung cho cac cho ABORT", than, "mat canh bao goc")
        self.assertIn("NGOAI LE", than, "cua moi o `_ab` mau thuan voi canh bao ma khong ghi lai")


if __name__ == "__main__":
    unittest.main()
