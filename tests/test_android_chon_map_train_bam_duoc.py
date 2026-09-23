# -*- coding: utf-8 -*-
"""APK - o "Map train": bang chon phai BAM DUOC khi ban phim dang mo.

Ban cu dung `Box` tran + `PopupProperties(focusable = false)`. Popup mang co `FLAG_NOT_FOCUSABLE`
va VE DE LEN vung ban phim, nen khi IME gianh lai pointer giua chung thi gesture bi CANCEL:
  - scroll DA BAT DAU tu truoc  -> van chay tiep
  - tap (phai CHO UP moi tinh)  -> bi huy -> `onClick` KHONG BAO GIO chay
Ket qua: vuot duoc ma bam khong duoc, va list khong dong vi `pickTrainMap` chua he chay.

User 23/09: *"no xuat hien ca keyboard va list map de len keyboard, list map vuot len vuot xuong
van dc nhung click thi ko co gi xay ra, list map van con do"*.

DOI CHUNG NGAY TRONG CUNG FILE: o "Quai" va o chon thanh - cung man hinh, cung kieu dropdown -
dung `ExposedDropdownMenuBox` + `.menuAnchor()` va chay tot. `ExposedDropdownMenuBox` neo qua
`menuAnchor` va TU GIOI HAN chieu cao menu theo cho trong phia tren ban phim, nen list khong con
de len keyboard.

O "Map train" VAN PHAI GO TIM DUOC (co `filterTrainMapOptions`) nen KHONG dat `readOnly` - khac o
"Quai" (readOnly vi khong co o loc).
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android",
                  "MainActivity.kt")


def _src():
    with io.open(KT, encoding="utf-8") as fh:
        return fh.read()


def _khoi_map_train(s):
    """Khoi dung o "Map train" - tu cho tinh `mapOptions` toi truoc o "Quai"."""
    i = s.find("val mapOptions = trainMapOptions()")
    assert i > 0, "mat khoi chon map train"
    j = s.find("if (isPickMode) {", i)
    assert j > i
    return s[i:j]


def _dong_that(s):
    """Cac dong KHONG phai comment - de phan biet 'con dung' voi 'con nhac trong chu thich'."""
    return [l for l in s.splitlines() if not l.strip().startswith("//")]


class TestONeoBangExposedDropdown(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.khoi = _khoi_map_train(self.src)

    def test_dung_ExposedDropdownMenuBox(self):
        self.assertIn("ExposedDropdownMenuBox(", self.khoi,
                      "o map train khong neo bang ExposedDropdownMenuBox -> popup de len ban phim")

    def test_co_menuAnchor(self):
        self.assertIn(".menuAnchor()", self.khoi,
                      "thieu menuAnchor thi ExposedDropdownMenuBox khong biet neo vao dau")

    def test_KHONG_con_focusable_false(self):
        _that = "\n".join(_dong_that(self.khoi))
        self.assertNotIn("PopupProperties(", _that,
                         "focusable=false lam popup de len ban phim -> tap bi CANCEL")

    def test_VAN_GO_TIM_duoc(self):
        """Khong duoc tien tay dat `readOnly = true` nhu o "Quai" - o nay co o loc."""
        self.assertIn("filterTrainMapOptions(", self.khoi, "mat duong loc map")
        _i = self.khoi.find("label = { Text(\"Map train\") }")
        self.assertGreater(_i, 0)
        _truoc = self.khoi[:_i]
        self.assertNotIn("readOnly = true", _truoc, "dat readOnly thi khong go tim map duoc nua")


class TestDongListThiGIU_NGUYEN(unittest.TestCase):
    """`snapToFirst` cu: dong list thi tu chon map DAU TIEN khop voi chu dang co trong o. Ma chu do
    chinh la TEN MAP DANG CHON -> loc ra chinh no -> chon lai chinh no -> KHONG MOT DAU HIEU GI.

    Duong am tham nay lam hien tuong "bam vao list ma khong thay gi xay ra" khong the doc duoc tu
    ngoai: nhin nhu bam hong, thuc ra la menu tu dong roi tu chon lai cai cu."""

    def setUp(self):
        self.khoi = _khoi_map_train(_src())

    def test_KHONG_con_snapToFirst(self):
        """Soi DONG CODE THAT, khong grep ca comment: chu thich co nhac ten cu de giai thich vi
        sao da bo - do la tai lieu, khong phai code."""
        _that = "\n".join(_dong_that(self.khoi))
        self.assertNotIn("snapToFirst", _that, "van con duong tu chon ho map dau danh sach")

    def test_dong_list_chi_tra_ve_map_dang_chon(self):
        i = self.khoi.find("fun closeTrainMapDropdown(")
        self.assertGreater(i, 0)
        than = self.khoi[i:self.khoi.find("\n                    ", i + 40)]
        self.assertIn("selectedTrainMapTextValue()", than)
        self.assertNotIn("pickTrainMap(", than, "dong list ma van tu chon map")


class TestGiongHaiODangCHAY_TOT(unittest.TestCase):
    """O "Quai" va o chon thanh la BAN DOI CHUNG - chung chay tot. Neu sau nay ai do doi chung
    sang kieu khac thi test nay do, vi luc do doi chung khong con."""

    def setUp(self):
        self.src = _src()

    def test_o_quai_van_dung_ExposedDropdownMenuBox(self):
        i = self.src.find("val mobOptions = trainMobOptions(trainMapKey)")
        self.assertGreater(i, 0, "mat o chon diem quai")
        than = self.src[i:i + 1200]
        self.assertIn("ExposedDropdownMenuBox(", than)
        self.assertIn(".menuAnchor()", than)

    def test_khong_con_o_nao_dung_focusable_false(self):
        """Mot cho dung lai la mot cho se hong y het."""
        _that = _dong_that(self.src)
        _xau = [l for l in _that if "focusable = false" in l]
        self.assertEqual(_xau, [], "con dropdown khai focusable=false: %s" % _xau)

    def test_import_thua_da_don(self):
        _that = "\n".join(_dong_that(self.src))
        if "PopupProperties(" not in _that:
            self.assertNotIn("import androidx.compose.ui.window.PopupProperties", _that,
                             "import thua -> canh bao bien dich")


if __name__ == "__main__":
    unittest.main()
