"""TANG CHOT 2K: cong len chi HIEN SAU KHI THANG -> phai DANH HET TANG roi moi ket luan.

Party 1 va party 11 (06/09) - user: "len dinh thap thi ko thay danh tiep":

    14:45:28 [xGAx] 2K: da len tang 11 - Đỉnh Tháp (12934)
    14:45:28 [xGAx] 2K: tang 11 - Đỉnh Tháp (12934) KHONG co cong len trong world_nav -> DUNG o day
    14:45:28 [xGAx] (LEADER) 2K: vong leo thap ket thuc (ket) -> bao DIEU PHOI

Vong leo kiem cong len TRUOC khi danh, nen o tang chot bot thoat ma KHONG danh mot tran nao.
`_up_gate` da ghi san: 12934/12939/12943/12949/12954 chi co cong xuong - do la 5 TANG CHOT, va
user xac nhan cong len chi hien sau khi THANG.

Capture `captures/2k_tang11_20260906.pcap` (m tu di len tang 11 roi vao cho danh quai):
    10.80  C2S 0x14 0800 02        qua cong idx 2 (tu 12933)
    10.91  S2C 0x0c map=12934 pos=(630,890)
    12.76  C2S 0x0c 0100 -> 13.70 C2S 0x14 0600 -> S2C 0x14 08 2a    (scene_resume)
    14.97..16.26  C2S 0x06 move -> (650,430)
    16.70  C2S 0x14 0800 02        <- KICH TRAN bang idx 2
    16.94  S2C 0x14 0100 ...       thoai mo
    17.00..19.77  C2S 0x14 0600 x6 <-> S2C 0x14 0100 x6
    19.91  S2C 0x14 0900           thoai xong
    23.93  C2S 0x32 0100           DANH

Hai cho khac tang thuong:
  - diem danh: (650,430)  [tang thuong: (510,1190) (290,730) (510,330)]
  - idx kich tran: 2      [tang thuong: 3..8]  -> NGOAI khoang quet cua bot
"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import floor_crawl as FC  # noqa: E402


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _ev():
    with io.open(os.path.join(ROOT, "events.json"), encoding="utf-8") as fh:
        return json.load(fh)["events"]["nhi_kieu"]


class TestDuLieuTang11(unittest.TestCase):
    def setUp(self):
        self.ev = _ev()

    def test_diem_danh_quai_dung_capture(self):
        self.assertEqual(FC._battle_points(self.ev, 12934), [(650, 430)])

    def test_idx_kich_tran_la_2(self):
        self.assertEqual(FC._battle_idx(self.ev, 12934), [2])

    def test_tang_thuong_van_dung_khoang_mac_dinh(self):
        self.assertEqual(FC._battle_idx(self.ev, 12930), list(FC._BATTLE_IDX_RANGE))
        self.assertEqual(FC._battle_points(self.ev, 12930),
                         [(510, 1190), (290, 730), (510, 330)])

    def test_KHONG_mo_rong_khoang_mac_dinh_xuong_2(self):
        """O tang thuong idx 2 THUONG LA CONG (12933 door=2) -> quet xuong 2 la qua cong som."""
        self.assertNotIn(2, FC._BATTLE_IDX_RANGE)


class TestDanhTruocRoiMoiXetCong(unittest.TestCase):
    def setUp(self):
        self.src = _doc("bot", "floor_crawl.py")
        i = self.src.find("def run_floor_crawl(")
        self.than = self.src[i:]

    def test_khong_break_ngay_khi_thieu_cong_len(self):
        i = self.than.find("up = _up_gate(scene)")
        self.assertGreater(i, 0)
        khoi = self.than[i:i + 500]
        self.assertNotIn("break", khoi[:khoi.find("points = _battle_points")],
                         "van thoat truoc khi danh -> tang chot khong danh tran nao")

    def test_danh_xong_moi_ket_luan_khong_co_cong(self):
        i = self.than.find("VAN khong co cong len")
        self.assertGreater(i, 0, "khong con cho ket luan sau khi danh")
        j = self.than.find("for idx in _battle_idx(ev, scene):")
        self.assertGreater(i, j, "ket luan phai nam SAU vong danh")

    def test_thu_lai_up_gate_sau_khi_danh(self):
        """Cong hien sau khi thang -> hoi lai mot lan (va chay duoc ngay khi bo sung world_nav)."""
        i = self.than.find("for idx in _battle_idx(ev, scene):")
        self.assertIn("up = _up_gate(scene)", self.than[i:])

    def test_van_dung_duoc_khi_KHONG_co_cong(self):
        """`nxt/door/center` phai co gia tri an toan khi up=None, khong duoc nem."""
        self.assertIn("up if up else (None, None, None)", self.than)


class TestAPKGiongPC(unittest.TestCase):
    def test_apk_giong(self):
        apk = _doc("android", "app", "src", "main", "python", "train_bot", "floor_crawl.py")
        self.assertEqual(apk, _doc("bot", "floor_crawl.py"))

    def test_asset_events_giong(self):
        a = _doc("android", "app", "src", "main", "assets", "train_bot_data", "events.json")
        self.assertEqual(json.loads(a)["events"]["nhi_kieu"]["party_battle"]["battle_idx"],
                         {"12934": [2]})


if __name__ == "__main__":
    unittest.main()
