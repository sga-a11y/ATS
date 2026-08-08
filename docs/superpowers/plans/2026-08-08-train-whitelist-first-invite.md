# Train Whitelist-First Invite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every normal train-party invitation pass invite nearby whitelisted players before bot members.

**Architecture:** Add one `GameClient` helper parallel to the existing team-dungeon participant helper. Route only train startup, train reform/reconnect/relogin, and periodic train retry calls through it; retain existing methods and gates for every other mode.

**Tech Stack:** Python 3, `unittest`, mirrored PC/APK Python runtime.

## Global Constraints

- Whitelist candidates must pass the existing nearby current-map/current-channel validation.
- Whitelist acceptance remains optional and does not change bot joined-member accounting.
- Bot member live map/channel validation and reform timing remain unchanged.
- PC and APK implementations must remain byte-identical.
- Do not build or publish artifacts in this task.

---

### Task 1: Whitelist-first normal train invitation pass

**Files:**
- Modify: `tests/test_channel_switch.py`
- Modify: `bot/client.py`
- Modify: `android/app/src/main/python/train_bot/client.py`
- Modify: `run_party_digioi.py`
- Modify: `android/app/src/main/python/train_bot/run_party_digioi.py`
- Modify: `KNOWLEDGE.md`

**Interfaces:**
- Consumes: `GameClient.invite_whitelist_leaders(gap: float) -> int` and `GameClient.invite_members(gap: float) -> int`.
- Produces: `GameClient.invite_train_party_participants(gap: float) -> tuple[int, int]`, returning `(whitelist_count, bot_count)` after attempting invitations in that order.

- [ ] **Step 1: Write failing ordering and fallback tests**

Add tests using a real `GameClient` instance with patched invitation boundary methods. Record calls and assert:

```python
events = []
game.invite_whitelist_leaders = mock.Mock(
    side_effect=lambda gap=1.0: events.append(("whitelist", gap)) or 1
)
game.invite_members = mock.Mock(
    side_effect=lambda gap=1.0: events.append(("bots", gap)) or 2
)
self.assertEqual(game.invite_train_party_participants(gap=0), (1, 2))
self.assertEqual(events, [("whitelist", 0), ("bots", 0)])
```

Add a second test where `invite_whitelist_leaders` raises and assert the bot method is still called and the result is `(0, 2)`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest tests.test_channel_switch
```

Expected: both new tests fail because `invite_train_party_participants` does not exist.

- [ ] **Step 3: Implement the minimal PC/APK helper**

In both `client.py` copies, add:

```python
def invite_train_party_participants(self, gap: float = 1.0):
    whitelist_count = 0
    try:
        whitelist_count = self.invite_whitelist_leaders(gap=gap)
    except Exception as exc:
        log.warning("[%s] (LEADER) moi whitelist truoc party train loi: %s", self._label, exc)
    bot_count = self.invite_members(gap=gap)
    return whitelist_count, bot_count
```

- [ ] **Step 4: Route train-only invitation passes through the helper**

In both `run_party_digioi.py` copies, introduce a local wrapper that calls `invite_train_party_participants` when `train_on_map` is true and otherwise calls `invite_members`. Use it at train startup, `_do_reform`, route-less train reconnect, train relogin recovery, and the 60-second incomplete-party retry. Leave manual route, Dị Giới, event, solo, and PB room calls unchanged.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
python -m unittest tests.test_channel_switch tests.test_train_routing_policy tests.test_npc40_party_policy tests.test_digioi_channel_report
```

Expected: all tests pass.

- [ ] **Step 6: Document and verify mirrored runtime**

Record the whitelist-first train ordering in `KNOWLEDGE.md`, then run:

```powershell
python -m py_compile bot/client.py run_party_digioi.py android/app/src/main/python/train_bot/client.py android/app/src/main/python/train_bot/run_party_digioi.py
git diff --check
```

Compare SHA-256 for both mirrored file pairs; each PC/APK pair must match.

- [ ] **Step 7: Commit only task files when explicitly requested**

Do not commit, push, build, or publish during implementation unless the user explicitly requests it.
