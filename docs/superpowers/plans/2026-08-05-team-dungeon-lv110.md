# Team Dungeon Level 110 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-enabled PB110 flow to PC and Android which follows the five captured encounters and treats `0x35/0600` enemy replacement as reinforcement inside the current battle.

**Architecture:** Put immutable PB110 route data and the pure reinforcement decoder in a focused `bot/team_dungeon_lv110.py` module. `GameClient` owns only runtime packet observations, explicit battle-end waits, and execution through existing room/move/dialog/heal helpers; Android receives the shared Python files through `tools/sync_apk_python.py`. PC and Android configuration both expose level 110 but default it to disabled.

**Tech Stack:** Python 3, `unittest`, existing `analyze_pcap.load_frames`, Tkinter configuration, Kotlin/Jetpack Compose Android UI, Chaquopy shared Python.

## Global Constraints

- PB110 is visible but disabled by default on PC and Android; only an explicitly saved `true` enables it.
- Keep levels 20, 50, and 80 enabled by default.
- PB110 uses dungeon ID `0x0010` and completion mission `0x30ae`.
- `0x35/0600` is a same-battle reinforcement signal and must never advance the route.
- Encounters 1-4 finish only on a fresh server `0x14/0700`.
- Encounter 5 finishes only when mission `0x30ae` reaches step `1` or the equivalent existing PB110 completion state.
- Do not alter the working PB20/PB50/PB80 route behavior.
- Keep PC and APK behavior synchronized.
- Do not build or publish a release until implementation tests pass and the user requests a build.

---

## File Map

- Create `bot/team_dungeon_lv110.py`: PB110 IDs, five-stage action data, and pure `0x35/0600` decoder.
- Create `tests/test_team_dungeon_lv110.py`: packet, state-machine, dispatch, capture, and PC/Android parity regression tests.
- Modify `bot/client.py`: PB110 observation state, explicit end latch, route executor, dispatch, and cleanup.
- Modify `bot/config.py`: selectable levels and default-off PB110 setting.
- Modify `gui.py`: PC settings normalization and checkbox list include PB110 default-off.
- Modify `tools/sync_apk_python.py`: copy `team_dungeon_lv110.py` into the APK package.
- Modify `android/app/src/main/python/train_bot/config.py`: Android Python default-off PB110 setting.
- Modify `android/app/src/main/python/train_bot/client.py`: generated shared copy of PC client.
- Create `android/app/src/main/python/train_bot/team_dungeon_lv110.py`: generated shared copy of the new module.
- Modify `android/app/src/main/java/com/tsbot/android/Party.kt`: Kotlin model default includes `110 to false`.
- Modify `android/app/src/main/java/com/tsbot/android/PartyStore.kt`: old-file migration and persistence include PB110.
- Modify `android/app/src/main/java/com/tsbot/android/MainActivity.kt`: PB110 checkbox/default/JSON serialization.
- Modify `android/app/src/main/python/train_bot/run_party_digioi.py` only through the existing sync command if its generated copy changes.

### Task 1: Default-Off PB110 Configuration on PC and Android

**Files:**
- Modify: `bot/config.py:7-23`
- Modify: `gui.py:41-62`
- Modify: `android/app/src/main/python/train_bot/config.py:9-25`
- Modify: `android/app/src/main/java/com/tsbot/android/Party.kt:24-28`
- Modify: `android/app/src/main/java/com/tsbot/android/PartyStore.kt:20-26,95-97`
- Modify: `android/app/src/main/java/com/tsbot/android/MainActivity.kt:175-187`
- Test: `tests/test_team_dungeon_lv110.py`

**Interfaces:**
- Consumes: existing `normalize_team_dungeons(value)` and Android `defaultTeamDungeons(src)` behavior.
- Produces: `TEAM_DUNGEON_LEVELS == (20, 50, 80, 110)` and defaults `{20: True, 50: True, 80: True, 110: False}` on both products.

- [ ] **Step 1: Write failing behavior tests for defaults and saved overrides**

```python
class TestTeamDungeon110Config(unittest.TestCase):
    def test_pc_missing_setting_defaults_110_off(self):
        self.assertEqual(config.TEAM_DUNGEON_LEVELS, (20, 50, 80, 110))
        self.assertEqual(
            config.normalize_team_dungeons(None),
            {20: True, 50: True, 80: True, 110: False},
        )

    def test_pc_preserves_explicit_110_setting(self):
        self.assertTrue(config.normalize_team_dungeons({"110": True})[110])

    def test_android_ui_and_store_default_110_off(self):
        self.assertIn("private val TeamDungeonLevels = listOf(20, 50, 80, 110)", ANDROID_UI)
        self.assertIn("110 to (src[110] ?: false)", ANDROID_UI)
        self.assertIn("110 to false", ANDROID_PARTY)
        self.assertIn("110 to false", ANDROID_STORE)
        self.assertIn("listOf(20, 50, 80, 110)", ANDROID_STORE)
```

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m unittest tests.test_team_dungeon_lv110.TestTeamDungeon110Config -v`

Expected: FAIL because level 110 is absent from PC and Android defaults/UI persistence.

- [ ] **Step 3: Add PB110 without changing legacy defaults**

Use these exact values in `bot/config.py`, `gui.py`, and Android Python config:

```python
TEAM_DUNGEON_LEVELS = (20, 50, 80, 110)
DEFAULT_TEAM_DUNGEONS = {20: True, 50: True, 80: True, 110: False}
```

Use these exact Kotlin defaults:

```kotlin
private val TeamDungeonLevels = listOf(20, 50, 80, 110)

private fun defaultTeamDungeons(src: Map<Int, Boolean> = emptyMap()): Map<Int, Boolean> =
    linkedMapOf(
        20 to (src[20] ?: true),
        50 to (src[50] ?: true),
        80 to (src[80] ?: true),
        110 to (src[110] ?: false),
    )
```

Update `Party.teamDungeons`, `PartyStore.teamDungeons`, and the save list to include `110 to false` / `listOf(20, 50, 80, 110)`.

- [ ] **Step 4: Run the config tests and verify GREEN**

Run: `python -m unittest tests.test_team_dungeon_lv110.TestTeamDungeon110Config -v`

Expected: PASS, including explicit `"110": true` preservation.

- [ ] **Step 5: Commit the independently working configuration change**

```bash
git add bot/config.py gui.py android/app/src/main/python/train_bot/config.py android/app/src/main/java/com/tsbot/android/Party.kt android/app/src/main/java/com/tsbot/android/PartyStore.kt android/app/src/main/java/com/tsbot/android/MainActivity.kt tests/test_team_dungeon_lv110.py
git commit -m "Add default-off PB110 setting"
```

### Task 2: Pure PB110 Capture Model and Reinforcement Decoder

**Files:**
- Create: `bot/team_dungeon_lv110.py`
- Modify: `tools/sync_apk_python.py:14-18`
- Test: `tests/test_team_dungeon_lv110.py`

**Interfaces:**
- Consumes: full decoded packet bytes whose seven-byte protocol header precedes the body.
- Produces: `decode_reinforcement(pkt: bytes) -> tuple[bytes, bytes] | None`, `DUNGEON_ID`, `MISSION_ID`, and `STAGES`.

- [ ] **Step 1: Add failing decoder and capture regression tests**

```python
REPLACEMENTS = [
    (0x9D39, 0x9D3D), (0x9D3B, 0x9D3D),
    (0x9D3E, 0x9D42), (0x9D3E, 0x9D41),
    (0x9D3E, 0x9D40), (0x9D43, 0x9D49),
    (0x9D43, 0x9D4A), (0x9D43, 0x9D4B),
]

class TestTeamDungeon110Capture(unittest.TestCase):
    def test_decoder_accepts_only_exact_reinforcement_shape(self):
        pkt = b"\x00" * 7 + bytes.fromhex(
            "060001399d0000000000003d9d000000000000"
        )
        old_entity, new_entity = pb110.decode_reinforcement(pkt)
        self.assertEqual(int.from_bytes(old_entity[:2], "little"), 0x9D39)
        self.assertEqual(int.from_bytes(new_entity[:2], "little"), 0x9D3D)
        self.assertIsNone(pb110.decode_reinforcement(b"\x00" * 7 + b"\x06\x00"))
        self.assertIsNone(pb110.decode_reinforcement(
            b"\x00" * 7 + bytes.fromhex("010001399d0000000000003d9d000000000000")
        ))

    def test_capture_contains_all_reinforcements_and_final_completion(self):
        frames, _ = load_frames(str(CAPTURE))
        actual = []
        for frame in frames:
            if frame["dir"] != "S2C" or frame["op"] != 0x35:
                continue
            decoded = pb110.decode_reinforcement(b"\x00" * 7 + frame["body"])
            if decoded:
                actual.append(tuple(int.from_bytes(e[:2], "little") for e in decoded))
        self.assertEqual(actual, REPLACEMENTS)
        self.assertEqual(sum(
            f["dir"] == "S2C" and f["op"] == 0x14
            and f["body"][:2] == b"\x07\x00"
            for f in frames
        ), 4)
        self.assertTrue(any(
            f["dir"] == "S2C" and f["op"] == 0x18
            and f["body"][:5] == bytes.fromhex("0100ae3001")
            for f in frames
        ))
```

- [ ] **Step 2: Run capture tests and verify RED**

Run: `python -m unittest tests.test_team_dungeon_lv110.TestTeamDungeon110Capture -v`

Expected: ERROR because `bot.team_dungeon_lv110` does not exist.

- [ ] **Step 3: Implement the strict decoder and immutable five-stage action data**

```python
DUNGEON_ID = 0x0010
MISSION_ID = 0x30AE

def decode_reinforcement(pkt: bytes):
    body = pkt[7:]
    if len(body) != 19 or body[:3] != b"\x06\x00\x01":
        return None
    return body[3:11], body[11:19]
```

Define `STAGES` as five tuples of action tuples. Use only these action kinds:
`send`, `advance`, `moves`, `heal`, `battle`. A `battle` action carries the
maximum number of dialog advances and snapshots `_battle_start_seq` **before**
sending any of them, so a battle which starts on the last captured advance is
not missed. Encode the captured route literally:

```python
STAGES = (
    (("send", 0x14, bytes.fromhex("08000800")),
     ("send", 0x0C, bytes.fromhex("0100")), ("battle", 23)),
    (("heal",), ("advance", 10),
     ("moves", ((490, 2410), (222, 2446), (126, 2459), (50, 2470), (50, 2470))),
     ("send", 0x14, bytes.fromhex("08000600")), ("advance", 1),
     ("send", 0x14, bytes.fromhex("08000900")), ("battle", 7)),
    (("heal",), ("advance", 9),
     ("moves", ((733, 350), (710, 350), (452, 226), (366, 185), (280, 143),
                (210, 110), (210, 110))),
     ("send", 0x14, bytes.fromhex("08000200")), ("advance", 1),
     ("moves", ((2796, 2314), (2721, 2255), (2647, 2195), (2590, 2150),
                (2590, 2150))),
     ("send", 0x14, bytes.fromhex("08000a00")), ("battle", 15)),
    (("heal",), ("advance", 12),
     ("moves", ((2623, 2176), (2796, 2313), (2871, 2372), (2946, 2432),
                (3020, 2491), (3070, 2530), (3070, 2530))),
     ("send", 0x14, bytes.fromhex("08000500")), ("advance", 1),
     ("moves", ((430, 370), (430, 370))),
     ("send", 0x14, bytes.fromhex("08000b00")), ("battle", 15)),
    (("heal",), ("advance", 15),
     ("moves", ((430, 370), (228, 459), (141, 498), (70, 530), (70, 530))),
     ("send", 0x14, bytes.fromhex("08000300")), ("advance", 1),
     ("moves", ((2268, 219), (2181, 258), (2110, 290), (2110, 290))),
     ("send", 0x41, bytes.fromhex("01006464010100000101000000")),
     ("heal",), ("moves", ((2110, 290),)),
     ("send", 0x14, bytes.fromhex("08000c00")),
     ("advance", 1), ("send", 0x41, bytes.fromhex("0200")),
     ("battle", 12)),
)
```

Add `"team_dungeon_lv110.py"` to `tools/sync_apk_python.py::SHARED`.

- [ ] **Step 4: Run capture tests and verify GREEN**

Run: `python -m unittest tests.test_team_dungeon_lv110.TestTeamDungeon110Capture -v`

Expected: PASS with exactly eight replacements in capture order and mission `0x30ae/1` present.

- [ ] **Step 5: Commit the capture model**

```bash
git add bot/team_dungeon_lv110.py tools/sync_apk_python.py tests/test_team_dungeon_lv110.py
git commit -m "Model PB110 capture flow"
```

### Task 3: Explicit PB110 Reinforcement and Battle-End State

**Files:**
- Modify: `bot/client.py:850-935,1415-1540,1800-1820`
- Test: `tests/test_team_dungeon_lv110.py`

**Interfaces:**
- Consumes: `team_dungeon_lv110.decode_reinforcement(pkt)` and existing `config.NPC_NAMES`.
- Produces: `_active_team_dungeon_level: int | None`, `_team_dungeon_end_seq: int`, `_team_dungeon_reinforcement_seq: int`, `_observe_team_dungeon_packet(opcode, pkt)`, and `_wait_team_dungeon_end(start_seq, timeout) -> bool`.

- [ ] **Step 1: Write failing state-transition tests**

```python
class TestTeamDungeon110PacketState(unittest.TestCase):
    def make_client(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game._label = "pb110-test"
        game.running = True
        game._active_team_dungeon_level = 110
        game._team_dungeon_end_seq = 0
        game._team_dungeon_reinforcement_seq = 0
        game._battle_end_grace_until = 0.0
        game.state = BattleState()
        return game

    def test_reinforcement_restores_battle_without_ending_stage(self):
        game = self.make_client()
        game.state.in_battle = False
        packet = b"\x00" * 7 + bytes.fromhex(
            "060001399d0000000000003d9d000000000000"
        )
        game._observe_team_dungeon_packet(0x35, packet)
        self.assertTrue(game.state.in_battle)
        self.assertEqual(game._team_dungeon_reinforcement_seq, 1)
        self.assertEqual(game._team_dungeon_end_seq, 0)

    def test_only_0700_increments_normal_end_sequence(self):
        game = self.make_client()
        game._observe_team_dungeon_packet(0x14, b"\x00" * 7 + b"\x08\x00\x04")
        self.assertEqual(game._team_dungeon_end_seq, 0)
        game._observe_team_dungeon_packet(0x14, b"\x00" * 7 + b"\x07\x00")
        self.assertEqual(game._team_dungeon_end_seq, 1)
```

- [ ] **Step 2: Run packet-state tests and verify RED**

Run: `python -m unittest tests.test_team_dungeon_lv110.TestTeamDungeon110PacketState -v`

Expected: FAIL because the observation fields and method do not exist.

- [ ] **Step 3: Add minimal state and observer before generic packet handling**

Initialize:

```python
self._active_team_dungeon_level = None
self._team_dungeon_end_seq = 0
self._team_dungeon_reinforcement_seq = 0
```

Call the observer near the start of `_dispatch`, before `_on_actions` can process `0x35`:

```python
self._observe_team_dungeon_packet(opcode, pkt)
```

Implement:

```python
def _observe_team_dungeon_packet(self, opcode, pkt):
    if self._active_team_dungeon_level != 110:
        return
    if opcode == 0x14 and pkt[7:9] == b"\x07\x00":
        self._team_dungeon_end_seq += 1
        return
    if opcode != 0x35:
        return
    replacement = team_dungeon_lv110.decode_reinforcement(pkt)
    if replacement is None:
        return
    old_entity, new_entity = replacement
    self._team_dungeon_reinforcement_seq += 1
    self.state.in_battle = True
    old_id = int.from_bytes(old_entity[:2], "little")
    new_id = int.from_bytes(new_entity[:2], "little")
    log.info("[%s] PB110 thay quan giua tran: %s -> %s (dot %d)",
             self._label, config.NPC_NAMES.get(old_id, hex(old_id)),
             config.NPC_NAMES.get(new_id, hex(new_id)),
             self._team_dungeon_reinforcement_seq)
```

Do not modify generic `0x14/0800`, idle, or `enemy_slots` behavior for other modes.

- [ ] **Step 4: Run packet-state tests and verify GREEN**

Run: `python -m unittest tests.test_team_dungeon_lv110.TestTeamDungeon110PacketState -v`

Expected: PASS; reinforcement changes only reinforcement/battle state, while only `0700` changes the explicit end sequence.

- [ ] **Step 5: Commit the PB110 packet latch**

```bash
git add bot/client.py tests/test_team_dungeon_lv110.py
git commit -m "Track PB110 battle reinforcements"
```

### Task 4: Five-Encounter PB110 Executor and Safe Completion

**Files:**
- Modify: `bot/client.py:4545-4555,4715-4930`
- Test: `tests/test_team_dungeon_lv110.py`

**Interfaces:**
- Consumes: `team_dungeon_lv110.STAGES`, `_create_team_dungeon_room`, `_battle_start_seq`, `_team_dungeon_end_seq`, `_route_move`, `_adv_dialog`, `do_heal`, and `team_dungeon_remaining(110)`.
- Produces: `do_team_dungeon_lv110(ready_wait: float = 9.0) -> bool`, `_do_team_dungeon_lv110_inner(ready_wait: float = 9.0) -> bool`, `_run_team_dungeon_lv110_stage(actions: tuple, stage_no: int) -> bool`, `_wait_team_dungeon_end(start_seq: int, timeout: float = 360.0) -> bool`, `_wait_team_dungeon_complete(timeout: float = 360.0) -> bool`, and `do_team_dungeon(110)` dispatch.

- [ ] **Step 1: Write failing dispatch, explicit-wait, and scripted-route tests**

```python
class TestTeamDungeon110Execution(unittest.TestCase):
    def test_dispatch_calls_pb110(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.do_team_dungeon_lv110 = mock.Mock(return_value=True)
        self.assertTrue(game.do_team_dungeon(110))
        game.do_team_dungeon_lv110.assert_called_once_with()

    def test_end_wait_ignores_empty_enemies_and_false_combat(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.running = True
        game._team_dungeon_end_seq = 4
        game.state = BattleState()
        game.state.in_battle = False
        with mock.patch.object(client_module.time, "time", side_effect=[0.0, 0.1, 0.2, 0.3]), \
             mock.patch.object(client_module.time, "sleep", side_effect=lambda _n: setattr(game, "running", False)):
            self.assertFalse(game._wait_team_dungeon_end(4, timeout=1.0))

    def test_wrapper_always_clears_pb110_mode(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.state = BattleState()
        game._team_dungeon_until = 10.0
        game._phoban_until = 10.0
        with mock.patch.object(game, "_do_team_dungeon_lv110_inner", return_value=False):
            self.assertFalse(game.do_team_dungeon_lv110())
        self.assertIsNone(game._active_team_dungeon_level)
        self.assertFalse(game.state.quest_mode)
        self.assertEqual(game._team_dungeon_until, 0.0)
        self.assertEqual(game._phoban_until, 0.0)
```

Exercise the real stage runner with only time/network boundaries replaced:

```python
    def test_stage_runs_captured_actions_then_waits_for_explicit_end(self):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.running = True
        game._label = "pb110-test"
        game._battle_start_seq = 10
        game._team_dungeon_end_seq = 20
        game.send = mock.Mock()
        game._route_move = mock.Mock()
        game.do_heal = mock.Mock()
        game._wait_team_dungeon_end = mock.Mock(return_value=True)

        def advance(n=1, gap=0.4):
            game._battle_start_seq += 1

        game._adv_dialog = mock.Mock(side_effect=advance)
        with mock.patch.object(client_module.time, "sleep", return_value=None):
            self.assertTrue(game._run_team_dungeon_lv110_stage(pb110.STAGES[1], 2))

        self.assertEqual(game._route_move.call_args_list, [
            mock.call(490, 2410), mock.call(222, 2446),
            mock.call(126, 2459), mock.call(50, 2470), mock.call(50, 2470),
        ])
        game._wait_team_dungeon_end.assert_called_once_with(20)
```

Add orchestration tests at the real inner-method boundary:

```python
    def configured_inner_client(self, completes=True):
        game = client_module.GameClient.__new__(client_module.GameClient)
        game.running = True
        game._label = "pb110-test"
        game.state = BattleState()
        game._create_team_dungeon_room = mock.Mock(return_value=True)
        game.scene_resume = mock.Mock()
        game.set_party_strategist = mock.Mock()
        game._run_team_dungeon_lv110_stage = mock.Mock(return_value=True)
        game._wait_team_dungeon_complete = mock.Mock(return_value=completes)
        game._adv_dialog = mock.Mock()
        game._route_move = mock.Mock()
        game.leave_party = mock.Mock()
        return game

    def test_inner_runs_five_stages_and_leaves_after_verified_completion(self):
        game = self.configured_inner_client(completes=True)
        with mock.patch.object(client_module.time, "sleep", return_value=None):
            self.assertTrue(game._do_team_dungeon_lv110_inner())
        self.assertEqual(
            [call.args[1] for call in game._run_team_dungeon_lv110_stage.call_args_list],
            [1, 2, 3, 4, 5],
        )
        game._wait_team_dungeon_complete.assert_called_once_with()
        game._adv_dialog.assert_called_with(7, gap=0.4)
        game._route_move.assert_called_with(2124, 283)
        game.leave_party.assert_called_once_with()

    def test_inner_does_not_leave_when_final_completion_times_out(self):
        game = self.configured_inner_client(completes=False)
        with mock.patch.object(client_module.time, "sleep", return_value=None):
            self.assertFalse(game._do_team_dungeon_lv110_inner())
        game.leave_party.assert_not_called()
        game._route_move.assert_not_called()
```

- [ ] **Step 2: Run execution tests and verify RED**

Run: `python -m unittest tests.test_team_dungeon_lv110.TestTeamDungeon110Execution -v`

Expected: FAIL because PB110 dispatch/executor/wait methods do not exist.

- [ ] **Step 3: Implement explicit waits and the five-stage executor**

Add dispatch:

```python
if level == 110:
    return self.do_team_dungeon_lv110()
```

Add the end wait without consulting `in_combat()`, `state.in_battle`, or enemy slots:

```python
def _wait_team_dungeon_end(self, start_seq, timeout=360.0):
    deadline = time.time() + timeout
    while self.running and time.time() < deadline:
        if self._team_dungeon_end_seq > start_seq:
            return True
        time.sleep(0.2)
    return False
```

The wrapper must activate PB110 before room creation and clear it in `finally`:

```python
def do_team_dungeon_lv110(self, ready_wait=9.0):
    self._active_team_dungeon_level = 110
    try:
        return self._do_team_dungeon_lv110_inner(ready_wait)
    finally:
        self._active_team_dungeon_level = None
        self.state.quest_mode = False
        self._team_dungeon_until = 0.0
        self._phoban_until = 0.0
```

In `_do_team_dungeon_lv110_inner`:

1. Call `_create_team_dungeon_room(DUNGEON_ID, 110, ready_wait)`.
2. Reset `dungeon_complete = False`, then call `scene_resume(settle=0.5)` and `set_party_strategist()`.
3. `_run_team_dungeon_lv110_stage` executes each stage action literally; `moves` uses `_route_move`, `advance` uses `_adv_dialog`, `heal` uses `do_heal`, and `send` uses `send` followed by the existing human-like delay.
4. For each `battle`, snapshot `_battle_start_seq` first, send at most the action's advance cap until a fresh start is observed, then for stages 1-4 snapshot/wait on `_team_dungeon_end_seq`.
5. `_wait_team_dungeon_complete` polls while running until `team_dungeon_remaining(110) == 0` or the freshly reset `dungeon_complete` is true, with a bounded 360-second timeout.
6. On any timeout/disconnect, log the stage and return `False` without sending route/leave packets.
7. On verified final completion, call `_adv_dialog(7, gap=0.4)`, move to `(2124,283)`, call `leave_party()`, and return `True`.

- [ ] **Step 4: Run execution tests and verify GREEN**

Run: `python -m unittest tests.test_team_dungeon_lv110.TestTeamDungeon110Execution -v`

Expected: PASS; fake empty-enemy/false-combat state cannot end a stage, and cleanup always runs.

- [ ] **Step 5: Commit the working PB110 executor**

```bash
git add bot/client.py tests/test_team_dungeon_lv110.py
git commit -m "Implement PB110 dungeon route"
```

### Task 5: Android Shared-Code Sync, Parity, and Regression Verification

**Files:**
- Modify: `android/app/src/main/python/train_bot/client.py` (generated)
- Create: `android/app/src/main/python/train_bot/team_dungeon_lv110.py` (generated)
- Modify: `android/app/src/main/python/train_bot/run_party_digioi.py` only if the sync output changes it
- Test: `tests/test_team_dungeon_lv110.py`

**Interfaces:**
- Consumes: `tools/sync_apk_python.py` shared-file list and completed PC PB110 implementation.
- Produces: AST-equivalent PB110 methods and byte-identical pure PB110 module on PC and Android.

- [ ] **Step 1: Add failing PC/Android parity tests**

```python
class TestTeamDungeon110AndroidParity(unittest.TestCase):
    def test_pb110_module_is_shared_verbatim(self):
        self.assertEqual(
            (ROOT / "bot/team_dungeon_lv110.py").read_bytes(),
            (ROOT / "android/app/src/main/python/train_bot/team_dungeon_lv110.py").read_bytes(),
        )

    def test_pb110_client_methods_match(self):
        wanted = {
            "_observe_team_dungeon_packet", "_wait_team_dungeon_end",
            "_wait_team_dungeon_complete",
            "_run_team_dungeon_lv110_stage",
            "do_team_dungeon_lv110", "_do_team_dungeon_lv110_inner",
        }
        self.assertEqual(client_methods(DESKTOP_CLIENT, wanted),
                         client_methods(ANDROID_CLIENT, wanted))
```

- [ ] **Step 2: Run parity tests and verify RED**

Run: `python -m unittest tests.test_team_dungeon_lv110.TestTeamDungeon110AndroidParity -v`

Expected: FAIL because Android has not received the new module/client methods.

- [ ] **Step 3: Run the repository sync mechanism**

Run: `python tools/sync_apk_python.py`

Review `git diff --stat` and `git diff --check`. Confirm the sync copied only the declared shared Python/assets and did not overwrite Android-only config or Kotlin files.

- [ ] **Step 4: Run focused and full regression suites**

Run focused tests:

```bash
python -m unittest tests.test_team_dungeon_lv110 -v
```

Run related regressions:

```bash
python -m unittest tests.test_npc40 tests.test_party_restart tests.test_socket_lifecycle tests.test_android_party_leader_mode -v
```

Run the complete suite:

```bash
python -m unittest discover -s tests -v
```

Expected: all PB110 tests pass; pre-existing PB20/PB50/PB80, event 40 NPC, reconnect, and Android tests remain green.

- [ ] **Step 5: Perform final static and workspace checks**

Run:

```bash
python -m compileall -q bot android/app/src/main/python/train_bot
git diff --check
git status --short
```

Confirm there are no syntax errors, whitespace errors, unexpected generated files, or changes outside the PB110 scope.

- [ ] **Step 6: Commit the synchronized Android implementation and tests**

```bash
git add android/app/src/main/python/train_bot/client.py android/app/src/main/python/train_bot/team_dungeon_lv110.py android/app/src/main/python/train_bot/run_party_digioi.py tests/test_team_dungeon_lv110.py
git commit -m "Sync PB110 flow to Android"
```

- [ ] **Step 7: Report implementation status without building**

Report the exact focused/full test results and commits. State explicitly that no PC/APK product build or GitHub release was created because this task asked to implement and test first.
