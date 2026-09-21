# -*- coding: utf-8 -*-
"""APK phai hien SO QUAI + HE QUAI o dropdown diem quai, y het ban PC.

User 21/09: "ban apk luc chon diem quai ko thay hien so quai va he quai nhu ban PC, ban apk ko
ghi file train block nhung van phai up qua de dung va hien thi chu".

Loi: chuoi phu (' | 3-5 | Thủy 110, Địa 112') duoc ghep trong `_spot_infos` cua `gui.py`, ma
`gui.py` nam trong `PC_ONLY` -> ban APK khong goi duoc -> dropdown chi con "Điểm 1 (x, y)".

Cach sua (user chot: "dong bo tu PC qua, cam viet moi"): DOI than ham sang
`bot/train_block_stats.py` (file DUNG CHUNG), ca hai ban cung goi mot ham. KHONG ghep chuoi rieng
ben Kotlin - hai ban se lech dinh dang ngay lan sua dau tien.

APK KHONG GHI file nay (chi PC ghi) nhung VAN DOC duoc: `_load_unlocked` co duong doc tu
`assets/train_bot_data/`, va file da khai trong CA `SHARED_ASSETS` lan `DATA_JSON`.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import train_block_stats as T


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestHamDungChung(unittest.TestCase):
    def test_ham_nam_o_file_DUNG_CHUNG(self):
        self.assertTrue(hasattr(T, "spot_infos"), "mat `spot_infos` o file dung chung")
        self.assertIn("train_block_stats.py", _doc("tools", "sync_apk_python.py"),
                      "file nay phai duoc sync sang APK")

    def test_APK_co_ban_giong_het(self):
        pc = _doc("bot", "train_block_stats.py")
        apk = _doc("android", "app", "src", "main", "python", "train_bot", "train_block_stats.py")
        self.assertIn("def spot_infos(", apk, "ban APK chua co ham")
        self.assertEqual(pc.count("def spot_infos("), apk.count("def spot_infos("))

    def test_diem_co_so_lieu_thi_CO_chuoi_phu(self):
        _stats = T.load_stats().get("maps", {})
        _map = next((m for m, d in _stats.items() if (d.get("spots") or {})), None)
        self.assertIsNotNone(_map, "train_block_stats.json rong -> khong kiem duoc")
        _xy = next(iter(_stats[_map]["spots"])).split(",")
        ra = T.spot_infos(int(_map), [(int(_xy[0]), int(_xy[1]))])
        self.assertTrue(ra[0].startswith(" | "), "diem co so lieu ma khong ra chuoi phu")

    def test_diem_CHUA_co_so_lieu_thi_chuoi_RONG(self):
        """Khong duoc bia chu gi - dropdown hien nhu cu."""
        self.assertEqual(T.spot_infos(21862, [(999999, 999999)]), [""])

    def test_map_None_khong_no(self):
        self.assertEqual(T.spot_infos(None, [(1, 2), (3, 4)]), ["", ""])


class TestPC_KHONG_giu_ban_rieng(unittest.TestCase):
    """Giu hai ban = som muon lech dinh dang, luc do doi chieu bang mat lai sai."""

    def test_gui_goi_lai_ham_dung_chung(self):
        than = _doc("gui.py")
        i = than.find("def _spot_infos(")
        self.assertGreater(i, 0)
        khoi = than[i:than.find("\ndef ", i + 10)]
        self.assertIn("train_block_stats.spot_infos(", khoi, "gui.py van giu ban chep rieng")
        self.assertNotIn("format_mob_range", khoi, "van tu ghep chuoi -> hai ban se lech")


class TestKotlinGoiHamPython(unittest.TestCase):
    def setUp(self):
        self.kt = _doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                       "MainActivity.kt")
        i = self.kt.find("fun trainMobOptions(")
        self.assertGreater(i, 0, "mat ham dung dropdown diem quai")
        self.khoi = self.kt[i:i + 1800]

    def test_goi_spot_infos(self):
        self.assertIn('callAttr("spot_infos"', self.khoi)

    def test_KHONG_tu_ghep_chuoi_ben_Kotlin(self):
        _ma = "\n".join(d for d in self.khoi.split("\n") if not d.strip().startswith("//"))
        for tu in ("format_mob_range", "format_mobs", "Thủy", "patterns"):
            self.assertNotIn(tu, _ma, "ghep chuoi rieng ben Kotlin -> lech voi ban PC")

    def test_thieu_so_lieu_thi_VAN_hien_diem(self):
        """`spot_infos` loi/thieu -> nhan van phai co 'Điểm N (x, y)', khong duoc mat dropdown."""
        self.assertIn('infos.getOrNull(i) ?: ""', self.khoi)
        self.assertIn('"Điểm ${i + 1} (${coords[0]}, ${coords[1]})"', self.khoi)


if __name__ == "__main__":
    unittest.main()
