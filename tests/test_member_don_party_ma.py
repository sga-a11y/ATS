"""Member ket ngoai party phai DON PARTY MA truoc khi retry.

Server KHONG gui loi moi cho nguoi DANG O PARTY. Ma bot chi gui goi roi party khi TRANG THAI
LOCAL noi minh dang o party (`in_party` trong do_channel_sync doc party_members/party_leader).
Local rong + server con giu party cu = KET VINH VIEN: leader moi hoai, member khong bao gio
nhan duoc goi moi nao.

Party 15 (27/08): goi roster CUOI CUNG luc 08:48:44; sau do 35 phut leader gui hang tram luot
moi, 2/4 member (trubay, trumuoi) khong nhan duoc mot goi moi nao, 2 con lai accept ma party
van khong hinh thanh (`da join=2 | roster server=0 nguoi`).
"""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()




class TestLogChanDoan(unittest.TestCase):
    """Party 15 ton 2 vong dieu tra vi log khong noi leader dang dem duoc may nguoi."""

    def test_vong_moi_in_so_dem_va_roster(self):
        s = _doc("bot", "client.py")
        i = s.find("moi %d member theo entity")
        self.assertGreater(i, 0)
        khoi = s[i:i + 500]
        self.assertIn("da join=%d", khoi)
        self.assertIn("roster server=%d", khoi)


if __name__ == "__main__":
    unittest.main()
