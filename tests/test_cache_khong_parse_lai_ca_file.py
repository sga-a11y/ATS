# -*- coding: utf-8 -*-
"""File cache chung (`account_skills_cache.json`) KHONG duoc parse/ghi lai ca file trong khoa.

File nay la MOT file cho moi acc: 876 KB / 265 acc (do thuc te 17/09). Sau nam duong ghi
(`save_skill_cache`, `save_inn_cache`, `save_point_cache`, `save_skill_char_cache`, `_cache_ghi`,
`save_dac_ky_cache`) deu tung mo + `json.load` LAI CA FILE roi `_ghi_json_an_toan` LAI CA FILE,
tat ca nam trong `_skill_cache_lock`: 43 ms giu khoa moi lan ghi (load 24 + dumps 19).

Ca that 17/09 (user: "sao bi not responding roi" - chi stop MOT party) - py-spy PID 1544:
      1 thread   GIU khoa, dang `json.load` (save_skill_cache)
    101 thread   xep hang cho khoa (70 o `_cache_ghi` + 31 o `save_skill_cache`)
MainThread lot vao hang do la GUI dung hinh, bat ke user stop 1 acc hay 100.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "bot", "client.py")


def _src():
    with io.open(SRC, encoding="utf-8") as fh:
        return fh.read()


class TestKhongDocLaiCaFileMoiLanGhi(unittest.TestCase):
    def test_chi_con_MOT_cho_doc_file(self):
        """Duy nhat `_cache_all` duoc doc dia, va no chi doc LAN DAU."""
        s = _src()
        self.assertEqual(s.count("json.load(fh) or {}"), 1,
                         "van con duong doc lai ca file - moi lan ghi la parse 876 KB trong khoa")
        i = s.index("json.load(fh) or {}")
        self.assertIn("_skill_cache_all", s[max(0, i - 400):i])

    def test_moi_duong_ghi_deu_qua_RAM(self):
        s = _src()
        self.assertGreaterEqual(s.count("allc = _cache_all()"), 6,
                                "co duong ghi khong dung ban RAM chung")


class TestGhiDiaNgoaiKhoa(unittest.TestCase):
    def test_khong_serialize_trong_khoa(self):
        """Trong khoa chi chup ban sao nong; `json.dumps` (19 ms) phai nam NGOAI."""
        s = _src()
        i = s.index("def _cache_flush(")
        than = s[i:s.index("\ndef ", i + 10)]
        i_nha = than.index("_skill_cache_ban.clear()")
        i_ghi = than.index("_ghi_json_an_toan(")
        self.assertLess(i_nha, i_ghi, "ghi dia phai nam SAU khi nha khoa")
        # `with _skill_cache_lock:` chi bao quanh doan chup ban sao
        self.assertIn("_ban = dict(_skill_cache_all)", than)

    def test_duong_ghi_chi_HEN_chu_khong_ghi_thang(self):
        s = _src()
        self.assertEqual(len(re.findall(r"_ghi_json_an_toan\(path, allc\)", s)), 0,
                         "van con duong ghi thang ca file trong khoa")
        self.assertGreaterEqual(s.count("_cache_hen_ghi()"), 6)

    def test_thoat_app_thi_ghi_not(self):
        """Cache trong RAM chua kip flush ma app dong la mat - phai co atexit."""
        s = _src()
        self.assertIn("atexit.register", s)
        self.assertIn("_cache_flush(force=True)", s)


if __name__ == "__main__":
    unittest.main()
