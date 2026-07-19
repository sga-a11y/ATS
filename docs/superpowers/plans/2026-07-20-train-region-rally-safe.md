# Train Region Rally Safe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive one nearby walkable rally safe outside each learned monster patrol region and persist aligned safe/mob pairs directly in `train_maps.json` on PC and Android.

**Architecture:** Add a deterministic BFS safe-search primitive to `GroundMapStore`, expose grouped learned regions from `mob_scanner`, and atomically upsert complete pairs through a focused train-map store. Android merges the bundled baseline into a writable app-data `train_maps.json`; the coordinator updates both disk and the active in-memory map before party rally.

**Tech Stack:** Python 3.12, `unittest`, existing `GroundMapStore`, JSON + `os.replace`, Android Chaquopy/Kotlin asset materialization.

## Global Constraints

- `safe[i]` corresponds to `mobs[i]` for automatically learned entries.
- A regional safe must be walkable and at least 200 world pixels from every observed monster point.
- Search no farther than 600 world pixels of walkable path; otherwise use the post-warp safe.
- Existing non-empty configured `mobs` are never overwritten automatically.
- Interrupted or incomplete probes never alter `train_maps.json`.
- PC and Android source behavior stay synchronized.
- Do not build EXE or APK until the user finishes source testing.

---

### Task 1: Deterministic walkable safe search

**Files:**
- Modify: `bot/pathfind.py:181-276`
- Test: `tests/test_mob_scan_coverage.py`

**Interfaces:**
- Consumes: `GroundMapStore.world_to_block`, `block_to_world`, decoded collision grid.
- Produces: `GroundMapStore.nearest_walkable_outside(map_id: int, start: Point, hazards: Iterable[Point], clearance: float = 200, max_path: float = 600) -> Point | None`.

- [ ] **Step 1: Write failing BFS tests**

Add tests proving a point inside patrol clearance is rejected, a wall forces the reachable-side candidate, and no candidate inside 600 returns `None`:

```python
def test_nearest_walkable_outside_patrol_clearance(self):
    safe = self.store.nearest_walkable_outside(
        99, (90, 90), [(90, 90), (110, 90)], clearance=40, max_path=120
    )
    self.assertIsNotNone(safe)
    self.assertGreaterEqual(min(math.dist(safe, p) for p in [(90, 90), (110, 90)]), 40)

def test_nearest_walkable_outside_does_not_cross_wall(self):
    safe = self.store.nearest_walkable_outside(
        99, (90, 90), [(90, 90)], clearance=60, max_path=160
    )
    self.assertLess(safe[0], 130)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_mob_scan_coverage -v`

Expected: `AttributeError: 'GroundMapStore' object has no attribute 'nearest_walkable_outside'`.

- [ ] **Step 3: Implement layered BFS**

Add a four-direction BFS from the nearest valid start block. Examine complete BFS layers so ties are deterministic; reject blocked blocks, path length beyond `ceil(max_path / 20)`, and candidates whose Euclidean distance to any hazard is below clearance:

```python
def nearest_walkable_outside(self, map_id, start, hazards,
                             clearance=200.0, max_path=600.0):
    m = self.get(map_id)
    if m is None:
        return None
    origin = _empty_target(m["grid"], m["grid_w"], m["grid_h"],
                           self.world_to_block(map_id, start))
    if origin is None:
        return None
    hazards = [tuple(map(int, point)) for point in hazards]
    limit = max(0, math.ceil(float(max_path) / 20.0))
    queue = deque([(origin, 0)])
    seen = {origin}
    current_depth = -1
    valid = []
    while queue:
        block, depth = queue.popleft()
        if depth != current_depth and valid:
            return min(valid, key=lambda item: (item[0], item[1][1], item[1][0]))[1]
        if depth > limit:
            break
        current_depth = depth
        point = self.block_to_world(map_id, block)
        nearest = min((math.dist(point, hazard) for hazard in hazards), default=float("inf"))
        if nearest >= float(clearance):
            valid.append((math.dist(point, start), point))
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nxt = block[0] + dx, block[1] + dy
            if nxt in seen or _blocked(m["grid"], m["grid_w"], m["grid_h"], *nxt):
                continue
            seen.add(nxt)
            queue.append((nxt, depth + 1))
    return min(valid, key=lambda item: (item[0], item[1][1], item[1][0]))[1] if valid else None
```

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python -m unittest tests.test_mob_scan_coverage tests.test_pathfind -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add bot/pathfind.py tests/test_mob_scan_coverage.py
git commit -m "feat: find rally safes outside patrol regions"
```

---

### Task 2: Preserve patrol groups and compute aligned regions

**Files:**
- Modify: `bot/mob_scanner.py`
- Test: `tests/test_mob_scanner_model.py`

**Interfaces:**
- Consumes: `GroundMapStore.nearest_walkable_outside` from Task 1.
- Produces: `LearnedRegion(center: CenterCandidate, safe: Point | None)` and `compute_regions(session, ground, start, fallback_safe=None, now=None, stable_only=True) -> list[LearnedRegion]`.

- [ ] **Step 1: Write failing region tests**

Use a recording ground object to prove all observed patrol points are passed as hazards and output order keeps safe aligned with center:

```python
class SafeGround(ProjectingGround):
    def __init__(self):
        self.calls = []
    def nearest_walkable_outside(self, map_id, center, hazards, clearance, max_path):
        self.calls.append((map_id, center, tuple(hazards), clearance, max_path))
        return center[0] + 200, center[1]

def test_regions_pair_each_center_with_safe_outside_all_traces(self):
    session = self._session()
    feed_cycle(session, b"monster1", [(310, 850), (430, 930), (530, 830)])
    feed_cycle(session, b"monster2", [(1050, 430), (1150, 530), (1250, 430)])
    ground = SafeGround()
    regions = compute_regions(session, ground, (410, 1050), now=30.0)
    self.assertEqual(len(regions), 2)
    self.assertTrue(all(region.safe[0] == region.center.point[0] + 200 for region in regions))
    self.assertTrue(all(len(call[2]) == 6 for call in ground.calls))
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_mob_scanner_model -v`

Expected: import error for missing `LearnedRegion`/`compute_regions`.

- [ ] **Step 3: Refactor grouping once and implement regional safes**

Extract the union-find body currently inside `compute_centers` into `_trace_groups`. Implement:

```python
@dataclass(frozen=True)
class LearnedRegion:
    center: CenterCandidate
    safe: Point | None

def compute_regions(session, ground, start, fallback_safe=None, now=None,
                    stable_only=True):
    now = time.monotonic() if now is None else float(now)
    traces = session.stable_traces(now) if stable_only else session.bounded_traces()
    groups = _trace_groups(traces, session.merge_distance, ground, session.map_id)
    hazards = [point for trace in traces for point in trace.unique_points]
    regions = []
    for group in groups:
        center = _center_candidate(group, ground, session.map_id, start)
        if center is None:
            continue
        safe = ground.nearest_walkable_outside(
            session.map_id, center.point, hazards, clearance=200, max_path=600
        ) if ground is not None else None
        regions.append(LearnedRegion(center, safe or fallback_safe))
    return sorted(regions, key=lambda region: (
        -region.center.monster_count, -region.center.confidence,
        region.center.point[1], region.center.point[0]
    ))
```

Make `compute_centers` return `[region.center for region in compute_regions(...)]` without changing existing callers.

- [ ] **Step 4: Run model and capture regressions**

Run: `python -m unittest tests.test_mob_scanner_model tests.test_mob_scanner_capture -v`

Expected: all tests pass and legacy center ordering is unchanged.

- [ ] **Step 5: Commit**

```powershell
git add bot/mob_scanner.py tests/test_mob_scanner_model.py
git commit -m "feat: pair learned patrol centers with rally safes"
```

---

### Task 3: Atomic writable train-map store

**Files:**
- Create: `bot/train_maps_store.py`
- Modify: `bot/config.py`
- Modify: `android/app/src/main/python/train_bot/config.py`
- Modify: `android/app/src/main/java/com/tsbot/android/BotForegroundService.kt`
- Modify: `tools/sync_apk_python.py`
- Test: `tests/test_train_map_store.py`
- Test: `tests/test_train_map_config.py`

**Interfaces:**
- Consumes: complete aligned `safes: Sequence[Point]`, `centers: Sequence[Point]`.
- Produces: `save_learned_regions(path: str, map_id: int, safes, centers) -> bool`.

- [ ] **Step 1: Write failing atomic-store tests**

```python
def test_save_regions_preserves_name_and_other_maps(self):
    self.write({"maps": {"20801": {"name": "RCN1", "safe": [], "mobs": []},
                         "99": {"name": "keep", "safe": [], "mobs": []}}})
    saved = save_learned_regions(self.path, 20801, [(100, 200)], [(300, 400)])
    data = self.read()
    self.assertTrue(saved)
    self.assertEqual(data["maps"]["20801"]["name"], "RCN1")
    self.assertEqual(data["maps"]["20801"]["safe"], [[100, 200]])
    self.assertEqual(data["maps"]["20801"]["mobs"], [[300, 400]])
    self.assertIn("99", data["maps"])
    self.assertFalse(os.path.exists(self.path + ".tmp"))

def test_nonempty_configured_mobs_are_not_overwritten(self):
    self.write({"maps": {"20801": {"safe": [[1, 2]], "mobs": [[3, 4]]}}})
    self.assertFalse(save_learned_regions(self.path, 20801, [(10, 20)], [(30, 40)]))
```

- [ ] **Step 2: Run store tests and verify RED**

Run: `python -m unittest tests.test_train_map_store -v`

Expected: import error for missing `bot.train_maps_store`.

- [ ] **Step 3: Implement guarded atomic upsert**

```python
def save_learned_regions(path, map_id, safes, centers):
    safes = _points(safes)
    centers = _points(centers)
    if not centers or len(safes) != len(centers):
        return False
    with _LOCK:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        maps = data.setdefault("maps", {})
        entry = maps.setdefault(str(int(map_id)), {"name": str(map_id)})
        if entry.get("mobs"):
            return False
        entry["safe"] = safes
        entry["mobs"] = centers
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    return True
```

Set desktop `TRAIN_MAPS_PATH = os.path.join(_base_dir(), "train_maps.json")` and have `_load_train_maps` read it.

- [ ] **Step 4: Make Android train maps writable**

In `BotForegroundService.materializeSmartNavAssets`, copy bundled `train_maps.json` to `filesDir/train_maps.json` only when missing. In Android config set `TRAIN_MAPS_PATH = os.path.join(_app_dir(), "train_maps.json")`; load bundled baseline and local JSON, preserving local non-empty `mobs` while adding/updating baseline entries whose local `mobs` are empty. Atomically rewrite the merged local file.

Add `train_maps_store.py` to `tools/sync_apk_python.py::SHARED`.

- [ ] **Step 5: Run store/config tests**

Run: `python -m unittest tests.test_train_map_store tests.test_train_map_config tests.test_navigation_assets -v`

Expected: all tests pass; Android config points at app-data `train_maps.json`.

- [ ] **Step 6: Commit**

```powershell
git add bot/train_maps_store.py bot/config.py android/app/src/main/python/train_bot/config.py android/app/src/main/java/com/tsbot/android/BotForegroundService.kt tools/sync_apk_python.py tests/test_train_map_store.py tests/test_train_map_config.py tests/test_navigation_assets.py
git commit -m "feat: persist learned regions in train maps"
```

---

### Task 4: Promote completed probe results and use paired safes immediately

**Files:**
- Modify: `run_party_digioi.py:120-205,1065-1115`
- Modify via sync: `android/app/src/main/python/train_bot/run_party_digioi.py`
- Test: `tests/test_train_mob_scan_policy.py`

**Interfaces:**
- Consumes: `compute_regions(...)`, `save_learned_regions(...)`, writable `config.TRAIN_MAPS_PATH`.
- Produces: probe return centers as before, while mutating `train_map["safe"]`/`["mobs"]` only after a complete successful write.

- [ ] **Step 1: Write failing coordinator test**

Patch `compute_regions` to return two aligned regions and assert the writer receives them, the active `train_map` is updated, and rally selection uses the paired safe:

```python
regions = [
    LearnedRegion(CenterCandidate((1000, 1000), 1, 0.8), (800, 1000)),
    LearnedRegion(CenterCandidate((3000, 2000), 1, 0.8), (2800, 2000)),
]
compute.return_value = regions
train_map = {"safe": [], "mobs": []}
centers = coordinator._stationary_train_mob_probe(
    client, 20801, train_map=train_map, seconds=60,
    clock=clock, sleep=sleeps.append,
)
self.assertEqual(centers, [(1000, 1000), (3000, 2000)])
self.assertEqual(train_map["safe"], [(800, 1000), (2800, 2000)])
self.assertEqual(train_map["mobs"], centers)
save.assert_called_once_with(config.TRAIN_MAPS_PATH, 20801,
                             train_map["safe"], centers)
```

- [ ] **Step 2: Run coordinator test and verify RED**

Run: `python -m unittest tests.test_train_mob_scan_policy -v`

Expected: `_stationary_train_mob_probe` rejects `train_map` or does not call persistence.

- [ ] **Step 3: Integrate region persistence**

Pass `train_map` into the probe. After capture finishes, call `compute_regions(..., fallback_safe=current arrival safe, stable_only=False)`. Require every region to have a safe; call `save_learned_regions`. On success update the active dict with tuple lists and save the same centers in `mob_spots.json` for backward compatibility. Log every pair:

```python
log.info("[%s] AUTO LEARN map %s: bai %s -> safe %s", label, map_id,
         region.center.point, region.safe)
```

After `_resolve_train_mob_centers`, refresh `train_safes[:]` from `tm["safe"]` so the current session selects the new nearest safe before rally.

- [ ] **Step 4: Sync Android and run policy/parity tests**

Run: `python tools/sync_apk_python.py`

Run: `python -m unittest tests.test_train_mob_scan_policy tests.test_android_mob_scan_parity -v`

Expected: all tests pass and Android coordinator uses relative imports.

- [ ] **Step 5: Commit**

```powershell
git add run_party_digioi.py android/app/src/main/python/train_bot/run_party_digioi.py tests/test_train_mob_scan_policy.py
git commit -m "feat: rally each learned train region at nearby safe"
```

---

### Task 5: Promote map 20801 regional safes and verify end-to-end

**Files:**
- Modify: `train_maps.json`
- Modify: `KNOWLEDGE.md`
- Test: `tests/test_train_map_config.py`

**Interfaces:**
- Consumes: latest map `20801` packet capture and `compute_regions`.
- Produces: nine aligned safe/mob pairs for Rừng Cửu Nguyên 1 in canonical `train_maps.json`.

- [ ] **Step 1: Add failing canonical-data assertions**

Extend the map 20801 test to require equal counts and each safe outside the recorded patrol clearance:

```python
entry = maps[20801]
self.assertEqual(len(entry["safe"]), len(entry["mobs"]))
self.assertEqual(len(entry["mobs"]), 9)
self.assertTrue(all(math.dist(safe, mob) <= 600
                    for safe, mob in zip(entry["safe"], entry["mobs"])))
```

- [ ] **Step 2: Run the canonical test and verify RED**

Run: `python -m unittest tests.test_train_map_config.TestTrainMapConfig.test_rung_cuu_nguyen_has_promoted_safe_and_mob_centers -v`

Expected: FAIL because only one safe exists for nine mobs.

- [ ] **Step 3: Replay the newest map 20801 capture**

Feed every record through `GameClient._observe_mob_packet`, call `compute_regions(..., stable_only=False)`, and print the aligned pairs. Verify each safe is at least 200 pixels from every `0x16/0200` observed position before updating JSON.

- [ ] **Step 4: Write the nine aligned pairs to `train_maps.json`**

Preserve the existing map name. Keep mob ordering deterministic from `compute_regions`; write the corresponding safe at the same index.

- [ ] **Step 5: Document confirmed protocol and persistence**

Update `KNOWLEDGE.md` with the `0x16/0200` safe derivation, 200-pixel clearance, aligned-array rule, and Android writable-file behavior.

- [ ] **Step 6: Run complete verification**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

Run: `git diff --check`

Expected: exit code 0.

- [ ] **Step 7: Commit**

```powershell
git add train_maps.json KNOWLEDGE.md tests/test_train_map_config.py
git commit -m "data: add regional safes for Rung Cuu Nguyen"
```

Do not build or publish. Hand the source back for Party 19 dev testing first.
