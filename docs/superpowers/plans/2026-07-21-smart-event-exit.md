# Smart Event Exit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thoát map 40NPC và các event tương tự bằng tọa độ vừa được server xác nhận và đường A* suy từ ID map, không replay waypoint capture.

**Architecture:** `GameClient` đánh generation mỗi lần nhận self-spawn `S2C 0x03`, rồi `refresh_server_position()` yêu cầu scene state và chỉ fallback sang relogin nếu không có generation mới. `exit_event()` dùng vị trí đó để gọi smart scene router hiện có; router chọn cổng từ `world_nav.json`, tìm đường cục bộ từ `Ground.mmg`, và executor xác nhận đổi map.

**Tech Stack:** Python 3, `unittest`, `unittest.mock`, JSON assets, Android Chaquopy source mirror.

## Global Constraints

- Không dùng `exit.steps` hoặc waypoint capture làm fallback.
- Chỉ route khi `current_map` vẫn bằng source map và `pos` là tọa độ self-spawn mới.
- Nếu request scene không sinh self-spawn mới thì relogin; nếu relogin/graph/Ground/A* thất bại thì trả `False` và log rõ.
- Sửa source PC trước, sau đó dùng `tools/sync_apk_python.py` để đồng bộ APK.
- Không build PC/APK cho tới khi người dùng test bản dev.
- Không đưa các file runtime `mob_packets_*.jsonl`, `mob_spots.json` hoặc `aTSBot-drive/` vào commit.

---

## File Structure

- `bot/client.py`: sở hữu generation vị trí, resync tọa độ server và orchestration thoát event.
- `events.json`: cấu hình khai báo đích thoát của 40NPC; không chứa đường capture.
- `tests/test_event_exit.py`: test packet self-spawn, request/relogin policy và `exit_event` orchestration.
- `tests/test_smart_route.py`: test tích hợp dữ liệu thật cho route `10991 -> 12003` từ vị trí gần NPC.
- `android/app/src/main/python/train_bot/client.py`: bản mirror APK sinh từ source PC.
- `android/app/src/main/assets/train_bot_data/events.json`: bản mirror cấu hình APK.

### Task 1: Server-confirmed position generation and refresh

**Files:**
- Modify: `bot/client.py:734`
- Modify: `bot/client.py:1339-1355`
- Modify: `bot/client.py:4511-4520`
- Create: `tests/test_event_exit.py`

**Interfaces:**
- Consumes: self-spawn packet `S2C 0x03`, `GameClient.send(opcode, payload)` và `GameClient.relogin() -> bool`.
- Produces: `GameClient._position_generation: int` và `GameClient.refresh_server_position(source_map: int, request_timeout: float = 2.0) -> bool`.

- [ ] **Step 1: Write failing generation tests**

```python
import struct
import unittest
from unittest import mock

from bot import protocol
from bot.client import GameClient


def self_spawn(entity, map_id, x, y):
    body = b"\x00\x00" + entity + bytes(11) + struct.pack("<HHH", map_id, x, y)
    return protocol.build_packet(0x03, body)


class TestServerPositionRefresh(unittest.TestCase):
    def setUp(self):
        self.client = GameClient("user", "token")
        self.client.self_entity = b"self0000"
        self.client.current_map = 10991
        self.client.pos = (910, 290)
        self.client.running = True

    def test_self_spawn_updates_position_and_generation(self):
        before = self.client._position_generation
        self.client._dispatch(0x03, self_spawn(self.client.self_entity, 10991, 900, 300))
        self.assertEqual(self.client.pos, (900, 300))
        self.assertEqual(self.client._position_generation, before + 1)

    def test_other_entity_does_not_update_position_generation(self):
        before = self.client._position_generation
        self.client._dispatch(0x03, self_spawn(b"other000", 10991, 100, 100))
        self.assertEqual(self.client.pos, (910, 290))
        self.assertEqual(self.client._position_generation, before)
```

- [ ] **Step 2: Run generation tests and verify red**

Run: `python -m unittest tests.test_event_exit.TestServerPositionRefresh.test_self_spawn_updates_position_and_generation tests.test_event_exit.TestServerPositionRefresh.test_other_entity_does_not_update_position_generation -v`

Expected: `ERROR` vì `GameClient` chưa có `_position_generation`.

- [ ] **Step 3: Add generation state and increment only for valid self position**

In `GameClient.__init__`, immediately after `self.pos = None`, add:

```python
self._position_generation = 0  # tang khi server xac nhan self pos qua S2C 0x03
```

In the valid coordinate branch of `_dispatch`, immediately after `self.pos = (sx, sy)`, add:

```python
self._position_generation += 1
```

- [ ] **Step 4: Run generation tests and verify green**

Run: `python -m unittest tests.test_event_exit.TestServerPositionRefresh.test_self_spawn_updates_position_and_generation tests.test_event_exit.TestServerPositionRefresh.test_other_entity_does_not_update_position_generation -v`

Expected: `Ran 2 tests ... OK`.

- [ ] **Step 5: Write failing refresh policy tests**

Append to `TestServerPositionRefresh`:

```python
    def test_scene_request_fresh_spawn_avoids_relogin(self):
        def answer_scene(opcode, payload):
            self.assertEqual((opcode, payload), (0x0C, b"\x01\x00"))
            self.client._dispatch(
                0x03,
                self_spawn(self.client.self_entity, 10991, 880, 320),
            )

        with mock.patch.object(self.client, "send", side_effect=answer_scene), \
             mock.patch.object(self.client, "relogin") as relogin:
            self.assertTrue(self.client.refresh_server_position(10991, request_timeout=0.1))
        relogin.assert_not_called()
        self.assertEqual(self.client.pos, (880, 320))

    def test_scene_timeout_relogins_and_requires_new_spawn(self):
        def relogin():
            self.client._dispatch(
                0x03,
                self_spawn(self.client.self_entity, 10991, 870, 330),
            )
            return True

        with mock.patch.object(self.client, "send"), \
             mock.patch.object(self.client, "relogin", side_effect=relogin) as relogin_mock:
            self.assertTrue(self.client.refresh_server_position(10991, request_timeout=0.0))
        relogin_mock.assert_called_once_with()
        self.assertEqual(self.client.pos, (870, 330))

    def test_relogin_without_fresh_spawn_fails(self):
        with mock.patch.object(self.client, "send"), \
             mock.patch.object(self.client, "relogin", return_value=True):
            self.assertFalse(self.client.refresh_server_position(10991, request_timeout=0.0))

    def test_fresh_spawn_on_different_map_fails(self):
        def answer_scene(_opcode, _payload):
            self.client._dispatch(
                0x03,
                self_spawn(self.client.self_entity, 12003, 170, 780),
            )

        with mock.patch.object(self.client, "send", side_effect=answer_scene), \
             mock.patch.object(self.client, "relogin") as relogin:
            self.assertFalse(self.client.refresh_server_position(10991, request_timeout=0.1))
        relogin.assert_not_called()
```

- [ ] **Step 6: Run refresh tests and verify red**

Run: `python -m unittest tests.test_event_exit.TestServerPositionRefresh -v`

Expected: generation tests pass; four policy tests fail vì chưa có `refresh_server_position`.

- [ ] **Step 7: Implement bounded scene request with relogin fallback**

Add above `build_smart_scene_route`:

```python
    def refresh_server_position(self, source_map: int, request_timeout: float = 2.0) -> bool:
        source_map = int(source_map)
        generation = self._position_generation
        self.send(0x0C, b"\x01\x00")
        deadline = time.time() + max(0.0, float(request_timeout))
        while self.running and time.time() < deadline:
            if self._position_generation != generation:
                ok = self.current_map == source_map and self.pos is not None
                if not ok:
                    log.warning("[%s] resync pos doi sang map %s, can map %s",
                                self._label, self.current_map, source_map)
                return ok
            time.sleep(0.05)

        log.info("[%s] request scene khong co self-spawn moi -> relogin", self._label)
        if not self.relogin():
            log.warning("[%s] resync pos that bai: relogin loi", self._label)
            return False
        ok = (self._position_generation != generation
              and self.current_map == source_map
              and self.pos is not None)
        if not ok:
            log.warning("[%s] resync pos sau relogin khong hop le: gen=%s->%s map=%s pos=%s",
                        self._label, generation, self._position_generation,
                        self.current_map, self.pos)
        return ok
```

- [ ] **Step 8: Run refresh tests and verify green**

Run: `python -m unittest tests.test_event_exit.TestServerPositionRefresh -v`

Expected: `Ran 6 tests ... OK`.

- [ ] **Step 9: Commit the position refresh unit**

```bash
git add bot/client.py tests/test_event_exit.py
git commit -m "feat: resync server position before event routing"
```

### Task 2: Replace captured event exit with smart scene routing

**Files:**
- Modify: `bot/client.py:4655-4683`
- Modify: `events.json:99-112`
- Modify: `tests/test_event_exit.py`
- Modify: `tests/test_smart_route.py`

**Interfaces:**
- Consumes: `refresh_server_position(source_map, request_timeout=2.0) -> bool` and `follow_smart_scene_route(source_map, dest_map, safe=None, abort=None, flee=True) -> bool`.
- Produces: `exit_event(ev: dict) -> bool` that ignores all captured steps and succeeds only on exact destination map.

- [ ] **Step 1: Write failing exit orchestration tests**

Append to `tests/test_event_exit.py`:

```python
class TestSmartEventExit(unittest.TestCase):
    def setUp(self):
        self.client = GameClient("user", "token")
        self.client.running = True
        self.client.current_map = 10991
        self.client.pos = (910, 290)
        self.event = {
            "exit": {
                "out_map": 12003,
                "steps": [{"move": [1, 2], "flag": 5}, {"gate": 99, "x": 3, "y": 4}],
            }
        }

    def test_exit_resyncs_then_uses_smart_scene_route_and_ignores_steps(self):
        def finish_route(source_map, dest_map, safe=None, abort=None, flee=True):
            self.assertEqual((source_map, dest_map, safe, flee), (10991, 12003, None, True))
            self.client.current_map = 12003
            return True

        with mock.patch.object(self.client, "refresh_server_position", return_value=True) as refresh, \
             mock.patch.object(self.client, "follow_smart_scene_route", side_effect=finish_route) as route, \
             mock.patch.object(self.client, "_exit_event_gate") as captured_gate, \
             mock.patch.object(self.client, "_route_move") as captured_move:
            self.assertTrue(self.client.exit_event(self.event))
        refresh.assert_called_once_with(10991)
        route.assert_called_once()
        captured_gate.assert_not_called()
        captured_move.assert_not_called()

    def test_exit_stops_when_position_refresh_fails(self):
        with mock.patch.object(self.client, "refresh_server_position", return_value=False), \
             mock.patch.object(self.client, "follow_smart_scene_route") as route:
            self.assertFalse(self.client.exit_event(self.event))
        route.assert_not_called()

    def test_exit_requires_router_to_reach_exact_out_map(self):
        with mock.patch.object(self.client, "refresh_server_position", return_value=True), \
             mock.patch.object(self.client, "follow_smart_scene_route", return_value=False):
            self.assertFalse(self.client.exit_event(self.event))
        self.assertEqual(self.client.current_map, 10991)
```

- [ ] **Step 2: Write failing real-data route test**

Append to `TestSmartWorldRouter` in `tests/test_smart_route.py`:

```python
    def test_builds_40npc_exit_from_current_position(self):
        route = self.router.build_scene_route(10991, 12003, start=(910, 290))

        self.assertIsNotNone(route)
        self.assertEqual(route["source_map"], 10991)
        self.assertEqual(route["dest_map"], 12003)
        self.assertEqual([leg["gate"] for leg in route["legs"]], [1])
        self.assertEqual(route["legs"][0]["paths"]["910,290"][-1], [90, 870])
```

- [ ] **Step 3: Run exit and real-data tests and verify red state**

Run: `python -m unittest tests.test_event_exit.TestSmartEventExit tests.test_smart_route.TestSmartWorldRouter.test_builds_40npc_exit_from_current_position -v`

Expected: real-data router test passes; orchestration test fails vì `exit_event` còn replay `exit.steps`.

- [ ] **Step 4: Replace `exit_event` with position-resynced smart routing**

Replace the body of `exit_event` after the docstring with:

```python
        ex = ev.get("exit") if ev else None
        if not ex:
            return False
        out_map = int(ex.get("out_map", 0))
        source_map = self.current_map
        if not out_map or source_map is None:
            log.warning("[%s] exit_event: thieu source/out map", self._label)
            return False
        source_map = int(source_map)
        log.info("[%s] exit_event smart route: %s -> %s", self._label, source_map, out_map)
        self.flee_mode = True
        if not self.refresh_server_position(source_map):
            return False
        if not self.follow_smart_scene_route(source_map, out_map, safe=None, flee=True):
            log.warning("[%s] exit_event: khong di duoc %s -> %s tu pos=%s",
                        self._label, source_map, out_map, self.pos)
            return False
        return self.current_map == out_map
```

Update the docstring to state that the method uses server-confirmed coordinates and smart scene routing, not capture replay.

- [ ] **Step 5: Remove captured exit metadata from 40NPC config**

Replace the `npc_40.exit` object in `events.json` with:

```json
"exit": {
  "out_map": 12003
}
```

Update `npc_40._note` so it says map `10991` blocks teleport and exit is inferred from map data; remove all references to `ts_exit.pcap`.

- [ ] **Step 6: Run Task 2 tests and verify green**

Run: `python -m unittest tests.test_event_exit tests.test_smart_route tests.test_smart_route_execution -v`

Expected: all event-exit and smart-route tests report `OK`.

- [ ] **Step 7: Commit the smart event exit unit**

```bash
git add bot/client.py events.json tests/test_event_exit.py tests/test_smart_route.py
git commit -m "fix: route event exits from live position"
```

### Task 3: Sync APK and run scoped regression verification

**Files:**
- Modify: `android/app/src/main/python/train_bot/client.py`
- Modify: `android/app/src/main/assets/train_bot_data/events.json`
- Verify: `bot/client.py`
- Verify: `events.json`
- Verify: `tests/test_event_exit.py`
- Verify: `tests/test_smart_route.py`

**Interfaces:**
- Consumes: PC `bot/client.py`, root `events.json`, and `tools/sync_apk_python.py`.
- Produces: byte-identical PC/APK client logic and JSON-equivalent PC/APK event configuration.

- [ ] **Step 1: Sync PC source and event asset into APK**

Run: `python tools/sync_apk_python.py`

Expected: output contains `synced (shared): client.py` and `synced (asset): events.json` with exit code 0.

- [ ] **Step 2: Verify exact PC/APK parity**

Run:

```powershell
python -c "from pathlib import Path; assert Path('bot/client.py').read_bytes() == Path('android/app/src/main/python/train_bot/client.py').read_bytes()"
python -c "import json; assert json.load(open('events.json', encoding='utf-8')) == json.load(open('android/app/src/main/assets/train_bot_data/events.json', encoding='utf-8'))"
```

Expected: both commands exit 0 without output.

- [ ] **Step 3: Compile both Python clients**

Run: `python -m py_compile bot/client.py android/app/src/main/python/train_bot/client.py tests/test_event_exit.py tests/test_smart_route.py`

Expected: exit code 0 without output.

- [ ] **Step 4: Run focused regression suite**

Run: `python -m unittest tests.test_event_exit tests.test_smart_route tests.test_smart_route_execution tests.test_npc40 tests.test_npc40_party_policy -v`

Expected: all selected tests report `OK`.

- [ ] **Step 5: Run full suite and classify only known unrelated failure**

Run: `python -m unittest discover -s tests -v`

Expected: all new event-exit tests pass. The previously known unrelated `test_train_map_config` Android-loader mismatch may remain; record the exact count and traceback rather than claiming a fully green suite.

- [ ] **Step 6: Inspect the scoped diff and exclude runtime artifacts**

Run: `git diff --check; git status --short; git diff -- bot/client.py events.json tests/test_event_exit.py tests/test_smart_route.py android/app/src/main/python/train_bot/client.py android/app/src/main/assets/train_bot_data/events.json`

Expected: no whitespace errors; no `mob_packets_*.jsonl`, `mob_spots.json`, `aTSBot-drive/` or captures are staged by this task.

- [ ] **Step 7: Commit APK parity without building**

```bash
git add android/app/src/main/python/train_bot/client.py android/app/src/main/assets/train_bot_data/events.json
git commit -m "chore: sync smart event exit to apk"
```

- [ ] **Step 8: Hand off dev test instructions**

Report that no build was performed. Ask the user to run party 40NPC from a post-battle position and provide the log lines beginning `RESYNC pos`, `scene route 10991 -> 12003`, and `scene route reached map 12003` if the character does not exit correctly.
