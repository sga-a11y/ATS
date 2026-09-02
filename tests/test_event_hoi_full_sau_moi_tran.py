"""Di event nao cung vay: HET TRAN la hoi FULL HP/SP ca char lan pet roi moi danh tiep.

User chot 02/09: "co rule di event, het tran thi phai hoi full HP SP roi moi danh tiep chu" va
"di event nao cung vay, cu het tran la hoi full ca char va pet roi moi danh tiep".

Truoc do 2K (`floor_crawl`) va Loan dau (`loandau`) da dung luat, RIENG 40NPC thi khong: tu commit
ee515db (03/08) viec hoi mau bi gac sau `casualties = alive < total` de tiet kiem ~5s/tran bang
duong tat CHOOSE_YES+advance. Hai cai sai:
  1. Con song nhung THOI THOP thi khong hoi.
  2. `alive/total` doc tu `state.allies` chi dem char cua chinh leader.

Hau qua that (party 42, luu_bi, 02/09): het tran 10 leader con 27/796 HP -> `casualties=False` ->
vao thang tran 11 -> char + pet chet sach tu luot 4 -> thua.
"""
from __future__ import annotations

import io
import os
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import npc40                    # noqa: E402


def _doc(p):
    with io.open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return fh.read()


class _Client:
    """Client gia: moi lan bam ADVANCE sau mot CHOOSE_YES thi coi nhu tran moi bat dau."""

    def __init__(self):
        self.running = True
        self.sent = []
        self.ready = 0
        self._label = "t"
        self._battle_start_seq = 0
        self._npc40_prompt_seq = 0
        self._npc40_last_defeated = False
        self._npc40_last_alive = 10
        self._npc40_last_total = 10
        self._npc40_last_dialog = ""
        self._npc40_done = False
        self._npc40_bo_thuong = False

    def navigate_to(self, x, y, flee=True):
        return True

    def _wait_combat_clear(self, idle=1.0, cap=20.0):
        return True

    def rearm_ready(self):
        self.ready += 1

    def send(self, opcode, payload):
        self.sent.append((opcode, payload))
        yes = sum(p == npc40.CHOOSE_YES for _o, p in self.sent)
        if payload == npc40.ADVANCE and yes > self._battle_start_seq:
            self._battle_start_seq += 1


def _gia(**kw):
    """Doi tuong toi gian de thu `_da_thua_that`."""
    return type("X", (), kw)()


def _chay(client, so_tran, heals, sleep_extra=None):
    """Chay run_loop cho `so_tran` tran roi het gio event -> thoat."""
    def _sleep(_s):
        if client._battle_start_seq > client._npc40_prompt_seq:
            client._npc40_prompt_seq += 1
        if sleep_extra is not None:
            sleep_extra()

    cua_so = [True] * (so_tran * 4) + [False] * 8
    with mock.patch.object(npc40, "in_event_window", side_effect=cua_so):
        return npc40.run_loop(
            client, (910, 290), threading.Event(), lambda: None,
            before_repeat=lambda: heals.append(len(client.sent)),
            sleep_fn=_sleep, poll_interval=0, max_advances=4,
        )


class TestNpc40HoiSauMoiTran(unittest.TestCase):
    def test_THANG_tran_van_phai_hoi(self):
        """Loi that cua P42: thang tran nhung con 27/796 HP ma khong hoi."""
        c = _Client()
        c._npc40_last_alive = c._npc40_last_total = 10   # khong ai chet
        heals = []
        _chay(c, 3, heals)
        self.assertGreaterEqual(len(heals), 3, "thang tran thi khong hoi mau")

    def test_khong_con_gac_sau_casualties(self):
        src = _doc("bot/npc40.py")
        self.assertNotIn("casualties = total > 0 and alive < total", src)
        self.assertNotIn("if casualties:", src)

    def test_duong_tat_KHONG_hoi_mau_da_bi_xoa(self):
        """`_confirm_repeat_battle` = CHOOSE_YES + advance thang, bo qua hoi mau -> khong duoc ton tai."""
        self.assertFalse(hasattr(npc40, "_confirm_repeat_battle"))
        self.assertNotIn("_confirm_repeat_battle", _doc("bot/npc40.py"))

    def test_DONG_DIALOG_truoc_khi_hoi(self):
        """Dung item luc prompt con mo -> server tra `08 0001` roi KICK."""
        c = _Client()
        heals = []
        _chay(c, 1, heals)
        self.assertTrue(heals)
        truoc = [p for _o, p in c.sent[:heals[0]]]
        self.assertEqual(truoc[-3:], [npc40.CHOOSE_NO, npc40.ADVANCE, npc40.ADVANCE])

    def test_MO_LAI_NPC_sau_khi_hoi(self):
        c = _Client()
        heals = []
        _chay(c, 1, heals)
        sau = c.sent[heals[0]:]
        self.assertIn((npc40.OP_EVENT, npc40.OPEN_EVENT), sau)
        self.assertIn((npc40.OP_DIALOG, npc40.OPEN_NPC), sau)


class TestThuaSachKhongTreo(unittest.TestCase):
    """Thua sach -> server KHONG gui prompt "danh tiep?" -> phai coi la thua, khong duoc treo."""

    def test_timeout_cho_prompt_thi_BAO_PARTY_va_thoat(self):
        c = _Client()
        losses = []
        # khong bao gio tang prompt_seq -> mo phong tran thua sach
        with mock.patch.object(npc40, "in_event_window", return_value=True):
            ok = npc40.run_loop(
                c, (910, 290), threading.Event(), lambda: losses.append(True),
                before_repeat=None, sleep_fn=lambda _s: None,
                poll_interval=0, max_advances=4,
            )
        self.assertTrue(ok, "phai di duong ket thuc chu khong tra False cam")
        self.assertEqual(losses, [True], "on_loss() khong duoc goi -> member dung cho mai")
        self.assertTrue(c._npc40_done, "khong bat co di doi thuong")

    def test_chua_toi_22h_thi_danh_dau_BO_THUONG(self):
        c = _Client()
        with mock.patch.object(npc40, "in_event_window", return_value=True):
            npc40.run_loop(c, (910, 290), threading.Event(), lambda: None,
                           sleep_fn=lambda _s: None, poll_interval=0, max_advances=4)
        self.assertTrue(c._npc40_bo_thuong)

    def test_ROT_giua_chung_thi_KHONG_phai_thua(self):
        """`_wait_counter` tra False ca khi HET GIO CHO lan khi acc ROT/Stop (`not _active`).

        Coi nham "rot" la "thua" thi leader dat `_npc40_done` -> coordinator bat `go_claim` -> CA 4
        member dang khoe manh lap tuc bo chay di doi thuong du chua danh tran nao.
        Da xay ra that (party 6 tao_thao 02/09): leader bi kick ma 47 luc 21:43:26 (17s sau khi vao
        tran DAU), 21:43:31 ca 4 member sang map 12003; leader login lai luc 21:43:35 tu chon kenh 10
        trong khi member con o kenh 5 -> user thay la "party loan kenh".
        """
        c = _Client()
        losses = []

        def _rot(_s):
            c.running = False       # mo phong bi kick giua chung

        with mock.patch.object(npc40, "in_event_window", return_value=True):
            ok = npc40.run_loop(
                c, (910, 290), threading.Event(), lambda: losses.append(True),
                sleep_fn=_rot, poll_interval=0, max_advances=4,
            )
        self.assertFalse(ok, "rot ma bao da xu ly xong -> supervisor khong login lai")
        self.assertEqual(losses, [], "ROT bi coi la THUA -> ca party bo chay")
        self.assertFalse(c._npc40_done, "dat co di doi thuong du chua danh xong")

    def test_GUI_Stop_cung_KHONG_phai_thua(self):
        c = _Client()
        losses = []
        stop = threading.Event()
        with mock.patch.object(npc40, "in_event_window", return_value=True):
            ok = npc40.run_loop(
                c, (910, 290), stop, lambda: losses.append(True),
                sleep_fn=lambda _s: stop.set(), poll_interval=0, max_advances=4,
            )
        self.assertFalse(ok)
        self.assertEqual(losses, [])
        self.assertFalse(c._npc40_done)

    def test_MAT_PROMPT_ma_quan_nha_CON_SONG_thi_THU_LAI_chu_khong_bo(self):
        """Mot lan hut goi khong duoc lam ca party mat phan con lai cua event."""
        c = _Client()
        c._npc40_hp_snap = (False, 5, 5)     # con song -> KHONG co bang chung thua
        losses = []
        with mock.patch.object(npc40, "in_event_window", return_value=True):
            npc40.run_loop(c, (910, 290), threading.Event(), lambda: losses.append(True),
                           sleep_fn=lambda _s: None, poll_interval=0, max_advances=4)
        mo_lai = sum(p == npc40.OPEN_EVENT for _o, p in c.sent)
        self.assertGreater(mo_lai, 1, "khong he thu mo lai NPC")
        self.assertLessEqual(mo_lai, npc40.MAX_THU_LAI + 2, "thu lai vo han")
        self.assertEqual(losses, [True], "thu het so lan van hong thi phai bao party")

    def test_MAT_PROMPT_va_quan_nha_NAM_HET_thi_THUA_ngay(self):
        c = _Client()
        c._npc40_hp_snap = (True, 0, 5)      # CO bang chung thua
        losses = []
        with mock.patch.object(npc40, "in_event_window", return_value=True):
            ok = npc40.run_loop(c, (910, 290), threading.Event(), lambda: losses.append(True),
                                sleep_fn=lambda _s: None, poll_interval=0, max_advances=4)
        self.assertTrue(ok)
        self.assertEqual(losses, [True])
        self.assertEqual(sum(p == npc40.OPEN_EVENT for _o, p in c.sent), 1,
                         "da co bang chung thua roi con mo lai NPC")

    def test_bang_chung_thua_doc_tu_chot_HP(self):
        self.assertTrue(npc40._da_thua_that(_gia(_npc40_hp_snap=(True, 0, 5))))
        self.assertFalse(npc40._da_thua_that(_gia(_npc40_hp_snap=(False, 3, 5))))
        self.assertFalse(npc40._da_thua_that(_gia(_npc40_hp_snap=None)),
                         "chua doc duoc HP lan nao -> KHONG duoc doan la thua")
        self.assertFalse(npc40._da_thua_that(_gia()))

    def test_cho_du_LAU_cho_mot_tran_binh_thuong(self):
        """1 tran 40NPC chay ~100s (P42: tran 10 tu 20:31:42 den 20:33:15) -> nguong phai > the."""
        self.assertGreaterEqual(npc40.CHECK_CHO_PROMPT * 0.4, 150)


class TestCacEventKhacVanDungLuat(unittest.TestCase):
    def test_2K_hoi_sau_moi_tran(self):
        src = _doc("bot/floor_crawl.py")
        i = src.find("if heal_party is not None:")
        self.assertGreater(i, 0)
        self.assertIn("client.heal_full(force=True)", src[i:i + 260])

    def test_loan_dau_hoi_giua_hai_tran(self):
        self.assertIn("before_repeat()", _doc("bot/loandau.py"))

    def test_ham_hoi_la_FULL_ca_char_lan_pet(self):
        src = _doc("bot/client.py")
        i = src.find("def heal_npc40_between_battles")
        self.assertIn("self.heal_full(force=True)", src[i:i + 900])


class TestVongLapChetAmThamThiBaoParty(unittest.TestCase):
    """run_loop chay trong thread -> tri tra ve bi vut di. Moi loi ra that bai phai goi on_loss."""

    def test_start_npc40_loop_boc_run_loop(self):
        src = _doc("bot/client.py")
        i = src.find("def start_npc40_loop")
        khoi = src[i:i + 1800]
        self.assertIn("ok = npc40.run_loop(", khoi)
        self.assertIn("if not ok and self.running", khoi)
        self.assertIn("on_loss()", khoi)
        self.assertNotIn("target=npc40.run_loop", khoi,
                         "van goi thang run_loop -> that bai la thread chet am tham")


if __name__ == "__main__":
    unittest.main()
