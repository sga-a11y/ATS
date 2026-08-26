# -*- coding: utf-8 -*-
"""Bam vao mon DANG MAC -> hien thong tin + nut "Coi ra"; chi so day du; do pet.

Crack client (user yeu cau xem client thay vi tu nghi ra nut):
  UI_UIStatus.lua:1896  -> UI.Open(UIItemInfo, EThings.Equip, fitType, followIndex,
                                   string.Get(98003), Item.UnEquip)
  => bam mon dang mac chi co DUNG MOT lua chon: Coi ra. Khong co "phan giai"/"bo" nhu trong tui.
  (Rieng vu khi chuyen thuoc - ExclusiveWeapon - co them "xem ky nang", bot khong lam.)

  Logic_Item.lua:2690-2704 (Item.UnEquip):
      char: C:023-012 <卸下玩家裝備> +vi tri do(1) +o tui trong(1)        = 0x17 sub0c
      pet : C:023-018 <卸下武將裝備> +petIdx(1) +vi tri do(1) +o tui(1)   = 0x17 sub12
  O tui trong do CLIENT tu chon roi gui len -> tui day la khong coi duoc.
"""
import io
import os
import re
import unittest

from bot.client import GameClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI = os.path.join(ROOT, "gui.py")
CLIENT = os.path.join(ROOT, "bot", "client.py")


def _doc(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def _src():
    return _doc(GUI)


def _bot(bag_slots, cap=50):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.bag_slots = dict(bag_slots)
    c.role_counts = {}
    c.sent = []
    c.send = lambda op, pl: c.sent.append((op, pl.hex()))
    c.bag_capacity = lambda: cap
    return c


class TestGoiCoiDo(unittest.TestCase):
    def test_char_dung_goi_C023_012(self):
        c = _bot({1: [0x1234, 1]})
        self.assertTrue(c.unequip_item(3))            # 3 = vu khi
        op, hx = c.sent[-1]
        self.assertEqual(op, 0x17)
        self.assertEqual(hx, "0c00" + "03" + "02", "sub0c + vi tri 3 + o trong dau tien (2)")

    def test_pet_dung_goi_C023_018(self):
        c = _bot({1: [0x1234, 1]})
        self.assertTrue(c.unequip_item(1, follow=2))  # 1 = mu, pet slot 2
        self.assertEqual(c.sent[-1][1], "1200" + "02" + "01" + "02",
                         "sub12 + petIdx + vi tri do + o trong")

    def test_o_trong_dau_tien(self):
        c = _bot({1: [1, 1], 2: [1, 1], 3: [1, 1]})
        c.unequip_item(3)
        self.assertTrue(c.sent[-1][1].endswith("04"), "o trong dau tien phai la 4")

    def test_tui_day_thi_KHONG_gui(self):
        """Client tu chon o trong roi moi gui -> tui day la khong coi duoc, phai bao chu khong
        gui hut roi tuong xong."""
        c = _bot({i: [1, 1] for i in range(1, 6)}, cap=5)
        self.assertFalse(c.unequip_item(3))
        self.assertEqual(c.sent, [])


class TestGuiOTrangBiBamDuoc(unittest.TestCase):
    def test_o_trang_bi_co_bat_su_kien_bam(self):
        self.assertIn("self._select_equip(f))", _src())

    def test_co_nut_coi_ra(self):
        s = _src()
        self.assertIn("def _select_equip", s)
        self.assertIn('text="Cởi ra"', s)
        self.assertIn("self.c.unequip_item(fit, follow=who)", s)

    def test_KHONG_them_nut_ngoai_client(self):
        """Client chi cho 1 lua chon o mon dang mac. Them 'Phan giai'/'Bo' o day la bia them."""
        s = _src()
        i = s.find("def _select_equip")
        doan = s[i:i + 1600]
        for cam in ('"Phân giải"', '"Bỏ"', '"Sử dụng"'):
            self.assertNotIn(cam, doan, "mon dang mac khong co lua chon %s trong client" % cam)

    def test_o_trong_thi_bao_trong(self):
        self.assertIn("đang trống", _src())


class TestChiSoMoiPet(unittest.TestCase):
    def test_client_co_ham_cho_tung_slot(self):
        self.assertTrue(hasattr(GameClient, "pet_stats"))

    def test_luu_ban_ghi_cua_MOI_pet(self):
        self.assertIn("self.pet_login_records[marker] = _rec", _doc(CLIENT),
                      "phai luu ban ghi tung pet, khong rieng con active")

    def test_gui_khong_con_bao_chi_theo_doi_pet_xuat_chien(self):
        s = _src()
        self.assertNotIn("chỉ theo dõi pet đang xuất chiến", s,
                         "gio moi pet deu co so -> bo cau tu choi cu")
        self.assertIn("c.pet_stats(int(who))", s)


class TestBatGoiCoiDoTraVe(unittest.TestCase):
    """Server XAC NHAN coi do bang goi rieng - khong bat thi bang "do dang mac" khong bao gio doi.

    Bug that (user 26/08): "Thao do ko co gi xay ra ca". Bot GUI duoc lenh, mon co ve tui (0x17
    sub08 bot da bat) nhung bang do dang mac van hien y nguyen.
        S:023-016 <卸下裝備>     +vi tri do(1) +o tui(1)     -> sub 16 = 0x10 (char)
        S:023-021 <武將卸下裝備> +petIdx(1) +vi tri do(1)    -> sub 21 = 0x15 (pet)
    """

    def _bot(self):
        c = GameClient.__new__(GameClient)
        c._label = "test"
        c.equip_by_fit = {3: 0x1111, 1: 0x2222}
        c.pet_equip_by_fit = {2: {3: 0x3333}}
        c.equipped_items = [{"id": 0x1111}, {"id": 0x2222}]
        c._equip_seq = 0
        c._mount_item_name = lambda t: "0x%04x" % t
        return c

    def test_char_xoa_khoi_bang_do_mac(self):
        c = self._bot()
        c._on_unequip_done(3, follow=0)
        self.assertNotIn(3, c.equip_by_fit, "vi tri 3 phai bien mat khoi bang")
        self.assertIn(1, c.equip_by_fit, "vi tri khac KHONG duoc dung toi")
        self.assertEqual([x["id"] for x in c.equipped_items], [0x2222])

    def test_pet_xoa_dung_con(self):
        c = self._bot()
        c._on_unequip_done(3, follow=2)
        self.assertNotIn(3, c.pet_equip_by_fit[2])
        self.assertIn(3, c.equip_by_fit, "do CHAR khong duoc dung toi khi coi do PET")

    def test_bump_equip_seq_de_UI_ve_lai(self):
        c = self._bot()
        c._on_unequip_done(3)
        self.assertEqual(c._equip_seq, 1, "khong bump thi tui do khong tu ve lai")

    def test_dispatch_bat_dung_2_sub(self):
        src = _doc(CLIENT)
        self.assertIn("_on_unequip_done(pkt[9], follow=0)", src)
        self.assertIn("_on_unequip_done(pkt[10], follow=pkt[9])", src)


class TestDoPetDocTuGoi0x0f(unittest.TestCase):
    def test_doc_trang_bi_pet_tu_ban_ghi_login(self):
        """S:023-024 khong phai luc nao cung ve luc login -> bang do pet trong tron.
        Goi 0x0f thi LUC NAO CUNG co, va no chua san 6 x ThingData."""
        self.assertIn("self.pet_equip_by_fit.setdefault(marker, {})[_k + 1] = _t", _doc(CLIENT))


class TestChiSoDayDu(unittest.TestCase):
    def test_bang_id_lay_tu_client(self):
        """Controller_RoleController.lua EAttribute: 27 Int, 28 Atk, 29 Def, 30 Agi, 31 Hpx,
        32 Spx. KHONG duoc tu dat so."""
        src = _src()
        i = src.find("_ATTR = (")
        self.assertGreater(i, 0)
        khoi = src[i:i + 400]
        co = dict((int(a), b) for a, b in re.findall(r'\((\d+), "([^"]+)"\)', khoi))
        self.assertEqual(co.get(28), "ATK")
        self.assertEqual(co.get(29), "DEF")
        self.assertEqual(co.get(31), "HPx")
        self.assertEqual(co.get(32), "SPx")

    def test_agi_int_lay_so_DA_CONG_do(self):
        """char_agi/char_int da cong do/collection/thu cuoi; char_attrs chi la so GOC."""
        self.assertIn('if _id == 30 and getattr(c, "char_agi", None) is not None:', _src())


if __name__ == "__main__":
    unittest.main()
