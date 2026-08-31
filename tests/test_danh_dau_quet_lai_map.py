"""Danh dau map CAN QUET LAI bang co `rescan`, KHONG duoc xoa `mobs`.

Xoa `mobs` = loai han map khoi vong quay chu khong phai xep hang quet lai:
`_spots_of_maps` chi sinh diem tu `mobs`, map khong co mobs thi `pick_train_spot` khong bao gio
chon toi -> khong ai toi map do -> `_needs_train_mob_probe` khong bao gio duoc goi -> khong bao
gio quet.

31/08: xoa mobs cua 4 map co safe nam sat diem quai; party lv 138 sau do bo qua
"Trại Phạm Thành2 137-139" (map 21812) va chon map 136.
"""
from __future__ import annotations

import io
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import sys
sys.path.insert(0, ROOT)
from bot import train_pick                                  # noqa: E402
from bot.train_maps_store import save_learned_regions        # noqa: E402


class TestCoRescan(unittest.TestCase):
    def test_probe_chay_khi_co_co(self):
        import run_party_digioi as rpd
        self.assertTrue(rpd._needs_train_mob_probe(None, 1, {"mobs": [[1, 2]], "rescan": True}))
        self.assertFalse(rpd._needs_train_mob_probe(None, 1, {"mobs": [[1, 2]]}))
        self.assertTrue(rpd._needs_train_mob_probe(None, 1, {"mobs": []}))

    def test_map_co_rescan_VAN_chon_duoc(self):
        """Diem mau chot: co danh dau ma van phai vao duoc vong quay, khong thi khong ai toi quet."""
        maps = [(21812, "Trại Phạm Thành2 137-139", [[750, 1990], [1550, 1190]])]
        spots = train_pick._spots_of_maps(maps, 138)
        self.assertTrue(spots, "map bi danh dau ma khong sinh ra diem nao")

    def test_map_MAT_mobs_thi_KHONG_chon_duoc(self):
        """Chung minh vi sao khong duoc xoa mobs."""
        maps = [(21812, "Trại Phạm Thành2 137-139", [])]
        self.assertEqual(train_pick._spots_of_maps(maps, 138), [])


class TestGhiDeKhiRescan(unittest.TestCase):
    def _file(self, entry):
        import tempfile
        fd, p = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with io.open(p, "w", encoding="utf-8") as fh:
            json.dump({"maps": {"77": entry}}, fh)
        self.addCleanup(lambda: os.path.exists(p) and os.remove(p))
        return p

    def _doc(self, p):
        with io.open(p, encoding="utf-8") as fh:
            return json.load(fh)["maps"]["77"]

    def test_co_rescan_thi_GHI_DE(self):
        p = self._file({"name": "x", "safe": [[1, 1]], "mobs": [[2, 2]], "rescan": True})
        self.assertTrue(save_learned_regions(p, 77, [(9, 9)], [(8, 8)]))
        e = self._doc(p)
        self.assertEqual(e["mobs"], [[8, 8]])
        self.assertEqual(e["safe"], [[9, 9]])

    def test_quet_xong_thi_BO_CO(self):
        p = self._file({"name": "x", "safe": [[1, 1]], "mobs": [[2, 2]], "rescan": True})
        save_learned_regions(p, 77, [(9, 9)], [(8, 8)])
        self.assertNotIn("rescan", self._doc(p), "khong bo co -> quet lai mai moi lan toi map")

    def test_KHONG_co_co_thi_van_KHONG_ghi_de(self):
        p = self._file({"name": "x", "safe": [[1, 1]], "mobs": [[2, 2]]})
        self.assertFalse(save_learned_regions(p, 77, [(9, 9)], [(8, 8)]))
        self.assertEqual(self._doc(p)["mobs"], [[2, 2]])


class TestDuLieuDangCho(unittest.TestCase):
    """KHONG neo "4 map do phai rong": bot dang chay se quet lai va dien vao ngay - neo the la
    test do ngay khi tinh nang chay dung. Neo theo dieu KIEN PHAI DUNG cua MOI map."""

    def test_khong_map_nao_co_safe_nam_trong_vung_quai(self):
        """Safe cach diem quai gan nhat < RALLY_BAN_KINH thi dung o bai quai van bi coi la
        "da ra safe" -> ca chuoi gom party/doi kenh hong."""
        import math
        with io.open(os.path.join(ROOT, "train_maps.json"), encoding="utf-8") as fh:
            maps = json.load(fh)["maps"]
        xau = []
        for mid, m in maps.items():
            safes, mobs = m.get("safe") or [], m.get("mobs") or []
            if not safes or not mobs:
                continue          # chua quet -> se duoc uu tien den quet
            for s in safes:
                d = min(math.dist(s, p) for p in mobs)
                if d < 100:
                    xau.append("map %s '%s' safe %s cach mob %d" % (mid, m.get("name"), s, d))
        self.assertEqual(xau, [], "safe nam trong vung quai: " + "; ".join(xau))


if __name__ == "__main__":
    unittest.main()
