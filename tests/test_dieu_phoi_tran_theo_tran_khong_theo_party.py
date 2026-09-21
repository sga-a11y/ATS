# -*- coding: utf-8 -*-
"""BO DIEU PHOI TRAN gom theo TRAN, khong theo cau hinh party.

User 21/09 (party 20): "bon no dang danh bos QD ma bao party-battle lech phien cai lon gi the,
danh boss thi solo ma".

Boss Quan Doan (`0x27 7700` -> `0x14 08000100`) va boss the gioi la instance RIENG cua tung acc.
Truoc day `_battle_coordinator` lay khoa = `party_idx`, nen ca 5 acc cua party dung CHUNG mot
coordinator trong khi moi acc dang o mot `generation/turn` khac nhau:

  - `active_key` chi khop duoc DUNG MOT acc -> 4 acc con lai luot nao cung `khop_key=False`;
  - `mark_sent` co `account_id` trong khoa nen lenh DANH van gui duoc (log ghi "VAN GUI") - vi the
    loi nay nhin qua chi giong log rac;
  - nhung `reserve()` gac bang `if self.active_key != (generation, turn): return False` - KHONG
    theo acc - nen 4 acc kia bi tu choi dat cho MOI hanh dong khong phai sat thuong (hoi mau, CC,
    bao ve) trong suot tran boss. Day moi la thiet hai that.

Dau hieu dung: DOI HINH PHE TA trong tran (`state.tran_mot_minh`), cung nguon da dung de suy
`solo_multipet`. Xem `tests/test_solo_multipet_suy_tu_doi_hinh.py`.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.state import BattleState, Unit


class _Cli:
    """Chi muon `_battle_coordinator` - khong dung duoc GameClient that (no mo socket)."""

    def __init__(self, party_idx, state):
        self.party_idx = party_idx
        self.state = state
        self.battle_tracker = None
        self._battle_party_key = None
        self._battle_party_coordinator = None

    _battle_coordinator = None   # gan o setUpClass


def _doi_hinh(st, so_char, so_pet=1):
    for i in range(so_char):
        st.allies[(st.char_row, i)] = Unit("char%d" % i)
    for i in range(so_pet):
        st.allies[(st.hang_pet_ta(), i)] = Unit("pet%d" % i)
    st.suy_solo_multipet()
    return st


class TestKhoaDieuPhoi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from bot.client import GameClient
        # `staticmethod`: gan thang ham vao class cua TestCase thi no thanh method, `self.ham(c)`
        # se truyen ca self -> TypeError.
        cls.ham = staticmethod(GameClient._battle_coordinator)

    def setUp(self):
        # GIU THAM CHIEU: khoa solo la `("solo", id(self))`; tha client ra cho bi thu gom thi
        # CPython cap lai dung dia chi cho client sau -> hai khoa trung nhau va bai test do oan.
        self._song = []

    def _khoa(self, party_idx, st):
        c = _Cli(party_idx, st)
        self._song.append(c)
        c.state.attach_tracker = lambda *a, **k: None
        self.ham(c)
        return c._battle_party_key

    def test_boss_QD_moi_acc_mot_KHOA_RIENG(self):
        """5 acc cung party 20, moi dua mot instance boss -> 5 khoa khac nhau."""
        khoa = [self._khoa(19, _doi_hinh(BattleState(), so_char=1)) for _ in range(5)]
        self.assertEqual(len(set(khoa)), 5, "van gom chung -> 4 acc bi `reserve` tu choi ca tran")
        for k in khoa:
            self.assertNotEqual(k, 19, "van lay khoa theo party_idx")

    def test_tran_PARTY_that_van_CHUNG_khoa(self):
        """PB110 / Di Gioi party: nhieu char trong tran -> phai dung chung de dieu phoi."""
        a = self._khoa(19, _doi_hinh(BattleState(), so_char=5))
        b = self._khoa(19, _doi_hinh(BattleState(), so_char=5))
        self.assertEqual(a, b)
        self.assertEqual(a, 19)

    def test_CHUA_BIET_doi_hinh_thi_GIU_khoa_party(self):
        """Luot dau tran party, `allies` co the chua kip co nguoi thu hai. Doan nham huong solo la
        MAT dieu phoi that - nen mac dinh phai nghieng ve party."""
        st = BattleState()
        self.assertIsNone(st.tran_mot_minh)
        self.assertEqual(self._khoa(19, st), 19)

    def test_khong_co_party_idx_thi_van_nhu_cu(self):
        k = self._khoa(None, BattleState())
        self.assertIsInstance(k, tuple)
        self.assertEqual(k[0], "solo")

    def test_party_0_KHONG_bi_coi_la_thieu(self):
        """`party_idx = 0` la party 1 - `if self.party_idx` (thay vi `is not None`) se nuot mat."""
        self.assertEqual(self._khoa(0, _doi_hinh(BattleState(), so_char=3)), 0)


class TestNguonDauHieu(unittest.TestCase):
    def test_tran_mot_minh_suy_cung_cho_voi_solo_multipet(self):
        """Hai co phai cung mot nguon: tach ra la som muon lech nhau."""
        with io.open(os.path.join(ROOT, "bot", "state.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("    def suy_solo_multipet(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("self.tran_mot_minh =", than)
        self.assertIn("self.solo_multipet =", than)

    def test_mot_char_KHONG_pet_van_la_tran_mot_minh(self):
        """Khac `solo_multipet` (can co pet): boss QD co the ra tran khong mang pet."""
        st = _doi_hinh(BattleState(), so_char=1, so_pet=0)
        self.assertTrue(st.tran_mot_minh)
        self.assertFalse(st.solo_multipet)


if __name__ == "__main__":
    unittest.main()
