# Smart World Router Design

## Goal

Train mode must reach any configured train map without requiring a handwritten
entry in `train_routes.json`. The router selects the nearest teleport city,
builds the scene/gate chain, navigates around collision inside each scene, and
caches the result for reconnects.

## Routing policy

1. Smart routing is the primary path for every train map.
2. During live validation, an existing `train_routes.json` entry is used only
   when smart route construction or execution fails.
3. After smart routing is proven stable, the compatibility fallback and
   `train_routes.json` can be removed without changing the smart-router API.

## Data model

An offline indexer reads the authoritative game data:

- `Warp_C.dat`: teleport cities, flags, and arrival positions.
- `DoorGroupData.dat`: directed scene/area graph and gate IDs.
- `Eve.emg`: per-scene door rectangles and gate centers.
- `Ground.mmg`: collision grids used by the existing local A* implementation.

The indexer produces a compact versioned navigation asset containing teleport
cities, directed graph edges, and gate centers. Runtime code must not parse the
full event pack.

## Runtime components

`WorldNavStore` loads the compact navigation asset once. It exposes:

- `find_nearest_city(target_scene)`
- `find_scene_route(source_scene, target_scene)`
- `get_gate(scene_id, gate_id)`

`SmartWorldRouter` composes `WorldNavStore` with `GroundMapStore`. Given a train
map and safe point, it:

1. Evaluates all teleport cities and selects the route with the fewest gates.
2. Uses route distance as the tie-breaker, then city ID for deterministic output.
3. Returns a route with city ID, teleport flag/arrival point, ordered scene
   legs, gate IDs/centers, and final safe point.
4. Builds collision-safe local waypoints from the actual player position to
   each gate. Local paths are recalculated when the observed start position
   differs from the cached start block.

`Client.follow_smart_route()` executes the route:

1. Teleport to the selected city.
2. Wait for both `current_map` and `pos`.
3. Navigate to the leg's gate with local A*.
4. Enter the gate and verify the resulting scene.
5. Repeat until the destination, then navigate to the selected safe point.

## Cache

`smart_routes.json` is shared by accounts in the same installation and keyed by
destination map plus safe point. Each entry stores:

- navigation-data fingerprint;
- selected city and flag;
- ordered scene/gate chain and gate centers;
- cached local waypoints and their start blocks.

Writes are atomic. A fingerprint mismatch invalidates the entry. Reconnects
reuse the structural route and only rebuild a local leg if the current scene or
start block differs.

## Failure handling

- Missing data or no graph route: report a clear routing error; never call
  `go_to_town()` with a non-city train-map ID.
- Gate leads to an unexpected scene: discard the cache and rebuild once.
- Local A* cannot reach a gate: discard that route candidate and try the next
  nearest teleport city.
- A second smart-route failure may use the existing handwritten routine during
  the validation period. If no fallback exists, stop the route without sending
  speculative movement or gate packets.
- Stop/reform callbacks remain active during every wait and movement leg.

## Integration

Train startup and reform call smart routing before consulting
`TRAIN_ROUTES`. Existing direct-city, event, dungeon, and Di Gioi flows are not
changed. `navigate_to()` remains responsible only for collision-safe movement
inside the current scene.

## Verification

Tests use real compact navigation data and collision data where practical:

- `14821` selects Truong An (`14001`, flag `6`).
- Its chain is `14001 --gate 1--> 22000 --gate 17--> 14821`.
- An existing-routine map still attempts smart routing first.
- Cache round-trip preserves the route; a changed fingerprint rebuilds it.
- Unexpected gate result rebuilds once, then falls back or stops.
- Every generated local segment passes `is_line_clear` between consecutive
  waypoints.
- The full existing unit-test suite remains green.

Live acceptance uses one party on `14821`: initial travel, reconnect while off
map, reconnect on an intermediate scene, and reform after a member is displaced.
