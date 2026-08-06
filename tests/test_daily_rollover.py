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
        self.client.vantieu_req = {"he": "Dia", "doanh": "Huynh"}
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
        self.assertIsNone(self.client.vantieu_req)
        self.assertIsNone(self.client.dungeon_runs_today)
        self.assertEqual(self.client._gift_status, {})
        self.assertEqual(self.client._gift_recv, 0)
        self.assertEqual(self.client.digioi_minutes, 90)
        self.assertEqual(self.client.legion_boss_count, 3)
        self.assertEqual(self.client.legion_boss_next, 9999.0)
        self.assertEqual(self.client.current_map, 20801)
        self.assertEqual(self.client.party_members, [b"member00"])

    def test_online_gift_waits_for_server_state_after_rollover(self):
        with mock.patch.object(client_module, "_save_gift_state"), \
             mock.patch.object(self.client, "send") as send, \
             mock.patch.object(client_module.config, "GIFT_MILESTONES", [10]):
            self.client.reset_daily_counters_if_needed(
                today="2026-07-22", now=1000.0
            )
            self.client._connect_time = 1000.0
            self.client._online_base = 99999.0
            with mock.patch.object(client_module.time, "time", return_value=2000.0):
                self.assertFalse(self.client.claim_online_gifts())
        send.assert_not_called()
        self.assertNotIn(10, self.client.claimed_gifts)


class TestOnlineGiftServerState(unittest.TestCase):
    def setUp(self):
        self.client = GameClient("user", "token")
        self.client._label = "hero"

    def test_parses_online_gift_flags_from_data(self):
        self.assertEqual(
            {k: client_module._load_online_gift_flags()[k] for k in (10, 20, 30, 60, 90, 180)},
            {10: 2, 20: 3, 30: 4, 60: 5, 90: 6, 180: 7},
        )

    def test_does_not_claim_without_server_bitflags_or_online_time(self):
        with mock.patch.object(self.client, "send") as send, \
             mock.patch.object(client_module.config, "GIFT_MILESTONES", [10]), \
             mock.patch.object(client_module.time, "time", return_value=100.0):
            self.client._server_online_seconds = 600
            self.client._server_online_ts = 100.0
            self.assertFalse(self.client.claim_online_gifts())
            self.client._bitflags_loaded = True
            self.client._bitflag_bytes = bytearray([0])
            self.client._server_online_seconds = None
            self.assertFalse(self.client.claim_online_gifts())
        send.assert_not_called()

    def test_claims_first_available_unclaimed_milestone_only(self):
        with mock.patch.object(self.client, "send") as send, \
             mock.patch.object(client_module.config, "GIFT_MILESTONES", [10, 20]), \
             mock.patch.object(client_module.time, "time", return_value=100.0):
            self.client._bitflags_loaded = True
            self.client._bitflag_bytes = bytearray([0])
            self.client._server_online_seconds = 1200
            self.client._server_online_ts = 100.0
            self.assertFalse(self.client.claim_online_gifts())
        send.assert_called_once_with(0x57, b"\x02\x00\x03\x0a\x00\x00\x00\x01")
        self.assertEqual(self.client._online_gift_pending, 10)

    def test_success_response_marks_pending_flag_claimed(self):
        self.client._bitflags_loaded = True
        self.client._bitflag_bytes = bytearray([0])
        self.client._online_gift_pending = 10
        self.client._online_gift_pending_ts = 100.0
        self.client._on_gift(b"\x00" * 7 + b"\x02\x00\x03\x00")
        self.assertTrue(self.client._bitflag_get(2))
        self.assertIn(10, self.client.claimed_gifts)

    def test_already_claimed_flag_skips_to_next_milestone(self):
        with mock.patch.object(self.client, "send") as send, \
             mock.patch.object(client_module.config, "GIFT_MILESTONES", [10, 20]), \
             mock.patch.object(client_module.time, "time", return_value=100.0):
            self.client._bitflags_loaded = True
            self.client._bitflag_bytes = bytearray([0])
            self.client._bitflag_set(2, True)
            self.client._server_online_seconds = 1200
            self.client._server_online_ts = 100.0
            self.assertFalse(self.client.claim_online_gifts())
        send.assert_called_once_with(0x57, b"\x02\x00\x03\x14\x00\x00\x00\x01")


class TestDailyRolloverWiring(unittest.TestCase):
    def test_keepalive_resets_before_claiming_online_gift(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "run_party_digioi.py"), encoding="utf-8") as fh:
            source = fh.read()
        reset_at = source.index("c.reset_daily_counters_if_needed()")
        claim_at = source.index("c.claim_online_gifts()", reset_at)
        self.assertLess(reset_at, claim_at)
        self.assertLess(claim_at - reset_at, 300)


if __name__ == "__main__":
    unittest.main()
