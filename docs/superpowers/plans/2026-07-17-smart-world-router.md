# Smart World Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make train mode automatically select the nearest teleport city and travel through collision-safe scene/gate legs to any configured train map, with reconnect cache and temporary handwritten-route fallback.

**Architecture:** An offline builder converts `Warp_C.dat`, `DoorGroupData.dat`, and `Eve.emg` into a compact versioned `world_nav.json`. Runtime `WorldNavStore` performs cached graph searches, while `SmartWorldRouter` combines graph legs with `GroundMapStore` A* paths and persists structural routes plus start-sensitive local waypoints in `smart_routes.json`.

**Tech Stack:** Python 3.12 standard library, `unittest`, existing `bot.pathfind.GroundMapStore`, JSON assets, binary little-endian parsers.

## Global Constraints

- Smart routing runs before `train_routes.json`; handwritten routines are fallback only during live validation.
- Existing direct-city, event, dungeon, and Di Gioi flows must not change.
- Missing data, unreachable gates, or unexpected scenes must never trigger speculative movement, gate packets, or `go_to_town()` with a non-city map ID.
- Cache writes are atomic and entries are invalidated by navigation-data fingerprint changes.
- Stop and reform callbacks remain active during waits and movement legs.
- Runtime does not parse the 10 MB `Eve.emg`; only the offline builder does.

---

### Task 1: Build the compact world-navigation asset

**Files:**
- Create: `tools/build_world_nav.py`
- Create: `tests/test_build_world_nav.py`
- Create: `world_nav.json`

**Interfaces:**
- Consumes: raw `gamedata/Warp_C.dat`, `gamedata/DoorGroupData.dat`, and `gamedata/Eve.emg`.
- Produces: `parse_warps(data: bytes, flags_by_city: dict[int, int]) -> list[dict]`, `parse_door_graph(data: bytes) -> list[dict]`, `parse_eve_index(data: bytes) -> dict[int, tuple[int, int]]`, `parse_eve_doors(data: bytes, offset: int) -> dict[int, dict]`, and `build_world_nav(...) -> dict`.
- Produces asset schema: `{"version":1,"fingerprint":"...","cities":[],"edges":[],"gates":{}}`.

- [ ] **Step 1: Write failing parser tests**

```python
import struct
import unittest

from tools.build_world_nav import parse_door_graph, parse_eve_doors, parse_warps


class TestWorldNavBuilder(unittest.TestCase):
    def test_parse_warp_record(self):
        raw = struct.pack("<iIHHii", 1, 21707, 14001, 11810, 770, 610)
        self.assertEqual(parse_warps(raw, {14001: 6}), [{
            "city": 14001, "flag": 6, "mark": 11810,
            "arrival": [770, 610], "name_id": 21707,
        }])

    def test_parse_door_edge(self):
        raw = struct.pack("<iBiB4B", 14001, 1, 22000, 1, 1, 2, 1, 1)
        self.assertEqual(parse_door_graph(raw), [{
            "from": 14001001, "to": 22000001,
            "scene": 14001, "target_scene": 22000,
            "door": 1, "priority": 2,
        }])

    def test_parse_door_center_from_minimal_event(self):
        # EventData: zero NPCs, zero goods, one door.
        raw = (struct.pack("<iHHHH", 0, 0, 1, 17, 1) + b"\x06" +
               struct.pack("<iiiiBHHB", 26, 122, 6, 9, 1, 606, 2429, 0))
        self.assertEqual(parse_eve_doors(raw, 0)[17]["center"], [560, 2510])
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_build_world_nav -v`

Expected: `ModuleNotFoundError: No module named 'tools.build_world_nav'`.

- [ ] **Step 3: Implement the minimal binary parsers and builder**

```python
def parse_warps(data, flags_by_city):
    count = struct.unpack_from("<i", data)[0]
    result = []
    for index in range(count):
        name_id, city, mark, x, y = struct.unpack_from("<IHHii", data, 4 + index * 16)
        result.append({"city": city, "flag": flags_by_city[city], "mark": mark,
                       "arrival": [x, y], "name_id": name_id})
    return result


def parse_eve_doors(data, offset):
    cursor = skip_npcs_and_goods(data, offset)
    count = struct.unpack_from("<H", data, cursor)[0]
    cursor += 2
    doors = {}
    for _ in range(count):
        door_id, event_count = struct.unpack_from("<HH", data, cursor)
        cursor += 4 + event_count
        x, y, width, height = struct.unpack_from("<iiii", data, cursor)
        cursor += 22
        doors[door_id] = {
            "grid": [x, y, width, height],
            "center": [(x - 1) * 20 + width * 10,
                       (y - 1) * 20 + height * 10],
        }
    return doors
```

Implement `skip_npcs_and_goods()` using the verified record sizes: NPC size is `89 + event_count + sale_count + (motion_node_count + 1) * 8`; goods size is 13 bytes. Parse the Eve index as `u16 count`, followed by `count` entries of 32 bytes; each entry is a one-byte length, a 23-byte name field, `i32 offset`, and `i32 size`, with event position `offset + 103`.

Use SHA-256 over the three raw input files for `fingerprint`. Store graph codes as `scene_id * 1000 + area_id`. Set city flags from the existing authoritative mapping in `cities.json`, not from the Warp mark field.

- [ ] **Step 4: Generate and validate the real asset**

Run: `python tools/build_world_nav.py --warp gamedata/Warp_C.dat --doors gamedata/DoorGroupData.dat --eve gamedata/Eve.emg --cities cities.json --output world_nav.json`

Expected output includes:

```text
3823 Eve scenes
3844 navigation states
41 teleport cities
wrote world_nav.json
```

Add this real-data assertion to `tests/test_build_world_nav.py`:

```python
def test_generated_asset_has_hap_coc_gate(self):
    nav = json.load(open("world_nav.json", encoding="utf-8"))
    self.assertEqual(nav["gates"]["22000"]["17"]["center"], [560, 2510])
```

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.test_build_world_nav -v`

Expected: all tests pass.

```powershell
git add tools/build_world_nav.py tests/test_build_world_nav.py world_nav.json
git commit -m "feat: build compact world navigation data"
```

---

### Task 2: Add fast graph search and nearest-city selection

**Files:**
- Create: `bot/world_nav.py`
- Create: `tests/test_world_nav.py`

**Interfaces:**
- Consumes: Task 1 `world_nav.json` schema.
- Produces: `WorldNavStore(path: str)`, `find_scene_routes(source_scene: int, target_scene: int) -> list[list[dict]]`, `rank_cities(target_scene: int) -> list[dict]`, `get_gate(scene_id: int, gate_id: int) -> dict | None`, and property `fingerprint: str`.

- [ ] **Step 1: Write failing nearest-city tests**

```python
import unittest
from bot.world_nav import WorldNavStore


class TestWorldNavStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nav = WorldNavStore("world_nav.json")

    def test_hap_coc_uses_truong_an(self):
        best = self.nav.rank_cities(14821)[0]
        self.assertEqual((best["city"], best["flag"]), (14001, 6))
        self.assertEqual(
            [(leg["scene"], leg["door"], leg["target_scene"])
             for leg in best["legs"]],
            [(14001, 1, 22000), (22000, 17, 14821)],
        )

    def test_unknown_destination_returns_empty(self):
        self.assertEqual(self.nav.rank_cities(999999), [])
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_world_nav -v`

Expected: import fails because `bot.world_nav` does not exist.

- [ ] **Step 3: Implement reverse-BFS indexing**

```python
class WorldNavStore:
    def __init__(self, path):
        with open(path, encoding="utf-8") as fh:
            self.data = json.load(fh)
        self.fingerprint = self.data["fingerprint"]
        self.graph = build_graph(self.data["edges"])
        self.gates = self.data["gates"]
        self._target_cache = {}

    def rank_cities(self, target_scene):
        routes = self._routes_to(target_scene)
        ranked = []
        for city in self.data["cities"]:
            candidates = [routes[code] for code in routes
                          if code // 1000 == city["city"]]
            for legs in candidates:
                ranked.append({**city, "legs": legs, "gate_count": len(legs)})
        return sorted(ranked, key=lambda item: (item["gate_count"], item["city"]))
```

Build one reverse-BFS result per destination and cache it in `_target_cache`; do not BFS once per city. Preserve `from`, `to`, `scene`, `target_scene`, `door`, and `priority` on every reconstructed leg.

- [ ] **Step 4: Verify performance and tests**

Run: `python -m unittest tests.test_world_nav -v`

Expected: all tests pass.

Run: `python -c "from time import perf_counter; from bot.world_nav import WorldNavStore; n=WorldNavStore('world_nav.json'); t=perf_counter(); print(n.rank_cities(14821)[0], (perf_counter()-t)*1000)"`

Expected: city `14001`, gates `1,17`, and query under 20 ms on the current workstation.

- [ ] **Step 5: Commit**

```powershell
git add bot/world_nav.py tests/test_world_nav.py
git commit -m "feat: find nearest teleport city and gate chain"
```

---

### Task 3: Build and persist smart routes

**Files:**
- Create: `bot/smart_route.py`
- Create: `tests/test_smart_route.py`
- Modify: `bot/config.py`

**Interfaces:**
- Consumes: `WorldNavStore`, `GroundMapStore.find_world_path(map_id, start, target)`.
- Produces: `SmartRouteCache(path: str)`, `SmartWorldRouter(nav, ground, cache)`, `build_route(dest_map: int, safe: tuple[int, int]) -> dict | None`, `get_leg_path(route: dict, scene_id: int, start: tuple[int, int]) -> list[tuple[int, int]] | None`, and `record_leg_path(...)`.

- [ ] **Step 1: Write failing route/cache tests**

```python
class TestSmartWorldRouter(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.nav = WorldNavStore("world_nav.json")
        self.ground = GroundMapStore("gamedata/Ground.mmg")
        self.cache = SmartRouteCache(os.path.join(self.temp.name, "smart_routes.json"))
        self.router = SmartWorldRouter(self.nav, self.ground, self.cache)

    def test_builds_and_caches_hap_coc_route(self):
        route = self.router.build_route(14821, (1230, 470))
        self.assertEqual(route["city"], 14001)
        self.assertEqual([leg["gate"] for leg in route["legs"]], [1, 17])
        self.assertEqual(self.cache.get(14821, (1230, 470), self.nav.fingerprint), route)

    def test_changed_fingerprint_invalidates_cache(self):
        route = self.router.build_route(14821, (1230, 470))
        self.assertIsNotNone(route)
        self.assertIsNone(self.cache.get(14821, (1230, 470), "changed"))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_smart_route -v`

Expected: import fails because `bot.smart_route` does not exist.

- [ ] **Step 3: Implement cache and structural route building**

```python
class SmartRouteCache:
    def get(self, dest_map, safe, fingerprint):
        entry = self.data.get(f"{dest_map}:{safe[0]},{safe[1]}")
        if not entry or entry["fingerprint"] != fingerprint:
            return None
        return entry["route"]

    def put(self, dest_map, safe, fingerprint, route):
        key = f"{dest_map}:{safe[0]},{safe[1]}"
        self.data[key] = {"fingerprint": fingerprint, "route": route}
        write_json_atomic(self.path, self.data)


class SmartWorldRouter:
    def build_route(self, dest_map, safe):
        cached = self.cache.get(dest_map, safe, self.nav.fingerprint)
        if cached:
            return cached
        for candidate in self.nav.rank_cities(dest_map):
            route = self._candidate_route(candidate, dest_map, safe)
            if route:
                self.cache.put(dest_map, safe, self.nav.fingerprint, route)
                return route
        return None
```

Every leg must include `scene`, `target_scene`, `from_code`, `to_code`, `gate`, `gate_center`, and optional `paths` keyed by start block. Reject candidates whose gate definition is missing. Implement atomic cache writes with a temporary file in the cache directory followed by `os.replace()`.

For precomputed legs, derive the next scene's arrival point from the reverse graph edge back to the previous scene. If no reverse edge exists, leave that leg start unset and calculate it from the observed runtime position. Calculate collision-safe paths for every known start and rank equal-gate-count city candidates by `(total_path_distance, city_id)`, satisfying the deterministic distance tie-breaker in the design.

Add to `bot/config.py`:

```python
WORLD_NAV_PATH = os.path.join(_base_dir(), "world_nav.json")
SMART_ROUTE_CACHE_PATH = os.path.join(_base_dir(), "smart_routes.json")
SMART_ROUTE_FALLBACK = True
```

- [ ] **Step 4: Add start-sensitive local-path tests**

```python
def test_local_leg_path_is_cached_by_start_block(self):
    route = self.router.build_route(14821, (1230, 470))
    path = self.router.get_leg_path(route, 14001, (770, 610))
    self.assertEqual(path[-1], (940, 670))
    again = self.router.get_leg_path(route, 14001, (770, 610))
    self.assertEqual(again, path)
```

Run: `python -m unittest tests.test_smart_route -v`

Expected: all tests pass and `smart_routes.json` is created only inside the temporary test directory.

- [ ] **Step 5: Commit**

```powershell
git add bot/smart_route.py bot/config.py tests/test_smart_route.py
git commit -m "feat: build and cache collision-safe world routes"
```

---

### Task 4: Execute smart routes safely in the game client

**Files:**
- Modify: `bot/client.py`
- Create: `tests/test_smart_route_execution.py`

**Interfaces:**
- Consumes: Task 3 `SmartWorldRouter` route dictionaries.
- Produces: `Client.follow_smart_route(dest_map: int, safe: tuple[int, int], abort=None) -> bool` and shared lazy `_smart_world_router()` loader.

- [ ] **Step 1: Write a failing execution-state test**

```python
class FakeClient:
    running = True
    current_map = 14001
    pos = (770, 610)

    def __init__(self):
        self.calls = []

    def navigate_to(self, x, y, **kwargs):
        self.calls.append(("navigate", x, y))
        self.pos = (x, y)

    def _enter_gate(self, x, y, gate):
        self.calls.append(("gate", gate, x, y))
        self.current_map = 22000 if gate == 1 else 14821
        self.pos = (1760, 20) if gate == 1 else (3150, 230)
        return True


def test_executor_navigates_and_verifies_each_gate():
    client = FakeClient()
    ok = execute_smart_route(client, HAP_COC_ROUTE, abort=lambda: False)
    self.assertTrue(ok)
    self.assertEqual([call[1] for call in client.calls if call[0] == "gate"], [1, 17])
    self.assertEqual(client.current_map, 14821)
```

- [ ] **Step 2: Run test and verify RED**

Run: `python -m unittest tests.test_smart_route_execution -v`

Expected: `execute_smart_route` is missing.

- [ ] **Step 3: Implement pure executor, then Client wrapper**

```python
def execute_smart_route(client, route, abort=None):
    for leg in route["legs"]:
        if abort and abort() or not client.running:
            return False
        if client.current_map != leg["scene"]:
            return False
        client.navigate_to(*leg["gate_center"], abort=abort)
        if not client._enter_gate(*leg["gate_center"], leg["gate"]):
            return False
        if client.current_map != leg["target_scene"]:
            return False
    client.navigate_to(*route["safe"], abort=abort)
    return client.current_map == route["dest_map"]
```

The real wrapper must teleport using the route's `city` and `flag`, wait up to 20 seconds for matching `current_map` and non-`None` `pos`, then call the executor. Reuse `_wait_combat_clear()` and `_enter_gate()`; do not duplicate gate packet logic. On unexpected scene, invalidate the cache, rebuild once, and only then return failure for fallback handling.

- [ ] **Step 4: Add failure tests**

Add tests proving abort stops before the next gate, an unexpected scene returns `False`, and a failed `_enter_gate()` sends no later gate calls.

Run: `python -m unittest tests.test_smart_route_execution -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add bot/client.py tests/test_smart_route_execution.py
git commit -m "feat: execute smart routes through verified gates"
```

---

### Task 5: Make smart routing primary in train startup and reform

**Files:**
- Modify: `run_party_digioi.py`
- Create: `tests/test_train_routing_policy.py`

**Interfaces:**
- Consumes: `Client.follow_smart_route()` and existing `Client.follow_route()`.
- Produces: `_travel_to_train_map(client, map_id, safe, legacy_route, abort=None) -> bool` used by initial travel, reconnect, and reform.

- [ ] **Step 1: Write failing policy tests**

```python
def test_smart_route_runs_before_legacy_route():
    client = RecordingClient(smart_result=True, legacy_result=True)
    self.assertTrue(_travel_to_train_map(client, 14821, (1230, 470), {"steps": []}))
    self.assertEqual(client.calls, ["smart"])


def test_legacy_route_is_temporary_fallback():
    client = RecordingClient(smart_result=False, legacy_result=True)
    self.assertTrue(_travel_to_train_map(client, 14821, (1230, 470), {"steps": []}))
    self.assertEqual(client.calls, ["smart", "legacy"])


def test_missing_both_routes_stops_without_direct_teleport():
    client = RecordingClient(smart_result=False, legacy_result=None)
    self.assertFalse(_travel_to_train_map(client, 14821, (1230, 470), None))
    self.assertNotIn("go_to_town:14821", client.calls)
```

- [ ] **Step 2: Run test and verify RED**

Run: `python -m unittest tests.test_train_routing_policy -v`

Expected: `_travel_to_train_map` does not exist.

- [ ] **Step 3: Implement the routing policy helper**

```python
def _travel_to_train_map(client, map_id, safe, legacy_route, abort=None):
    if client.follow_smart_route(map_id, safe, abort=abort):
        return True
    if config.SMART_ROUTE_FALLBACK and legacy_route:
        return client.follow_route(legacy_route)
    log.error("[%s] khong co smart route toi map %s", client._label, map_id)
    return False
```

Replace direct `TRAIN_ROUTES.get(sc)` travel decisions in initial party travel, `_do_reform()`, and reconnect recovery with this helper. Preserve the existing party barrier: only the leader travels and members are pulled through gates. If the client is already on the destination map, call `navigate_to()` for the nearest safe and skip world routing.

- [ ] **Step 4: Run focused and full tests**

Run: `python -m unittest tests.test_train_routing_policy -v`

Expected: policy tests pass.

Run: `python -m unittest discover -s tests -p "test_*.py"`

Expected: all tests pass with zero failures.

- [ ] **Step 5: Commit**

```powershell
git add run_party_digioi.py tests/test_train_routing_policy.py
git commit -m "feat: prefer automatic routes in train mode"
```

---

### Task 6: Package data, document operation, and perform live acceptance

**Files:**
- Modify: `.gitignore`
- Modify: `KNOWLEDGE.md`
- Modify: `build_product.py`
- Modify: `tools/sync_apk_python.py`
- Modify: `android/app/src/main/python/train_bot/config.py`

**Interfaces:**
- Consumes: `world_nav.json`, `gamedata/Ground.mmg`, all runtime modules.
- Produces: development and desktop-release installations containing the navigation asset and collision data. Android keeps the legacy fallback in this iteration and receives the new Python modules without enabling smart world routing.

- [ ] **Step 1: Add packaging assertions**

Add a test that loads `config.WORLD_NAV_PATH`, `config.GROUND_MAP_PATH`, and asserts both exist in the development layout. Add build-time checks in `build_product.py` that fail with explicit filenames when either asset is absent from desktop release staging.

- [ ] **Step 2: Copy generated navigation data through existing build paths**

Keep `world_nav.json` as the canonical generated asset. Add it to `build_product.DATA_JSON`. Add `gamedata/Ground.mmg` to a new `DATA_FILES` mapping and copy it to `aTSBot/gamedata/Ground.mmg`, preserving `config.GROUND_MAP_PATH`.

Add `world_nav.py` and `smart_route.py` to `tools/sync_apk_python.py`'s `OPTIONAL` list so Android imports stay valid. Set `SMART_WORLD_ROUTING = False` in Android's platform-specific `config.py`; Android continues through the legacy fallback until binary asset materialization is designed and tested separately.

Update `.gitignore` to continue ignoring raw `Eve.emg`, `Warp_C.dat`, and `DoorGroupData.dat`; only generated `world_nav.json` and the already-authorized `Ground.mmg` are tracked.

- [ ] **Step 3: Update operational knowledge**

Document:

```text
Smart routing is primary for train maps.
world_nav.json supplies cities, scene graph, and gate centers.
Ground.mmg supplies local collision.
smart_routes.json is disposable runtime cache and must remain gitignored.
train_routes.json is temporary fallback and may be removed after live acceptance.
```

- [ ] **Step 4: Run final verification**

Run:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m py_compile bot\world_nav.py bot\smart_route.py bot\pathfind.py bot\client.py run_party_digioi.py tools\build_world_nav.py
git diff --check
```

Expected: every command exits 0; test output reports zero failures.

- [ ] **Step 5: Perform controlled live acceptance on map 14821**

Use one party and select Hạp Cốc Tử Ngọ 1. Confirm logs show:

```text
smart route 14821: city=14001 flag=6 gates=1,17
14001 -> 22000 via gate 1
22000 -> 14821 via gate 17
smart route reached safe (1230,470)
```

Then test reconnect from an intermediate scene and reform after one member is displaced. Stop and retain legacy fallback if any unexpected scene, speculative gate packet, or party split occurs.

- [ ] **Step 6: Commit**

```powershell
git add .gitignore KNOWLEDGE.md world_nav.json build_product.py tools/sync_apk_python.py android/app/src/main/python/train_bot/config.py
git commit -m "build: package automatic world routing data"
```
