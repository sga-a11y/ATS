"""Bam Luu setting KHONG duoc lam engine thay PARTIES dang do (ca that 28/09).

`importlib.reload(config)` chay lai config.py ngay tren module dang dung -> giua chung `PARTIES`
chi con 1 party mau -> `_cap_nhat_engine` tuong party bi xoa -> 35-37 party thoat moi lan Luu.
"""
import ast
import importlib
import importlib.util
import logging
import os
import sys
import tempfile
import textwrap
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lay_ham():
    src = open(os.path.join(ROOT, "gui.py"), encoding="utf-8").read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == "_nap_lai_config_nguyen_khoi":
            return ast.get_source_segment(src, node)
    raise AssertionError("gui.py mat ham _nap_lai_config_nguyen_khoi")


class NapLaiConfigNguyenKhoi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ten = "cfg_nap_lai_test"
        self.f = os.path.join(self.tmp, self.ten + ".py")
        sys.path.insert(0, self.tmp)
        self._ghi(3)
        self.cfg = importlib.import_module(self.ten)

    def tearDown(self):
        sys.path.remove(self.tmp)
        sys.modules.pop(self.ten, None)

    def _ghi(self, n):
        # Y het config.py: dau file gan PARTIES mau 1 party, cuoi file moi gan danh sach that.
        # Giua chung ghi lai so party module THAT dang lo ra cho thread khac.
        with open(self.f, "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent("""
                import sys
                PARTIES = [["mau"]]
                _that = sys.modules.get(__name__)
                THAY_GIUA_CHUNG = len(getattr(_that, "PARTIES", [])) if _that else -1
                PARTIES = [["p%%d" %% i] for i in range(%d)]
            """ % n))
        importlib.invalidate_caches()
        pyc = importlib.util.cache_from_source(self.f)
        if os.path.exists(pyc):
            os.remove(pyc)

    def _chay(self):
        g = {"importlib": importlib, "config": self.cfg, "log": logging.getLogger("t")}
        exec(_lay_ham(), g)
        g["_nap_lai_config_nguyen_khoi"]()

    def test_khong_lo_parties_dang_do(self):
        self._ghi(5)
        self._chay()
        self.assertEqual(self.cfg.THAY_GIUA_CHUNG, 3, "giua luc nap, module that phai giu 3 party cu")
        self.assertEqual(len(self.cfg.PARTIES), 5)
        self.assertIs(sys.modules[self.ten], self.cfg)

    def test_reload_config_dung_ham_nguyen_khoi(self):
        src = open(os.path.join(ROOT, "gui.py"), encoding="utf-8").read()
        self.assertNotIn("importlib.reload(config)   # doc lai", src)
        self.assertIn("_nap_lai_config_nguyen_khoi()   # doc lai accounts.json", src)


if __name__ == "__main__":
    unittest.main()
