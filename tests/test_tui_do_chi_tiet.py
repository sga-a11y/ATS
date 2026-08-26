# -*- coding: utf-8 -*-
"""Tui do: mo la vao tab Trang bi, bam item hien CHI TIET, thay do thi tinh lai chi so.

User 26/08:
  - "khi mo tui do thi mac dinh tab Trang bi cho nho bot, do nhieu item"
  - "click item thi t muon hien them chi tiet thong tin, vi tri mac, level yeu cau, chi so cong
     them the nao (ca long da cac thu)"
  - "thay do thi thay cac chi so chua duoc cap nhat lai (ca nut check agi nua)"

Ma chi so trong DU LIEU ITEM - Data_ItemData.lua GetAttributeName -> TextData_C.dat (KHONG tu dat):
  20348='HP :' 20349='SP :' 20350='Atk:' 20351='Def:' 20352='Int:' 20353='Agi:'
  10068='Thể chất' 10069='Năng lượng' 90136='Thuyền tốc'
  => 207 HP | 208 SP | 210 Atk | 211 Def | 212 Int | 214 Agi | 217 Thuyen toc
     218 The chat (HPx) | 219 Nang luong (SPx)
"""
import io
import json
import os
import unittest

from bot.client import GameClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestTabMacDinh(unittest.TestCase):
    def test_mo_tui_la_vao_tab_trang_bi(self):
        s = _doc("gui.py")
        self.assertIn("self._tab = _BAG.EQUIP", s)
        self.assertNotIn("self._tab = _BAG.ALL", s, "tab mac dinh cu (ve ca 170 o) da bo")


class TestDuLieuChiTietCoTrongJson(unittest.TestCase):
    """items_gamedata.json phai co san nl/a1k/a1v - khong co thi UI khong hien duoc gi."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
            self.db = json.load(fh)

    def test_trang_bi_co_level_yeu_cau_va_chi_so(self):
        it = self.db.get("0x4fd0") or {}          # Boi Tinh Quan
        self.assertTrue(it, "thieu 0x4fd0 -> chay lai tools/crack_items_gamedata.py")
        self.assertEqual(it.get("nl"), 111, "level yeu cau")
        self.assertEqual(it.get("a1k"), 212, "212 = Int")
        self.assertTrue(it.get("a1v"))

    def test_co_he_va_bo_do(self):
        it = self.db.get("0x3aea") or {}          # Manh Ho Dia Thuong
        self.assertEqual(it.get("el"), 1, "he Dia")
        self.assertTrue(it.get("su"), "bo do")


class TestGuiHienChiTiet(unittest.TestCase):
    def test_co_ham_chi_tiet(self):
        s = _doc("gui.py")
        self.assertIn("def _item_chi_tiet", s)
        self.assertIn("Yêu cầu cấp", s)
        self.assertIn("Vị trí:", s)

    def test_bang_ten_chi_so_dung_ma_cua_client(self):
        s = _doc("gui.py")
        i = s.find("_ITEM_ATTR = {")
        self.assertGreater(i, 0)
        khoi = s[i:i + 300]
        for ma, ten in ((210, "ATK"), (211, "DEF"), (212, "INT"), (214, "AGI")):
            self.assertIn("%d: \"%s\"" % (ma, ten), khoi, "ma %d phai la %s" % (ma, ten))

    def test_chi_tiet_hien_TRUOC_mo_ta(self):
        """Mo ta chi la loi van; thong tin user hoi la vi tri/cap/chi so -> phai len truoc."""
        s = _doc("gui.py")
        self.assertIn('("%s\\n%s" % (_ct, _mt) if (_ct and _mt) else (_ct or _mt))', s)


class TestTinhLaiChiSoKhiThayDo(unittest.TestCase):
    """`_char_equip_agi` truoc day CHI duoc dat mot lan luc login (goi 0x05).

    Thay do thi server khong gui lai - client tu tinh tai cho. Bot khong tinh nen chi so va nut
    "Check AGI" dung nguyen so cu.
    """

    def test_co_ham_tinh_lai(self):
        s = _doc("bot", "client.py")
        self.assertIn("def _recalc_char_equip_stats", s)
        self.assertIn("def char_equip_bonus", s)

    def test_goi_lai_sau_KHI_MAC_va_KHI_COI(self):
        s = _doc("bot", "client.py")
        self.assertEqual(s.count("self._recalc_char_equip_stats()"), 2,
                         "phai goi o CA _on_equip_done lan _on_unequip_done")

    def test_chi_tinh_cho_CHAR(self):
        """Do PET khong cong vao AGI/INT cua char -> phai chan bang `if not follow`."""
        s = _doc("bot", "client.py")
        self.assertIn("if not follow:\n            self._recalc_char_equip_stats()", s)

    def test_snapshot_luu_du_truong_ThingData(self):
        s = _doc("bot", "client.py")
        for k in ('"element": raw[7]', '"element_value": raw[8]',
                  '"stone_attr": raw[16]', '"stone_lv": raw[17]'):
            self.assertIn(k, s, "thieu %s thi khong tinh duoc cong tu linh da/he" % k)

    def test_dung_chung_ham_voi_pet(self):
        """pet_login_stats.equipment_bonus da tinh du linh da + he + bo do - khong viet lai."""
        s = _doc("bot", "client.py")
        self.assertIn("pet_login_stats.equipment_bonus(rec, data, _he)", s)

    def test_ma_chi_so_khai_bao_dung(self):
        self.assertEqual(GameClient.ATTR_ATK, 210)
        self.assertEqual(GameClient.ATTR_DEF, 211)
        self.assertEqual(GameClient.ATTR_INT, 212)
        self.assertEqual(GameClient.ATTR_AGI, 214)
        self.assertEqual(GameClient.ATTR_HPX, 218)
        self.assertEqual(GameClient.ATTR_SPX, 219)


if __name__ == "__main__":
    unittest.main()
