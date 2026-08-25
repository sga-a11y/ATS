"""Loan dau la PvP -> phe cua minh KHONG co dinh o hang 2-3.

Su co that 25/08/2026 21:33: bot mac dinh coi hang 0-1 la dich, nhung server xep no o hang 0
-> no ban vao chinh phe minh -> server tra `S:000-000` ly do **42 `修改戰鬥封包`** (goi chien
dau bi sua, `quit=true`) -> DA HAN 3 acc cung luc.

Capture `captures/loandau_20260825.pcap` cho thay nguoi that o (0,1) tran 1 va (0,0) tran 2.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import combat, loandau  # noqa: E402
from bot.state import BattleState  # noqa: E402
from bot import config  # noqa: E402


class TestMacDinhKhongDOI(unittest.TestCase):
    """Moi mode khac PHAI giu nguyen hanh vi cu - day la cua chan quan trong nhat."""

    def test_mac_dinh_dung_nhu_truoc(self):
        st = BattleState()
        self.assertEqual(st.enemy_rows, (0, 1))
        self.assertEqual(st.ally_rows, (2, 3))
        self.assertEqual(st.char_row, 3)

    def test_helper_hang_char_pet_mac_dinh(self):
        st = BattleState()
        self.assertEqual(combat._hang_cua(st, config.UNIT_CHAR), 3)
        self.assertNotEqual(combat._hang_cua(st, config.UNIT_PET), 3)
        self.assertEqual(combat._hang_cua(st, config.UNIT_PET), 2)

    def test_state_thieu_thuoc_tinh_van_chay(self):
        """Duong cu / object dung do khong duoc vo."""
        class Tro:
            pass
        self.assertEqual(combat._hang_cua(Tro(), config.UNIT_CHAR), 3)
        self.assertEqual(combat._hang_cua(Tro(), config.UNIT_PET), 2)


class TestDoiPhe(unittest.TestCase):
    def test_minh_o_hang_0_thi_dich_la_2_3(self):
        st = BattleState()
        self.assertTrue(st.doi_phe_theo_hang_cua_minh(0))
        self.assertEqual(st.enemy_rows, (2, 3))
        self.assertEqual(st.ally_rows, (0, 1))
        self.assertEqual(st.char_row, 0)
        self.assertEqual(combat._hang_cua(st, config.UNIT_CHAR), 0)
        self.assertEqual(combat._hang_cua(st, config.UNIT_PET), 1)

    def test_minh_o_hang_3_thi_giu_nhu_cu(self):
        st = BattleState()
        st.doi_phe_theo_hang_cua_minh(3)
        self.assertEqual((st.enemy_rows, st.ally_rows, st.char_row), BattleState.PHE_MAC_DINH)

    def test_hang_vo_ly_thi_khong_doi_gi(self):
        st = BattleState()
        self.assertFalse(st.doi_phe_theo_hang_cua_minh(9))
        self.assertEqual(st.enemy_rows, (0, 1))

    def test_tra_ve_mac_dinh(self):
        st = BattleState()
        st.doi_phe_theo_hang_cua_minh(0)
        st.dat_phe_mac_dinh()
        self.assertEqual((st.enemy_rows, st.ally_rows, st.char_row), BattleState.PHE_MAC_DINH)


class TestQuaiTheoPhe(unittest.TestCase):
    """sync_from_tracker phai lay quai theo enemy_rows, khong phai hang 0-1 co dinh."""

    class _Unit:
        def __init__(self, hp):
            self.hp = hp
            self.hp_max = hp
            self.sp = 0
            self.sp_max = 0
            self.role_id = b""

    @staticmethod
    def _Tracker(units):
        """Tracker THAT (chi nhet san units) - stub tay se lech khi tracker doi thuoc tinh."""
        from bot.battle_tracker import BattleTracker
        tr = BattleTracker(b"")
        tr.active = True
        tr.units = units
        return tr

    def _st(self, hang_minh=None):
        st = BattleState()
        st.tracker = self._Tracker({
            (0, 0): self._Unit(100), (0, 1): self._Unit(200),
            (1, 0): self._Unit(300),
            (2, 0): self._Unit(400),
            (3, 0): self._Unit(500), (3, 1): self._Unit(600),
        })
        if hang_minh is not None:
            st.doi_phe_theo_hang_cua_minh(hang_minh)
        st.sync_from_tracker()
        return st

    def test_tran_thuong_quai_o_hang_0_1(self):
        st = self._st()
        self.assertEqual(sorted(st.enemy_hp), [0, 1, 10])

    def test_loan_dau_minh_o_hang_0_thi_quai_la_hang_2_3(self):
        st = self._st(hang_minh=0)
        self.assertEqual(sorted(st.enemy_hp), [20, 30, 31])
        self.assertNotIn(0, st.enemy_hp, "van coi phe minh la quai -> se bi da han")


class TestDocOCuaMinh(unittest.TestCase):
    """Byte lay tu capture that (t=355.68 va t=501.15)."""

    TA = bytes.fromhex("5910fdf4878d0300")

    def _pkt(self, than_hex):
        than = bytes.fromhex(than_hex)
        n = len(than) + 7
        return bytes([0xC0, 0x91, n & 0xFF, n >> 8, 0, 0, 0x0B]) + than

    def _tu_file(self, ten):
        """Goi TAO TRAN nguyen ban, cat ra tu capture (phai ghep luong TCP moi doc duoc:
        goi nay dai 1071/1500 byte nen bi TCP cat lam nhieu segment)."""
        with open(os.path.join(ROOT, "tests", ten), "rb") as fh:
            than = fh.read()
        n = len(than) + 7
        return bytes([0xC0, 0x91, n & 0xFF, n >> 8, 0, 0, 0x0B]) + than

    def test_tran_that_1_minh_o_hang_0(self):
        self.assertEqual(loandau.o_cua_minh(self._tu_file("loandau_create_0.bin"), self.TA),
                         (0, 1))

    def test_tran_that_2_minh_o_hang_0(self):
        self.assertEqual(loandau.o_cua_minh(self._tu_file("loandau_create_1.bin"), self.TA),
                         (0, 0))

    def test_tran_that_dan_den_dich_la_hang_2_3(self):
        """Chinh la tinh huong lam VANG 3 acc: bot cu tuong dich o hang 0-1."""
        st = BattleState()
        o = loandau.o_cua_minh(self._tu_file("loandau_create_0.bin"), self.TA)
        st.doi_phe_theo_hang_cua_minh(o[0])
        self.assertEqual(st.enemy_rows, (2, 3))

    def test_khong_co_entity_thi_tra_None(self):
        self.assertIsNone(loandau.o_cua_minh(self._pkt("fa0000"), None))

    def test_goi_rac_khong_lam_sap(self):
        self.assertIsNone(loandau.o_cua_minh(self._pkt("fa00ffffff"), self.TA))


class TestNoiVaoClient(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_khong_doc_duoc_o_thi_KHONG_danh(self):
        """Danh mo trong loan dau = bi da han acc. Phai bo luot thay vi doan."""
        import re
        m = re.search(r"def _loandau_dat_phe\(self, pkt\):(.*?)\n    def ", self.src, re.S)
        self.assertIsNotNone(m)
        than = re.sub(r"#.*", "", m.group(1))
        self.assertIn("enemy_rows = ()", than)
        self.assertIn("dat_phe_mac_dinh", than)

    def test_hang_nguon_trong_goi_danh_KHONG_duoc_lay_thang_d_unit(self):
        """Goi `0x32` = [hang nguon][cot nguon][hang dich][cot dich].

        `d.unit` (3=char, 2=pet) truoc day duoc dung THANG lam hang nguon - trung nhau vi tran
        thuong luon xep phe ta o hang 2-3. Loan dau o hang 0-1 ma van gui 3/2 = khai bao mot o
        KHONG PHAI cua minh -> ly do 42 -> da han acc (su co 25/08 21:58: dich da dung hang 2-3
        roi ma van van vi hang nguon con 3).
        """
        import re
        m = re.search(r"payload = \(b\"\\x01\\x00\"\s*\+ bytes\(\[([^\]]*)\]\)", self.src)
        self.assertIsNotNone(m, "khong tim thay cho dung payload 0x32")
        dau = m.group(1).split(",")[0].strip()
        self.assertEqual(dau, "hang_nguon", "byte dau goi danh van la %s" % dau)
        self.assertIn("hang_nguon = combat._hang_cua(self.state, d.unit)", self.src)

    def test_doc_HP_char_pet_theo_hang_thuc_te(self):
        """`0x33` doc HP minh theo (hang, slot). Hardcode 0x03/0x02 -> loan dau ra HP=0/0."""
        with open(os.path.join(ROOT, "bot", "state.py"), encoding="utf-8") as fh:
            st_src = fh.read()
        self.assertIn("cd = groups.get((self.char_row, self.self_slot))", st_src)
        self.assertNotIn("cd = groups.get((0x03, self.self_slot))", st_src)
        self.assertNotIn("pd = groups.get((0x02, self.self_slot))", st_src)

    def test_dat_phe_duoc_goi_khi_tao_tran(self):
        import re
        m = re.search(r"is_battle_create\(opcode, pkt\):(.*?)\n\n", self.src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("_loandau_dat_phe", re.sub(r"#.*", "", m.group(1)))


if __name__ == "__main__":
    unittest.main()
