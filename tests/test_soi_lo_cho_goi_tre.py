"""SOI LO phai CHO DU LAU - server lag thi goi lo ve TRE, cho 3s la bo lo "Chu y".

Ca that 07/10 party 40 (user: "party 40 no ko co chu y Soi lo"):
    11:26:50 [dtmot~dt801] SOI LO: gui query (0x59 sub01)...
    11:26:53 [dtmot~dt801] SOI LO: khong nhan duoc data sau 3s
    11:27:10 [dtmot~dt801] LO HOANG KIM tab GoldNpc(vo tuong) ...   <- goi lo ve TRE 20s
Sau 11:11 co 85 acc dinh, 77 acc sau do VAN nhan duoc goi (tre 3-44s). Do tre 95 ca tren
2 file log: 3-5s:16  6-10s:35  11-20s:19  21-30s:8  31-45s:11  >45s:6.
Xem documents/SOI_LO.md muc "Cho goi lo".
"""
from __future__ import annotations

import inspect
import os
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402


class _Fake:
    """Chi du thuoc tinh cho scan_furnace chay."""

    def __init__(self, tre=None):
        self._furnace_seq = 0
        self.furnace_shop = None
        self.running = True
        self._label = "test"
        self._tre = tre

    def send(self, op, data):
        if self._tre is None:
            return

        def _ve():
            time.sleep(self._tre)
            self.furnace_shop = {"tabs": {}}
            self._furnace_seq += 1
        threading.Thread(target=_ve, daemon=True).start()


class TestChoDuLau(unittest.TestCase):
    def test_mac_dinh_cho_toi_thieu_60s(self):
        wait = inspect.signature(GameClient.scan_furnace).parameters["wait"].default
        self.assertGreaterEqual(wait, 60.0,
                                "cho ngan -> server lag la mat Chu y lo (ca party 40 ngay 07/10)")

    def test_process_furnace_KHONG_truyen_wait_ngan(self):
        src = inspect.getsource(GameClient.process_furnace)
        self.assertIn("self.scan_furnace()", src,
                      "process_furnace truyen wait rieng -> de mat mac dinh 60s")

    def test_goi_ve_tre_4s_van_nhan(self):
        f = _Fake(tre=4.0)
        self.assertTrue(GameClient.scan_furnace(f))
        self.assertEqual(f.furnace_shop, {"tabs": {}})

    def test_goi_ve_ngay_thi_KHONG_cho_them(self):
        f = _Fake(tre=0.0)
        t0 = time.time()
        self.assertTrue(GameClient.scan_furnace(f))
        self.assertLess(time.time() - t0, 2.0, "goi ve roi ma van ngoi cho -> cham viec vat")

    def test_khong_ve_thi_van_bo_qua(self):
        f = _Fake(tre=None)
        self.assertFalse(GameClient.scan_furnace(f, wait=0.3))


if __name__ == "__main__":
    unittest.main()
