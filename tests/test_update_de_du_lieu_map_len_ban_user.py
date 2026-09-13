"""UPDATE: du lieu map/route cua DEV luon DE len ban cua user.

User 13/09: "truoc la neu user thay doi file train map va train block json thi ko tai file moi ve
dung ko, neu dung the thi sua lai la luon tai file moi ve de file cu cua user".

BAN CU (option A - user-wins): `_merge_user_config` lay ban update lam nen roi
`merged.update(live_sub)` - key nao may user DA CO thi giu ban user. Nhung `train_maps.json` /
`train_routes.json` chinh la noi dev sua safe / diem quai / route sau moi lan boc lai pcap. Hau
qua: may user da tung chay map do thi KET vinh vien ban cu, bug duong di da sua o dev khong bao
gio den duoc user - va khong co dau hieu gi, vi update van bao thanh cong.

`train_block_stats.json` von khong nam trong ham merge -> da bi ghi de binh thuong tu truoc.

CON GIU: `dangerous_npcs.json` - user tu go tay ten NPC, khong phai du lieu boc tu game.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import updater


class _Nen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.live = os.path.join(self.tmp, "live")
        self.stage = os.path.join(self.tmp, "stage")
        os.makedirs(self.live)
        os.makedirs(self.stage)

    def _viet(self, thu_muc, ten, data):
        with io.open(os.path.join(thu_muc, ten), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _doc_stage(self, ten):
        with io.open(os.path.join(self.stage, ten), encoding="utf-8") as f:
            return json.load(f)


class TestDuLieuMapBiDeLen(_Nen):
    def test_map_user_sua_thi_ban_tai_ve_THANG(self):
        """Cot loi: user chay map 12001 tu lau, dev vua sua lai diem safe -> phai nhan ban dev."""
        self._viet(self.live, "train_maps.json", {"maps": {"12001": {"safe": [1, 1]}}})
        self._viet(self.stage, "train_maps.json", {"maps": {"12001": {"safe": [9, 9]}}})
        updater._merge_user_config(self.live, self.stage)
        self.assertEqual(self._doc_stage("train_maps.json")["maps"]["12001"]["safe"], [9, 9])

    def test_map_chi_co_o_may_user_thi_BIEN_MAT(self):
        """De len = de ca file, khong giu lai key rieng cua user (map do dev da bo di)."""
        self._viet(self.live, "train_maps.json", {"maps": {"99999": {"safe": [1, 1]}}})
        self._viet(self.stage, "train_maps.json", {"maps": {"12001": {"safe": [9, 9]}}})
        updater._merge_user_config(self.live, self.stage)
        self.assertNotIn("99999", self._doc_stage("train_maps.json")["maps"])

    def test_route_user_sua_thi_ban_tai_ve_THANG(self):
        self._viet(self.live, "train_routes.json", {"routes": {"a": ["cu"]}})
        self._viet(self.stage, "train_routes.json", {"routes": {"a": ["moi"]}})
        updater._merge_user_config(self.live, self.stage)
        self.assertEqual(self._doc_stage("train_routes.json")["routes"]["a"], ["moi"])


class TestVanGiuNpcNguyHiem(_Nen):
    """NPC nguy hiem la thu user go tay - de len la mat cong user."""

    def test_gop_ten_cua_ca_hai_ben(self):
        self._viet(self.live, "dangerous_npcs.json", {"names": ["cua user"]})
        self._viet(self.stage, "dangerous_npcs.json", {"names": ["cua dev"]})
        updater._merge_user_config(self.live, self.stage)
        _ten = self._doc_stage("dangerous_npcs.json")["names"]
        self.assertIn("cua user", _ten)
        self.assertIn("cua dev", _ten)


class TestKhongConMaUserWins(unittest.TestCase):
    """Neo trong ma: `merged.update(live_sub)` chinh la dong lam user thang."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "updater.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_khong_con_gop_kieu_user_wins(self):
        self.assertNotIn("merged.update(live_sub)", self.src)

    def test_khong_con_dung_train_maps_trong_ham_merge(self):
        i = self.src.find("def _merge_user_config(")
        self.assertGreater(i, 0)
        j = self.src.find("\ndef ", i + 10)
        khoi = self.src[i:j]
        _ma = khoi[khoi.find('"""', khoi.find('"""') + 3):]
        self.assertNotIn("train_maps.json", _ma, "van con dung du lieu map de gop")
        self.assertNotIn("train_routes.json", _ma)


if __name__ == "__main__":
    unittest.main()
