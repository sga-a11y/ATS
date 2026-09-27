"""PET ROI CHUC (S:019-007, het trung thanh) -> bot thoi doi sang con do + bao o man Chu y.

User chot 27/09: pet het trung thanh bi "Roi chuc", khong xuat chien duoc -> khong co doi sang no
nua TRONG PHIEN LOGIN do (login lai tinh lai tu dau); bao "acc xxx pet yyy da bi Roi chuc ko xuat
chien duoc". Goi: `S:019-007 <跟隨武將下野> <<+索引(1) +是否(1)>>` (protocal.lua), `索引` =
followIndex = marker record trong goi 0x0f (protocal.lua:2202).
"""
import os
import sys
import threading
import unittest
from unittest import mock
from types import SimpleNamespace as NS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient   # noqa: E402
with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R    # noqa: E402


def make_client():
    c = GameClient.__new__(GameClient)
    c._label = "t"
    c.running = True
    c.pet_retired = set()
    c._pet_marker_pid = {1: 0xa058, 2: 0xa0db}
    c._pet_switch_fail = {}
    c.pet_faith = {0xa058: 21}
    c.state = NS(active_pet_id=0xa0db, active_pet_confirmed=True, in_battle=False,
                 carried_pets=[(0xa058, "a"), (0xa0db, "b")], battle_config={})
    c.sent = []
    c.send = lambda op, body: c.sent.append((op, body))
    return c


class TestPetRoiChuc(unittest.TestCase):
    def test_parse_goi_roi_chuc(self):
        c = make_client()
        c._on_pet_retire(bytes([1, 1, 2, 0]))
        self.assertEqual(c.pets_roi_chuc(), [0xa058])
        c._on_pet_retire(bytes([1, 0]))       # het roi chuc
        self.assertEqual(c.pets_roi_chuc(), [])

    def test_goi_toi_truoc_0x0f_van_quy_ra_duoc(self):
        c = make_client()
        c._pet_marker_pid = {}
        c._on_pet_retire(bytes([1, 1]))
        self.assertEqual(c.pets_roi_chuc(), [])
        c._pet_marker_pid = {1: 0xa058}      # 0x0f ve sau
        self.assertEqual(c.pets_roi_chuc(), [0xa058])

    def test_switch_pet_khong_gui_lenh_cho_pet_roi_chuc(self):
        c = make_client()
        c._on_pet_retire(bytes([1, 1]))
        self.assertFalse(c.switch_pet(0xa058, wait=0.1))
        self.assertEqual(c.sent, [], "pet roi chuc thi KHONG duoc gui lenh doi")

    def test_client_moi_la_tinh_lai(self):
        c = GameClient.__new__(GameClient)
        GameClient.__init__(c, "u", "tok")
        self.assertEqual(c.pet_retired, set())

    def test_recv_dispatch_goi_0x13_sub07(self):
        src = open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8").read()
        self.assertIn('pkt[7:9] == b"\\x07\\x00":\n            self._on_pet_retire(pkt[9:])', src)

    def test_notify_items_va_bo_qua(self):
        c = make_client()
        c._on_pet_retire(bytes([1, 1]))
        _cu_clients, _cu_pa = dict(R.account_clients), R.party_accounts
        try:
            R.account_clients.clear()
            R.account_clients["acc1"] = c
            R.party_accounts = lambda pidx: [("acc1", "", "", "")]
            items = R.pet_roi_chuc_notify_items(0)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["kind"], "pet_roi_chuc")
            self.assertEqual(items[0]["pid"], str(0xa058))
            R.pet_roi_chuc_notify_skip("acc1", items[0]["pid"])
            self.assertEqual(R.pet_roi_chuc_notify_items(0), [])
        finally:
            R.account_clients.clear()
            R.account_clients.update(_cu_clients)
            R.party_accounts = _cu_pa

    def test_gui_va_apk_hien_dong_chu_y(self):
        g = open(os.path.join(ROOT, "gui.py"), encoding="utf-8").read()
        self.assertIn("pet_roi_chuc_notify_items", g)
        self.assertIn("đã bị Rời chức ko xuất chiến được", g)
        kt = open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot",
                               "android", "MainActivity.kt"), encoding="utf-8").read()
        self.assertIn("petRoiChucNotifyItems", kt)
        self.assertIn("đã bị Rời chức ko xuất chiến được", kt)


if __name__ == "__main__":
    unittest.main()
