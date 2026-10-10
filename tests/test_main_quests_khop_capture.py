# -*- coding: utf-8 -*-
"""main_quests.json (sinh tu Eve.emg bang tools/crack_eve_quest.py) phai KHOP 8 capture Cu Thu.

8 capture `captures/cs1_<id>_*.pcap` (03/10) la bang chung duy nhat ve hanh vi server; data sinh tu
Eve.emg ma lech capture o bat ky cho nao (cho nhan, NPC/cua, ma chon, buoc tra quest) nghia la parse
sai -> bot se kich hoat sai su kien / chon sai ma (server NGAT KET NOI). Test do sua TOOL, khong sua
ky vong. Chi tiet: documents/QUEST_CHINH_TUYEN.md, KNOWLEDGE.md muc "NHIEM VU (Mark)".
"""
from __future__ import annotations

import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (scene, kieu, idx, chon) do duoc tu capture. Buoc khong co o day = capture khong di qua rieng.
NHAN = {
    10324: (13243, "npc", 1, []), 10326: (11021, "npc", 4, [30]), 10328: (56501, "cua", 4, [30]),
    10360: (55003, "npc", 2, [30]), 10384: (19011, "npc", 1, []), 10528: (18001, "npc", 4, []),
    10564: (56101, "npc", 1, [30]), 10806: (19176, "npc", 1, []),
}
BUOC = {
    10324: {1: (13022, "npc", 2, []), 2: (13513, "cua", 5, []), 3: (13519, "cua", 2, [30]),
            4: (13519, "cua", 3, [])},
    10326: {1: (58000, "cua", 2, [])},
    10328: {1: (56517, "cua", 2, []), 3: (56501, "cua", 5, [])},
    # B3 capture chon 31 (danh boss, nhay +3); data cho 30 cung len buoc KHONG danh -> bot chon 30
    10360: {1: (57501, "cua", 6, []), 2: (57511, "cua", 2, []), 3: (57511, "cua", 3, [30]),
            6: (55003, "npc", 2, [])},
    10384: {1: (19174, "npc", 1, []), 2: (19506, "npc", 2, []), 3: (19174, "npc", 1, [])},
    10528: {1: (18301, "npc", 4, [30]), 2: (18506, "npc", 1, [30]), 3: (18506, "npc", 2, []),
            4: (18301, "npc", 4, [])},
    10564: {1: (56528, "npc", 1, []), 4: (56101, "npc", 1, [])},
    # B1 capture CO chon 30 nhung do la cau hoi cua su kien KHAC tren cung NPC (quest 10600) ->
    # duong cua 10806 khong chon; kiem bang_chon o test_10806_b1_npc_hai_su_kien
    10806: {1: (19175, "npc", 1, []), 2: (19525, "npc", 1, []), 3: (19175, "npc", 1, [])},
}
# bitId co xong (capture: `0x18 05` bat co) - KNOWLEDGE.md
BIT = {10324: 174, 10326: 175, 10328: 176, 10360: 192, 10384: 204, 10528: 280, 10564: 298,
       10806: 428}


def _load():
    with open(os.path.join(ROOT, "main_quests.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    return d, {**d["phu_tuyen"], **d["huong_dan"], **d["chinh_tuyen"]}


class TestMainQuestsKhopCapture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d, cls.q = _load()

    def test_co_hai_chuoi(self):
        self.assertEqual(set(self.d), {"chinh_tuyen", "huong_dan", "phu_tuyen"})
        self.assertGreater(len(self.d["chinh_tuyen"]), 300)
        self.assertGreater(len(self.d["phu_tuyen"]), 300)

    def test_cho_nhan_khop_capture(self):
        for mid, (scene, kieu, idx, chon) in NHAN.items():
            ds = [(u["scene"], u["kieu"], u["idx"], u["chon"]) for u in self.q[str(mid)]["nhan"]]
            self.assertIn((scene, kieu, idx, chon), ds, "quest %d nhan" % mid)

    def test_buoc_khop_capture(self):
        for mid, buoc in BUOC.items():
            steps = self.q[str(mid)]["steps"]
            for n, (scene, kieu, idx, chon) in buoc.items():
                s = steps[str(n)]
                self.assertFalse(s.get("thieu"), "quest %d buoc %d thieu" % (mid, n))
                self.assertEqual((s["scene"], s["kieu"], s["idx"], s["chon"]),
                                 (scene, kieu, idx, chon), "quest %d buoc %d" % (mid, n))

    def test_10528_b2_cham_cua_3_truoc(self):
        # capture: client cham cua 3 (3651,365) -> server hien NPC 1 -> moi noi chuyen duoc
        truoc = self.q["10528"]["steps"]["2"]["truoc"]
        self.assertEqual([t["cua"] for t in truoc], [3])

    def test_buoc_co_boss_danh_dau_tran(self):
        for mid, n in ((10384, 2), (10528, 2), (10806, 2), (10326, 1), (10324, 4)):
            s = self.q[str(mid)]["steps"][str(n)]
            self.assertTrue(s["tran"], "quest %d buoc %d co boss" % (mid, n))
            self.assertGreater(s["boss"], 0)
        self.assertEqual(self.q["10384"]["steps"]["2"]["boss"], 90)   # Thuong Cu Thu lv90

    def test_10806_b1_npc_hai_su_kien(self):
        # NPC 1 o 19175 mang su kien 2 (quest 10600) + 4 (10806); capture: server hoi "nhan 10600?"
        # (surface 2) -> client chon 30 -> 10806 len buoc 2 KEM 10600 +1
        self.assertEqual(self.q["10806"]["steps"]["1"]["chon_map"].get("2"), 30)

    def test_moi_cau_chon_capture_co_trong_bang(self):
        # Moi ma chon cua capture phai tra duoc qua chon_map (bot tra loi theo surface server gui)
        for mid, buoc in BUOC.items():
            for n, (_sc, _k, _i, chon) in buoc.items():
                bang = self.q[str(mid)]["steps"][str(n)]["chon_map"]
                for ma in chon:
                    self.assertIn(ma, bang.values(), "quest %d buoc %d" % (mid, n))

    def test_bit_xong_khop_capture(self):
        for mid, bit in BIT.items():
            self.assertEqual(self.q[str(mid)]["bit"], bit, "quest %d" % mid)

    def test_dieu_kien_nhan_10384(self):
        # NPC 1 Thon Vong Binh: cap > 19, co 10401 xong, chua nhan 10384, chua xong 10385
        dk = [u["dk"] for u in self.q["10384"]["nhan"] if u["scene"] == 19011][0]
        self.assertIn([7, 0, 1, 2, 19], dk)
        self.assertIn([2, 10401, 3, 5, 1], dk)
        self.assertIn([2, 10384, 2, 0, 0], dk)
        self.assertIn([2, 10385, 3, 5, 0], dk)


if __name__ == "__main__":
    unittest.main()
