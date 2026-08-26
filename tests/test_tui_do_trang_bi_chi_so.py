# -*- coding: utf-8 -*-
"""Tui do bot: hang 6 o TRANG BI DANG MAC + dong CHI SO, theo doi tuong dang tick.

User: "them 1 hang 6 o, tuong ung voi 6 item cua char/pet, select con nao thi hien do cua con do,
cac o nho ghi ro vi tri: vu khi, dau, chan... duoi hang 6 o nay la chi so hien tai cua char/pet,
select con nao thi hien thi con do; duoi hang stats la tui do nhu hien tai".

6 o = DUNG 6 vi tri that cua game, doc tu client:
  Data_ItemData.lua EItemFitType 1..6 = mu / ao / vu khi / ho uyen / giay / dac biet
  Logic_Item.lua Item.IsEquip() liet ke dung 6 cai nay (thoi trang 7..11 va ao choang 100 KHONG).
"""
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI = os.path.join(ROOT, "gui.py")


def _src():
    with io.open(GUI, encoding="utf-8") as fh:
        return fh.read()


def _equip_slots():
    """Doc cac cap (fitType, ten) cua _EQUIP_SLOTS tu MA NGUON.

    Khong `import gui`: no keo theo run_party_digioi, ma module do doc sys.argv[1] luc import ->
    chay bang `unittest discover` la no thu int("discover"). Ca bo test o repo nay deu doc ma
    nguon vi ly do do.
    """
    import re
    src = _src()
    i = src.find("_EQUIP_SLOTS = ")
    assert i > 0, "khong tim thay _EQUIP_SLOTS"
    khoi = src[i:src.find("\n\n", i)]
    return [(int(a), b) for a, b in re.findall(r'\((\d+),\s*"([^"]+)"\)', khoi)]


class TestSauOTrangBi(unittest.TestCase):
    def test_dung_6_vi_tri_that_cua_game(self):
        fits = [f for f, _t in _equip_slots()]
        self.assertEqual(sorted(fits), [1, 2, 3, 4, 5, 6],
                         "phai dung fitType 1..6 (Item.IsEquip), khong dinh thoi trang 7..11")
        self.assertEqual(len(_equip_slots()), 6)

    def test_moi_o_co_ten_vi_tri(self):
        tens = [t for _f, t in _equip_slots()]
        self.assertIn("Vũ khí", tens)
        self.assertIn("Giày", tens)
        for t in tens:
            self.assertTrue(t.strip(), "o nao cung phai co ten vi tri")

    def test_char_va_pet_doc_2_nguon_KHAC_nhau(self):
        """Char: equip_by_fit (S:023-011). Pet: pet_equip_by_fit (S:023-024).

        Lay chung mot nguon la sai - do pet KHONG nam trong equipped_items cua char.
        """
        s = _src()
        self.assertIn('getattr(c, "equip_by_fit", None)', s)
        self.assertIn('getattr(c, "pet_equip_by_fit", None)', s)


class TestDoiDoiTuong(unittest.TestCase):
    def test_tick_sang_pet_thi_ve_lai(self):
        s = _src()
        i_re = s.find("def _retarget")
        self.assertGreater(i_re, 0)
        doan = s[i_re:i_re + 900]
        self.assertIn("_refresh_equip_stats()", doan,
                      "doi doi tuong phai ve lai 2 hang tren")

    def test_refresh_luoi_cung_ve_lai_2_hang(self):
        s = _src()
        i = s.find("    def refresh(self):")
        self.assertGreater(i, 0)
        self.assertIn("_refresh_equip_stats()", s[i:i + 300])


class TestDauVanTrangThai(unittest.TestCase):
    def test_fp_co_ca_2_bang_do_mac(self):
        """Login dien 2 bang nay nhung _equip_seq KHONG doi -> thieu thi o luon trong."""
        s = _src()
        self.assertIn("fit_c = tuple(sorted((getattr(c, \"equip_by_fit\", None) or {}).items()))", s)
        self.assertIn("fit_p = tuple(sorted((k, tuple(sorted(v.items())))", s)
        self.assertIn("return bag, eq, eq_seq, fit_c, fit_p", s)


class TestChiSoKhongDoan(unittest.TestCase):
    def test_pet_nao_cung_co_so_rieng_cua_no(self):
        """MOI pet mang theo deu co so rieng, khong rieng con xuat chien (user yeu cau 26/08).

        Truoc day bot chi tinh cho con active nen phai ghi "chua co so" cho 3 con kia. Nay goi
        0x0f mang ban ghi cua tung con va pet_login_stats von la ham tong quat -> tinh duoc het.
        Dieu PHAI giu: khong duoc gan so cua con dang danh cho con khac.
        """
        s = _src()
        self.assertIn("c.pet_stats(int(who))", s, "phai lay so THEO SLOT cua chinh con do")
        self.assertNotIn("chỉ theo dõi pet đang xuất chiến", s, "cau tu choi cu da het dung")
        # HP/SP cua state.pet la cua con DANG DANH -> chi duoc dung khi who == active
        self.assertIn('unit = getattr(st, "pet", None) if (st and _active and int(who) == _active)',
                      s)

    def test_thieu_so_thi_ghi_dau_hoi(self):
        s = _src()
        self.assertIn('"Cấp %s" % (lv if lv is not None else "?")', s)


if __name__ == "__main__":
    unittest.main()
