"""NGOC PHUC THAN: bot phai biet DU 4 LOAI va luon deo cai TOT NHAT dang co.

He so kinh nghiem (items_desc.json), ca 4 deu `ft=6` (EQUIP_POS_SPEC) va cap yeu cau 15 -> dung
MOT o, deo duoc nhu nhau:
    0x5AAC Ngoc Ba Phuc Than    x3
    0x5AAB Ngoc Sieu Phuc Than  x2,5
    0x5A2D Ngoc Dai Phuc Than   x2
    0x59EF Ngoc Tieu Phuc Than  x1,5

Truoc day bot chi biet Sieu + Dai (user phat hien 31/08):
  - co Ngoc Ba (xin nhat) van deo Ngoc Sieu,
  - chi con Ngoc Tieu thi KHONG deo gi ca, nhay thang sang item tieu hao.
"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as CL          # noqa: E402
from bot.client import GameClient     # noqa: E402

BA, SIEU, DAI, TIEU = 0x5AAC, 0x5AAB, 0x5A2D, 0x59EF
TUI = 0xB5F4          # "Tui Dai Phuc Than" - item tieu hao, chi dung khi KHONG co ngoc nao


def _cfg(*tids):
    out = {t: {"name": "ngoc 0x%04x" % t, "phuc_than": True, "equip": True} for t in tids}
    if TUI in out:
        out[TUI] = {"name": "Tui Dai Phuc Than", "qty": 1, "phuc_than": True}
    return out


def _bot(bag, dang_deo=0):
    c = GameClient.__new__(GameClient)
    c._label = "t"
    c.bag_slots = {i + 1: [tid, 1] for i, tid in enumerate(bag)}
    c.equipped_items = ([{"id": dang_deo, "pos": CL.EQUIP_POS_SPEC,
                          "damage": 0, "damaged_item_id": 0}] if dang_deo else [])
    c.da_deo = []
    c.da_dung = []
    c.equip_item = lambda slot: (c.da_deo.append(c.bag_slots[slot][0]), True)[1]
    c.use_slot = lambda slot, qty=1: (c.da_dung.append(c.bag_slots[slot][0]), True)[1]
    c._drop_broken_gem = lambda: None
    return c


def _chay(bag, dang_deo=0, cfg_tids=None):
    c = _bot(bag, dang_deo)
    c._use_items_from_cfg(_cfg(*(cfg_tids if cfg_tids is not None else bag)), "test")
    return c


class TestBangXepHang(unittest.TestCase):
    def test_du_4_loai(self):
        self.assertEqual(CL.PHUC_THAN_GEM_ORDER, (BA, SIEU, DAI, TIEU))
        self.assertEqual(CL.PHUC_THAN_GEM_TIDS, {BA, SIEU, DAI, TIEU})

    def test_thu_hang_tot_den_kem(self):
        self.assertLess(CL.phuc_than_hang(BA), CL.phuc_than_hang(SIEU))
        self.assertLess(CL.phuc_than_hang(SIEU), CL.phuc_than_hang(DAI))
        self.assertLess(CL.phuc_than_hang(DAI), CL.phuc_than_hang(TIEU))

    def test_khong_phai_ngoc_thi_hang_RAT_LON(self):
        """Chua deo gi (tid=0) phai thua MOI loai ngoc, khong thi bot khong bao gio deo."""
        self.assertGreater(CL.phuc_than_hang(0), CL.phuc_than_hang(TIEU))
        self.assertGreater(CL.phuc_than_hang(0x1234), CL.phuc_than_hang(TIEU))

    def test_bang_uu_tien_sinh_tu_thu_hang(self):
        equip = [t for t, a in CL.PHUC_THAN_PROTECTION_PRIORITY if a == "equip"]
        self.assertEqual(tuple(equip), CL.PHUC_THAN_GEM_ORDER,
                         "bang uu tien chep tay -> them ngoc moi la quen mot cho")
        self.assertEqual(CL.PHUC_THAN_PROTECTION_PRIORITY[-1][1], "use",
                         "item tieu hao phai o CUOI (chi dung khi khong co ngoc nao)")


class TestChonNgocDeoDung(unittest.TestCase):
    def test_co_NGOC_BA_thi_deo_Ba(self):
        c = _chay([SIEU, BA, DAI])
        self.assertEqual(c.da_deo, [BA], "co Ngoc Ba (x3) ma van deo cai kem hon")

    def test_CHI_co_TIEU_thi_van_deo(self):
        c = _chay([TIEU])
        self.assertEqual(c.da_deo, [TIEU], "chi con Ngoc Tieu ma khong deo -> mat han x1,5")

    def test_dang_deo_BA_thi_KHONG_dong_toi(self):
        c = _chay([SIEU, DAI, TIEU], dang_deo=BA)
        self.assertEqual(c.da_deo, [], "dang deo cai tot nhat ma van thay = ha cap")

    def test_KHONG_HA_CAP(self):
        """Dang deo Sieu, trong tui chi co Dai/Tieu -> giu nguyen."""
        c = _chay([DAI, TIEU], dang_deo=SIEU)
        self.assertEqual(c.da_deo, [])

    def test_NANG_CAP_duoc(self):
        """Dang deo Dai, trong tui co Ba -> phai doi len."""
        c = _chay([TIEU, BA], dang_deo=DAI)
        self.assertEqual(c.da_deo, [BA])

    def test_dang_deo_cung_loai_thi_khong_deo_lai(self):
        c = _chay([DAI], dang_deo=DAI)
        self.assertEqual(c.da_deo, [])

    def test_co_ngoc_thi_KHONG_dung_item_tieu_hao(self):
        c = _chay([TIEU, TUI])
        self.assertEqual(c.da_deo, [TIEU])
        self.assertEqual(c.da_dung, [], "deo duoc ngoc roi ma van dot item tieu hao")

    def test_KHONG_co_ngoc_nao_thi_moi_dung_item(self):
        c = _chay([TUI])
        self.assertEqual(c.da_deo, [])
        self.assertEqual(c.da_dung, [TUI])


class TestUseItemsJson(unittest.TestCase):
    """`_use_items_from_config` loc bang `if tid not in cfg` (= use_items.json) -> thieu tid o day
    thi code o tren khong bao gio chay toi."""

    def test_du_4_ngoc_trong_use_items(self):
        with io.open(os.path.join(ROOT, "use_items.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        src = d.get("items", d)
        for tid in CL.PHUC_THAN_GEM_ORDER:
            key = "0x%04x" % tid
            self.assertIn(key, src, "use_items.json thieu %s -> bot khong bao gio deo" % key)
            self.assertTrue((src[key] or {}).get("equip"), "%s phai co equip=true" % key)


if __name__ == "__main__":
    unittest.main()
