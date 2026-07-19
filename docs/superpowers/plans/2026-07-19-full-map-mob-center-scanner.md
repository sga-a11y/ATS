# Full-map Mob Center Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fully scan a reachable training map until monster patrols repeat, reduce each discovered roaming area to one walkable center point, cache only those centers, and use them for training on both Windows and Android.

**Architecture:** Add collision-map coverage helpers, a pure thread-safe observation/model layer, and a small atomic center cache. `GameClient` forwards S2C entity spawn/move/player packets to an active observer; the leader runs the scanner before party rally selection, while members wait, then the existing train flow consumes cached centers exactly like configured mob points.

**Tech Stack:** Python 3.12 standard library (`threading`, `json`, `zlib`, `unittest`), existing TS Online protocol parser, `GroundMapStore`, Nuitka, Chaquopy, Gradle/JDK 17.

## Global Constraints

- Full-accuracy mode waits for bounded patrol waypoint repetition and an 8-second quiet window.
- Each observation station has a 90-second hard timeout and low-confidence stations receive one second pass.
- Coverage station stride is 320 world pixels horizontally and 240 world pixels vertically.
- A monster candidate needs at least three samples and two distinct coordinates.
- Patrols with a diameter above 800 world pixels are rejected as ambiguous.
- Patrol traces merge only within 200 world pixels and only when their collision-grid connection does not cross a wall.
- Runtime cache is `mob_spots.json` and persists center points plus scan-status metadata only; entity ids, waypoint traces, visit counts, polygons, bounding boxes, and cell masks are never persisted.
- Existing `train_maps.json` mob points are validation/fallback data, not the primary result after a complete scan.
- Missing Ground data or incomplete coverage must never be labeled a complete scan.
- PC and APK behavior and cache schema must remain identical.
- Existing smart world routing, party rally, combat, daily tasks, battle statistics, and reconnect recovery remain intact.

---

### Task 1: Add collision-map coverage and center projection primitives

**Files:**
- Modify: `bot/pathfind.py:18-188`
- Modify: `android/app/src/main/python/train_bot/pathfind.py` via `tools/sync_apk_python.py`
- Modify: `tools/sync_apk_python.py:14-18`
- Test: `tests/test_mob_scan_coverage.py`

**Interfaces:**
- Consumes: existing X-major collision bytes and `GroundMapStore.get(map_id)`.
- Produces: `GroundMapStore.world_to_block(map_id, point)`, `block_to_world(map_id, block)`, `reachable_blocks(map_id, start)`, `coverage_stations(map_id, start, stride_world=(320, 240))`, `nearest_walkable_world(map_id, point, reachable_from)`, and `map_fingerprint(map_id)`.

- [ ] **Step 1: Write failing coverage tests**

Create an in-memory `GroundMapStore` fixture with `__new__`, a 12x10 X-major grid, and a wall with one gap. Cover these exact behaviors:

```python
def test_coverage_stations_cover_only_start_component(self):
    stations = self.store.coverage_stations(99, (30, 30), (80, 80))
    self.assertTrue(stations)
    self.assertTrue(all(self.store.find_world_path(99, (30, 30), p) for p in stations))
    self.assertNotIn((210, 30), stations)  # isolated side of the test wall

def test_nearest_walkable_center_stays_in_reachable_component(self):
    point = self.store.nearest_walkable_world(99, (130, 90), (30, 30))
    self.assertIsNotNone(point)
    self.assertIsNotNone(self.store.find_world_path(99, (30, 30), point))

def test_map_fingerprint_changes_with_map_blob(self):
    before = self.store.map_fingerprint(99)
    self.store.data = self.store.data[:-1] + bytes([self.store.data[-1] ^ 1])
    self.assertNotEqual(before, self.store.map_fingerprint(99))
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_mob_scan_coverage -v`

Expected: errors stating the new `GroundMapStore` methods do not exist.

- [ ] **Step 3: Implement shared coordinate/component helpers**

Factor the current centered-map conversion out of `find_world_path`, preserve the game's 20-pixel block rules, flood-fill only four-direction walkable neighbors, and select one station nearest the center of every reachable stride bucket. Order buckets by Y and alternate X direction per row.

Use this public shape:

```python
def reachable_blocks(self, map_id, start):
    """Return set[(bx, by)] in the four-way component containing start."""

def coverage_stations(self, map_id, start, stride_world=(320, 240)):
    """Return serpentine world points, one per reachable coarse bucket."""

def nearest_walkable_world(self, map_id, point, reachable_from):
    """Project point to the nearest block in reachable_from's component."""

def map_fingerprint(self, map_id):
    """Return lowercase 8-digit CRC32 of the indexed .map entry bytes."""
```

- [ ] **Step 4: Run coverage and existing pathfinding tests**

Run: `python -m unittest tests.test_mob_scan_coverage tests.test_pathfind -v`

Expected: all tests PASS and existing A*/smoothing behavior remains unchanged.

- [ ] **Step 5: Synchronize the pathfinding module to APK and commit**

Run: `python tools/sync_apk_python.py`

Run: `python -m unittest tests.test_mob_scan_coverage tests.test_navigation_assets -v`

Expected: PASS; Android `pathfind.py` contains the same new methods.

Commit:

```bash
git add bot/pathfind.py tools/sync_apk_python.py tests/test_mob_scan_coverage.py android/app/src/main/python/train_bot/pathfind.py
git commit -m "feat: add full map coverage primitives"
```

### Task 2: Implement patrol observation, stabilization, grouping, and centers

**Files:**
- Create: `bot/mob_scanner.py`
- Modify: `tools/sync_apk_python.py:14-18`
- Test: `tests/test_mob_scanner_model.py`
- Test: `tests/test_mob_scanner_capture.py`

**Interfaces:**
- Consumes: `(map_id, entity, x, y, timestamp)` observations and an optional `GroundMapStore`.
- Produces: `MobScanSession`, `PatrolTrace`, `CenterCandidate`, and `compute_centers(session, ground, start)`.

- [ ] **Step 1: Write failing model tests**

Test that player/self/party entities are excluded even if movement arrived first, two bounded repeating patrols stabilize after the quiet window, a one-off mover is ignored, a route over 800 pixels is rejected, overlapping patrols merge, separated patrols remain separate, and center projection returns a reachable world coordinate.

Use the following public calls in tests:

```python
session = MobScanSession(map_id=11013, self_entity=b"self0000", party_entities=set())
session.observe_spawn(entity, 11013, x, y, now)
session.observe_move(entity, 11013, x, y, now)
session.mark_player(entity)
self.assertTrue(session.station_stable(now + 8.1))
centers = compute_centers(session, ground=None, start=(410, 1050))
```

- [ ] **Step 2: Run model tests and verify RED**

Run: `python -m unittest tests.test_mob_scanner_model -v`

Expected: import failure for `bot.mob_scanner`.

- [ ] **Step 3: Implement the thread-safe observation model**

Implement `PatrolTrace` with sample count, ordered unique waypoints, observed edges, repeated-edge count, `last_new_at`, and diameter. Protect `MobScanSession` mutations with `threading.RLock` because the receive thread writes while the scanner thread reads.

Stability must require all of:

```python
sample_count >= 3
len(unique_points) >= 2
repeated_edge_count >= 1
now - last_new_at >= quiet_seconds
diameter <= max_patrol_diameter
```

`mark_player` must remove any trace already collected for that entity. All observations with a different map id or invalid coordinates are ignored.

- [ ] **Step 4: Implement in-memory grouping and medoid centers**

Group traces whose minimum waypoint distance is at most 200 pixels. When Ground is present, require a collision-clear local path between the closest waypoint pair before merging. Compute each area's center as the waypoint minimizing the sum of distances to the area's unique waypoints, then project it through `nearest_walkable_world`. Return only:

```python
@dataclass(frozen=True)
class CenterCandidate:
    point: tuple[int, int]
    monster_count: int
    confidence: float
```

Do not expose or serialize a polygon, bounding box, entity id, or waypoint list.

- [ ] **Step 5: Add the real capture regression**

Load `captures/bachai_route_20260716.pcap` through `analyze_pcap.load_frames`, mark entities from rich S2C `0x0c` records as players, and feed map `11013` S2C `0x07`/`0x06` positions from the final segment into `MobScanSession` with synthetic monotonically increasing timestamps.

Assert exactly two stable centers. One must be within 180 pixels of `(530, 930)` and the other within 120 pixels of `(1150, 530)`. Also assert no player-profile entity contributes to either center's monster count.

- [ ] **Step 6: Run model and capture tests, synchronize, and commit**

Run: `python -m unittest tests.test_mob_scanner_model tests.test_mob_scanner_capture -v`

Expected: all tests PASS.

Add `mob_scanner.py` to `SHARED` in `tools/sync_apk_python.py`, then run: `python tools/sync_apk_python.py`.

Commit:

```bash
git add bot/mob_scanner.py tools/sync_apk_python.py tests/test_mob_scanner_model.py tests/test_mob_scanner_capture.py android/app/src/main/python/train_bot/mob_scanner.py
git commit -m "feat: infer monster area center points"
```

### Task 3: Add the minimal atomic center cache and full-scan runner

**Files:**
- Create: `bot/mob_spots.py`
- Modify: `bot/mob_scanner.py`
- Modify: `tools/sync_apk_python.py`
- Test: `tests/test_mob_spots.py`
- Test: `tests/test_full_map_mob_scan.py`

**Interfaces:**
- Consumes: `GroundMapStore.coverage_stations`, `GameClient.navigate_to`, active `MobScanSession`, scanner config values, and `app_dir()`.
- Produces: `load_complete_centers(map_id, fingerprint) -> list[tuple[int, int]] | None`, `save_progress(...)`, `save_complete(...)`, and `scan_full_map(client, map_id, seed_points=(), stop=None) -> ScanResult`.

- [ ] **Step 1: Write failing cache tests**

Patch the cache path to a temporary directory and test atomic round-trip, fingerprint invalidation, incomplete scans returning `None` from `load_complete_centers`, and exact schema minimization:

```python
self.assertEqual(set(saved_map), {
    "fingerprint", "status", "updated_at", "coverage", "settings", "centers"
})
self.assertEqual(saved_map["centers"], [[530, 930], [1150, 530]])
serialized = json.dumps(saved_map)
for forbidden in ("entity", "waypoint", "polygon", "bounds", "trace"):
    self.assertNotIn(forbidden, serialized.lower())
```

- [ ] **Step 2: Implement `mob_spots.py`**

Use schema version 1 and `app_dir()/mob_spots.json`. Write through `mob_spots.json.tmp` followed by `os.replace`. Persist completed-station integer indices inside coverage metadata for resume, but never persist station coordinates, packet observations, or route geometry.

Use these signatures:

```python
def load_complete_centers(map_id: int, fingerprint: str) -> list[tuple[int, int]] | None: ...
def load_progress(map_id: int, fingerprint: str) -> dict: ...
def save_progress(map_id: int, fingerprint: str, completed_stations, centers, coverage, settings): ...
def save_complete(map_id: int, fingerprint: str, centers, coverage, settings): ...
```

- [ ] **Step 3: Write failing full-runner tests with a fake client**

The fake client records navigation, exposes a fake ground store, and injects repeating entity movement whenever a station is reached. Test cache hit skips every navigation call, a first pass visits every station, low-confidence stations receive exactly one second visit, stop/disconnect saves incomplete progress, missing Ground returns a non-complete result, and final persisted data contains center points only.

- [ ] **Step 4: Implement `scan_full_map`**

The runner must:

1. return a matching complete cache immediately;
2. derive or resume the coverage station list;
3. call `client.begin_mob_observation(session)`;
4. navigate to each unfinished station with `flee=True`;
5. wait until `session.station_stable(time.monotonic())` or 90 seconds;
6. save provisional mob-area centers and completed station indices;
7. revisit timed-out/low-confidence stations once;
8. compute/rank centers, save complete only when meaningful reachable coverage is complete;
9. always call `client.end_mob_observation(session)` in `finally`.

Return:

```python
@dataclass(frozen=True)
class ScanResult:
    status: str  # "cached", "complete", "incomplete", "empty", "unavailable"
    centers: tuple[CenterCandidate, ...]
    visited: int
    total: int
```

- [ ] **Step 5: Run tests, synchronize both modules, and commit**

Run: `python -m unittest tests.test_mob_spots tests.test_full_map_mob_scan -v`

Expected: all tests PASS.

Add `mob_spots.py` to `SHARED`, run `python tools/sync_apk_python.py`, then commit:

```bash
git add bot/mob_spots.py bot/mob_scanner.py tools/sync_apk_python.py tests/test_mob_spots.py tests/test_full_map_mob_scan.py android/app/src/main/python/train_bot/mob_spots.py android/app/src/main/python/train_bot/mob_scanner.py
git commit -m "feat: cache full scan monster centers"
```

### Task 4: Forward live entity packets into the active scanner

**Files:**
- Modify: `bot/client.py:680-745,1149-1186`
- Modify: `android/app/src/main/python/train_bot/client.py` via `tools/sync_apk_python.py`
- Test: `tests/test_mob_packet_observer.py`

**Interfaces:**
- Consumes: full incoming packet bytes in `GameClient._handle_packet` and `MobScanSession` methods from Task 2.
- Produces: `GameClient.begin_mob_observation(session)` and `end_mob_observation(session)`.

- [ ] **Step 1: Write failing packet-offset tests**

Instantiate `GameClient` without a socket, attach a recording observer, and feed full protocol frames proving:

```python
S2C 0x07 -> observe_spawn(entity, map_id, x, y, now)
S2C 0x06 subtype 0100 -> observe_move(entity, current_map, x, y, now)
S2C 0x0c rich 0000 record -> mark_player(entity)
self entity and known party entities -> excluded by the session
malformed/short packets -> no callback and no exception
```

Use the confirmed offsets: `0x07` entity `pkt[9:17]`, map `pkt[17:19]`, X `pkt[19:21]`, Y `pkt[21:23]`; `0x06` entity `pkt[9:17]`, X `pkt[18:20]`, Y `pkt[20:22]`; rich `0x0c` entity `pkt[9:17]`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m unittest tests.test_mob_packet_observer -v`

Expected: missing observation methods/callbacks.

- [ ] **Step 3: Implement the minimal receive hook**

Initialize `self._mob_observer = None` and `self._mob_observer_lock = threading.Lock()`. Snapshot the observer under the lock, then call it outside the lock so packet receive cannot deadlock with scanner reads. Catch observer exceptions at debug level and never interrupt normal packet processing.

`begin_mob_observation` must replace any previous observer; `end_mob_observation` must clear only when the passed session is still active.

- [ ] **Step 4: Run tests, synchronize, and commit**

Run: `python -m unittest tests.test_mob_packet_observer tests.test_mob_scanner_capture -v`

Expected: PASS.

Run: `python tools/sync_apk_python.py`.

Commit:

```bash
git add bot/client.py tests/test_mob_packet_observer.py android/app/src/main/python/train_bot/client.py
git commit -m "feat: observe live monster movement packets"
```

### Task 5: Integrate cached/scanned centers into party train mode

**Files:**
- Modify: `bot/config.py:68-86`
- Modify: `android/app/src/main/python/train_bot/config.py:335-350`
- Modify: `run_party_digioi.py:325-372,858-914,1149-1200`
- Modify: `android/app/src/main/python/train_bot/run_party_digioi.py` via `tools/sync_apk_python.py`
- Test: `tests/test_train_mob_scan_policy.py`
- Test: `tests/test_android_mob_scan_parity.py`

**Interfaces:**
- Consumes: `scan_full_map`, `load_complete_centers`, existing `tm["safe"]`, `tm["mobs"]`, `mob_index`, `st["mob_spot"]`, and party stop/reform signals.
- Produces: leader-selected cached/scanned center in the existing party state and unchanged downstream rally/training behavior.

- [ ] **Step 1: Add exact shared configuration defaults**

Add these values to desktop and Android config:

```python
MOB_SCAN_ENABLED = True
MOB_SCAN_STATION_STRIDE = (320, 240)
MOB_SCAN_QUIET_SECONDS = 8.0
MOB_SCAN_STATION_TIMEOUT = 90.0
MOB_SCAN_MIN_SAMPLES = 3
MOB_SCAN_MAX_PATROL_DIAMETER = 800
MOB_SCAN_MERGE_DISTANCE = 200
MOB_SCAN_SECOND_PASS = True
MOB_SPOTS_CACHE_PATH = os.path.join(_base_dir(), "mob_spots.json")  # desktop
```

Android uses `_app_dir()` for `MOB_SPOTS_CACHE_PATH`.

- [ ] **Step 2: Write failing train policy tests**

Extract a small helper `_resolve_train_mob_centers(client, map_id, tm, stop)` and test:

```python
valid complete cache -> return cached centers, do not scan
no cache + successful scan -> return scanned centers
scan unavailable/incomplete -> return configured tm["mobs"] fallback
complete empty scan -> return [] and do not invent a point
stop during scan -> return fallback without marking complete
```

Also test that member wait for `rally_ready` is stop-aware and has no 60-second timeout, because full scanning may take many minutes.

- [ ] **Step 3: Integrate leader-only scanning before rally selection**

When the leader reaches the train map, resolve centers before choosing `mob_index`. Members remain at the existing safe point and wait until the leader sets `rally_ready`. Use resolved centers in place of `tm["mobs"]`; preserve explicit index and random `-1` selection semantics.

Before a live scan, switch channel once without calling `combat_ready()` so channel reset suppresses combat-active state. After the existing party is formed and the leader reaches the chosen center, the unchanged `_start_training` path calls `combat_ready()` and restores aggro.

Keep existing `MOB_PATHS` only for configured fallback spots. A newly scanned center always uses smart `navigate_to` from the rally point.

- [ ] **Step 4: Add PC/APK parity tests and synchronize coordinator**

Assert `mob_scanner.py`, `mob_spots.py`, `client.py`, and rewritten coordinator behavior are present in Android; assert both configs expose identical numeric scan defaults.

Run: `python tools/sync_apk_python.py`.

Run: `python -m unittest tests.test_train_mob_scan_policy tests.test_android_mob_scan_parity -v`

Expected: PASS.

- [ ] **Step 5: Run coordinator regression tests and commit**

Run: `python -m unittest tests.test_train_routing_policy tests.test_smart_route_execution tests.test_train_block_stats tests.test_train_mob_scan_policy -v`

Expected: PASS and no current party-train routing behavior regresses.

Commit:

```bash
git add bot/config.py run_party_digioi.py android/app/src/main/python/train_bot/config.py android/app/src/main/python/train_bot/run_party_digioi.py tests/test_train_mob_scan_policy.py tests/test_android_mob_scan_parity.py
git commit -m "feat: scan and use monster centers in train mode"
```

### Task 6: Document protocol findings and verify both products

**Files:**
- Modify: `KNOWLEDGE.md:335-350`
- Modify: `build_product.py:37-48` only if packaging validation needs to assert new shared modules
- Test: `tests/test_mob_scanner_capture.py`
- Test: complete Python suite
- Generated: `aTSBot/aTSBot.exe`, `aTSBot.zip`, `aTSBot-drive.zip`
- Generated: `android/app/build/outputs/apk/debug/aTSBot-<version>-debug.apk`

**Interfaces:**
- Consumes: completed shared implementation and existing build pipelines.
- Produces: documented packet layouts, verified Windows artifacts, and verified Android APK.

- [ ] **Step 1: Update confirmed reverse-engineering notes**

Record the confirmed `0x06`, `0x07`, and rich `0x0c` offsets, the map `11013` waypoint evidence, the two inferred center neighborhoods, player exclusion rule, and the rule that only center points are cached. Explicitly retain the note that `Ground.mmg` has no spawn list.

- [ ] **Step 2: Run the complete Python suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with zero failures/errors.

- [ ] **Step 3: Verify Android source parity and imports**

Run: `python tools/sync_apk_python.py`

Run: `python -m unittest tests.test_android_mob_scan_parity tests.test_navigation_assets -v`

Expected: PASS.

- [ ] **Step 4: Build and verify desktop artifacts**

Run: `python build_product.py --no-upload`

Expected: exit code 0; a timestamped EXE, unencrypted updater `aTSBot.zip`, and password-protected `aTSBot-drive.zip` using password `aTSBot`. Confirm `mob_spots.json` is not shipped as seeded data and is created only at runtime.

- [ ] **Step 5: Build and verify APK**

Run from `android`: `./gradlew.bat clean assembleDebug`

Expected: `BUILD SUCCESSFUL`; APK name follows `aTSBot-1.1.<timestamp>-debug.apk`, contains `train_bot/mob_scanner.py`, `train_bot/mob_spots.py`, and `train_bot_data/gamedata/Ground.mmg`.

- [ ] **Step 6: Commit documentation and final verification state**

```bash
git add KNOWLEDGE.md build_product.py
git commit -m "docs: record monster patrol scan protocol"
```

Do not add generated EXE/APK/ZIP files to the source repository unless the existing release workflow explicitly tracks them.

## Self-review

- Spec coverage: packet collection, full-map coverage, full stabilization, second pass, player exclusion, wall-aware grouping, center-only cache, resume/invalidation, leader integration, fallback behavior, Windows/Android parity, protocol documentation, and both builds are assigned to concrete tasks.
- Placeholder scan: the plan contains no `TBD`, deferred implementation, generic error-handling instruction, or unnamed test step.
- Type consistency: Tasks 2-5 consistently use `MobScanSession`, `CenterCandidate`, `ScanResult`, `scan_full_map`, and the four `mob_spots` cache functions with the signatures defined above.
