"""Roster SERVER noi minh dang o party CUA LEADER MINH -> so dem noi bo sai, KHONG duoc roi.

Nhanh "don party ma" chay khi `is_joined()` (so nho) noi la CHUA vao party. Truoc day no chi loai
tru mot truong hop: party cua CHINH MINH. Party cua LEADER MINH van bi coi la "party la" ->
member tu da minh ra khoi doi vua vao -> leader mat het member -> moi lai -> lai roi: vong vo tan.

Log 31/08 party 7 (19:22:05-30):
    19:22:08 [tttam]  roster SERVER noi minh dang o party cua e3f4e44c -> ROI PARTY DO
    19:22:09 [ttmuoi] ... (y het)
    19:22:10 [ttbay]  ... 19:22:10 [ttnne] ...
    19:22:12 [ttsau]  (LEADER) MAT PARTY giua chung (0/4) -> GOM LAI
    19:22:26 [ttsau]  (LEADER) MAT PARTY giua chung (0/4) -> GOM LAI      <- lap lai
`e3f4e44c` CHINH LA ttsau - leader cua ho.

Su that thuoc ve SERVER: server noi da o trong doi thi la da o trong doi, so nho phai sua theo.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestKhongRoiPartyCuaLeader(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("_ket_party_la = c._doi_truong_dang_ket()")
        self.assertGreater(i, 0, "mat nhanh don party ma")
        self.khoi = s[max(0, i - 1400):i + 2600]
        self.than = re.sub(r"#.*", "", self.khoi)
        self.src = s

    def test_van_loai_tru_party_CUA_CHINH_MINH(self):
        self.assertIn("bytes(_ket_party_la) == bytes(c.self_entity)", self.than)

    def test_LOAI_TRU_them_party_cua_LEADER_MINH(self):
        self.assertIn("bytes(_ket_party_la) == bytes(_chu_ent)", self.than,
                      "khong loai tru -> member tu da minh ra khoi doi cua leader")

    def test_SUA_so_dem_thay_vi_roi(self):
        """Su that thuoc ve server: da o trong doi thi ghi nhan da vao, khong phai roi ra."""
        i = self.than.find("bytes(_ket_party_la) == bytes(_chu_ent)")
        khoi = self.than[i:i + 900]
        self.assertIn("mark_joined(pidx, c.self_entity)", khoi,
                      "khong sua so dem -> vong sau lai vao day, lai xu ly lai")
        self.assertIn("_ket_party_la = None", khoi, "phai bo co party la thi moi khong roi")

    def test_mark_joined_duoc_export(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            cl = fh.read()
        self.assertIn("def mark_joined(party_idx, entity):", cl)
        self.assertNotIn("def _mark_joined(", cl, "con ten cu -> import se hong")
        self.assertIn("mark_joined,", self.src, "coordinator chua import")

    def test_KHONG_tinh_leader_entity_hai_lan(self):
        """`_chu_ent` dung o ca hai cho (nhan dien + gui ID doi truong khi roi)."""
        self.assertEqual(self.than.count("for _u2, _p2, _il2, _ip2 in party_accounts(pidx):"), 1)
        self.assertIn("c.leave_party(leader_entity=_chu_ent)", self.than)


if __name__ == "__main__":
    unittest.main()
