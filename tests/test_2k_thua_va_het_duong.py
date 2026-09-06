"""Thua o tang chot 2K: phai BIET la thua, va KHONG duoc dung im an va.

Party 1 (06/09) tang 11 - user: "danh thua roi m dung do an va a":

    15:12:00 [gamo] 2K: tang 11 - Đỉnh Tháp (12934) -> len None (cong door=None tai None),
                    1 diem danh quai, idx [2]        <- fix truoc chay dung: da chiu DANH
    15:12:03 [gamo] da toi diem (650,430) sau 5 lenh move
    15:12:09..15:14:32  BATTLE SEND/ACK g=1 t=1..t=7   HP quai gan nhu khong tut
                        (0: 10001 -> 9575, 1: 7379 -> 7379 ...)
    15:14:39  ca 5 acc deu tut 1 luot Phuc Than = ca party CHET
    15:14:41 [gamo]  2K: xong tran idx=2, party song 0/0    <- bot tuong THANG
    15:14:43 [gamo]  2K: tang 11 da danh 1/1 tran ma VAN khong co cong len -> dung o day
    15:14:44..15:15:09  (LEADER) pos=(650, 430) map=12934 combat=False   <- DUNG IM

HAI LOI:
  1. `npc40.party_defeated` doc HP cua `state.allies`. `allies` la danh sach DONG DOI, chi day du
     khi co `0x0b` party-broadcast, va bi clear() moi `0x34` -> RONG -> `bool(known) and
     alive == 0` tra **False**. "party song 0/0" khong phai "song 0 tren 0" ma la "KHONG BIET".
     SERVER KHONG GUI GOI THANG/THUA: `S:011-000 <結束戰鬥>` chi mang `roleId + npcIndex`, va
     `FightManager.FightOver` chi `SetWar(EWar.None)`. Client biet chet bang HP
     (`FightField.lua:1034`). Bot lam y het, doc HP cua CHINH TUNG ACC (ca 5 nam trong mot tien
     trinh) - chot LIEN TUC trong tran vi sau tran server hoi/hoi sinh la mat dau vet.
  2. Danh het tang ma khong co cong len ("het_duong") thi khong con gi lam o do nua, nhung bot
     xep chung vao "ket" (= chua het, de dieu phoi gom/moi lai) -> dung im vo han.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class _C:
    def __init__(self, chet=False, running=True):
        self.running = running
        self.chet_tran_nay = chet
        self.current_map = 12934
        self.current_channel = 1


class TestThuaDocHPCuaChinhMinh(unittest.TestCase):
    """Server KHONG gui goi thang/thua. Client biet chet bang HP (FightField.lua:1034).
    Bot lam y het - va lam duoc tot hon vi ca 5 acc trong MOT tien trinh."""

    PARTY = 5
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._apu = R._active_party_usernames
        R._active_party_usernames = lambda pidx: list(self.ACCS)
        self._cl = dict(R.account_clients)
        R.account_clients.clear()

    def tearDown(self):
        R._active_party_usernames = self._apu
        R.account_clients.clear(); R.account_clients.update(self._cl)

    def _dat(self, **kw):
        for u, v in kw.items():
            R.account_clients[u] = _C(chet=v)

    def test_CA_PARTY_chet_thi_la_THUA(self):
        self._dat(a1=True, a2=True, a3=True)
        self.assertTrue(R._party_chet_het(self.PARTY))

    def test_mot_dua_con_song_thi_KHONG_thua(self):
        self._dat(a1=True, a2=True, a3=False)
        self.assertFalse(R._party_chet_het(self.PARTY))

    def test_khong_ai_chet_thi_KHONG_thua(self):
        self._dat(a1=False, a2=False, a3=False)
        self.assertFalse(R._party_chet_het(self.PARTY))

    def test_khong_con_acc_nao_chay_thi_KHONG_ket_luan(self):
        self.assertFalse(R._party_chet_het(self.PARTY))

    def test_acc_TAT_khong_tinh_vao(self):
        self._dat(a1=True, a2=True, a3=False)
        R.account_clients["a3"].running = False
        self.assertTrue(R._party_chet_het(self.PARTY))

    def test_KHONG_dung_party_defeated_cua_allies(self):
        """`allies` rong -> `bool(known) and alive == 0` tra False = 'khong thua'."""
        src = _doc("run_party_digioi.py")
        i = src.find("def _party_chet_het(")
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        ma = than[than.find('"""', than.find('"""') + 3):]      # bo docstring
        self.assertNotIn("party_defeated", ma)
        self.assertIn("chet_tran_nay", ma)


class TestClientTuChotMinhChet(unittest.TestCase):
    def setUp(self):
        self.src = _doc("bot", "client.py")
        i = self.src.find("def _chot_minh_chet(")
        self.assertGreater(i, 0, "client khong tu chot 'minh da chet'")
        self.than = self.src[i:self.src.find(chr(10) + "    def ", i + 10)]

    def test_doc_HP_cua_CHINH_MINH(self):
        self.assertIn('getattr(st, "char", None)', self.than)
        self.assertIn("hp_max", self.than)

    def test_khong_nem_khi_client_chua_co_state(self):
        """Ham nay nam tren duong NONG (_dispatch) - nem la chet ca luong doc goi."""
        import bot.client as CL
        c = CL.GameClient.__new__(CL.GameClient)
        c._chot_minh_chet(0x17)          # khong co `state` -> phai im lang

    def test_xoa_dau_khi_vao_tran_MOI(self):
        self.assertIn("protocol.OP_BATTLE_START", self.than)
        self.assertIn("self.chet_tran_nay = False", self.than)

    def test_chot_LIEN_TUC_o_dispatch(self):
        """Chot sau tran la mat dau vet (server hoi/hoi sinh)."""
        i = self.src.find("def _dispatch(")
        self.assertIn("self._chot_minh_chet(opcode)", self.src[i:i + 400])


class TestNoiDayVaoLuongDanh(unittest.TestCase):
    def test_lost_check_co_them_ca_party_chet(self):
        src = _doc("run_party_digioi.py")
        i = src.find("start_floor_crawl(")
        khoi = src[i:i + 400]
        self.assertIn("_party_chet_het(pidx)", khoi)
        self.assertIn("_party_left_tower(pidx, ev)", khoi, "khong duoc bo duong cu")


class TestHetDuongKhongDungIm(unittest.TestCase):
    PARTY = 6

    def setUp(self):
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)

    def tearDown(self):
        R._party_state.pop(self.PARTY, None)

    def test_het_duong_thi_THOAT(self):
        self.st["2k_ket_qua"] = "het_duong"
        R._dieu_phoi_chot_2k_xong(self.PARTY, self.st, [("a1", _C())])
        self.assertTrue(self.st["event_exit_now"].is_set(),
                        "danh het tang, khong co cong len ma van dung im = an va")

    def test_ket_va_dut_van_KHONG_thoat(self):
        for kq in ("ket", "dut"):
            R._party_state.pop(self.PARTY, None)
            st = R._pstate(self.PARTY)
            st["2k_ket_qua"] = kq
            R._dieu_phoi_chot_2k_xong(self.PARTY, st, [("a1", _C())])
            self.assertFalse(st["event_exit_now"].is_set(), kq)

    def test_floor_crawl_dat_ly_do_het_duong(self):
        fc = _doc("bot", "floor_crawl.py")
        i = fc.find("HET DUONG")
        self.assertGreater(i, 0)
        self.assertIn('ly_do = "het_duong"', fc[i:i + 400])

    def test_ly_do_het_duong_chi_dat_SAU_khi_danh(self):
        fc = _doc("bot", "floor_crawl.py")
        i = fc.find("for idx in _battle_idx(ev, scene):")
        self.assertGreater(fc.find('ly_do = "het_duong"'), i)


class TestAPKGiongPC(unittest.TestCase):
    def test_apk_giong(self):
        for f in ("floor_crawl.py", "client.py", "run_party_digioi.py"):
            apk = _doc("android", "app", "src", "main", "python", "train_bot", f)
            key = {"floor_crawl.py": "het_duong", "client.py": "_chot_minh_chet",
                   "run_party_digioi.py": "_party_chet_het"}[f]
            self.assertIn(key, apk)


if __name__ == "__main__":
    unittest.main()
