# Protocol Battle Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace heuristic battle handling with a protocol-driven tracker and a non-blocking party coordinator that keeps PC/APK decisions correct when identical packets reach accounts at different times.

**Architecture:** `BattleTracker` owns one socket's decoded lifecycle and unit state. `PartyBattleCoordinator`, keyed by `party_idx`, merges valid semantic events, deduplicates broadcast packets, owns the canonical snapshot and action reservations, while each `GameClient` retains a local turn gate and ACK/retry state. `BattleState` exposes compatibility views so existing combat rules can migrate without a broad rewrite.

**Tech Stack:** Python 3, `dataclasses`, `threading.RLock`, `unittest`/`pytest`, existing packet transport and combat modules.

## Global Constraints

- Packet server state is authoritative; do not infer battle end from `0x14` dialogs.
- `0x0B/FA` creates a generation, `0x34/01` opens a turn, and matching local `0x0B/00` ends the battle.
- An account sends only after its own socket receives matching `0x34/01`; no all-account READY barrier and no fixed source account.
- PC and APK Python modules must remain byte-for-byte identical.
- Preserve unrelated dirty worktree changes; stage or commit only exact files belonging to a completed task.
- Do not build or publish unless the user asks after verification.

---

### Task 1: Protocol decoder and local battle model

**Files:**
- Create: `bot/battle_tracker.py`
- Create: `tests/test_battle_tracker.py`

**Interfaces:**
- Produces: `BattleUnit`, `BattleEvent`, `BattleSnapshot`, `BattleTracker.apply(opcode: int, body: bytes) -> tuple[BattleEvent, ...]`
- Produces: `BattleTracker.generation`, `turn`, `revision`, `active`, `units`, `statuses`, `pending_actions`

- [ ] **Step 1: Write failing lifecycle and decoder tests**

```python
def test_create_turn_and_local_end_are_authoritative():
    tracker = BattleTracker(local_role_id=b"SELFROLE")
    tracker.apply(0x0B, battle_create_packet())
    tracker.apply(0x34, b"\x01\x00")
    tracker.apply(0x14, b"\x08\x00")
    assert (tracker.generation, tracker.turn, tracker.active) == (1, 1, True)
    tracker.apply(0x0B, battle_end_packet(b"OTHER___"))
    assert tracker.active is True
    tracker.apply(0x0B, battle_end_packet(b"SELFROLE"))
    assert tracker.active is False
```

Also cover `0x0B/0A`, fixed-header `0x0B/05`, truncated packets, and a second `0x34` preserving roster/status/HP.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_battle_tracker.py -q`

Expected: collection fails because `bot.battle_tracker` does not exist.

- [ ] **Step 3: Implement the minimal model and opcode `0x0B`, `0x34` decoders**

```python
@dataclass
class BattleUnit:
    row: int
    col: int
    role_id: bytes
    template_id: int
    hp: int
    hp_max: int
    sp: int
    sp_max: int
    level: int
    alive: bool = True

class BattleTracker:
    def apply(self, opcode: int, body: bytes) -> tuple[BattleEvent, ...]:
        """Validate the whole packet, then atomically mutate state."""
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest tests/test_battle_tracker.py -q`

Expected: all Task 1 tests pass.

### Task 2: Status, buffs, action ACK and roster transitions

**Files:**
- Modify: `bot/battle_tracker.py`
- Modify: `tests/test_battle_tracker.py`

**Interfaces:**
- Consumes: `BattleTracker.apply`
- Produces semantic event kinds `status`, `buff`, `ack`, `flyout`, `exit`, `move`, `transform`, `spawn`

- [ ] **Step 1: Add failing tests for incremental state**

```python
def test_zero_status_clears_only_one_category():
    tracker = active_tracker_with_unit((0, 1))
    tracker.apply(0x35, restore_status((0, 1, 1, 11014), (0, 1, 3, 14021)))
    tracker.apply(0x35, restore_status((0, 1, 1, 0)))
    assert tracker.statuses[(0, 1)] == {3: 14021}
```

Add one test each for `0x35/03`, `/05`, `/07`, `/14`, `/15`, `/20`, `0x0B/01`, replacement `0x0B/05`, and all-or-nothing behavior on truncation.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m pytest tests/test_battle_tracker.py -q`

Expected: failures identify each unsupported event without altering earlier passing tests.

- [ ] **Step 3: Implement validated decoders and atomic mutations**

Parse each packet into temporary records first. Commit changes only after every record and length is valid; emit immutable `BattleEvent` objects after mutation.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_battle_tracker.py -q`

### Task 3: Correct action results and absolute attributes

**Files:**
- Modify: `bot/battle_tracker.py`
- Create: `tests/test_battle_action_results.py`

**Interfaces:**
- Produces: semantic `action` events with source, skill, target, result, signed deltas and final values
- Produces: correct `0x33/01` absolute int32 updates and revive state

- [ ] **Step 1: Write failing delta/absolute tests**

```python
def test_damage_is_signed_delta_not_absolute_hp():
    tracker = tracker_with_enemy(hp=2104, hp_max=3000)
    tracker.apply(0x32, attack_result(hp_value=428, sign=1))
    assert tracker.units[(0, 1)].hp == 1676

def test_absolute_update_reads_full_int32():
    tracker = tracker_with_enemy(hp=1, hp_max=200000)
    tracker.apply(0x33, absolute_attr(value=70000))
    assert tracker.units[(0, 1)].hp == 70000
```

Cover healing, miss, clamp, SP, revive, multiple targets and malformed chunks.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_battle_action_results.py -q`

- [ ] **Step 3: Implement `RevAttackSkill` and `0x33/01` parsers**

Apply `signed = value if sign == 0 else -value`, clamp current attributes, and never scan for guessed byte markers.

- [ ] **Step 4: Run focused tracker tests and verify GREEN**

Run: `python -m pytest tests/test_battle_tracker.py tests/test_battle_action_results.py -q`

### Task 4: Non-blocking party coordinator

**Files:**
- Create: `bot/party_battle.py`
- Create: `tests/test_party_battle_coordinator.py`

**Interfaces:**
- Consumes: `BattleEvent`, `BattleSnapshot`
- Produces: `get_party_battle(party_idx) -> PartyBattleCoordinator`
- Produces: `observe(account_id, event)`, `open_local_turn(account_id, generation, turn)`, `reserve(account_id, action_class, target)`, `can_send(account_id, generation, turn)`

- [ ] **Step 1: Write failing skew, dedup and disconnect tests**

```python
def test_fast_account_does_not_send_for_slow_account():
    c = PartyBattleCoordinator(19)
    c.observe("a", turn_start_event(generation=4))
    c.open_local_turn("a", 4, 1)
    assert c.can_send("a", 4, 1)
    assert not c.can_send("b", 4, 1)
    c.open_local_turn("b", 4, 1)
    assert c.can_send("b", 4, 1)

def test_missing_account_never_blocks_others():
    c = coordinator_with_accounts("a", "b", "frozen")
    c.observe("a", turn_start_event(generation=2))
    assert c.can_plan(2, 1)
```

Also test identical broadcast copies increment one turn/log once, invalid-first valid-later, stale local turn rejection, semantic conflicts warning once, and coordinator isolation by party.

- [ ] **Step 2: Run coordinator tests and verify RED**

Run: `python -m pytest tests/test_party_battle_coordinator.py -q`

- [ ] **Step 3: Implement coordinator with `RLock` and phase state**

```python
class PartyBattleCoordinator:
    def can_send(self, account_id, generation, turn):
        return (
            self.active_key == (generation, turn)
            and self.local_turns.get(account_id) == (generation, turn)
        )
```

Use semantic keys from the spec, per-socket confirmations, conflict counts, bounded history, and no condition wait/barrier.

- [ ] **Step 4: Run coordinator tests and verify GREEN**

Run: `python -m pytest tests/test_party_battle_coordinator.py -q`

### Task 5: Central action reservations and combat compatibility views

**Files:**
- Modify: `bot/party_battle.py`
- Modify: `bot/state.py`
- Modify: `bot/combat.py`
- Modify: `tests/test_party_battle_coordinator.py`
- Modify: `tests/test_combat_turn_claims.py`

**Interfaces:**
- Produces: `BattleState.attach_tracker(tracker, coordinator)` and tracker-derived `enemy_hp`, `enemy_slots`, `allies`, `protect_status`, `crowd_status`
- Produces: turn-scoped reservation classes `cc`, `protect`, `revive`, `heal_hp`, `heal_sp`, `break_protect`

- [ ] **Step 1: Write failing view and reservation tests**

```python
def test_two_accounts_reserve_different_cc_targets_in_same_turn():
    c = coordinator_with_enemy_targets((0, 1), (0, 2))
    assert c.reserve("a", "cc", (0, 1), generation=3, turn=2)
    assert not c.reserve("b", "cc", (0, 1), generation=3, turn=2)
    assert c.reserve("b", "cc", (0, 2), generation=3, turn=2)
```

Assert reservations expire only when canonical turn changes, damage focus is not blocked, existing HP `>1500` gates remain, and protection/CC views mirror status categories.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_party_battle_coordinator.py tests/test_combat_turn_claims.py -q`

- [ ] **Step 3: Implement views and route claim helpers through coordinator**

Keep legacy dictionaries as properties/views during migration. Do not use `enemy_gen` as a turn timer; expose tracker revision for compatibility.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_party_battle_coordinator.py tests/test_combat_turn_claims.py -q`

### Task 6: Integrate tracker/coordinator into `GameClient`

**Files:**
- Modify: `bot/client.py`
- Create: `tests/test_client_battle_flow.py`

**Interfaces:**
- Consumes: `BattleTracker.apply`, `get_party_battle`, `PartyBattleCoordinator.can_send`
- Changes: `_make_decisions` runs from local `0x34/01`, `_send_combat` registers pending, `0x35/05` ACKs the exact source

- [ ] **Step 1: Write failing integration tests**

```python
def test_status_packet_never_arms_a_decision(client):
    client.handle_packet(status_packet())
    assert client.decision_timer is None

def test_dialog_does_not_end_an_active_battle(client):
    client.handle_packet(dialog_0800())
    assert client.state.in_battle is True
```

Add tests for local `0x34` send gate, delayed second account, ACK clearing only its source, retry guards, local `0x0B/00`, and cancellation on generation/turn change.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `python -m pytest tests/test_client_battle_flow.py -q`

- [ ] **Step 3: Replace heuristic dispatch paths**

Forward battle opcodes to the tracker, publish semantic events to the party coordinator, arm once on local `0x34`, and remove action offers from zero-status records, 1.5-second unlocks, and `0x14` mutations of battle activity.

- [ ] **Step 4: Run focused integration/regression tests and verify GREEN**

Run: `python -m pytest tests/test_client_battle_flow.py tests/test_npc40.py tests/test_team_dungeon_lv110.py -q`

### Task 7: Single-copy battle logging

**Files:**
- Modify: `bot/party_battle.py`
- Modify: `bot/client.py`
- Create: `tests/test_battle_logging.py`

**Interfaces:**
- Produces common `[P{party_idx} BATTLE g={generation} t={turn}]` logs once per semantic event
- Produces per-account `DECISION`, `SEND`, `ACK` logs

- [ ] **Step 1: Write failing `caplog` tests**

Feed the same action/status/turn from five account IDs and assert one common event line, then assert each local send/ACK remains attributable to its account.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_battle_logging.py -q`

- [ ] **Step 3: Implement structured formatter and deduplicated emission**

Use stable unit names with `role:<hex>` or `npc:<id>` fallbacks. Keep raw payload logging at DEBUG only.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m pytest tests/test_battle_logging.py -q`

### Task 8: PB110 capture replay

**Files:**
- Create: `tests/test_battle_capture_replay.py`
- Modify: `bot/battle_tracker.py` only if a failing capture-derived test proves a decoder defect

**Interfaces:**
- Consumes capture: `captures/teamdungeon_lv110_mumu12_20260805_202150.pcap`

- [ ] **Step 1: Write failing replay assertions**

Decode server payloads using the repository's existing capture helper and assert 5 generations, 31 canonical turns, 8 flyout/reinforcement transitions, non-negative HP/SP, correct slot replacement, and no battle end from NPC dialog.

- [ ] **Step 2: Run replay and verify RED for any remaining mismatch**

Run: `python -m pytest tests/test_battle_capture_replay.py -q`

- [ ] **Step 3: Apply minimal parser fixes proven by replay**

Do not add packet guesses. Record each new confirmed layout in `KNOWLEDGE.md`.

- [ ] **Step 4: Run replay and all battle tests until GREEN**

Run: `python -m pytest tests/test_battle_tracker.py tests/test_battle_action_results.py tests/test_party_battle_coordinator.py tests/test_client_battle_flow.py tests/test_battle_logging.py tests/test_battle_capture_replay.py -q`

### Task 9: Mirror Android code and verify the whole project

**Files:**
- Create: `android/app/src/main/python/train_bot/battle_tracker.py`
- Create: `android/app/src/main/python/train_bot/party_battle.py`
- Modify: `android/app/src/main/python/train_bot/client.py`
- Modify: `android/app/src/main/python/train_bot/combat.py`
- Modify: `android/app/src/main/python/train_bot/state.py`
- Modify: `KNOWLEDGE.md`

**Interfaces:**
- APK imports remain package-relative in the same way as PC modules.

- [ ] **Step 1: Copy corresponding PC modules byte-for-byte to APK**

Use the repository's normal formatting/copy mechanism; do not manually maintain divergent implementations.

- [ ] **Step 2: Compile both trees**

Run: `python -m compileall -q bot android/app/src/main/python/train_bot`

Expected: exit code 0.

- [ ] **Step 3: Run full regression suite**

Run: `python -m pytest -q`

Expected: all tests pass; investigate every failure rather than accepting the previous 144/158 baseline.

- [ ] **Step 4: Verify mirrors and diff hygiene**

Run: `Get-FileHash bot/battle_tracker.py,android/app/src/main/python/train_bot/battle_tracker.py,bot/party_battle.py,android/app/src/main/python/train_bot/party_battle.py,bot/client.py,android/app/src/main/python/train_bot/client.py,bot/combat.py,android/app/src/main/python/train_bot/combat.py,bot/state.py,android/app/src/main/python/train_bot/state.py`

Run: `git diff --check`

Expected: each PC/APK pair has matching SHA-256 and diff check is clean.

- [ ] **Step 5: Report verified behavior without building**

Report focused/full test counts, capture replay counts, mirror hashes, and any pre-existing unrelated failures. Build/release only after a separate explicit user request.
