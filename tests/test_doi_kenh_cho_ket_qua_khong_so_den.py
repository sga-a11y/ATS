"""DOI KENH: gui lenh thi PHAI CHO ket qua server tra ve; chon kenh KHONG dung so den.

Ca that 27/09 party 1 Di Gioi (user: "bao chuyen kenh 64 that bai, server day, nhung kenh do chi
8/20 nguoi"). `S:007-002 <換分區結果>` chi mang MOT byte ma, KHONG co so kenh. Bot cho 4s roi gui
lenh moi, nen tra loi TRE cua lenh cu (kenh day that) roi vao lenh moi va bi dan nhan kenh moi:

    16:41:38 [nanam] Chuyen kenh -> 64 (cho server xac nhan, lan 1/1)
    16:41:42 [nanam] Doi kenh 64 TIMEOUT sau 4.0s
    16:41:42 [nanam] Doi kenh 64 THAT BAI: khu da day nguoi (result=4)     <- tra loi TRE

Do tren log cung ngay: 5005 lan gui lenh moi khi lenh truoc CHUA co tra loi; 1088/2159 lan ACK OK
xong scene lai vao kenh KHAC kenh vua xin. Tra loi p90 = 4s, dung bang nguong timeout cu.

Va so den (ma 4 + timeout -> cam kenh) lam party 1 lat dich 71 lan (46 lan chi vi timeout).
User chot 27/09: "gui lenh doi kenh thi phai cho ket qua server tra ve chu" + "ko can so den, moi
lan chon kenh luon chon kenh it nguoi nhat roi".
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as client_module
from bot.client import GameClient, _PARTY_ENTITIES

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _kq(result):
    return b"\xc0\x91\x0a\x00\x00\x00\x07\x02\x00" + bytes([result])


class TestChoKetQuaDoiKenh(unittest.TestCase):
    def tearDown(self):
        if hasattr(client_module, "_PARTY_CLIENTS"):
            client_module._PARTY_CLIENTS.clear()
        _PARTY_ENTITIES.clear()

    def _game(self):
        g = GameClient("user", "token")
        g._label = "hero"
        g.running = True
        g._note_current_channel(44, "0x0c")
        return g

    def test_cho_ket_qua_du_lau_hon_wait(self):
        """Server tra loi sau 0.3s ma `wait` chi 0.05s -> van phai cho va nhan duoc ket qua."""
        g = self._game()

        def tra_loi_cham(*_):
            def _di():
                time.sleep(0.3)
                g._on_channel_switch_result(_kq(0))
                g._note_current_channel(64, "0x0c")
            threading.Thread(target=_di, daemon=True).start()

        with mock.patch.object(g, "send", side_effect=tra_loi_cham):
            self.assertTrue(g.switch_channel(64, wait=0.05, retries=1))
        self.assertEqual(g.current_channel, 64)

    def test_lenh_truoc_chua_co_ket_qua_thi_KHONG_gui_lenh_moi(self):
        g = self._game()
        with mock.patch.object(client_module, "DOI_KENH_CHO_KQ_SEC", 0.05), \
                mock.patch.object(g, "send") as send:
            self.assertFalse(g.switch_channel(55, wait=0.05, retries=1))
            self.assertFalse(g.switch_channel(64, wait=0.05, retries=1))
        self.assertEqual(send.call_count, 1, "lenh 55 chua co ket qua ma da gui lenh 64")

    def test_tra_loi_TRE_gan_dung_lenh_cu_khong_dan_nhan_lenh_moi(self):
        g = self._game()
        with mock.patch.object(client_module, "DOI_KENH_CHO_KQ_SEC", 0.05), \
                mock.patch.object(g, "send") as send:
            self.assertFalse(g.switch_channel(55, wait=0.05, retries=1))
            g._on_channel_switch_result(_kq(4))          # tra loi TRE cua lenh 55
            self.assertEqual((g._chan_switch_target, g._chan_switch_result), (55, 4))
            send.side_effect = lambda *_: (g._on_channel_switch_result(_kq(0)),
                                           g._note_current_channel(64, "0x0c"))
            self.assertTrue(g.switch_channel(64, wait=0.5, retries=1))
        self.assertEqual(send.call_count, 2)
        self.assertEqual((g._chan_switch_target, g._chan_switch_result), (64, 0))

    def test_lenh_treo_qua_han_thi_duoc_gui_lai(self):
        """Server im lang han (vd xin dung kenh dang o) -> khong duoc ket vinh vien."""
        g = self._game()
        with mock.patch.object(client_module, "DOI_KENH_CHO_KQ_SEC", 0.05), \
                mock.patch.object(g, "send") as send:
            self.assertFalse(g.switch_channel(55, wait=0.05, retries=1))
            g._chan_switch_cho = (55, time.time() - client_module.DOI_KENH_TREO_MAX_SEC - 1)
            g.switch_channel(64, wait=0.05, retries=1)
        self.assertEqual(send.call_count, 2)


class _C:
    def __init__(self, ch, channels, nhan_luc):
        self.running = True
        self.current_map = 10991
        self.current_channel = ch
        self.channels = dict(channels)
        self._ds_kenh_nhan_luc = nhan_luc
        self.party_members = []
        self._chan_switch_result = None
        self._chan_switch_target = None
        self._chan_switch_luc = 0.0
        self.hoi = 0

    def in_combat(self, *_a, **_k):
        return False

    def request_channel_list(self):
        self.hoi += 1


class TestChotKenhKhongSoDen(unittest.TestCase):
    PARTY = 4343
    ACCS = ("a", "b", "c")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "40npc"}}

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        R.config.PARTY_CONFIG = self._pc

    def _song(self, chans, ds, nhan_luc=None):
        nhan_luc = time.time() if nhan_luc is None else nhan_luc
        for u, ch in zip(self.ACCS, chans):
            R.account_clients[u] = _C(ch, ds, nhan_luc)
        return [(u, R.account_clients[u]) for u in self.ACCS]

    def _ket_qua(self, u, target, result, luc=None):
        c = R.account_clients[u]
        c._chan_switch_target, c._chan_switch_result = target, result
        c._chan_switch_luc = time.time() if luc is None else luc

    def test_TIMEOUT_tren_dich_KHONG_lam_lat_dich(self):
        """Party 1 27/09: 46/71 lan lat dich chi vi mot acc timeout tren dich dang giu."""
        song = self._song([5, 5, 9], {5: (10, 20), 9: (5, 20), 7: (1, 20)})
        self.st["kenh_dich"], self.st["kenh_dich_luc"] = 9, time.time()
        self._ket_qua("a", 9, -1)
        self.assertEqual(R._engine_chot_kenh(self.PARTY, self.st, song), 9)

    def test_ma4_CU_hon_danh_sach_thi_tin_danh_sach(self):
        """Khong so den: danh sach MOI noi kenh 9 con cho thi chon 9, du truoc do tung bi ma 4."""
        bay = time.time()
        song = self._song([5, 5, 12], {5: (19, 20), 12: (18, 20), 9: (0, 20)}, nhan_luc=bay)
        self._ket_qua("a", 9, 4, luc=bay - 5)
        self.assertEqual(R._engine_chot_kenh(self.PARTY, self.st, song), 9)

    def test_ma4_MOI_hon_danh_sach_thi_hoi_lai_danh_sach_chu_khong_cam_kenh(self):
        bay = time.time()
        song = self._song([5, 5, 12], {5: (19, 20), 12: (18, 20), 9: (0, 20)}, nhan_luc=bay - 5)
        self._ket_qua("a", 9, 4, luc=bay)
        self.assertIsNone(R._engine_chot_kenh(self.PARTY, self.st, song),
                          "danh sach da CU (server vua bao day) -> chua duoc chot")
        self.assertGreaterEqual(sum(c.hoi for _u, c in song), 1, "phai hoi lai danh sach kenh")

    def test_khong_con_so_den(self):
        self.assertFalse(hasattr(R, "_SoDen"))

    def test_kenh_dong_member_nhat_day_thi_chon_kenh_con_du_cho_nguoi_chuyen(self):
        song = self._song([5, 5, 9], {5: (20, 20), 9: (18, 20)})
        self.assertEqual(R._engine_chot_kenh(self.PARTY, self.st, song), 9)

    def test_kenh_dong_member_nhat_chi_can_cho_cho_nguoi_chua_toi(self):
        song = self._song([5, 5, 9], {5: (19, 20), 9: (18, 20)})
        self.assertEqual(R._engine_chot_kenh(self.PARTY, self.st, song), 5)

    def test_moi_kenh_thieu_cho_thi_cho_danh_sach_moi_roi_tu_tiep_tuc(self):
        song = self._song([5, 5, 9], {5: (20, 20), 9: (19, 20)},
                          nhan_luc=time.time() - 5)
        self.st['kenh_dich'] = 5
        self.st['kenh_dich_luc'] = time.time()
        self._ket_qua('c', 5, 4, luc=time.time() - 1)
        self.assertIsNone(R._engine_chot_kenh(self.PARTY, self.st, song))
        for _, c in song:
            c._ds_kenh_nhan_luc = time.time()
        # Het cho phai xoa dich cu, ca cac nhip sau cung khong chot lai kenh day.
        for _ in range(10):
            self.assertIsNone(R._engine_chot_kenh(self.PARTY, self.st, song))
            self.assertIsNone(self.st['kenh_dich'])
        self.assertEqual(sum(c.hoi for _, c in song), 1)
        for _, c in song:
            c.channels[5] = (19, 20)
            c._ds_kenh_nhan_luc = time.time()
        self.assertEqual(R._engine_chot_kenh(self.PARTY, self.st, song), 5)

    def test_bang_co_kenh_nhung_khong_co_kenh_party_thi_khong_chot_bua(self):
        song = self._song([5, 5, 9], {3: (20, 20)})
        self.assertIsNone(R._engine_chot_kenh(self.PARTY, self.st, song))


if __name__ == "__main__":
    unittest.main()
