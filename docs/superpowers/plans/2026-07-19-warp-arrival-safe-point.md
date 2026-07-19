# Warp Arrival Safe Point Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let train parties route to a map with no configured safe, learn the actual post-warp position as safe, and avoid the route-less party shutdown shown on map 20801.

**Architecture:** Normalize empty safe lists correctly, allow smart routes to end at the final warp when no safe is known, then capture and persist the server-confirmed destination position. The coordinator resolves cached/configured/learned safe points through small helpers and shares the same Python implementation with Android.

**Tech Stack:** Python 3.12, `unittest`, existing `GroundMapStore`, `SmartWorldRouter`, JSON atomic cache, Chaquopy Android sync.

## Global Constraints

- Work directly on `master`, preserving the user's untracked `aTSBot-drive/` directory.
- Do not mutate `train_maps.json` at runtime.
- Cache only monster centers and one safe point; never cache entity traces or patrol geometry.
- Never overwrite safe from a session which logged in already inside the target map.
- Keep PC and Android behavior identical through `tools/sync_apk_python.py`.

---

### Task 1: Normalize empty safe and bootstrap smart routes

**Files:**
- Modify: `bot/config.py`
- Modify: `bot/smart_route.py`
- Modify: `bot/client.py`
- Test: `tests/test_train_map_config.py`
- Test: `tests/test_smart_route.py`

**Interfaces:**
- Produces: `TRAIN_MAPS[map_id]["safe"] == []` for JSON `"safe": []`.
- Produces: `SmartWorldRouter.build_route(dest_map: int, safe: tuple | None)` and matching client wrappers.

- [ ] **Step 1: Write failing tests**

Add a config loader test asserting map 20801 has `safe == []`. Add a smart-route test:

```python
def test_route_without_safe_stops_at_final_warp_arrival(self):
    route = self.router.build_route(20801, None)
    self.assertEqual(route["city"], 20001)
    self.assertEqual([leg["target_scene"] for leg in route["legs"]], [20000, 20801])
    self.assertIsNone(route["safe"])
    self.assertEqual(route["final_paths"], {})
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_train_map_config tests.test_smart_route -v`

Expected: empty safe currently equals `[()]`; `build_route(20801, None)` raises while indexing `safe`.

- [ ] **Step 3: Implement minimal support**

Normalize empty JSON safe explicitly:

```python
if not s:
    safes = []
elif isinstance(s[0], (list, tuple)):
    safes = [tuple(p) for p in s]
else:
    safes = [tuple(s)]
```

Make `_route_key`, cache methods, `build_route`, `_candidate_route`, and client wrappers accept `safe=None`. Store a distinct cache key such as `"20801:arrival"`. Skip the final destination-map path when safe is absent and keep `route["safe"] = None`. The executor must finish successfully after the final gate without calling `navigate_to` for a missing safe.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m unittest tests.test_train_map_config tests.test_smart_route tests.test_smart_route_execution -v`

Commit: `git commit -am "feat: route train parties without configured safe"`

---

### Task 2: Persist a fingerprint-valid arrival safe

**Files:**
- Modify: `bot/mob_spots.py`
- Modify: `tests/test_mob_spots.py`

**Interfaces:**
- Produces: `load_safe(map_id: int, fingerprint: str) -> tuple[int, int] | None`.
- Produces: `save_safe(map_id: int, fingerprint: str, safe: tuple[int, int]) -> None`.
- Existing scan save functions preserve the optional safe field.

- [ ] **Step 1: Write failing tests**

```python
def test_safe_round_trip_survives_incomplete_scan(self):
    mob_spots.save_safe(20801, "ground1", (4110, 2510))
    mob_spots.save_progress(20801, "ground1", [0], [], {"total": 2}, {})
    self.assertEqual(mob_spots.load_safe(20801, "ground1"), (4110, 2510))

def test_changed_fingerprint_invalidates_safe(self):
    mob_spots.save_safe(20801, "ground1", (4110, 2510))
    self.assertIsNone(mob_spots.load_safe(20801, "ground2"))
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_mob_spots -v`

Expected: FAIL because `save_safe` and `load_safe` do not exist.

- [ ] **Step 3: Implement minimal persistence**

`save_safe` atomically updates only the map fingerprint, `updated_at`, and `safe`. `_save` carries forward a matching entry's safe while replacing scan status/centers. `load_safe` validates the fingerprint and a two-number point before returning a tuple.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m unittest tests.test_mob_spots tests.test_full_map_mob_scan -v`

Commit: `git commit -am "feat: cache train map arrival safe"`

---

### Task 3: Capture arrival and prevent route-less shutdown

**Files:**
- Modify: `run_party_digioi.py`
- Create: `tests/test_train_safe_policy.py`
- Modify: `tests/test_train_routing_policy.py`

**Interfaces:**
- Produces: `_resolve_train_safe(client, map_id, configured_safes) -> tuple | None`.
- Produces: `_capture_arrival_safe(client, map_id, came_from_other_map) -> tuple | None`.
- Consumes: optional-safe smart route and `mob_spots.load_safe/save_safe`.

- [ ] **Step 1: Write failing policy tests**

Test that `_resolve_train_safe` prefers fingerprint-valid cache, then configured safe. Test that `_capture_arrival_safe` projects `client.pos` through `nearest_walkable_world`, saves it only when `came_from_other_map=True`, and leaves cached safe untouched when login began on the destination map. Extend `RecordingClient` to assert `_travel_to_train_map(client, 20801, None, None)` calls `follow_smart_route(20801, None)` before failing legacy fallback.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_train_safe_policy tests.test_train_routing_policy -v`

Expected: FAIL because safe resolver/capture helpers are absent and `_travel_to_train_map` assumes a tuple.

- [ ] **Step 3: Implement coordinator integration**

At train startup, resolve cached/configured safe before computing route availability. Smart routing remains possible whenever `SMART_WORLD_ROUTING` is enabled, even when safe is `None`. After the leader reaches `sc` from another map, capture the current `client.pos`, project it, save it, and set `st["rally_point"]`. Use this learned point for scanner origin/rally and share it with members. If arrival capture and both fallbacks are absent, set `leader_bad` with an explicit `khong lay duoc safe sau warp` reason; do not let a member independently call `stop_party` while the leader is still preparing a route.

- [ ] **Step 4: Verify GREEN and regressions**

Run: `python -m unittest tests.test_train_safe_policy tests.test_train_routing_policy tests.test_train_mob_scan_policy tests.test_smart_route_execution -v`

Expected: all PASS; map 20801 with empty safe is route-capable.

- [ ] **Step 5: Commit**

Commit: `git add run_party_digioi.py tests/test_train_safe_policy.py tests/test_train_routing_policy.py && git commit -m "fix: learn train safe after final warp"`

---

### Task 4: Android parity, full verification, and builds

**Files:**
- Modify via sync: `android/app/src/main/python/train_bot/config.py`
- Modify via sync: `android/app/src/main/python/train_bot/smart_route.py`
- Modify via sync: `android/app/src/main/python/train_bot/client.py`
- Modify via sync: `android/app/src/main/python/train_bot/mob_spots.py`
- Modify via sync: `android/app/src/main/python/train_bot/run_party_digioi.py`
- Modify: `tests/test_android_mob_scan_parity.py`
- Modify: `KNOWLEDGE.md`

**Interfaces:**
- Consumes all completed shared APIs.
- Produces verified PC ZIPs and Android debug APK.

- [ ] **Step 1: Synchronize and test parity**

Run: `python tools/sync_apk_python.py`

Add parity assertions for `load_safe`, `save_safe`, optional-safe routing, and arrival capture.

Run: `python -m unittest tests.test_android_mob_scan_parity -v`

- [ ] **Step 2: Document the confirmed failure chain**

Record that JSON empty safe was normalized to `[()]`, disabling smart-route construction and causing the first member to stop the party; subsequent disconnect messages were consequences.

- [ ] **Step 3: Run complete verification**

Run: `python -m unittest discover -s tests -v`

Expected: zero failures/errors.

- [ ] **Step 4: Build both products**

Run: `python build_product.py --no-upload`

Run from `android`: `.\gradlew.bat clean assembleDebug`

Expected: PC build exit 0, both ZIP archives test clean, Android reports `BUILD SUCCESSFUL`, and the APK contains the synchronized modules plus `Ground.mmg`.

- [ ] **Step 5: Commit final parity/docs**

Commit: `git add android/app/src/main/python KNOWLEDGE.md tests/test_android_mob_scan_parity.py && git commit -m "docs: record learned train safe flow"`

## Self-review

- Spec coverage: empty-safe bootstrap, actual post-warp capture, walkability projection, atomic persistence, fingerprint invalidation, relogin protection, explicit failure, PC/APK parity, and both builds are assigned.
- Root-cause coverage: the map 20801 `[()]` normalization bug and member-triggered party shutdown each have a regression test.
- Placeholder scan: no deferred implementation or unnamed test remains.
- Type consistency: all tasks use optional safe tuples, `load_safe`, `save_safe`, `_resolve_train_safe`, and `_capture_arrival_safe` consistently.
