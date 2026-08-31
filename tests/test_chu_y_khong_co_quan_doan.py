"""Chu y: bao acc KHONG CO QUAN DOAN - sau thong bao tui gan day, truoc thong bao lo.

Luat phai nam o CODE DUNG CHUNG (`run_party_digioi.py`): APK khong doc `gui.py`, no goi ham core
qua Chaquopy. Viet rieng trong gui.py = chi PC co thong bao, APK khong.
"""
from __future__ import annotations

import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _gui():
    with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
        return fh.read()


def _core():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _kt():
    with io.open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot",
                              "android", "MainActivity.kt"), encoding="utf-8") as fh:
        return fh.read()


class TestLuatDungChung(unittest.TestCase):
    def test_core_co_ham(self):
        core = _core()
        self.assertIn("def legion_notify_items(pidx):", core)
        self.assertIn("def legion_notify_skip(username):", core)
        self.assertIn("legion_notify_dismissed = set()", core)

    def test_CHI_bao_khi_da_chac_chan(self):
        """`org_id` con None luc chua nhan `0x05 sub03` -> bao luc do la bao lao moi acc luot dau."""
        core = _core()
        i = core.find("def legion_notify_items(pidx):")
        than = core[i:core.find("\ndef legion_notify_skip", i)]
        self.assertIn('getattr(c, "_no_legion_confirmed", False)', than,
                      "doc has_legion/org_id truc tiep thi acc chua login xong cung bi bao")

    def test_gui_PC_goi_ham_chung_chu_khong_chep_luat(self):
        gui = _gui()
        i = gui.find("def _party_legion_notify(self, pidx):")
        self.assertGreater(i, 0)
        than = gui[i:gui.find("\n    def ", i + 10)]
        self.assertIn("ctrl.legion_notify_items(pidx)", than,
                      "chep luat rieng trong gui.py = APK khong co thong bao nay")


class TestThuTuVaHienThiPC(unittest.TestCase):
    def setUp(self):
        self.src = _gui()

    def test_THU_TU_sau_tui_truoc_lo(self):
        i = self.src.find("def _party_notify_items(self, pidx):")
        self.assertGreater(i, 0)
        than = self.src[i:self.src.find("\n    def ", i + 10)]
        i_tui = than.find("_party_bag_notify(pidx)")
        i_qd = than.find("_party_legion_notify(pidx)")
        i_lo = than.find("account_furnace_notify")
        self.assertGreater(i_tui, 0)
        self.assertGreater(i_qd, i_tui, "quan doan phai SAU thong bao tui")
        self.assertGreater(i_lo, i_qd, "quan doan phai TRUOC thong bao lo")

    def test_co_dong_hien_thi_va_nut_bo_qua(self):
        i = self.src.find('if it.get("_legion"):')
        self.assertGreater(i, 0, "khong ve dong nao -> item co ma man hinh trong")
        khoi = self.src[i:i + 900]
        self.assertIn("KHÔNG có quân đoàn", khoi)
        self.assertIn('text="Bỏ qua"', khoi)
        self.assertIn("ctrl.legion_notify_skip(_u)", khoi)
        self.assertIn("_skips.append", khoi, "khong vao _skips thi 'Bo qua tat ca' khong phu")


class TestAPKCoThongBao(unittest.TestCase):
    """APK cung phai hien - truoc day man Chu y cua no CHI co thong bao lo."""

    def test_service_co_cau_noi(self):
        with io.open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot",
                                  "android", "BotForegroundService.kt"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn('callAttr("legion_notify_items"', s)
        self.assertIn('callAttr("legion_notify_skip"', s)

    def test_gop_vao_danh_sach_notify(self):
        s = _kt()
        self.assertIn("legionNotifyItems", s, "khong goi thi man Chu y van chi co lo")

    def test_ve_dong_quan_doan(self):
        s = _kt()
        self.assertIn("KHÔNG có quân đoàn", s)


if __name__ == "__main__":
    unittest.main()
