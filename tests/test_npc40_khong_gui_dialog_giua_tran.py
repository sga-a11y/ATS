"""40NPC: goi dialog/event roi vao GIUA TRAN = ma 47 -> dut ket noi -> party tan.

User 09/09: "40npc, ko dc party nao danh luon".

Do tren party.log: event chi keo 21:42 -> 22:00, va trong 18 phut do co **92 lan ma 47**. Nhung
cung khoang do co **357 lan `Nhan item: Thắng Lệnh 1`** - tuc party CO danh va CO thang. Khong
phai "khong danh duoc", ma la danh xong roi tu giet minh.

Chuoi that cua `ttsau` (leader party tt) - doc gui-cuoi/nhan-cuoi luc rot:

    21:44:13 [ttsau]  40NPC: het tran, party alive=1/1 defeated=False
    21:44:13 [tt*]    ca 5 acc: Nhan item: Thắng Lệnh 1          <- ca party VUA THANG
    21:44:15 [ttsau]  (LEADER) 40NPC: ca party da hoi phuc -> mo tran tiep
    21:44:17.241      <<nhan 0x35 ...        <- LUOT CUA TRAN MOI, tran da bat dau lai
    21:44:17.269      >>gui  0x14 0600       <- van dang ban not chuoi dialog cua tran TRUOC
    21:44:17          SERVER NGAT KET NOI: ma la 47
    21:44:17 [tt*]    PARTY: ... ROI doi (S:013-004) -> roster con 1 nguoi

Goi ap dao quanh cac lan rot la `0x14 0600` (ADVANCE): 55/92.

HAI LOI:

  1. `_end_npc_dialog` ban MU ba goi cach nhau 0.5 giay, khong kiem tran. Chuoi 40NPC la CAC TRAN
     LIEN TIEP - server tu mo tran ke tiep - nen khe giua hai tran rat hep.

  2. `alive/total` doc tu `state.allies`, ma tap do chi mang unit CHINH CLIENT DO thay -> luon ra
     `1/1` du party 5 acc. Ca 77 tran deu in `alive=1/1`. Con so vo nghia nay lam ca viec chan
     doan di sai huong ("khong party nao danh").
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import npc40

npc40.CHO_TRAN_XONG_SEC = 0.0      # test khong cho that 8 giay moi goi


class _Char:
    def __init__(self, hp=100, hp_max=100):
        self.hp = hp
        self.hp_max = hp_max


class _State:
    def __init__(self, in_battle=False, hp=100, hp_max=100):
        self.in_battle = in_battle
        self.char = _Char(hp, hp_max)
        self.allies = {}


class _C:
    def __init__(self, in_battle=False, grace=False, hp=100, hp_max=100, party_idx=0):
        self.running = True
        self.state = _State(in_battle, hp, hp_max)
        self._grace = grace
        self._label = "acc"
        self.party_idx = party_idx
        self.da_gui = []
        self._peers = None
        self._battle_start_seq = 0
        self._npc40_last_dialog = ""

    def _in_battle_end_grace(self):
        return self._grace

    def send(self, op, body):
        self.da_gui.append((op, bytes(body)))

    def party_peers(self):
        return self._peers if self._peers is not None else []


def _ngu(_s):
    return None


class TestKhongGuiDialogGiuaTran(unittest.TestCase):
    def test_dang_trong_tran_thi_KHONG_gui(self):
        c = _C(in_battle=True)
        self.assertFalse(npc40._gui_dialog_an_toan(c, npc40.ADVANCE, _ngu, cho=0.0))
        self.assertEqual(c.da_gui, [], "goi nay chinh la 0x14 0600 lam rot 55 lan")

    def test_grace_ket_tran_cung_KHONG_gui(self):
        """Server con dang giai tran sau END - gui luc do van dinh ma 47."""
        c = _C(grace=True)
        self.assertFalse(npc40._gui_dialog_an_toan(c, npc40.ADVANCE, _ngu, cho=0.0))
        self.assertEqual(c.da_gui, [])

    def test_ngoai_tran_thi_gui_binh_thuong(self):
        c = _C()
        self.assertTrue(npc40._gui_dialog_an_toan(c, npc40.ADVANCE, _ngu, cho=0.0))
        self.assertEqual(c.da_gui, [(npc40.OP_DIALOG, npc40.ADVANCE)])

    def test_end_dialog_DUNG_khi_tran_moi_bat_dau_giua_chuoi(self):
        """Ba goi cach nhau 0.5s - tran ke tiep co the bat dau O GIUA. Dung la ca ttsau."""
        c = _C()
        n = {"i": 0}

        def _ngu_va_vao_tran(_s):
            n["i"] += 1
            if n["i"] >= 1:
                c.state.in_battle = True      # server mo tran moi ngay sau goi dau

        npc40._end_npc_dialog(c, _ngu_va_vao_tran)
        self.assertEqual(len(c.da_gui), 1, "van ban not chuoi cu vao giua tran moi -> ma 47")

    def test_end_dialog_du_ba_goi_khi_khong_co_tran(self):
        c = _C()
        self.assertTrue(npc40._end_npc_dialog(c, _ngu))
        self.assertEqual(len(c.da_gui), 3)

    def test_open_battle_KHONG_mo_lai_khi_tran_da_chay(self):
        """Tran ke tiep tu bat dau san -> viec can lam DA XONG, mo NPC nua la ma 47."""
        c = _C(in_battle=True)
        self.assertTrue(npc40._open_event_battle(c, 0, _Stop(), _ngu, 0.1, 3))
        self.assertEqual(c.da_gui, [])

    def test_advance_to_battle_dung_khi_thay_0x35(self):
        """`_battle_start_seq` len o 0x34, `state.in_battle` len som hon o 0x35 - con mot khe hep."""
        c = _C()

        def _ngu_vao_tran(_s):
            c.state.in_battle = True

        npc40._advance_to_battle(c, 0, _Stop(), _ngu_vao_tran, 0.1, 5)
        self.assertLessEqual(len(c.da_gui), 1)


class _Stop:
    def is_set(self):
        return False


class TestDemNguoiSongCuaCA_PARTY(unittest.TestCase):
    """`state.allies` chi mang unit chinh client do thay -> `1/1` du party 5 acc."""

    def test_doc_thang_cac_client_cung_party(self):
        a, b, d = _C(), _C(), _C()
        a._peers = [a, b, d]
        self.assertEqual(npc40.party_song_that(a), (False, 3, 3))

    def test_acc_chet_thi_khong_dem(self):
        a, b = _C(), _C(hp=0)
        a._peers = [a, b]
        self.assertEqual(npc40.party_song_that(a), (False, 1, 2))

    def test_ca_party_chet_moi_la_THUA(self):
        a, b = _C(hp=0), _C(hp=0)
        a._peers = [a, b]
        self.assertEqual(npc40.party_song_that(a), (True, 0, 2))

    def test_CHUA_doc_duoc_HP_thi_coi_la_con_song(self):
        """Ket luan thua oan = ca party bi keo ra khoi event."""
        a = _C(hp=0, hp_max=0)
        a._peers = [a]
        self.assertEqual(npc40.party_song_that(a), (False, 1, 1))

    def test_khong_doc_duoc_party_thi_tra_None(self):
        a = _C()
        a._peers = []
        self.assertIsNone(npc40.party_song_that(a))


class TestNoiVaoClient(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.cli = fh.read()

    def test_client_dung_so_that_khi_in_va_ket_luan(self):
        i = self.cli.find("40NPC: het tran, party alive=")
        self.assertGreater(i, 0)
        self.assertIn("npc40.party_song_that(self)", self.cli[max(0, i - 900):i])

    def test_co_party_peers_doc_thang(self):
        i = self.cli.find("def party_peers(self):")
        self.assertGreater(i, 0)
        self.assertIn("_PARTY_CLIENTS", self.cli[i:i + 600])


if __name__ == "__main__":
    unittest.main()
