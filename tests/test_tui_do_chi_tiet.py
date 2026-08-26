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


class TestThuTuChiSo(unittest.TestCase):
    """User chot thu tu: INT, ATK, DEF, HPx, SPx, AGI, roi HP SP."""

    def test_char_dung_thu_tu(self):
        s = _doc("gui.py")
        i = s.find("_ATTR = (")
        khoi = s[i:i + 260]
        vt = [khoi.find('"%s"' % t) for t in ("INT", "ATK", "DEF", "HPx", "SPx", "AGI")]
        self.assertTrue(all(x > 0 for x in vt), "thieu chi so nao do")
        self.assertEqual(vt, sorted(vt), "sai thu tu INT/ATK/DEF/HPx/SPx/AGI")

    def test_pet_cung_thu_tu_do(self):
        s = _doc("gui.py")
        i = s.find('for _k, _ten in (("int", "INT")')
        self.assertGreater(i, 0, "pet phai duyet theo cung bang thu tu")
        khoi = s[i:i + 220]
        vt = [khoi.find('"%s"' % t) for t in ("INT", "ATK", "DEF", "HPx", "SPx", "AGI")]
        self.assertEqual(vt, sorted(vt))


class TestPetDayDuChiSo(unittest.TestCase):
    """Pet cung phai co du INT/ATK/DEF/HPx/SPx nhu char.

    Bo cuc ban ghi pet - Logic_Role.lua Role.FollowNpcAppear:
      +3 Exp(4) +7 Lv(1) +8 Hp(4) +12 Sp(2) +14 Int(2) +16 Atk(2) +18 Def(2)
      +20 Agi(2) +22 Hpx(2) +24 Spx(2)
    Ba moc +20/+22/+24 von da dung tu truoc -> bo cuc tin duoc, khong phai doan.
    """

    def test_parse_record_doc_them_int_atk_def(self):
        s = _doc("bot", "pet_login_stats.py")
        self.assertIn('"int": int.from_bytes(body[off + 14:off + 16], "little")', s)
        self.assertIn('"atk": int.from_bytes(body[off + 16:off + 18], "little")', s)
        self.assertIn('"def": int.from_bytes(body[off + 18:off + 20], "little")', s)

    def test_pet_stats_tra_du_khoa(self):
        s = _doc("bot", "client.py")
        self.assertIn('"int": rec.get("int"), "atk": rec.get("atk"), "def": rec.get("def")', s)

    def test_pet_cong_them_phan_trang_bi(self):
        """Ban ghi pet chi co so GOC (khac goi char - char co truong Equip* rieng)."""
        s = _doc("bot", "client.py")
        self.assertIn("b = pet_login_stats.equipment_bonus(rec, data, _he)", s)


class TestChiSoAmLaHopLe(unittest.TestCase):
    """User xac nhan 26/08: "so am duoc, vi item co am ma".

    Vd char phap su: ATK -6, DEF -2 (gay tang INT nhung tru ATK/DEF). Bai test nay de ai do sau
    nay thay so am roi tuong loi parse ma di kep ve 0 thi DO ngay.
    """

    def test_khong_kep_ve_0(self):
        c = GameClient.__new__(GameClient)
        c.char_base = {28: 0, 29: 0}
        c.char_equip = {28: -6, 29: -2}
        c.char_int = None
        c.char_agi = None
        f = c.char_stat_full()
        self.assertEqual(f[28], -6, "ATK am phai giu nguyen")
        self.assertEqual(f[29], -2)

    def test_khong_co_max_0_trong_ma_nguon(self):
        s = _doc("bot", "client.py")
        i = s.find("def char_stat_full")
        self.assertNotIn("max(0,", s[i:i + 900], "kep ve 0 la bao sai so cho user")


class TestGiaTriChiSoLechMot100(unittest.TestCase):
    """Gia tri chi so trong du lieu item LECH 100.

    Data_ItemData.lua ItemData:GetAttributeText:
        if value ~= 0 and value ~= 100 then ... " +", (value - 100)
    Tuc 100 = KHONG cong gi, 104 = +4, 96 = -4.
    Toi hien thang so tho nen ra "+104" trong khi that ra la "+4" (user bao 26/08: "+ thua 100",
    "item nay dung thi int+41, agi+4 thoi").
    """

    def test_tru_100(self):
        s = _doc("gui.py")
        self.assertIn("_n = int(_v) - 100", s)

    def test_bo_qua_gia_tri_100(self):
        s = _doc("gui.py")
        self.assertIn("if not _k or not _v or int(_v) == 100:", s)

    def test_he_cung_lech_100(self):
        """He CHINH: value = (elementValue - 100 neu >100) + growLv (GetMainElementText)."""
        s = _doc("gui.py")
        self.assertIn('_n = max(0, int(d.get("elv") or 0) - 100) + int((info or {}).get("grow_lv") or 0)', s)


class TestMonCuThe(unittest.TestCase):
    """Cuong hoa / da / dong phu nam o MON CU THE (ThingData), khong o ban mau item.

    Bo cuc Logic_Item.lua ThingData.New:
      +0 Id(2) +2 quant(4) +6 damage +7 element +8 elementValue +9 proofKind +10 growLv
      +11 growExp(4) +15 specialKind +16 stoneAttr +17 stoneLv +18 enhanceLv +19 delTime(8)
      +27 damagedItemId(2) +29 isLock +30 Reinforced +31 affix1 +32 affix2 +33 affix3 +34 styleLv
    Tong 35. Nam moc bot da dung tu truoc (7, 8, 16, 17, 27) deu trung -> bo cuc tin duoc.
    """

    def test_ham_doc_ThingData(self):
        from bot.client import thing_data_info
        raw = bytearray(35)
        raw[30] = 7          # Reinforced
        raw[31] = 3          # affix1
        raw[16], raw[17] = 2, 5   # stone Cong cap 5
        raw[18] = 4          # enhanceLv
        info = thing_data_info(bytes(raw))
        self.assertEqual(info["reinforced"], 7)
        self.assertEqual(info["affix"][0], 3)
        self.assertEqual(info["stone_attr"], 2)
        self.assertEqual(info["stone_lv"], 5)
        self.assertEqual(info["enhance_lv"], 4)

    def test_thieu_byte_thi_tra_rong(self):
        from bot.client import thing_data_info
        self.assertEqual(thing_data_info(b"123"), {})

    def test_tui_luu_ThingData_thay_vi_vut_29_byte(self):
        s = _doc("bot", "client.py")
        self.assertIn("new_info[idx] = thing_data_info(_td)", s)
        self.assertIn("self.bag_items = new_info", s)

    def test_gui_hien_cuong_hoa_va_dong_phu(self):
        s = _doc("gui.py")
        self.assertIn("def _mon_cu_the", s)
        self.assertIn("Cường hoá +", s)
        self.assertIn("Dòng phụ:", s)
        self.assertIn("Linh đá:", s)

    def test_dung_cho_CA_tui_lan_do_dang_mac(self):
        s = _doc("gui.py")
        self.assertEqual(s.count("self._mon_cu_the("), 2,
                         "phai dung o CA _select (tui) lan _select_equip (dang mac)")


class TestUuTienSoCuaServer(unittest.TestCase):
    """Server tra TONG phan cong tu do, khong phai so tung mon.

    Role.ReceivePlayerData doc MOT so cho moi loai:
        SetAttribute(EAttribute.EquipAtk, data:ReadInt32())  -- 裝備普通攻擊力
    Tong nay DA gom du linh da, LONG, bo do. Server con ban lai qua 0x08 sub0100 moi khi doi
    (EAttribute 207/208/210/211/212/214/218/219).

    Tu tinh bang pet_login_stats.equipment_bonus la SAI HUONG: ham do khong biet LONG
    (EItemKind.Feather) -> ra so THIEU, ghi de len so dung cua server (user chi ra 26/08).
    """

    def test_ma_equip_dung_cua_client(self):
        self.assertEqual(GameClient.EQUIP_ATTR, (207, 208, 210, 211, 212, 214, 218, 219))

    def test_uu_tien_char_attrs_hon_so_luc_login(self):
        c = GameClient.__new__(GameClient)
        c.char_base = {28: 100, 30: 40}
        c.char_equip = {28: 30, 30: 34}          # anh chup luc LOGIN (da cu sau khi thay do)
        c.char_attrs = {210: 55, 214: 60}        # so MOI server ban lai
        c.char_int = None
        c.char_agi = None
        f = c.char_stat_full()
        self.assertEqual(f[28], 155, "ATK phai dung EquipAtk moi cua server (100+55)")
        self.assertEqual(f[30], 100, "AGI phai dung EquipAgi moi (40+60)")

    def test_khong_co_so_server_thi_dung_so_login(self):
        c = GameClient.__new__(GameClient)
        c.char_base = {28: 100}
        c.char_equip = {28: 30}
        c.char_attrs = {}
        c.char_int = None
        c.char_agi = None
        self.assertEqual(c.char_stat_full()[28], 130)

    def test_recalc_uu_tien_server_truoc(self):
        s = _doc("bot", "client.py")
        i = s.find("def _recalc_char_equip_stats")
        doan = s[i:i + 1800]
        self.assertIn("co_server = self.ATTR_AGI in attrs or self.ATTR_INT in attrs", doan)
        self.assertIn("else:", doan)
        self.assertIn("CHUA co LONG", doan, "phai ghi ro duong lui la so THIEU")


class TestHeChinhVaHePhuLong(unittest.TestCase):
    """Client co HAI dong he khac nhau (Data_ItemData.lua):

      GetMainElementText - 主屬性 (HE CHINH): lay tu BAN MAU item (element/elementValue),
          tri so = (elementValue - 100 neu >100) + itemSave.growLv
      GetElementText - chu thich ngay tren ham la "--附屬性" (HE PHU): lay tu MON CU THE
          (itemSave.element/elementValue)

    HE PHU chinh la THUOC TINH LONG: long = 附加羽毛 ("long gan them"), gan vao mon thi ghi vao
    element/elementValue cua mon do. User hoi 26/08: "thuoc tinh long cua do thi client lay dau
    ra hien thi nhi".
    """

    def test_he_chinh_co_cong_growLv(self):
        s = _doc("gui.py")
        self.assertIn("Hệ chính", s)
        self.assertIn('int((info or {}).get("grow_lv") or 0)', s,
                      "thieu growLv la hien THIEU tri so he chinh")

    def test_he_phu_ghi_ro_la_long(self):
        s = _doc("gui.py")
        self.assertIn("Hệ phụ (lông)", s)

    def test_hai_dong_lay_hai_nguon_KHAC_nhau(self):
        """He chinh doc d (ban mau), he phu doc info (mon cu the). Lay chung nguon la sai."""
        s = _doc("gui.py")
        i = s.find("def _item_chi_tiet")
        j = s.find("def _mon_cu_the")
        self.assertIn('d.get("el")', s[i:j], "he chinh phai doc ban mau")
        self.assertIn('info.get("element")', s[j:j + 3200], "he phu phai doc mon cu the")

    def test_truyen_ThingData_vao_ham_chi_tiet(self):
        s = _doc("gui.py")
        self.assertEqual(s.count("self._item_chi_tiet(tid, _info)"), 2,
                         "ca 2 cho (tui + dang mac) deu phai truyen mon cu the vao")


if __name__ == "__main__":
    unittest.main()
