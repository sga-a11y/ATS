"""APK: hang nut cua moi acc phai XUONG DONG khi man HEP, khong duoc cat mat nut.

User bao 05/09: "sao ban apk van chua co tui do va skill" -> thuc ra CO (chuoi nam trong dex cua
chinh ban APK do), nhung hang nut

    Chay | sua | hoi HP/SP | Battle | Point | Skill | Tui | xoa

nam trong MOT `Row` thuong, khong xuong dong cung khong cuon. Man dien thoai DOC thi hang nay dai
hon be ngang -> `Skill`, `Tui` VA CA NUT XOA bi day ra ngoai mep, nhin nhu ban APK thieu tinh nang.
User xac nhan: "de man hinh ngang thi thay nut" - dung dau hieu tran be ngang.

`horizontalScroll` KHONG dung o day: no van giau nut, user khong biet ma vuot (cho khac trong file
dung duoc vi la thanh cong cu, con day la nut chinh cua tung acc).
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android")


def _src():
    with io.open(os.path.join(KT, "MainActivity.kt"), encoding="utf-8") as fh:
        return fh.read()


def _than_account_row(src):
    i = src.find("fun AccountRow(")
    assert i > 0, "khong tim thay AccountRow"
    j = src.find("\n@Composable", i + 10)
    return src[i:j if j > 0 else len(src)]


class TestHangNutXuongDong(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.than = _than_account_row(self.src)

    def test_dung_FlowRow_chu_khong_phai_Row_thuong(self):
        i = self.than.find('Text("Battle", maxLines = 1)')
        self.assertGreater(i, 0, "khong tim thay hang nut trong AccountRow")
        truoc = self.than[:i]
        # Container gan nhat BOC hang nut phai la FlowRow.
        self.assertIn("FlowRow(", truoc, "hang nut khong xuong dong -> man doc bi cat nut")
        self.assertGreater(truoc.rfind("FlowRow("), truoc.rfind("\n            Row("),
                           "van con `Row` thuong boc hang nut")

    def test_khong_dung_horizontalScroll_cho_hang_nut(self):
        """Cuon ngang van giau nut - user vua bao la 'khong co nut' vi khong thay."""
        i = self.than.find('Text("Battle", maxLines = 1)')
        truoc = self.than[max(0, i - 600):i]
        self.assertNotIn("horizontalScroll", truoc)

    def test_co_import_va_opt_in(self):
        self.assertIn("import androidx.compose.foundation.layout.FlowRow", self.src)
        self.assertIn("import androidx.compose.foundation.layout.ExperimentalLayoutApi", self.src)
        i = self.src.find("fun AccountRow(")
        self.assertIn("@OptIn(ExperimentalLayoutApi::class)", self.src[max(0, i - 200):i],
                      "FlowRow con la ExperimentalLayoutApi o compose-bom 2024.06.00")


class TestDuNutTrongHang(unittest.TestCase):
    """Cat nut nao la mat han tinh nang do tren APK - liet ke ro de con biet ma giu."""

    def setUp(self):
        self.than = _than_account_row(_src())

    def test_du_bon_nut_bang(self):
        for ten in ("Battle", "Point", "Skill", "Túi"):
            self.assertIn('Text("%s", maxLines = 1)' % ten, self.than, "thieu nut %s" % ten)

    def test_van_con_nut_xoa(self):
        """Nut xoa nam CUOI hang nen la cai bi cat dau tien - de sot thi khong xoa acc duoc."""
        self.assertIn('contentDescription = "Xóa"', self.than)

    def test_van_con_nut_chay_va_sua(self):
        self.assertIn('Text("Chạy")', self.than)
        self.assertIn('contentDescription = "Sửa tài khoản"', self.than)
        self.assertIn('contentDescription = "Hồi HP SP"', self.than)


if __name__ == "__main__":
    unittest.main()
