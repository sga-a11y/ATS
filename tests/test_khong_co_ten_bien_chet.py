"""KHONG duoc con TEN BIEN CHET (undefined name) trong ma nguon.

Day la loai loi im lang nhat trong repo nay: code van import duoc, test van xanh, chi den khi
CHAY DUNG NHANH DO moi no `NameError` - va no o giua mot vong lap nen bot chi "biến mất" khoi vong
do roi lam lai tu dau, khong ai biet.

Da can BA lan trong cung mot ngay 08/09, deu la tan du cua dot bo "acc bao cao":

  1. `o5_done`  - `_run_auto_team_dungeons_if_needed` con dung tham so da bo:
        00:31:44 >>> PARTY 13 DA THOAT HET vi: LOI ngoai le: name 'o5_done' is not defined
     -> chet ca party 13 va 14.

  2. `_arr_gen` - bang acc TU KHAI "da toi", bo roi ma vong cuu barrier con doc:
        12:18:20 [xGAx] (LEADER) reform: CHO ca party ve Giang Lăng (3/5, ...)
        12:18:20 [xGAx] LOI: name '_arr_gen' is not defined
     -> 21 lan, party 1 quay vong Trac Quan <-> Giang Lang gan mot tieng (user: "p1 lai moi dua
        1 noi").

  3. `_cat_do_mac_dinh` + `e` (bien `except ... as e` da het scope khi lambda chay) trong `gui.py`.

`python -m unittest` KHONG bat duoc chung. `pyflakes` bat duoc ca ba trong mot giay.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILE = ("run_party_digioi.py", "gui.py", os.path.join("bot", "client.py"),
        os.path.join("bot", "config.py"), os.path.join("bot", "party_battle.py"))


class TestKhongCoTenChet(unittest.TestCase):
    def test_khong_undefined_name(self):
        try:
            import pyflakes  # noqa: F401
        except ImportError:
            self.skipTest("chua cai pyflakes (pip install pyflakes)")
        co = [f for f in FILE if os.path.exists(os.path.join(ROOT, f))]
        r = subprocess.run([sys.executable, "-m", "pyflakes"] + co,
                           cwd=ROOT, capture_output=True, text=True)
        xau = [ln for ln in (r.stdout or "").splitlines() if "undefined name" in ln]
        self.assertEqual(xau, [], "con ten bien chet - se no NameError khi chay den:\n"
                         + "\n".join(xau))


if __name__ == "__main__":
    unittest.main()
