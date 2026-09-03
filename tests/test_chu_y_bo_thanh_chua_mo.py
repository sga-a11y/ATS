# -*- coding: utf-8 -*-
"""Dialog CHU Y: BO thong bao "CHUA MO thanh".

User chot 28/08 (kem anh chup dialog Chu y party 48): "bo thong bao thanh chua mo, vi bay gio bot
luon tu mo thanh roi". Canh bao nay sinh ra hoi bot con phai di bo tu thanh gan nhat; gio bot tu
mo thanh nen no chi lam ret danh sach, day cac muc CAN LAM THAT (tui day, Ba Dau, quan doan, du
diem, lo) xuong duoi.

_party_city_notify() GIU LAI (khong xoa ham) - chi khong gop vao danh sach Chu y nua.
"""
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestBoThongBaoThanhChuaMo(unittest.TestCase):
    def test_khong_gop_vao_danh_sach_chu_y(self):
        s = _doc("gui.py")
        i = s.find("def _party_notify_items(")
        self.assertGreater(i, 0)
        doan = s[i:i + 1400]
        self.assertNotIn("self._party_city_notify(pidx)", doan)

    def test_van_giu_ham_de_bat_lai_duoc(self):
        s = _doc("gui.py")
        self.assertIn("def _party_city_notify(", s)

    def test_docstring_khong_con_ke_THANH(self):
        s = _doc("gui.py")
        i = s.find("def _party_notify_items(")
        doan = s[i:i + 400]
        self.assertNotIn("THANH chua mo", doan)


if __name__ == "__main__":
    unittest.main()
