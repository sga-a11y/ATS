"""MOI file Python cua APK phai chay duoc tren Python 3.8 (Chaquopy).

Tren 3.8, chu thich kieu `X | None` va `list[int]` bi TINH LUC CHAY -> `TypeError` ngay khi import,
tru khi file co `from __future__ import annotations`. Test cu chi kiem tung file rieng le, nen file
MOI `party_route.py` (26/09, `lag_since: float | None` trong `NamedTuple`) lot qua: user update APK
27/09 -> moi acc bao "Loi doc log: TypeError: unsupported operand type(s) for |: 'type' and
'NoneType'".

Test nay quet TAT CA file .py cua APK bang AST - them file moi la tu duoc kiem.
"""
from __future__ import annotations

import ast
import glob
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK_PY = os.path.join(ROOT, "android", "app", "src", "main", "python", "train_bot")
_GENERIC = {"list", "dict", "set", "tuple", "type", "frozenset"}


def _co_future(tree):
    return any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
               and any(a.name == "annotations" for a in n.names) for n in tree.body)


def _vi_pham(ann):
    for n in ast.walk(ann):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
            return "X | Y"
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id in _GENERIC:
            return "%s[...]" % n.value.id
    return None


def _chu_thich(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.AnnAssign):
            yield n.lineno, n.annotation
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
                if arg is not None and arg.annotation is not None:
                    yield n.lineno, arg.annotation
            if n.returns is not None:
                yield n.lineno, n.returns


class TestApkChayDuocPython38(unittest.TestCase):
    def test_moi_file_apk_khong_co_chu_thich_kieu_moi_ma_thieu_future(self):
        files = sorted(glob.glob(os.path.join(APK_PY, "*.py")))
        self.assertGreater(len(files), 10)
        loi = []
        for f in files:
            with open(f, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            if _co_future(tree):
                continue
            for ln, ann in _chu_thich(tree):
                kieu = _vi_pham(ann)
                if kieu:
                    loi.append("%s:%d dung %s" % (os.path.basename(f), ln, kieu))
        self.assertEqual(loi, [], "thieu `from __future__ import annotations` (APK Python 3.8)")


if __name__ == "__main__":
    unittest.main()
