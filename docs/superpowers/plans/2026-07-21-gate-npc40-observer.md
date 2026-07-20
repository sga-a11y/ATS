# Gate 40NPC Packet Observer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent ordinary train-map battle packets from entering the 40NPC observer and suppressing train block statistics.

**Architecture:** Add one activity guard at the top of `GameClient._observe_npc40_packet`. Prove the inactive path preserves the battle-count latch, retain the existing active-event behavior, then mirror PC source to APK.

**Tech Stack:** Python 3, `unittest`, Android Chaquopy source mirror

## Global Constraints

- Active 40NPC behavior must remain unchanged.
- Inactive 40NPC observation must not mutate battle or NPC40 state.
- PC and APK source must remain synchronized.
- Do not build or publish a release.

---

### Task 1: Isolate 40NPC packet observation

**Files:**
- Modify: `tests/test_npc40.py`
- Modify: `bot/client.py`
- Modify: `android/app/src/main/python/train_bot/client.py`

**Interfaces:**
- Consumes: `GameClient._npc40_started: bool`
- Produces: `_observe_npc40_packet(opcode, pkt)` as a no-op while inactive

- [ ] **Step 1: Write the failing inactive-observer test**

Add this test to `TestNpc40ClientIntegration`:

```python
def test_inactive_observer_preserves_train_battle_latch(self):
    game = self._client(hp=1, started=False)
    game.state._battle_counted = True
    game._battle_end_grace_until = 123.0

    game._observe_npc40_packet(0x41, b"\x00" * 7 + b"\x0a\x00\x01")

    self.assertTrue(game.state.in_battle)
    self.assertTrue(game.state._battle_counted)
    self.assertEqual(game._npc40_prompt_seq, 0)
    self.assertFalse(game._npc40_last_defeated)
    self.assertEqual(game._battle_end_grace_until, 123.0)
```

Update `_client(self, hp, started=True)` to initialize `_npc40_started = started` and `_battle_end_grace_until = 0.0`, keeping existing active tests active.

- [ ] **Step 2: Run the new test and verify RED**

Run: `python -m unittest tests.test_npc40.TestNpc40ClientIntegration.test_inactive_observer_preserves_train_battle_latch -v`

Expected: FAIL because inactive observation currently clears `state.in_battle` and increments the prompt sequence.

- [ ] **Step 3: Add the minimal activity guard**

At the start of `_observe_npc40_packet` add:

```python
if not getattr(self, "_npc40_started", False):
    return
```

- [ ] **Step 4: Verify focused PC tests**

Run: `python -m unittest tests.test_npc40 tests.test_npc40_party_policy tests.test_train_block_stats -v`

Expected: all selected tests pass.

- [ ] **Step 5: Sync and verify APK parity**

Run:

```powershell
python tools/sync_apk_python.py
python -c "from pathlib import Path; assert Path('bot/client.py').read_bytes() == Path('android/app/src/main/python/train_bot/client.py').read_bytes()"
python -m py_compile bot/client.py android/app/src/main/python/train_bot/client.py tests/test_npc40.py
```

Expected: sync reports `client.py`, parity assertion and compilation exit 0.

- [ ] **Step 6: Run regression and commit**

Run: `python -m unittest tests.test_npc40 tests.test_npc40_party_policy tests.test_train_block_stats tests.test_smart_route -v`

Expected: all selected tests pass.

Commit only source, test, and this plan with message:

```text
fix: isolate npc40 observer from train battles
```
