# -*- coding: utf-8 -*-
"""APK - dialog SOI LO: 3 nut che mat ten item -> gom thanh MOT nut xoay vong.

User bao 28/08 (kem anh chup): "chỗ soi lò, list item thì 3 nút Bỏ qua, tự mua, Thông báo che mất
tên item, m gom 3 but này về 1 chỗ, thay đổi 3 nút theo vòng cho gọn button và xem được tên nhiều
hơn". Tren dien thoai 3 TextButton canh nhau an gan nua be ngang -> ten item chi con 1 tu.

Vong: Bo qua -> Tu mua -> Thong bao -> Bo qua.
LUU Y giu nguyen: item MAC DINH thong bao (dfltNotify) phai luu "skip" moi tat duoc - xoa key la
lan sau lai ve mac dinh notify.
"""
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android",
                  "MainActivity.kt")


def _doc():
    with io.open(KT, encoding="utf-8") as fh:
        return fh.read()


def _khoi_soi_lo(s):
    i = s.find('val lbl = when (m) { "auto" -> "Tự mua"')
    assert i > 0, "khong thay nut che do cua dialog soi lo"
    return s[i:i + 1600]


class TestMotNutXoayVong(unittest.TestCase):
    def test_khong_con_3_nut_canh_nhau(self):
        s = _doc()
        self.assertNotIn('listOf("" to "Bỏ qua", "auto" to "Tự mua", "notify" to "Thông báo")', s)

    def test_vong_day_du_3_che_do(self):
        doan = _khoi_soi_lo(_doc())
        self.assertIn('"auto" -> modes[tid] = "notify"', doan)
        self.assertIn('else -> modes[tid] = "auto"', doan)
        self.assertIn('"notify" ->', doan)

    def test_nhan_doi_theo_che_do_hien_tai(self):
        doan = _khoi_soi_lo(_doc())
        self.assertIn('"auto" -> "Tự mua"', doan)
        self.assertIn('"notify" -> "Thông báo"', doan)
        self.assertIn('else -> "Bỏ qua"', doan)

    def test_van_giu_luat_dfltNotify_phai_luu_skip(self):
        """Xoa key thay vi luu 'skip' thi item mac dinh thong bao se hien lai sau khi mo lai."""
        doan = _khoi_soi_lo(_doc())
        self.assertIn('if (dfltNotify.contains(tid)) modes[tid] = "skip"', doan)
        self.assertIn("else modes.remove(tid)", doan)

    def test_mau_phan_biet_3_che_do(self):
        """Mot nut thi mau/dam la thu DUY NHAT cho biet dang o che do nao."""
        doan = _khoi_soi_lo(_doc())
        self.assertIn("colorScheme.primary", doan)
        self.assertIn("colorScheme.tertiary", doan)
        self.assertIn("colorScheme.onSurfaceVariant", doan)


if __name__ == "__main__":
    unittest.main()
