# -*- coding: utf-8 -*-
"""Boss the gioi: KHONG gui `0x14 09` (chon muc) khi server khong mo menu.

Bao loi BL-1007-BA37 (07/10, acc moi tao HP 83): bam NPC boss 0x2d -> server chi tra THOAI 24732
"Dang cap cua nha nguoi that thap..." (S:020-001 resultType 1). Bot gui mu `0x14 09 1e` -> server
`0x14 080001` + `0x00 ma 5` "su kien vi pham" -> rot, relogin, lai danh boss, lai rot (4/4 lan).
Nguong vao boss = cap 15 (nguong server, user xac nhan).
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as client_mod
from bot.client import GameClient

# Goi server THAT tu log BL-1007-BA37 (18:12:22.373): thoai 24732 sau khi bam NPC 0x2d.
GOI_THOAI_CAP_THAP = bytes.fromhex("c091180000001401000000000101032d0000000000009c60")
# Server dong su kien (S:020-008 kind 1) - goi that ngay sau trong cung log.
GOI_HET = bytes.fromhex("c0910a00000014080001")


def _goi_menu():
    """S:020-001 resultType 6 (tuong tac, style 0) - dung bo cuc `ReceiveCommonEvent`."""
    body = bytes([0x00, 0x00, 0x00, 0x01, 0x06, 0x03, 0x2d, 0x00, 0x00, 0, 0, 0, 0, 0x01, 0x00])
    return b"\xc0\x91" + (9 + len(body)).to_bytes(4, "little") + b"\x14\x01\x00" + body


class _DongHo:
    """Thoi gian gia: sleep chi cong dong ho -> test chay tuc thi."""

    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += max(0.0, s)


class _Boss:
    def __init__(self, tra_loi_bam, cap=None):
        c = GameClient.__new__(GameClient)
        c.running = True
        c._label = "test"
        c.state = SimpleNamespace(in_battle=False, boss_mode=False)
        c._qev = None
        c.QEV_TALK_DELAY = 0.0
        c.current_map = 12001
        c.flee_mode = False
        c.char_level = cap
        c._world_boss_event_open = lambda: True
        c.thao_ngoc_phuc_than = lambda *a, **k: None
        c.in_combat = lambda *a, **k: False
        c._in_battle_end_grace = lambda: False
        c.heal_full = lambda *a, **k: None
        c._wait_combat_clear = lambda *a, **k: None
        c.teleport = lambda *a, **k: None
        c.send = self.send
        self.c = c
        self.tra_loi_bam = tra_loi_bam
        self.gui = []

    def send(self, op, body):
        self.gui.append((op, bytes(body)))
        if op != 0x14:
            return
        if body == b"\x01\x00\x2d\x00":
            for p in self.tra_loi_bam:
                self.c._observe_quest_event(0x14, p)
        elif body == b"\x06\x00":
            self.c._observe_quest_event(0x14, GOI_HET)

    def chay(self):
        dh = _DongHo()
        with mock.patch.object(client_mod, "time", dh):
            return self.c.do_world_boss()

    def da_chon(self):
        return [b for op, b in self.gui if op == 0x14 and b[:2] == b"\x09\x00"]


class TestWorldBossCapThap(unittest.TestCase):
    def test_server_tra_THOAI_thi_KHONG_chon(self):
        """Dung ca BA37: chua doc duoc cap, server tra thoai 24732 -> khong gui 0x14 09."""
        b = _Boss([GOI_THOAI_CAP_THAP], cap=None)
        self.assertFalse(b.chay())
        self.assertEqual(b.da_chon(), [], "chon khi khong co menu = su kien vi pham ma 5")
        # Dong thoai DUNG nhu client: tra `0x14 06`.
        self.assertIn((0x14, b"\x06\x00"), b.gui)
        self.assertNotIn(0x41, [op for op, _ in b.gui], "khong engage boss khi bi tu choi")
        self.assertTrue(b.c._world_boss_tu_choi)
        self.assertFalse(b.c.state.boss_mode)

    def test_bi_tu_choi_roi_thi_KHONG_bam_lai_trong_phien(self):
        b = _Boss([GOI_THOAI_CAP_THAP], cap=None)
        b.chay()
        b.gui.clear()
        self.assertFalse(b.chay())
        self.assertEqual(b.gui, [])

    def test_server_mo_MENU_thi_chon_30_nhu_cu(self):
        """Acc du cap: chuoi gui sau khi bam giu NGUYEN nhu ban cu (09 1e -> 06 -> 0x41)."""
        b = _Boss([_goi_menu()], cap=120)
        b.chay()
        sau_bam = b.gui[[x[1] for x in b.gui].index(b"\x01\x00\x2d\x00") + 1:]
        self.assertEqual(sau_bam[:3], [(0x14, b"\x09\x00\x1e"), (0x14, b"\x06\x00"),
                                       (0x41, bytes.fromhex("01003232010100000101000000"))])

    def test_cap_duoi_15_thi_KHONG_gui_gi(self):
        b = _Boss([GOI_THOAI_CAP_THAP], cap=14)
        self.assertFalse(b.chay())
        self.assertEqual(b.gui, [])

    def test_cap_15_thi_duoc_danh(self):
        b = _Boss([_goi_menu()], cap=15)
        b.chay()
        self.assertEqual(b.da_chon(), [b"\x09\x00\x1e"])

    def test_do_world_boss_all_cap_thap_bo_qua_som(self):
        b = _Boss([], cap=3)
        b.c.query_world_boss_attempts = mock.Mock(side_effect=AssertionError("khong duoc hoi"))
        dh = _DongHo()
        with mock.patch.object(client_mod, "time", dh):
            self.assertFalse(GameClient.do_world_boss_all.__wrapped__(b.c)
                             if hasattr(GameClient.do_world_boss_all, "__wrapped__")
                             else b.c.do_world_boss_all())
        self.assertEqual(b.gui, [])

    def test_nguong_la_15(self):
        self.assertEqual(client_mod.WORLD_BOSS_MIN_LEVEL, 15)


class TestPbDonCapThap(unittest.TestCase):
    """PB don cung can cap >= 15 (user chot 07/10). Chan TRUOC thao ngoc / roi party."""

    def _client(self, cap):
        c = GameClient.__new__(GameClient)
        c.running = True
        c._label = "test"
        c.char_level = cap
        c._quest_cells = set()
        c._query_quests = mock.Mock(side_effect=lambda: c._quest_cells.add(1))
        c.thao_ngoc_phuc_than = mock.Mock()
        c.leave_party = mock.Mock()
        return c

    def test_cap_14_KHONG_dung_vao_gi(self):
        c = self._client(14)
        c.do_daily_dungeon()
        c._query_quests.assert_not_called()
        c.thao_ngoc_phuc_than.assert_not_called()
        c.leave_party.assert_not_called()

    def test_cap_15_di_tiep(self):
        c = self._client(15)
        c.do_daily_dungeon()
        c._query_quests.assert_called()      # qua cong cap, toi buoc hoi o1 (o1 da xong -> dung)

    def test_chua_doc_duoc_cap_thi_giu_nhu_cu(self):
        c = self._client(None)
        c.do_daily_dungeon()
        c._query_quests.assert_called()

    def test_nguong_la_15(self):
        self.assertEqual(client_mod.SOLO_DUNGEON_MIN_LEVEL, 15)


if __name__ == "__main__":
    unittest.main()
