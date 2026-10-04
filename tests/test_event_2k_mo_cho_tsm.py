"""2K (Nhi Kieu) mo cho ban TSM tu 04/10/2026 (user: TSM cung co 2K ngay chu nhat, gio nhu VTC).
Event khac van chi VTC - mo nham thi party TSM tele toi map/NPC cua ban khac."""
import json
import os
import unittest

from bot import region

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK_EVENTS = os.path.join(ROOT, "android", "app", "src", "main", "assets", "train_bot_data",
                          "events.json")


def _events(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["events"]


class TestEvent2kMoChoTsm(unittest.TestCase):
    def test_2k_co_ca_vtc_lan_tsm(self):
        ev = _events(os.path.join(ROOT, "events.json"))["nhi_kieu"]
        self.assertTrue(region.co_trong_game(ev, "vtc"))
        self.assertTrue(region.co_trong_game(ev, "tsm"))

    def test_event_khac_van_chi_vtc(self):
        evs = _events(os.path.join(ROOT, "events.json"))
        for key in ("npc_40", "loan_dau"):
            self.assertFalse(region.co_trong_game(evs[key], "tsm"), key)

    def test_party_tsm_mode_2k_khong_bi_ve_stand(self):
        evs = _events(os.path.join(ROOT, "events.json"))
        pc = {"mode": "event", "event_key": "nhi_kieu", "game": "tsm"}
        region.chan_event_sai_game(pc, evs)
        self.assertEqual(pc["mode"], "event")

    def test_apk_cung_mo(self):
        self.assertEqual(_events(APK_EVENTS)["nhi_kieu"].get("games"), ["vtc", "tsm"])


if __name__ == "__main__":
    unittest.main()
