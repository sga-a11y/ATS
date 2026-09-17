# -*- coding: utf-8 -*-
"""`reload_config` KHONG duoc stop acc tren MAIN THREAD.

`stop_account` -> `client.close()` -> `_ghi_cache_tui` / `save_bag_cache` -> `_cache_ghi`, ma
`_cache_ghi` DOC + GHI LAI CA FILE `account_skills_cache.json` (876 KB, 265 acc) cho MOI acc,
duoi `_skill_cache_lock` dung chung voi ~700 thread acc dang chay.

Ca that 17/09 (user: "sao bi not responding roi") - py-spy PID 1544, CA 3/3 mau MainThread:
    _save -> reload_config -> stop_account -> close -> _ghi_cache_tui -> save_bag_cache
    -> _cache_ghi (bot/client.py:2052)

Cung cach da chua treo lan truoc (`_agi_worker`): viec nang chay o thread nen, main thread chi ve.
"""
from __future__ import annotations

import io
import os
import unittest

GUI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gui.py")


def _than_reload_config():
    with io.open(GUI, encoding="utf-8") as fh:
        s = fh.read()
    i = s.index("def reload_config(")
    return s[i:s.index("\n    def ", i + 10)]


class TestReloadConfigKhongStopTrenMainThread(unittest.TestCase):
    def test_stop_chay_o_thread_nen(self):
        than = _than_reload_config()
        self.assertIn("threading.Thread(", than,
                      "stop_account chay thang tren main thread -> GUI dung hinh")
        i_th = than.index("threading.Thread(")
        i_stop = than.index("ctrl.stop_account(")
        self.assertLess(i_th, i_stop, "stop_account phai nam TRONG thread nen")

    def test_thread_nen_la_daemon(self):
        """GUI dong app thi khong duoc treo lai cho vong stop nay."""
        than = _than_reload_config()
        self.assertIn("daemon=True", than)


if __name__ == "__main__":
    unittest.main()
