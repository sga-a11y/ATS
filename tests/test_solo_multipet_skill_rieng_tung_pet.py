# -*- coding: utf-8 -*-
"""DI GIOI SOLO nhieu pet: moi pet dung DUNG skill user set cho chinh no.

User 03/10 bao: "de che do solo DG thi bot ko cho dung skill, du da set roi".
Goc: `_battle_rules` tra rule pet theo `state.active_pet_id` cho MOI atype -> 3 con khong phai pet
dang xuat chien doc rule cua con khac, skill do chung khong hoc -> bo qua -> danh thuong.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import combat, config
from bot.state import BattleState, Unit

PET_A, PET_B = 0xa051, 0xb062
SK_B = 10301


def _state(active_pid):
    st = BattleState()
    st.solo_multipet = True
    st.active_pet_id = active_pid
    st.multi_pet_pid = {0: PET_A, 1: PET_B}
    st.battle_config = {"pets": {str(PET_B): [
        {"enabled": True, "condition": "always", "skill": SK_B, "target": "auto"}]}}
    st.enemy_slots = [1, 2]
    st.enemy_gen = 5
    return st


def _unit():
    u = Unit("pet_at1")
    u.hp = u.hp_max = 1000
    u.sp = 999
    return u


class SkillRiengTungPet(unittest.TestCase):
    def test_pet_KHONG_active_van_dung_skill_da_set(self):
        d = combat.decide_multipet(_state(PET_A), 1, [SK_B], _unit(), [(1, 1), (1, 2)])
        self.assertEqual(d.skill, SK_B)

    def test_pet_active_van_dung_skill_da_set(self):
        d = combat.decide_multipet(_state(PET_B), 1, [SK_B], _unit(), [(1, 1), (1, 2)])
        self.assertEqual(d.skill, SK_B)

    def test_pet_CHUA_set_thi_auto(self):
        st = _state(PET_B)
        d = combat.decide_multipet(st, 0, [SK_B], _unit(), [(0, 1), (0, 2)])
        self.assertEqual(d.skill, config.SKILL_NORMAL)

    def test_khong_biet_pid_cua_atype_thi_roi_ve_active_pet(self):
        st = _state(PET_B)
        st.multi_pet_pid = {}
        d = combat.decide_multipet(st, 1, [SK_B], _unit(), [(1, 1), (1, 2)])
        self.assertEqual(d.skill, SK_B)


if __name__ == "__main__":
    unittest.main()
