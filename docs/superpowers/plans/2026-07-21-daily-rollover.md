# Daily Rollover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reset state theo ngày đúng một lần khi bot treo xuyên 0h, để quà online đếm lại mà không tự di chuyển, relogin hoặc chạy daily.

**Architecture:** `GameClient` giữ `_daily_date` và cung cấp `reset_daily_counters_if_needed(today=None, now=None)`. Keepalive gọi helper này trước `claim_online_gifts()`; state quà dùng schema version 2 để bỏ record cũ đã bị ghi bẩn, còn các counter có thể kích hoạt di chuyển được giữ nguyên.

**Tech Stack:** Python 3, `unittest`, `unittest.mock`, JSON state files, Android Chaquopy mirror.

## Global Constraints

- Rollover không teleport, rời party, relogin, chạy daily quest, gửi vận tiêu hoặc kích hoạt boss.
- Quà online reset về 0 và tiếp tục chạy bằng tick hiện có.
- Không reset cưỡng bức `digioi_minutes`, `legion_boss_count` hoặc `legion_boss_next`.
- Record `gift_state.json` mới dùng `version: 2`; record cũ không version bị bỏ.
- Source PC sửa trước rồi đồng bộ APK bằng `tools/sync_apk_python.py`.
- Không build trước khi test source/dev.
- Không stage runtime cache, PCAP hoặc `aTSBot-drive/`.

---

## File Structure

- `bot/client.py`: schema gift-state, daily marker và reset state an toàn.
- `run_party_digioi.py`: gọi rollover trước online gift trong keepalive.
- `tests/test_daily_rollover.py`: test migration, idempotence, state boundary và mốc quà online.
- `android/app/src/main/python/train_bot/client.py`: mirror client PC.
- `android/app/src/main/python/train_bot/run_party_digioi.py`: mirror coordinator PC.

### Task 1: Versioned gift state and idempotent client rollover

**Files:**
- Modify: `bot/client.py:435-475`
- Modify: `bot/client.py:795-816`
- Modify: `bot/client.py:2024-2047`
- Create: `tests/test_daily_rollover.py`

**Interfaces:**
- Consumes: local date string and epoch timestamp.
- Produces: `_load_gift_state(label, today=None) -> dict`, `_save_gift_state(label, online_sec, claimed, today=None)`, and `GameClient.reset_daily_counters_if_needed(today=None, now=None) -> bool`.

- [x] **Step 1: Write failing gift-state migration tests**

```python
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
            "hero",
            12.5,
            {10},
            today="2026-07-22",
        )
        with open(self.path, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved, {"hero:2026-07-22": {
            "version": 2,
            "online_sec": 12.5,
            "claimed": [10],
        }})
```

- [x] **Step 2: Run migration tests and verify red**

Run: `python -m unittest tests.test_daily_rollover.TestGiftStateV2 -v`

Expected: three tests error/fail because helpers do not accept `today` and do not validate/write version 2.

- [x] **Step 3: Implement versioned state helpers**

Replace the gift key/load/save helpers with:

```python
def _gift_day(today=None) -> str:
    import datetime
    if today is None:
        return datetime.date.today().isoformat()
    return today.isoformat() if hasattr(today, "isoformat") else str(today)


def _gift_key(label: str, today=None) -> str:
    return f"{label}:{_gift_day(today)}"


def _load_gift_state(label: str, today=None) -> dict:
    import json, os
    default = {"online_sec": 0.0, "claimed": set()}
    if not os.path.exists(_GIFT_FILE):
        return default
    try:
        with open(_GIFT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        rec = data.get(_gift_key(label, today))
        if not rec or rec.get("version") != 2:
            return default
        return {
            "online_sec": float(rec.get("online_sec", 0)),
            "claimed": set(rec.get("claimed", [])),
        }
    except Exception:
        return default


def _save_gift_state(label: str, online_sec: float, claimed: set, today=None):
    import json, os
    day = _gift_day(today)
    with _gift_lock:
        data = {}
        if os.path.exists(_GIFT_FILE):
            try:
                with open(_GIFT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data = {k: v for k, v in data.items() if k.endswith(day)}
        data[_gift_key(label, day)] = {
            "version": 2,
            "online_sec": round(online_sec, 1),
            "claimed": sorted(claimed),
        }
        try:
            with open(_GIFT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass
```

- [x] **Step 4: Run migration tests and verify green**

Run: `python -m unittest tests.test_daily_rollover.TestGiftStateV2 -v`

Expected: `Ran 3 tests ... OK`.

- [x] **Step 5: Write failing rollover boundary and online milestone tests**

Append to `tests/test_daily_rollover.py`:

```python
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
                today="2026-07-21",
                now=500.0,
            ))
        save.assert_not_called()
        self.assertEqual(self.client.__dict__, before)

    def test_new_day_resets_only_safe_daily_state_once(self):
        with mock.patch.object(client_module, "_save_gift_state") as save:
            self.assertTrue(self.client.reset_daily_counters_if_needed(
                today="2026-07-22",
                now=500.0,
            ))
            self.assertFalse(self.client.reset_daily_counters_if_needed(
                today="2026-07-22",
                now=501.0,
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
                today="2026-07-22",
                now=1000.0,
            )
            with mock.patch.object(client_module.time, "time", return_value=1599.0):
                self.assertFalse(self.client.claim_online_gifts())
            send.assert_not_called()
            with mock.patch.object(client_module.time, "time", return_value=1600.0):
                self.assertTrue(self.client.claim_online_gifts())
        send.assert_called_once()
        self.assertIn(10, self.client.claimed_gifts)
```

- [x] **Step 6: Run rollover boundary tests and verify red**

Run: `python -m unittest tests.test_daily_rollover.TestDailyRollover -v`

Expected: all three tests error because `reset_daily_counters_if_needed` does not exist.

- [x] **Step 7: Add marker initialization and minimal reset method**

In `GameClient.__init__`, next to online gift fields, add:

```python
self._daily_date = None
```

In `connect()`, use one captured day for marker and load:

```python
self._daily_date = _gift_day()
self._connect_time = time.time()
st = _load_gift_state(self._label, today=self._daily_date)
```

Add immediately before `claim_online_gifts()`:

```python
    def reset_daily_counters_if_needed(self, today=None, now=None) -> bool:
        day = _gift_day(today)
        if self._daily_date == day:
            return False
        previous = self._daily_date
        self._daily_date = day
        self._online_base = 0.0
        self._connect_time = time.time() if now is None else float(now)
        self.claimed_gifts = set()
        self._quest_cells = set()
        self._claimed_lines = set()
        self._claimed_loaded = False
        self.vantieu_started = None
        self.vantieu_slots = {}
        self.vantieu_req_code = None
        self.dungeon_runs_today = None
        self._gift_status = {}
        self._gift_recv = 0
        _save_gift_state(self._label, 0.0, set(), today=day)
        log.info("[%s] DA SANG NGAY MOI %s -> %s: reset daily counters",
                 self._label, previous, day)
        return True
```

- [x] **Step 8: Run rollover boundary tests and verify green**

Run: `python -m unittest tests.test_daily_rollover.TestDailyRollover -v`

Expected: `Ran 3 tests ... OK`.

- [x] **Step 9: Commit client rollover unit**

```bash
git add bot/client.py tests/test_daily_rollover.py
git commit -m "fix: reset safe daily counters after midnight"
```

### Task 2: Keepalive hook, APK parity, and regression

**Files:**
- Modify: `run_party_digioi.py:2065-2069`
- Modify: `tests/test_daily_rollover.py`
- Modify: `android/app/src/main/python/train_bot/client.py`
- Modify: `android/app/src/main/python/train_bot/run_party_digioi.py`

**Interfaces:**
- Consumes: `GameClient.reset_daily_counters_if_needed(today=None, now=None) -> bool`.
- Produces: every keepalive tick checks rollover immediately before online gift claim on PC and APK.

- [ ] **Step 1: Write failing keepalive-order test**

Append to `tests/test_daily_rollover.py`:

```python
class TestDailyRolloverWiring(unittest.TestCase):
    def test_keepalive_resets_before_claiming_online_gift(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "run_party_digioi.py"), encoding="utf-8") as fh:
            source = fh.read()
        reset_at = source.index("c.reset_daily_counters_if_needed()")
        claim_at = source.index("c.claim_online_gifts()", reset_at)
        self.assertLess(reset_at, claim_at)
        self.assertLess(claim_at - reset_at, 300)
```

- [ ] **Step 2: Run wiring test and verify red**

Run: `python -m unittest tests.test_daily_rollover.TestDailyRolloverWiring -v`

Expected: error `substring not found` for `c.reset_daily_counters_if_needed()`.

- [ ] **Step 3: Call rollover before online gift claim**

Replace the keepalive block with:

```python
            try:
                c.reset_daily_counters_if_needed()
                c.claim_online_gifts()
            except Exception as e:
                log.warning("[%s] loi reset/qua online (bo qua): %s", label, e)
```

- [ ] **Step 4: Run wiring and client tests**

Run: `python -m unittest tests.test_daily_rollover -v`

Expected: `Ran 7 tests ... OK`.

- [ ] **Step 5: Sync PC source to APK**

Run: `python tools/sync_apk_python.py`

Expected: output includes `synced (shared): client.py` and `synced (coordinator): run_party_digioi.py`.

- [ ] **Step 6: Verify parity and compile**

Run:

```powershell
python -c "from pathlib import Path; assert Path('bot/client.py').read_bytes() == Path('android/app/src/main/python/train_bot/client.py').read_bytes()"
python -m py_compile bot/client.py run_party_digioi.py android/app/src/main/python/train_bot/client.py android/app/src/main/python/train_bot/run_party_digioi.py tests/test_daily_rollover.py
```

Expected: both commands exit 0 without output.

- [ ] **Step 7: Run focused regression**

Run: `python -m unittest tests.test_daily_rollover tests.test_event_exit tests.test_npc40 tests.test_npc40_party_policy -v`

Expected: all selected tests report `OK`.

- [ ] **Step 8: Run full suite and classify the known baseline**

Run: `python -m unittest discover -s tests -v`

Expected: rollover tests pass. The known unrelated `test_train_map_config` Android-loader mismatch may remain; report exact counts rather than claiming the whole suite is green.

- [ ] **Step 9: Inspect and commit only source/test changes**

```bash
git diff --check
git status --short
git add bot/client.py run_party_digioi.py tests/test_daily_rollover.py android/app/src/main/python/train_bot/client.py android/app/src/main/python/train_bot/run_party_digioi.py
git commit -m "fix: apply daily rollover in pc and apk loops"
```

Expected: runtime cache, PCAP and `aTSBot-drive/` remain untracked and unstaged. No build is run.
