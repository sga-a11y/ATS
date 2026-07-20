import json
import os
import tempfile
import unittest
from unittest import mock

from bot import client as client_module
from bot.client import GameClient


class TestGiftStateV2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "gift_state.json")
        self.file_patch = mock.patch.object(client_module, "_GIFT_FILE", self.path)
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)

    def write(self, payload):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_legacy_record_is_ignored(self):
        self.write({"hero:2026-07-21": {
            "online_sec": 21422.7,
            "claimed": [10, 20, 30, 60, 90, 180],
        }})
        self.assertEqual(
            client_module._load_gift_state("hero", today="2026-07-21"),
            {"online_sec": 0.0, "claimed": set()},
        )

    def test_v2_record_is_loaded(self):
        self.write({"hero:2026-07-21": {
            "version": 2,
            "online_sec": 620.0,
            "claimed": [10],
        }})
        self.assertEqual(
            client_module._load_gift_state("hero", today="2026-07-21"),
            {"online_sec": 620.0, "claimed": {10}},
        )

    def test_save_writes_v2_for_explicit_day(self):
        client_module._save_gift_state(
            "hero", 12.5, {10}, today="2026-07-22"
        )
        with open(self.path, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved, {"hero:2026-07-22": {
            "version": 2,
            "online_sec": 12.5,
            "claimed": [10],
        }})


class TestDailyRollover(unittest.TestCase):
    def setUp(self):
        self.client = GameClient("user", "token")
        self.client._label = "hero"
        self.client._daily_date = "2026-07-21"
        self.client._connect_time = 100.0
        self.client._online_base = 7200.0
        self.client.claimed_gifts = {10, 20, 30, 60, 90, 180}
        self.client._quest_cells = {1, 2, 3}
        self.client._claimed_lines = {1, 4}
        self.client._claimed_loaded = True
        self.client.vantieu_started = 3
        self.client.vantieu_slots = {1: {"end": 1.0, "pet": 2}}
        self.client.vantieu_req_code = "aabbcc"
        self.client.dungeon_runs_today = 2
        self.client._gift_status = {1: 0}
        self.client._gift_recv = 4
        self.client.digioi_minutes = 90
        self.client.legion_boss_count = 3
        self.client.legion_boss_next = 9999.0
        self.client.current_map = 20801
        self.client.party_members = [b"member00"]

    def test_same_day_is_noop(self):
        before = dict(self.client.__dict__)
        with mock.patch.object(client_module, "_save_gift_state") as save:
            self.assertFalse(self.client.reset_daily_counters_if_needed(
                today="2026-07-21", now=500.0
            ))
        save.assert_not_called()
        self.assertEqual(self.client.__dict__, before)

    def test_new_day_resets_only_safe_daily_state_once(self):
        with mock.patch.object(client_module, "_save_gift_state") as save:
            self.assertTrue(self.client.reset_daily_counters_if_needed(
                today="2026-07-22", now=500.0
            ))
            self.assertFalse(self.client.reset_daily_counters_if_needed(
                today="2026-07-22", now=501.0
            ))
        save.assert_called_once_with("hero", 0.0, set(), today="2026-07-22")
        self.assertEqual(self.client._daily_date, "2026-07-22")
        self.assertEqual(self.client._connect_time, 500.0)
        self.assertEqual(self.client._online_base, 0.0)
        self.assertEqual(self.client.claimed_gifts, set())
        self.assertEqual(self.client._quest_cells, set())
        self.assertEqual(self.client._claimed_lines, set())
        self.assertFalse(self.client._claimed_loaded)
        self.assertIsNone(self.client.vantieu_started)
        self.assertEqual(self.client.vantieu_slots, {})
        self.assertIsNone(self.client.vantieu_req_code)
        self.assertIsNone(self.client.dungeon_runs_today)
        self.assertEqual(self.client._gift_status, {})
        self.assertEqual(self.client._gift_recv, 0)
        self.assertEqual(self.client.digioi_minutes, 90)
        self.assertEqual(self.client.legion_boss_count, 3)
        self.assertEqual(self.client.legion_boss_next, 9999.0)
        self.assertEqual(self.client.current_map, 20801)
        self.assertEqual(self.client.party_members, [b"member00"])

    def test_online_gift_starts_again_from_zero_after_rollover(self):
        with mock.patch.object(client_module, "_save_gift_state"), \
             mock.patch.object(self.client, "send") as send, \
             mock.patch.object(client_module.config, "GIFT_MILESTONES", [10]):
            self.client.reset_daily_counters_if_needed(
                today="2026-07-22", now=1000.0
            )
            with mock.patch.object(client_module.time, "time", return_value=1599.0):
                self.assertFalse(self.client.claim_online_gifts())
            send.assert_not_called()
            with mock.patch.object(client_module.time, "time", return_value=1600.0):
                self.assertTrue(self.client.claim_online_gifts())
        send.assert_called_once()
        self.assertIn(10, self.client.claimed_gifts)


if __name__ == "__main__":
    unittest.main()
