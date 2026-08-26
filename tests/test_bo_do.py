# -*- coding: utf-8 -*-
"""BO DO (outfit): luu san mot bo cho char + pet, khi can doi CA BO mot lan.

User 26/08:
  - "dat san bo do cho cha va pet, khi nao can thi doi ca bo"
  - "so N thi ko co dinh, m co the chu dong them hoac xoa bo do di (nhu cai setting party), khi
     xoa co canh bao xac nhan"
  - "cho luon vao cho tui do, user se vao tui do, co nut nao do de thay doi, set up bo do"
  - chot: MAC DE luon, khong coi truoc (server tu tra mon cu ve o cu - bot xu ly o _on_equip_done)

RANG BUOC: lenh mac gui theo O TUI, ma o tui doi lien tuc -> bo do chi luu duoc ID MON. Hai mon
TRUNG ID khac cuong hoa thi khong phan biet duoc -> uu tien mon cuong hoa cao nhat.
"""
import io
import os
import unittest

from bot.client import GameClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _bot(bag=None, bag_items=None, char=None, pets=None):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.bag_slots = dict(bag or {})
    c.bag_items = dict(bag_items or {})
    c.equip_by_fit = dict(char or {})
    c.pet_equip_by_fit = {int(k): dict(v) for k, v in (pets or {}).items()}
    c.equipped = []
    c.equip_item = lambda s: c.equipped.append(("char", s))
    c.equip_pet_item = lambda p, s: c.equipped.append(("pet%d" % p, s))
    return c


class TestChupBoDo(unittest.TestCase):
    def test_chup_du_char_va_pet(self):
        c = _bot(char={1: 0x11, 3: 0x33}, pets={2: {1: 0xAA}})
        bo = c.outfit_snapshot()
        self.assertEqual(bo["char"], {1: 0x11, 3: 0x33})
        self.assertEqual(bo["pets"], {2: {1: 0xAA}})

    def test_bo_qua_vi_tri_ngoai_6_o(self):
        """Thoi trang (7..11) va ao choang (100) KHONG phai 6 o trang bi that."""
        c = _bot(char={1: 0x11, 9: 0x99, 100: 0xCC})
        self.assertEqual(c.outfit_snapshot()["char"], {1: 0x11})


class TestMacBoDo(unittest.TestCase):
    def test_bo_qua_mon_DANG_MAC_DUNG(self):
        """Mac lai mon dang mac la gui thua, va co the lam server tra do lung tung."""
        c = _bot(bag={5: [0x11, 1]}, char={1: 0x11})
        gui, thieu = c.apply_outfit({"char": {1: 0x11}})
        self.assertEqual(gui, 0)
        self.assertEqual(c.equipped, [])
        self.assertEqual(thieu, [])

    def test_mac_mon_khac(self):
        c = _bot(bag={5: [0x22, 1]}, char={1: 0x11})
        gui, thieu = c.apply_outfit({"char": {1: 0x22}})
        self.assertEqual(gui, 1)
        self.assertEqual(c.equipped, [("char", 5)])

    def test_mac_cho_PET_dung_con(self):
        c = _bot(bag={7: [0xAA, 1]}, pets={2: {1: 0xBB}})
        c.apply_outfit({"pets": {2: {1: 0xAA}}})
        self.assertEqual(c.equipped, [("pet2", 7)])

    def test_khoa_JSON_la_CHUOI_van_chay(self):
        """Doc lai tu file thi fitType/petIdx thanh CHUOI - khong ep int la so sanh lech het."""
        c = _bot(bag={5: [0x22, 1]}, char={1: 0x11})
        gui, _ = c.apply_outfit({"char": {"1": "34"}, "pets": {"2": {}}})
        self.assertEqual(gui, 1, "khoa chuoi phai xu ly duoc")

    def test_thieu_mon_thi_BAO_chu_khong_im(self):
        c = _bot(bag={}, char={})
        gui, thieu = c.apply_outfit({"char": {3: 0x99}})
        self.assertEqual(gui, 0)
        self.assertEqual(thieu, [(0, 3, 0x99)])

    def test_uu_tien_mon_CUONG_HOA_cao_nhat(self):
        """Bo do chi luu ID -> nhieu ban sao thi phai tu chon. Dung ban thuong trong khi dang co
        ban +10 la user se chui."""
        c = _bot(bag={3: [0x22, 1], 8: [0x22, 1], 9: [0x22, 1]},
                 bag_items={3: {"reinforced": 2}, 8: {"reinforced": 9}, 9: {"reinforced": 0}},
                 char={})
        c.apply_outfit({"char": {1: 0x22}})
        self.assertEqual(c.equipped, [("char", 8)], "phai lay o 8 (cuong hoa 9)")

    def test_bo_rong_thi_khong_lam_gi(self):
        c = _bot()
        self.assertEqual(c.apply_outfit({}), (0, []))
        self.assertEqual(c.apply_outfit(None), (0, []))


class TestLuuTruBoDo(unittest.TestCase):
    """Luu file RIENG canh accounts.json, khong nhet vao accounts.json (file chua mat khau)."""

    def test_co_ham_load_save(self):
        s = _doc("run_party_digioi.py")
        self.assertIn("def load_outfits(", s)
        self.assertIn("def save_outfit(", s)
        self.assertIn('"outfits.json"', s)

    def test_ghi_bang_file_tam_roi_replace(self):
        """Ghi thang de mat dien giua chung la mat sach bo do."""
        s = _doc("run_party_digioi.py")
        self.assertIn("os.replace(tmp, _outfits_path())", s)

    def test_xoa_bo_khi_truyen_None(self):
        s = _doc("run_party_digioi.py")
        self.assertIn("if bo is None:", s)


class TestGuiTuiDo(unittest.TestCase):
    def test_nut_nam_trong_tui_do(self):
        """User chot: "cho luon vao cho tui do"."""
        s = _doc("gui.py")
        self.assertIn('ttk.Label(bo, text="Bộ đồ:")', s)
        self.assertIn('text="Mặc bộ này"', s)
        self.assertIn('text="Lưu bộ đang mặc…"', s)
        self.assertIn('text="Xoá bộ"', s)

    def test_XOA_phai_hoi_xac_nhan(self):
        """User dan rieng: "khi xoa co canh bao xac nhan"."""
        s = _doc("gui.py")
        i = s.find("def _xoa_bo")
        doan = s[i:i + 600]
        self.assertIn("askyesno", doan)
        self.assertIn("Không lấy lại được", doan)

    def test_ghi_de_cung_hoi(self):
        s = _doc("gui.py")
        i = s.find("def _luu_bo")
        self.assertIn("askyesno", s[i:i + 900])

    def test_mac_bo_di_qua_run_de_bi_xep_hang_khi_dang_danh(self):
        """Phai goi qua _run: trong do co queue_bag_cmd -> dang danh thi xep hang."""
        s = _doc("gui.py")
        self.assertIn('self._run("Mặc bộ \'%s\'" % ten', s)


if __name__ == "__main__":
    unittest.main()
