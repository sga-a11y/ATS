# -*- coding: utf-8 -*-
"""Bam vao mon DANG MAC -> hien thong tin + nut "Coi ra"; chi so cho CA pet khong xuat chien.

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
import unittest

from bot.client import GameClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI = os.path.join(ROOT, "gui.py")


def _src():
    with io.open(GUI, encoding="utf-8") as fh:
        return fh.read()


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
        s = _src()
        self.assertIn('_w.bind("<Button-1>", lambda _e, f=_fit: self._select_equip(f))', s)

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
        s = _src()
        self.assertIn("đang trống", s)


class TestChiSoMoiPet(unittest.TestCase):
    def test_client_co_ham_cho_tung_slot(self):
        self.assertTrue(hasattr(GameClient, "pet_stats"))

    def test_luu_ban_ghi_cua_MOI_pet(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("self.pet_login_records[marker] = _rec", s,
                      "phai luu ban ghi tung pet, khong rieng con active")

    def test_gui_khong_con_bao_chi_theo_doi_pet_xuat_chien(self):
        s = _src()
        self.assertNotIn("chỉ theo dõi pet đang xuất chiến", s,
                         "gio moi pet deu co so -> bo cau tu choi cu")
        self.assertIn("c.pet_stats(int(who))", s)


if __name__ == "__main__":
    unittest.main()
