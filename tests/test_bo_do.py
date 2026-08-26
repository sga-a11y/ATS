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
        self.assertIn('text="Lưu thành bộ mới…"', s)
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
        i = s.find("def _luu_bo_moi")
        self.assertIn("askyesno", s[i:i + 1400])

    def test_mac_bo_di_qua_run_de_bi_xep_hang_khi_dang_danh(self):
        """Phai goi qua _run: trong do co queue_bag_cmd -> dang danh thi xep hang."""
        s = _doc("gui.py")
        self.assertIn("self._run(\"Mặc bộ '%s'\" % self._bo_ten", s)


class TestLuongSoanBoDo(unittest.TestCase):
    """User chot lai luong 26/08:
      - dong DAU dropdown la "Đồ đang mặc"; chon no thi KHONG co nut "Mặc bộ này"
      - chon mot bo -> 6 o tren hien DO CUA BO DO (xem truoc), chua mac
      - luoi duoi co CA tui do LAN 6 mon dang mac (do dang mac khong nam trong tui)
      - sua setup KHONG ap dung ngay, phai bam "Mặc bộ này"
      - co dong uoc tinh chi so se doi the nao
    """

    def test_dong_dau_la_do_dang_mac(self):
        s = _doc("gui.py")
        self.assertIn('DANG_MAC = "— Đồ đang mặc —"', s)
        self.assertIn("values=[self.DANG_MAC] + ds", s)

    def test_chon_do_dang_mac_thi_TAT_nut_mac(self):
        s = _doc("gui.py")
        self.assertIn('_co = self._bo_soan is not None', s)
        self.assertIn('_b.state(["!disabled"] if _hien else ["disabled"])', s)

    def test_6_o_tren_hien_BO_DANG_SOAN(self):
        s = _doc("gui.py")
        self.assertIn("def _equip_map_xem", s)
        self.assertIn("emap = self._equip_map_xem(who)", s)

    def test_luoi_co_them_do_dang_mac(self):
        """Do dang mac KHONG nam trong tui -> phai chen vao luoi moi chon vao bo duoc."""
        s = _doc("gui.py")
        self.assertIn("them.append((-int(fit), int(tid), 1, d))", s)
        self.assertIn("out = them + out", s)

    def test_slot_am_xu_ly_duoc(self):
        s = _doc("gui.py")
        self.assertIn("if int(slot) < 0:", s)
        self.assertIn("_giu < 0 or _giu in self.c.bag_slots", s)

    def test_sua_setup_KHONG_mac_ngay(self):
        s = _doc("gui.py")
        i = s.find("def _dat_vao_bo")
        doan = s[i:i + 500]
        self.assertIn("m[int(fit)] = int(tid)", doan)
        for cam in ("equip_item", "apply_outfit", "save_outfit"):
            self.assertNotIn(cam, doan, "dat vao bo KHONG duoc mac/luu ngay")

    def test_soan_bo_thi_AN_nut_lam_doi_tui(self):
        """Dang soan bo ma lo tay bam 'Phan giai' la mat mon."""
        s = _doc("gui.py")
        i = s.find("if self._bo_soan is not None:", s.find("def _show_actions"))
        self.assertGreater(i, 0)
        self.assertIn("return", s[i:i + 1400])

    def test_co_dong_chenh_lech_va_KHONG_con_la_uoc_tinh(self):
        """User 26/08: "phai co du het roi chu nhi" - dung, bot giu du ThingData ca tui lan do
        dang mac nen tinh DUNG duoc, khong duoc ghi "uoc tinh" nua."""
        s = _doc("gui.py")
        self.assertIn("def _dong_delta", s)
        self.assertNotIn("ước tính", s)
        # User 26/08: "dung ghi du tinh +- bao nhieu, ghi luon chi so neu thay bo do"
        self.assertIn('"Nếu mặc bộ này:   "', s)
        i = s.find("def _dong_delta")
        self.assertNotIn("%+d", s[i:i + 2600], "khong duoc hien do lech +-, phai hien so KET QUA")

    def test_cong_cua_mon_gom_du_4_nguon(self):
        """Ban mau + linh da + cuong hoa + dong phu. Thieu nguon nao la so chenh lech sai."""
        s = _doc("gui.py")
        i = s.find("def _cong_cua_mon")
        doan = s[i:s.find("def _cong_cua_bo", i)]
        self.assertIn("_STONE_ATTR", doan)
        self.assertIn("self._rf_db", doan)
        self.assertIn("self._affix_db", doan)
        self.assertIn("int(_v) - 100", doan, "gia tri ban mau LECH 100")

    def test_lay_dung_MON_CU_THE_chu_khong_chi_ban_mau(self):
        s = _doc("gui.py")
        self.assertIn("def _thing_cua_tid", s)
        self.assertIn("self._cong_cua_mon(tid, self._thing_cua_tid(tid))", s)


class TestBangCuongHoa(unittest.TestCase):
    def test_eq_affix_json_co_bang_cuong_hoa(self):
        import json
        with io.open(os.path.join(ROOT, "eq_affix.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertTrue(d.get("reinforced"), "thieu bang luat cuong hoa")
        self.assertTrue(d.get("value"), "thieu bang tri so cuong hoa")
        for r in d["reinforced"]:
            self.assertEqual(sorted(r), ["attr", "c1", "c2", "ft", "q"])

    def test_items_gamedata_co_quality(self):
        """Luat cuong hoa khop theo quality -> thieu `q` la khong tinh duoc."""
        import json
        with io.open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertTrue(any("q" in v for v in d.values()))

    def test_luu_thay_doi_TACH_khoi_sua(self):
        """Sua trong bo chi nam o RAM cho toi khi bam 'Lưu thay đổi'."""
        s = _doc("gui.py")
        self.assertIn("def _luu_thay_doi", s)
        self.assertIn("ctrl.save_outfit(self.username, self._bo_ten, self._bo_soan)", s)


if __name__ == "__main__":
    unittest.main()
