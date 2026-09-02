"""`scene_resume` KHONG duoc gui `0x14 06` khi tran chua giai xong -> server ngat ma 47.

Su co 02/09 (party 3, server trieu_van): 4 acc rot CUNG MOT GIAY 12:05:10, va 11:54:28 them mot
acc nua. **5/5 lan dinh ma 47 deu co `scene_resume` chay ngay truoc do.**

    ma 47 = `戰鬥未結束事件先結束` ("su kien ket thuc khi tran chua xong"), protocal.lua cause 47.
    `0x14 06` = `C:020-006 <事件下一步>` - buoc tiep SU KIEN, khong phai "scene resume" (xem
    KNOWLEDGE muc 7d-EVENT: gui sai luc = server NGAT KET NOI).

Goi cuoi cung acc nhan duoc truoc khi dut:

    12:05:10.853 <<nhan 0x14 c0910a00000014080003     <- 0x14 sub08 = END tran
    12:05:10.853 <<nhan 0x00 c0910e0000000000002f...  <- 23ms sau: ngat, 0x2f = 47

Cho goi o `_theo_leader_sua_pos` DA CO guard `not in_combat()` ma van dinh: END tran vua toi nen
`in_battle` da False, bot gui NGAY, con server thi chua giai xong. Nen guard phai nam TRONG
`scene_resume` (phu ca 4 duong goi) va phai cho het CA `_in_battle_end_grace()` (3s sau ket tran).
"""
from __future__ import annotations

import io
import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient        # noqa: E402


class _Bot:
    scene_resume = GameClient.scene_resume
    _in_battle_end_grace = GameClient._in_battle_end_grace

    def __init__(self, dang_danh=False, con_grace=False):
        self._label = "t"
        self.running = True
        self._need_scene_resume = True
        self._dang_danh = dang_danh
        self.battle_tracker = type("T", (), {"generation": 7})()
        self._battle_end_grace_gen = 7
        self._battle_end_grace_until = time.time() + 3.0 if con_grace else 0.0
        self.goi = []

    def in_combat(self, idle_secs=4.0):
        return self._dang_danh

    def send(self, op, payload):
        self.goi.append((op, payload.hex()))

    @property
    def da_gui_1406(self):
        return ("14", "0600") in [(("%02x" % o), p) for o, p in self.goi]


class TestChoHetTran(unittest.TestCase):
    def test_khong_danh_khong_grace_thi_GUI_binh_thuong(self):
        b = _Bot()
        b.scene_resume(settle=0)
        self.assertEqual([o for o, _p in b.goi], [0x0C, 0x14])
        self.assertTrue(b.da_gui_1406)

    def test_DANG_DANH_thi_KHONG_gui(self):
        """Danh mai khong dut -> qua han 20s thi BO gui (khong gui lieu)."""
        b = _Bot(dang_danh=True)

        def _tat_sau_mot_nhip(idle_secs=4.0):      # rut ngan: coi nhu acc bi stop giua luc cho
            b.running = False
            return True
        b.in_combat = _tat_sau_mot_nhip
        b.scene_resume(settle=0)
        self.assertEqual(b.goi, [], "gui 0x14 06 giua tran -> server ngat ma 47")

    def test_VUA_KET_TRAN_thi_CHO_het_grace_ROI_moi_gui(self):
        """Dung ca hong that: `in_battle` da False nhung server chua giai xong.

        Khong phai BO gui - chi la HOAN lai toi khi het grace (bo han thi member bi keo sang map
        se khong di chuyen duoc nua)."""
        b = _Bot(dang_danh=False)
        b._battle_end_grace_until = time.time() + 0.6
        _t0 = time.time()
        b.scene_resume(settle=0)
        _mat = time.time() - _t0
        self.assertTrue(b.da_gui_1406, "hoan han -> member bi keo sang map se dung im")
        self.assertGreaterEqual(_mat, 0.5, "gui NGAY khi grace chua het -> dung bay ma 47")

    def test_het_grace_thi_gui_lai_binh_thuong(self):
        b = _Bot(dang_danh=False, con_grace=True)
        b._battle_end_grace_until = time.time() - 0.01      # grace da het
        b.scene_resume(settle=0)
        self.assertTrue(b.da_gui_1406)

    def test_grace_cua_TRAN_KHAC_thi_khong_chan(self):
        """`_in_battle_end_grace` chi chan khi CUNG the he tran - tran moi da START thi thoi."""
        b = _Bot(dang_danh=False, con_grace=True)
        b.battle_tracker.generation = 8                     # da sang tran moi
        b.scene_resume(settle=0)
        self.assertTrue(b.da_gui_1406)

    def test_acc_da_STOP_thi_khong_gui(self):
        b = _Bot(dang_danh=True)
        b.running = False
        b.scene_resume(settle=0)
        self.assertEqual(b.goi, [])

    def test_co_need_scene_resume_luon_duoc_ha(self):
        """Ha co ngay dau ham: khong thi vong keepalive goi lai lien tuc."""
        b = _Bot(dang_danh=True)
        b.running = False
        b.scene_resume(settle=0)
        self.assertFalse(b._need_scene_resume)


class TestGuardNamTrongHam(unittest.TestCase):
    """Phai o TRONG `scene_resume` de phu ca 4 duong goi, khong phai chi cho `_theo_leader_sua_pos`."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("    def scene_resume(")
        self.than = s[i:s.find("\n    def ", i + 10)]
        self.src = s

    def test_guard_trong_scene_resume(self):
        self.assertIn("self._in_battle_end_grace()", self.than)
        self.assertIn("self.in_combat(", self.than)

    def test_co_HAN_cho_khong_treo_vo_han(self):
        self.assertIn("time.time() + 20.0", self.than)

    def test_qua_han_thi_BO_gui_chu_khong_gui_lieu(self):
        i = self.than.find("scene_resume: cho het tran qua 20s")
        self.assertGreater(i, 0, "khong log ly do -> lan sau khong lan ra duoc")
        self.assertIn("return", self.than[i:i + 260])

    def test_van_giu_guard_cu_o_theo_leader(self):
        """Guard cu ngan luon viec goi ham (re hon); giu ca hai."""
        self.assertIn("and not self.in_combat(idle_secs=1.5)", self.src)


if __name__ == "__main__":
    unittest.main()
