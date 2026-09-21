# -*- coding: utf-8 -*-
"""CHE DO NHIEU PET suy tu DOI HINH TRONG TRAN, khong doc config.

User 21/09 bao party Di Gioi: "4 con pet ko con nao danh" roi "no ko hoi HP SP cho 3 con pet, chi
hoi 1 con". Ca hai la MOT goc: `state.solo_multipet` khong duoc bat.

Truoc day co nay chi duoc bat o DUNG MOT DONG trong `run_party_digioi`, khi user chon
`digioi_mode == "solo"`. Bo sot hai truong hop THAT:
  - party cau hinh CHI CO 1 ACC di Di Gioi -> van la mode "party" -> khong bat. (Khong phai
    "thieu nguoi dung yen": 1/1 la DU nguoi nen leader van chay long vong danh binh thuong.)
  - MOI party chay ENGINE MOI -> no `return` ngay sau login (`run_party_digioi.py` cua re engine
    moi) nen KHONG BAO GIO chay toi dong do.

Co tat thi hong HAI duong, deu IM LANG:
  - danh : `pet_opts` bi loc theo `my_atype` (char atype 2, pet o 0/1/3/4) -> rong -> khong con
           nao danh, khong log gi.
  - hoi  : `do_heal` roi xuong `self.state.pet` -> chi hoi DUNG MOT con.

User chot cach lam: "ro rang la luc start tran m biet duoc danh sach doi hinh ben minh, thi biet
duoc bao nhieu pet xuat chien roi chu" va "1 char va 1 den 4 pet chu, dau phai co dinh 4 pet".
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.state import BattleState, Unit


def _doi_hinh(st, char_slots=(), pet_slots=()):
    for sl in char_slots:
        st.allies[(st.char_row, sl)] = Unit("char%d" % sl)
    for sl in pet_slots:
        st.allies[(st.hang_pet_ta(), sl)] = Unit("pet%d" % sl)
    return st


class TestSuyTuDoiHinh(unittest.TestCase):
    def test_mot_char_bon_pet_thi_BAT(self):
        st = _doi_hinh(BattleState(), char_slots=(2,), pet_slots=(0, 1, 3, 4))
        self.assertTrue(st.suy_solo_multipet())

    def test_mot_char_MOT_pet_cung_BAT(self):
        """User: "1 char va 1 den 4 pet chu, dau phai co dinh 4 pet". Mot pet ma nam o atype KHAC
        char thi bo loc `my_atype` cung loai mat -> van phai di duong nhieu pet."""
        st = _doi_hinh(BattleState(), char_slots=(2,), pet_slots=(0,))
        self.assertTrue(st.suy_solo_multipet())

    def test_HAI_char_tro_len_thi_TAT(self):
        """Party that: `0x35` mang ca pet cua NGUOI KHAC. Gui lenh cho pet nguoi khac = server coi
        la sua goi chien dau (ma 42) va DA HAN acc - da dinh that 01/09."""
        st = _doi_hinh(BattleState(), char_slots=(0, 1, 2), pet_slots=(0, 1, 2))
        self.assertFalse(st.suy_solo_multipet())

    def test_dang_BAT_ma_thay_them_char_thi_TAT_NGAY(self):
        st = _doi_hinh(BattleState(), char_slots=(2,), pet_slots=(0, 1))
        self.assertTrue(st.suy_solo_multipet())
        st.allies[(st.char_row, 3)] = Unit("char3")
        self.assertFalse(st.suy_solo_multipet(), "thay nguoi khac ma khong tat -> nguy co bi DA")

    def test_char_KHONG_co_pet_thi_TAT(self):
        st = _doi_hinh(BattleState(), char_slots=(2,))
        self.assertFalse(st.suy_solo_multipet())

    def test_CHUA_co_du_lieu_thi_GIU_NGUYEN(self):
        """`allies` bi `clear()` moi `0x34` (tran moi). Ha co luc rong = moi dau tran deu tu tat
        mot nhip, dung luc can nhat."""
        st = _doi_hinh(BattleState(), char_slots=(2,), pet_slots=(0, 1))
        self.assertTrue(st.suy_solo_multipet())
        st.allies.clear()
        self.assertTrue(st.suy_solo_multipet(), "mat co khi sang tran moi")

    def test_gop_khoa_cua_goi_HIEN_TAI(self):
        """Tham so `them` de ket luan dung NGAY goi dau, khong tre mot luot."""
        st = BattleState()
        self.assertTrue(st.suy_solo_multipet([(st.char_row, 2), (st.hang_pet_ta(), 0)]))

    def test_LOAN_DAU_lat_phe_van_dung(self):
        """Loan dau: server co the xep minh sang phe kia -> hang char/pet DOI. Viet chet hang 3/2
        la dem nham quai thanh dong doi."""
        st = BattleState()
        st.doi_phe_theo_hang_cua_minh(0)
        self.assertEqual(st.char_row, 0)
        _doi_hinh(st, char_slots=(2,), pet_slots=(0, 1))
        self.assertTrue(st.suy_solo_multipet())


class TestKhongCongDoiHinhVoiQUAI(unittest.TestCase):
    """Chi dem PHE TA. Dem ca hang dich thi tran nao cung "nhieu char" -> khong bao gio bat."""

    def test_quai_khong_tinh(self):
        st = _doi_hinh(BattleState(), char_slots=(2,), pet_slots=(0, 1, 3, 4))
        for hang in st.enemy_rows:
            for cot in range(5):
                st.allies[(hang, cot)] = Unit("quai")
        self.assertTrue(st.suy_solo_multipet())


class TestKhongRiengDiGioi(unittest.TestCase):
    """User 21/09: "cai nay la trong event Nhi Kieu cung co 4 pet xuat chien neu di ko co party do".

    Vi suy tu DOI HINH chu khong hoi "co phai Di Gioi khong", moi che do di mot minh deu tu dung -
    2K, loan dau, train le... Ai sau nay siet lai thanh "chi Di Gioi" se lam do bai nay.
    """

    def test_khong_hoi_map_hay_mode(self):
        with io.open(os.path.join(ROOT, "bot", "state.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("    def suy_solo_multipet(")
        than = s[i:s.find("\n    def ", i + 10)]
        for tu in ("DIGIOI_MAP_ID", "digioi_mode", "current_map", "event_key"):
            self.assertNotIn(tu, than, "suy theo %s -> bo sot cac che do di mot minh khac" % tu)

    def test_2K_di_mot_minh_van_BAT(self):
        """Doi hinh y het, chi khac la dang o thap 2K - ket qua phai giong het."""
        st = _doi_hinh(BattleState(), char_slots=(2,), pet_slots=(0, 1, 3, 4))
        self.assertTrue(st.suy_solo_multipet())

    def test_2K_di_THEO_PARTY_thi_TAT(self):
        st = _doi_hinh(BattleState(), char_slots=(1, 2), pet_slots=(1, 2))
        self.assertFalse(st.suy_solo_multipet())


class TestKhongConDocConfig(unittest.TestCase):
    def test_run_party_khong_con_tu_bat_co(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertNotIn("state.solo_multipet = True", s,
                         "bat theo config -> bo sot party 1 acc va CA engine moi")

    def test_engine_moi_khong_can_nhanh_rieng(self):
        """Suy trong `BattleState` nen hai engine dung chung, engine moi tu co."""
        with io.open(os.path.join(ROOT, "bot", "state.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("def suy_solo_multipet(", s)


if __name__ == "__main__":
    unittest.main()
