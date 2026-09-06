"""Mo ruong: don HET do thuoc ruong DA TICK trong tui, TRU do dang KHOA.

User chot 06/09: "tick mo ruong nao thi nhung item trong ruong do co trong tui do cung xu ly luon,
tuy nhien do nao o trang thai khoa thi ko xu ly, de user muon giu item nao thi phai khoa no lai".

VI SAO: ban cu CHI dung vao mon VUA ROI RA trong me do (user chot 03/09, so dung nham do cua
user). Chi can MOT me hut la mon do nam lai VINH VIEN - khong vong nao quay lai don. Me hut co
that, do tren log ca ngay 06/09:
    23 lan `MO HOP: khong thay do roi ra -> dung`  (cho 2.5s, server tra cham hon)
    mo 4.889 hop, chi xu ly 4.610 mon -> hut 279/ngay
Cong don: 5.407 mon rac tu ruong con nam trong tui cua 177 acc (~30 mon/acc), co ca mon fc=50
(phan giai duoc) nhu Viem Hoang Oan 141x, Kich Dieu Nhat 133x.

CO KHOA: ThingData byte +29 `isLock` (KNOWLEDGE.md, `Logic/Item.lua:95`). Client chan khoa o MOI
duong: `Item.DropItem`/`DropEquip` (vut), `UICompound` (phan giai/ghep), `UIFurnace` (lo),
`UIArmy.ArmyFilter:2647` (donate). Ban sao chep filter donate cua bot TRUOC DAY THIEU dung dong do.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as CL  # noqa: E402


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class _Gia(CL.GameClient):
    def __init__(self):
        self._label = "t"
        self._username = "t"
        self.running = True
        self.bag_slots = {}
        self.bag_items = {}
        self.da_phan_giai = []
        self.da_vut = []
        self.da_donate = []

    def decompose_slot(self, s):
        self.da_phan_giai.append(s); self.bag_slots.pop(s, None); return True

    def discard_item(self, s, n):
        self.da_vut.append(s); return True

    def donate_legion_equip(self, slots):
        self.da_donate.extend(slots); return True

    def heal_full(self, **k):
        pass


BOXES = {
    0xb539: {"name": "Tui Thap Thuong", "luot": "thuong", "kindCount": 1,
             "items": [{"id": 20017}, {"id": 18512}, {"id": 21017}]},
    0xb53a: {"name": "Thap Thuong Tinh", "luot": "tinh", "kindCount": 1,
             "items": [{"id": 20609}]},
}
GD = {
    20017: {"name": "Dap Lang Khoi", "fc": 50},        # phan giai duoc
    18512: {"name": "Tiep Yeu Binh Phap", "fc": 0, "mat": 37, "kd": 9, "lv": 1},  # vut
    21017: {"name": "Viem Hoang Oan", "fc": 50},
    20609: {"name": "Sung Son Quan", "fc": 50},
    99999: {"name": "Do cua user", "fc": 50},         # KHONG thuoc ruong nao
}


class TestDonHetDoRuongDaTick(unittest.TestCase):
    def setUp(self):
        self.c = _Gia()

    def test_don_ca_do_CO_SAN_trong_tui(self):
        self.c.bag_slots = {1: [20017, 1], 2: [21017, 1]}
        self.c.bag_items = {1: {"lock": False}, 2: {"lock": False}}
        kq = {"mo": 0, "phan_giai": 0, "donate": 0, "vut": 0}
        self.c._don_do_ruong_con_sot({0xb539}, BOXES, GD, kq)
        self.assertEqual(sorted(self.c.da_phan_giai), [1, 2])

    def test_do_KHOA_thi_KHONG_dung_vao(self):
        self.c.bag_slots = {1: [20017, 1], 2: [21017, 1]}
        self.c.bag_items = {1: {"lock": True}, 2: {"lock": False}}
        kq = {"mo": 0, "phan_giai": 0, "donate": 0, "vut": 0}
        self.c._don_do_ruong_con_sot({0xb539}, BOXES, GD, kq)
        self.assertEqual(self.c.da_phan_giai, [2], "da dung vao mon dang KHOA")
        self.assertEqual(kq.get("khoa"), 1)

    def test_CHI_ruong_DA_TICK(self):
        """Tick ruong A thi khong duoc dung vao do cua ruong B."""
        self.c.bag_slots = {1: [20017, 1], 5: [20609, 1]}
        self.c.bag_items = {1: {"lock": False}, 5: {"lock": False}}
        kq = {"mo": 0, "phan_giai": 0, "donate": 0, "vut": 0}
        self.c._don_do_ruong_con_sot({0xb539}, BOXES, GD, kq)
        self.assertEqual(self.c.da_phan_giai, [1])

    def test_KHONG_dung_vao_do_ngoai_danh_sach(self):
        self.c.bag_slots = {1: [20017, 1], 9: [99999, 1]}
        self.c.bag_items = {1: {"lock": False}, 9: {"lock": False}}
        kq = {"mo": 0, "phan_giai": 0, "donate": 0, "vut": 0}
        self.c._don_do_ruong_con_sot({0xb539}, BOXES, GD, kq)
        self.assertNotIn(9, self.c.da_phan_giai)
        self.assertNotIn(9, self.c.da_vut)

    def test_khong_tick_gi_thi_khong_lam_gi(self):
        self.c.bag_slots = {1: [20017, 1]}
        self.c.bag_items = {1: {"lock": False}}
        kq = {}
        self.c._don_do_ruong_con_sot(set(), BOXES, GD, kq)
        self.assertEqual(self.c.da_phan_giai, [])

    def test_mon_khong_phan_giai_khong_donate_thi_VUT(self):
        self.c.bag_slots = {3: [18512, 1]}
        self.c.bag_items = {3: {"lock": False}}
        kq = {"mo": 0, "phan_giai": 0, "donate": 0, "vut": 0}
        self.c._don_do_ruong_con_sot({0xb539}, BOXES, GD, kq)
        self.assertEqual(self.c.da_vut, [3])


class TestDonTruocKhiMo(unittest.TestCase):
    """Rac tu cac lan mo TRUOC da nam san trong tui -> don TRUOC khi mo."""

    def setUp(self):
        self.src = _doc("bot", "client.py")
        i = self.src.find("def tu_mo_hop_trang_bi(")
        self.than = self.src[i:self.src.find(chr(10) + "    def ", i + 10)]

    def test_don_TRUOC_vong_mo(self):
        i = self.than.find("_don_do_ruong_con_sot(")
        j = self.than.find('for luot in ("thuong", "tinh")')
        self.assertGreater(i, 0)
        self.assertLess(i, j, "don sau khi mo thi nhanh 'tui day' return som -> khong bao gio don")

    def test_quet_theo_TAT_CA_ruong_da_tick(self):
        """Moi login chi mo MOT loai -> rac tich tu tu nhieu loai. Chi quet loai vua mo thi rac
        loai khac nam mai."""
        for m in ("_don_do_ruong_con_sot(_tick", ):
            self.assertIn(m, self.than)
        self.assertNotIn("_don_do_ruong_con_sot({tid}", self.than)


class TestCoKhoa(unittest.TestCase):
    def setUp(self):
        self.c = _Gia()

    def test_doc_tu_ThingData_da_parse(self):
        self.c.bag_items = {7: {"lock": True}}
        self.assertTrue(self.c._item_bi_khoa(7))
        self.c.bag_items = {7: {"lock": False}}
        self.assertFalse(self.c._item_bi_khoa(7))

    def test_KHONG_doc_duoc_thi_coi_la_KHOA(self):
        """Thieu tin thi dung dung vao do cua user (L13: 'khong biet' khac 'khong sao')."""
        self.c.bag_items = {}
        self.assertTrue(self.c._item_bi_khoa(7))

    def test_bot_parse_isLock_tu_byte_29(self):
        src = _doc("bot", "client.py")
        i = src.find("def thing_data_info(")
        than = src[i:i + 2500]
        self.assertIn('"lock": bool(raw[29])', than)

    def test_filter_donate_cung_chan_KHOA(self):
        """`UIArmy.ArmyFilter:2647`: `if itemSave.isLock then return false end`."""
        src = _doc("bot", "client.py")
        i = src.find("def _donate_quan_doan_duoc(")
        than = src[i:src.find(chr(10) + "    def ", i + 10)]
        self.assertIn("_item_bi_khoa(slot)", than)


class TestAPKGiongPC(unittest.TestCase):
    def test_apk_giong(self):
        self.assertEqual(_doc("android", "app", "src", "main", "python", "train_bot", "client.py"),
                         _doc("bot", "client.py"))


if __name__ == "__main__":
    unittest.main()
