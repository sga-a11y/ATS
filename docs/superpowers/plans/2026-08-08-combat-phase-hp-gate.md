# Combat Phase HP Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skip automatic CC and ally-protection phases when no living enemy has current HP above 1500, while preserving enemy-protection breaking.

**Architecture:** A single predicate in `bot/combat.py` owns the threshold rule. The automatic CC and protection helpers call it; the break-protection helper remains unchanged. Shared Python sync keeps PC and APK identical.

**Tech Stack:** Python `unittest`, shared PC/APK Python runtime.

## Global Constraints

- Threshold comparison is strictly `current HP > 1500`.
- User-configured skill rules remain unchanged.
- PC and APK combat logic must be byte-identical after sync.

---

### Task 1: Add regression coverage and the shared phase gate

**Files:**
- Modify: `bot/combat.py`
- Modify: `tests/test_combat_turn_claims.py`
- Modify: `KNOWLEDGE.md`
- Sync: `android/app/src/main/python/train_bot/combat.py`

**Interfaces:**
- Produces: `_has_high_hp_enemy(state, threshold=1500) -> bool`
- Consumes: `state.enemy_slots` and `state.enemy_hp`

- [ ] **Step 1: Write failing tests**

Add tests proving HP 1500 disables automatic CC/protection, HP 1501 enables them, and breaking an enemy protection still works at HP 1500.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_combat_turn_claims -v`

Expected: the new boundary tests fail because no HP gate exists.

- [ ] **Step 3: Implement the minimal shared guard**

Add `_has_high_hp_enemy` and guard `_try_cc` plus `_try_protect`. Do not change `_try_break_enemy_protect`.

- [ ] **Step 4: Sync and verify**

Run:

```powershell
python tools/sync_apk_python.py
python -m unittest tests.test_combat_turn_claims tests.test_team_dungeon_lv110 -q
python -m py_compile bot/combat.py android/app/src/main/python/train_bot/combat.py
```

Expected: all selected tests pass and the PC/APK combat hashes match.
