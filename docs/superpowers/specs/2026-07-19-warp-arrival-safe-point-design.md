# Warp Arrival Safe Point Design

## Goal

Remove the monster scanner's dependency on a manually curated safe coordinate. When the
leader enters the selected train map through the final warp, use the server-confirmed arrival
position as that map's safe point for rallying, scanning, relogin, and later cached runs.

## Chosen approach

Capture the leader's first stable `client.pos` after `current_map` changes from another map to
the destination map. Project it to the nearest walkable point in the same reachable component
with `Ground.mmg`, then persist that one point in `mob_spots.json` under the map fingerprint.

Alternatives rejected:

- Writing the point back to `train_maps.json` would mutate user-distributed configuration.
- Inferring the point only from `world_nav.json` would use a static reverse-gate estimate rather
  than the actual landing coordinate reported by the server.

## Route bootstrap

Smart routing must also work before a learned safe exists. Its destination coordinate becomes
optional: when omitted, route construction stops at the final gate's known arrival point and
does not add a final local leg. The first actual destination-map position then becomes the
learned safe. Existing configured or cached safe points continue to produce the current final
local leg, preserving old routes.

Legacy `train_routes.json` remains a fallback only. A map must still be selectable as a train
map, but its `safe` list may be empty.

## Runtime flow

1. Resolve a safe point in this order: fingerprint-valid learned safe, configured safe, none.
2. Build/follow the city and warp chain. If no safe is known, stop after entering the target map.
3. Only when the leader came from another map, wait for the target-map self-spawn position.
4. Project that arrival position to a walkable coordinate and atomically cache it.
5. Use the learned point immediately as scan origin and party rally point.
6. Scan monster patrols as before and store only center points plus the single safe point.
7. On login already inside the train map with a cached/configured safe, never overwrite safe with
   the login/combat position.
8. On login already inside the train map with no safe at all, mark the map barrier incomplete so
   the whole party returns to the route city, reforms, re-enters through the final warp, and learns
   the actual arrival safe before scanning.

If the actual arrival position is unavailable after a real re-entry, retain the configured safe.
If neither exists after that bootstrap route, stop the train attempt safely instead of inventing
a coordinate.

## Cache and invalidation

`mob_spots.json` schema stays version 1 and adds an optional `safe: [x, y]` field to each map
entry. A Ground fingerprint mismatch invalidates both safe and monster centers. Incomplete scan
progress may still retain the learned safe so a relogin can resume from the same rally point.
No entity trace, patrol polygon, or roaming-region geometry is persisted.

## PC and Android parity

Safe resolution, persistence, route bootstrap, and coordinator behavior live in shared Python
modules and are synchronized to Android with `tools/sync_apk_python.py`. Both products use the
same cache shape and fallback rules.

## Tests

- A map entry round-trips a single safe point and invalidates it on fingerprint change.
- A transition into the target map captures and walkability-projects the arrival coordinate.
- Starting already inside the target map does not overwrite a cached safe.
- Starting already inside the target map without any safe forces a city-to-map bootstrap route.
- A smart route with no destination safe ends at the final gate arrival without a final path.
- Train mode with an empty configured `safe` uses the learned arrival safe for scan and rally.
- Existing configured-safe routing, scanner policy, PC/Android parity, full suite, and both builds
  remain green.
