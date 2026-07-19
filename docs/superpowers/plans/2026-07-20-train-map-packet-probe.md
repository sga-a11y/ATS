# Train Map Packet Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically route to an unconfigured train map, stand at the learned warp safe, and capture target-map raw packets without full-map walking or combat-based inference.

**Architecture:** Add a bounded target-map JSONL packet recorder to `GameClient`, arm it before train routing, and replace automatic coverage scanning with a stationary 60-second probe when no learned/configured mob point exists. Treat empty scan caches as retryable and preserve the first fingerprint-valid warp safe.

**Tech Stack:** Python 3.12 standard library, existing unittest suite, existing PC/Chaquopy shared-source sync.

## Global Constraints

- Do not infer visible monster positions from random encounter combat.
- Do not run full-map coverage by default.
- Do not require a user-entered mob coordinate.
- Capture only packets received while the dispatched client state is on the selected target map.
- Keep capture bounded to 50,000 packets and close it deterministically.
- Keep PC and Android source behavior identical.
- Do not build EXE, ZIP, or APK in this task.

---

### Task 1: Add bounded target-map raw packet capture

**Files:**
- Modify: `bot/client.py`
- Modify: `tests/test_mob_packet_observer.py`
- Modify: `tools/sync_apk_python.py` only through its existing sync command

**Interfaces:**
- Produces: `GameClient.arm_mob_packet_capture(map_id, path=None, max_packets=50000) -> str`, `finish_mob_packet_capture() -> tuple[str | None, int]`, and `_capture_mob_packet(opcode, pkt)`.
- The receive loop calls `_capture_mob_packet` in `finally` after `_dispatch`, so the packet which changes `current_map` is retained.

- [ ] **Step 1: Write failing packet capture tests**

Add a temporary-file test which arms map `20801`, dispatches one packet while `current_map=20000`, dispatches a synthetic map-change packet which sets `current_map=20801`, then dispatches another packet. Assert the JSONL file contains only target-map records, including the map-change frame after dispatch. Add a max-packet test proving additional records are ignored.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests.test_mob_packet_observer -v`

Expected: errors because `arm_mob_packet_capture` and `finish_mob_packet_capture` do not exist.

- [ ] **Step 3: Implement minimal thread-safe capture lifecycle**

Use an `RLock`, lazy-open the JSONL file on the first target-map packet, serialize `time.monotonic()`, `current_map`, opcode, packet length, and full hex, flush each record, and close/reset all state in `finish_mob_packet_capture`. Default paths use `config.MOB_PACKET_CAPTURE_DIR` and a timestamped `mob_packets_<map>_<timestamp>.jsonl` filename.

- [ ] **Step 4: Run packet observer tests and synchronize Android**

Run: `python -m unittest tests.test_mob_packet_observer -v`

Run: `python tools/sync_apk_python.py`

Expected: all packet observer tests pass and Android `client.py` contains the same lifecycle.

---

### Task 2: Replace sticky empty/full coverage with stationary probe policy

**Files:**
- Modify: `bot/config.py`
- Modify: `bot/mob_spots.py`
- Modify: `run_party_digioi.py`
- Modify: `tests/test_mob_spots.py`
- Modify: `tests/test_train_mob_scan_policy.py`
- Modify: `android/app/src/main/python/train_bot/*` through sync

**Interfaces:**
- Produces: `_needs_train_mob_probe(client, map_id, train_map) -> bool` and `_stationary_train_mob_probe(client, map_id, stop=None, seconds=None) -> list`.
- Consumes the capture lifecycle from Task 1.

- [ ] **Step 1: Write failing cache and policy tests**

Add tests proving `status="empty"` returns `None` from `load_complete_centers`, non-empty complete cache still wins, configured mob points return immediately without calling `scan_full_map`, and missing centers/config runs the stationary probe without navigation or `scan_full_map`. Inject a fake clock/sleep so the 60-second wait is instant in tests.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m unittest tests.test_mob_spots tests.test_train_mob_scan_policy -v`

Expected: empty cache currently returns `[]`, and the coordinator currently calls `scan_full_map`.

- [ ] **Step 3: Implement the minimal stationary policy**

Add shared defaults `MOB_PACKET_PROBE_SECONDS=60`, `MOB_PACKET_CAPTURE_MAX_PACKETS=50000`, and platform-specific `MOB_PACKET_CAPTURE_DIR`. Return only non-empty `status="complete"` center caches. Use configured mob points immediately. With neither source available, keep the leader at safe, switch the current channel while capture is armed, wait stop-aware for 60 seconds, close capture, log its path/count, and return no centers. Never invoke `scan_full_map` in the default coordinator flow.

- [ ] **Step 4: Arm capture before train routing**

In leader train startup, call `_needs_train_mob_probe` and arm the capture before the party map barrier or `_do_reform`, ensuring the final warp load is present. Always finish an armed capture on stop/disconnect/error paths through the existing account cleanup/finally section.

- [ ] **Step 5: Run focused policy/parity tests and synchronize Android**

Run: `python tools/sync_apk_python.py`

Run: `python -m unittest tests.test_mob_spots tests.test_train_mob_scan_policy tests.test_android_mob_scan_parity -v`

Expected: all pass with PC/Android parity.

---

### Task 3: Preserve the first learned warp safe

**Files:**
- Modify: `run_party_digioi.py`
- Modify: `tests/test_train_safe_policy.py`
- Modify: Android coordinator through sync

**Interfaces:**
- Changes `_capture_arrival_safe(client, map_id, came_from_other_map)` to return an existing fingerprint-valid cached safe without calling `save_safe`.

- [ ] **Step 1: Write the failing safe regression test**

Mock `load_safe` to return `(4110, 2510)`, invoke `_capture_arrival_safe` with `came_from_other_map=True` and a later client position, then assert the original safe is returned and `save_safe` is not called.

- [ ] **Step 2: Run the safe test and verify RED**

Run: `python -m unittest tests.test_train_safe_policy -v`

Expected: current code projects and overwrites the later position.

- [ ] **Step 3: Implement first-safe preservation and synchronize Android**

Load the fingerprint-valid safe before reading `client.pos`; return it immediately when present. Otherwise keep the existing arrival projection and atomic save.

- [ ] **Step 4: Run safe/routing tests**

Run: `python tools/sync_apk_python.py`

Run: `python -m unittest tests.test_train_safe_policy tests.test_train_routing_policy -v`

Expected: all pass and Android coordinator matches PC.

---

### Task 4: Source-only verification and test handoff

**Files:**
- Modify: `KNOWLEDGE.md`
- Do not modify generated release artifacts

**Interfaces:**
- Produces a source version the user can run with `pythonw gui.py` and a logged JSONL path for analysis.

- [ ] **Step 1: Document the failed full-scan evidence and probe workflow**

Record that map 20801 completed 124/124 stations with zero observed entities despite continuous random encounters, that combat positions are invalid evidence, and that the stationary raw probe supersedes automatic coverage pending protocol decoding.

- [ ] **Step 2: Run full source verification**

Run: `python -m unittest discover -s tests -v`

Expected: zero failures/errors.

- [ ] **Step 3: Verify source parity and Git scope**

Run: `python tools/sync_apk_python.py`

Run: `git diff --check` and confirm `aTSBot-drive/` plus runtime `mob_spots.json` remain untracked and untouched.

- [ ] **Step 4: Commit source changes without building**

Commit only source, tests, synchronized Android files, docs, and config. Do not run `build_product.py`, Gradle, push, or release upload.

## Self-review

- Spec coverage: automatic routing, capture-before-warp, stationary safe wait, raw target-map packets, no combat inference, no coverage walk, retryable empty cache, first-safe preservation, PC/APK parity, tests, and no-build handoff are covered.
- Placeholder scan: no deferred implementation placeholders are present.
- Type consistency: capture and stationary-probe method names are consistent across tasks.
