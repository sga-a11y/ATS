"""BI KEO SANG MAP KHAC giua duong -> HUY chuyen di, khong duoc di tiep toi dich cua map cu.

Dich `(x,y)` la toa do cua MAP CU; sang map moi no la mot cho hoan toan khac -> lenh move dau
tien nhay ca nghin don vi -> `SERVER NGAT KET NOI: di chuyen QUA XA (ma 14)`.

Client huy thang (`_lua_dec/Logic/SceneManager.lua:468-474`):
    if Role.player ~= nil and stopMove then Role.player:StopMove() end
    if CGTimer.ContainsListener(MoveController.SendRolePosition) and stopMove then
      CGTimer.RemoveListener(MoveController.SendRolePosition) end
=> vua HUY dich dang di, vua GO luon bo gui move.

Log 31/08 party 1 (14:05:42-14:07:01) - mot lan bi keo map lam hong ca vong train:
    14:05:42 [minh]       (member) sync kenh: ve diem tap ket (3170, 530) (bo chay)   [map 21814]
    14:05:42 [minhminhmq] bi keo sang map 12003 (khong tu qua cong) -> chay scene_resume truoc khi di
    14:05:45 [minhminhmq] request scene khong co self-spawn moi -> dung pos hien tai (502, 495)
    14:05:45 [minhminhmq] SERVER NGAT KET NOI: di chuyen QUA XA (ma 14)
    14:05:58 [minhminhmq] RESYNC pos tu 0x03 = (502,495) map=12003
    14:06:43 [xGAx] sync kenh/map: acc con lai o MAP KHAC {'minhminhmq': 12003} (can 21814)
    14:07:01 >>> PARTY 1: thanh xuat phat = Tương Dương  (ca party ve thanh gom lai)
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


class TestDoiMapGiuaDuong(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("    def navigate_to(")
        self.assertGreater(i, 0)
        j = s.find("\n    def follow_path(", i)
        self.assertGreater(j, i)
        self.khoi = s[i:j]
        self.than = re.sub(r"#.*", "", self.khoi)

    def test_co_chot_doi_map(self):
        self.assertIn("_map_bat_dau = self.current_map", self.than,
                      "khong nho map luc xuat phat thi khong biet duong nao ma so")
        self.assertIn("def _da_doi_map():", self.than)

    def test_chot_o_CA_BA_vong(self):
        """Ba cho co gui move: vong waypoint chinh, vong xac nhan, vong di bu."""
        self.assertEqual(self.than.count("if _da_doi_map():"), 3,
                         "thieu mot vong = van co duong gui move toi dich cua map cu")

    def test_HUY_chu_khong_di_tiep(self):
        i = self.than.find("def _da_doi_map():")
        for m in re.finditer(r"if _da_doi_map\(\):\n(\s+)(\S.*)", self.than[i:]):
            self.assertEqual(m.group(2).strip(), "return False",
                             "phai HUY han chuyen di, khong duoc chi log roi di tiep")

    def test_map_chua_biet_thi_KHONG_huy_oan(self):
        """`current_map` co luc None (vua login / vua qua cong) - coi do la 'doi map' thi huy oan
        moi chuyen di."""
        i = self.than.find("def _da_doi_map():")
        khoi = self.than[i:i + 400]
        self.assertIn("is None", khoi)
        self.assertIn("return False", khoi)

    def test_LOG_ro_ly_do(self):
        self.assertIn("DOI MAP giua chung", self.khoi)
        self.assertIn("dich thuoc map cu", self.khoi)


if __name__ == "__main__":
    unittest.main()
