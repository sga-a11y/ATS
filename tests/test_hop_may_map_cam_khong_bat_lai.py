"""MAP CAM HOP MAY thi KHONG duoc bat lai - bat lai = DUT KET NOI (ma 47).

Client that kiem TRUOC khi bat (`_lua_dec/Logic/MachineBox.lua:360`, `SetAutoFight`):

    if active then
      if SceneManager.CheckLimit(SceneManager.sceneId, ESceneLimit.NoMachinebox) then
        ShowCenterMessage(string.Get(20340));
        return;                      -- KHONG gui goi
      end

`ESceneLimit.NoMachinebox = 13` (`Logic/SceneManager.lua:23`) - bit trong `sceneDatas[id].limits`.
Va khi nhan `S:065-002 <暫停機關盒>` thi client CHI `MachineBox.SetAutoFight(false)` - no KHONG
BAO GIO tu bat lai. Bot thi tu bat lai, va do la hanh vi bia ra.

Bot khong co bang `limits`, nhung chinh `S:065-002` LA cau tra loi cua server: map nay cam.

Ca that 07/09 party 1 (40NPC, map 10991) - user: "bat dau tran thi leader dis luon":

    21:06:53 [xGAx] HOP MAY bi server DUNG (S:065-002) -> quai se khong vao tran
    21:06:53 [xGAx] -> da bat lai hop may
    21:06:57 [xGAx]   <<nhan 0x34                      (vao tran)
    21:06:57 [xGAx]   <<nhan 0x14 c0910a00000014080003  S:020-008 <事件結束>
    21:06:57 [xGAx] SERVER NGAT KET NOI: ma la 47      (戰鬥未結束事件先結束)

`gamo` (leader party khac) dinh y het 32 giay sau. Bang "goi gan nhat truoc khi rot" chi toan
`<<nhan`, khong mot goi GUI nao - nen thu phat khong phai goi battle luc do, ma la lenh bat-lai
hop may tu 4 giay truoc.
"""
from __future__ import annotations

import io
import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient   # noqa: E402


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


def _goi_dung():
    """`S:065-002 <暫停機關盒>` = 0x41 sub 0x0002."""
    return bytes(7) + b"\x02\x00"


def _gia(map_id=10991):
    """Client THAT (`GameClient.__new__`) chi set nhung truong nhanh nay dung - khong dung lop gia,
    vi `_dispatch` doc nhieu truong khac va lop gia se tra nham kieu."""
    c = GameClient.__new__(GameClient)
    c._label = "gia"
    c.current_map = map_id
    c._machinebox_rearm_at = 0.0
    c._machinebox_pause_sent_at = 0.0
    c._machinebox_map_cam = set()
    c.da_gui = []
    c.machinebox_payload = lambda: bytes(11)
    c.send = lambda op, pl: c.da_gui.append((op, pl))
    # `_dispatch` con di qua vai buoc quan sat chung truoc khi toi nhanh 0x41 - cho chung thanh no-op
    for _ten in ("_chot_minh_chet", "_observe_team_dungeon_packet", "_quan_sat_quai",
                 "_ghi_goi_nhan"):
        setattr(c, _ten, lambda *_a, **_k: None)
    import threading as _th
    c._mob_observer_lock = _th.Lock()
    c._mob_observer = None
    return c


def _nhan(c, pkt=None):
    GameClient._dispatch(c, 0x41, pkt or _goi_dung())


class TestMapCamThiThoiBat(unittest.TestCase):
    def test_lan_dau_van_bat_lai(self):
        """Server co the dung vi ly do khac (khong phai map cam) -> cho thu mot lan."""
        c = _gia()
        _nhan(c)
        self.assertEqual(len(c.da_gui), 1)
        self.assertIn(10991, c._machinebox_map_cam)

    def test_lan_hai_CUNG_map_thi_KHONG_bat(self):
        c = _gia()
        _nhan(c)
        c._machinebox_rearm_at = 0.0        # bo cooldown, chi con luat map cam
        _nhan(c)
        self.assertEqual(len(c.da_gui), 1, "van bat lai o map da biet la cam -> dut ket noi ma 47")

    def test_map_KHAC_van_duoc_thu(self):
        c = _gia()
        _nhan(c)
        c._machinebox_rearm_at = 0.0
        c.current_map = 21836               # bai train binh thuong
        _nhan(c)
        self.assertEqual(len(c.da_gui), 2)

    def test_nho_theo_TUNG_map(self):
        c = _gia()
        _nhan(c)
        c.current_map = 12922
        c._machinebox_rearm_at = 0.0
        _nhan(c)
        self.assertEqual(c._machinebox_map_cam, {10991, 12922})

    def test_chua_biet_map_thi_khong_ghi_nham(self):
        c = _gia(map_id=0)
        _nhan(c)
        self.assertEqual(c._machinebox_map_cam, set())


class TestVienDanCrackClient(unittest.TestCase):
    def test_co_ghi_nguon(self):
        s = _src()
        i = s.find("HOP MAY bi server DUNG (S:065-002)")
        self.assertGreater(i, 0)
        khoi = s[i:i + 2600]
        for m in ("MachineBox.lua", "NoMachinebox", "S:020-008", "ma la 47"):
            self.assertIn(m, khoi, m)

    def test_van_giu_cooldown_30s(self):
        """Bo cooldown thi mot map chua kip vao so cam da bi ban lien tuc."""
        s = _src()
        i = s.find("HOP MAY bi server DUNG (S:065-002)")
        self.assertIn("_machinebox_rearm_at", s[i:i + 2600])
        self.assertIn(">= 30.0", s[i:i + 2600])


if __name__ == "__main__":
    unittest.main()
