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


class TestChiSoDayDuTuGoi0x05(unittest.TestCase):
    """User hoi 3 lan: "hien thi day du chi so, atk, int, def, Hpx...".

    Truoc day bot chi doc INT/AGI tu goi 0x05 sub03 nen bang chi so THIEU HAN ATK/DEF/HPx/SPx -
    khong phai server khong gui, ma khong ai doc.
    Bo cuc crack Logic_Role.lua Role.ReceivePlayerData (KHONG doan offset):
      +9 Int(2) +11 Atk(2) +13 Def(2) +15 Agi(2) +17 Hpx(2) +19 Spx(2)
      +39 MaxHp(4) +43 MaxSp(2)
      +45 EquipAtk(4) +49 EquipDef(4) +53 EquipInt(4) +57 EquipAgi(4)
      +61 EquipMaxHp(4) +65 EquipMaxSp(4) +69 EquipHpx(4) +73 EquipSpx(4)
    Moc +9/+15/+53/+57 khop y het cai bot dung tu truoc -> bo cuc tin duoc.
    """

    def test_doc_du_6_chi_so_goc(self):
        s = _doc("bot", "client.py")
        self.assertIn("self.char_base = {27: _u16(9), 28: _u16(11), 29: _u16(13), 30: _u16(15)", s)

    def test_doc_du_phan_cong_tu_do(self):
        s = _doc("bot", "client.py")
        self.assertIn("self.char_equip = {28: _i32(45), 29: _i32(49), 27: _i32(53), 30: _i32(57)", s)

    def test_maxsp_doc_2_byte_khong_phai_4(self):
        """Client doc UInt16. Doc 4 byte la nuot 2 byte dau cua EquipAtk -> so khong lo ->
        tu roi vao nhanh kiem tra roi BO QUA ca khoi HP/SP login."""
        s = _doc("bot", "client.py")
        self.assertIn('sp_max = int.from_bytes(body[43:45], "little")', s)
        self.assertNotIn('sp_max = int.from_bytes(body[43:47], "little")', s)

    def test_ham_tong_hop(self):
        self.assertTrue(hasattr(GameClient, "char_stat_full"))

    def test_tong_la_goc_cong_do(self):
        c = GameClient.__new__(GameClient)
        c.char_base = {28: 100, 29: 50, 31: 10, 32: 5, 27: 200, 30: 40}
        c.char_equip = {28: 30, 29: 20, 31: 3, 32: 2, 27: 143, 30: 34}
        c.char_int = None
        c.char_agi = None
        f = c.char_stat_full()
        self.assertEqual(f[28], 130, "ATK = goc + do")
        self.assertEqual(f[29], 70)
        self.assertEqual(f[31], 13)

    def test_INT_AGI_uu_tien_so_da_cong_du(self):
        """char_int/char_agi da cong ca suu tap/the/thu cuoi - khong chi rieng trang bi."""
        c = GameClient.__new__(GameClient)
        c.char_base = {27: 200, 30: 40}
        c.char_equip = {27: 143, 30: 34}
        c.char_int = 385
        c.char_agi = 76
        f = c.char_stat_full()
        self.assertEqual(f[27], 385)
        self.assertEqual(f[30], 76)

    def test_chua_nhan_goi_thi_tra_rong(self):
        c = GameClient.__new__(GameClient)
        c.char_base = {}
        self.assertEqual(c.char_stat_full(), {})


class TestSuaKhoaJsonRutGon(unittest.TestCase):
    """items_gamedata.json dung ten khoa RUT GON. Doc bang ten dai thi luon rong."""

    def test_doc_dung_ten_khoa(self):
        s = _doc("gui.py")
        self.assertIn('d.get("nl")', s)
        self.assertIn('d.get("el")', s)
        self.assertIn('d.get("su")', s)
        self.assertNotIn('d.get("needLv")', s)
        self.assertNotIn('d.get("suitId")', s)


class TestTabMacDinhKhongBiDe(unittest.TestCase):
    def test_khong_ep_ve_tab_tat_ca(self):
        """Dat _tab = EQUIP o tren roi nhung _set_tab(_BAG.ALL) o duoi DE LEN -> van ra tab
        Tat ca (user bao 26/08 lan 2)."""
        s = _doc("gui.py")
        self.assertIn("self._set_tab(self._tab)", s)
        self.assertNotIn("self._set_tab(_BAG.ALL)", s)


class TestTabDangChonKhongTrongNhuBiKhoa(unittest.TestCase):
    """User: "tab bi chon no text mau xam, t cu nghi la disable co".

    Danh dau tab dang chon bang state(["disabled"]) lam chu xam y het nut bi khoa. Doi sang
    Radiobutton kieu nut: lom xuong + chu dam, van bam duoc.
    """

    def test_khong_dung_disabled_de_danh_dau(self):
        s = _doc("gui.py")
        self.assertNotIn('b.state(["disabled"] if t == tab else ["!disabled"])', s)

    def test_dung_radiobutton_kieu_nut(self):
        s = _doc("gui.py")
        self.assertIn("indicatoron=0", s)
        self.assertIn("self._tab_var.set(tab)", s)

    def test_tab_dang_chon_in_dam(self):
        s = _doc("gui.py")
        self.assertIn('"bold" if t == tab else "normal"', s)


if __name__ == "__main__":
    unittest.main()
