# Full-map mob region scanner design

## Goal

Discover a usable center point for every observable monster roaming area on a
normal training map without requiring `train_maps.json` points. The scanner favors
completeness and accuracy over speed: it walks the whole reachable map, observes
monsters until their patrol paths stabilize, groups overlapping patrols into
training areas, chooses one safe reachable center point per area, and caches only
those points for future logins.

The implementation lives in the shared Python bot core so the Windows and Android
builds use the same scanner and cache format.

## Confirmed protocol evidence

The design is based on existing capture
`captures/bachai_route_20260716.pcap`:

- S2C `0x07` body starts with `[00 00][entity 8B][map_id u16][x u16][y u16]`
  and supplies an entity's initial position on a map.
- S2C `0x06` subtype `01 00` contains
  `[entity 8B][direction u8][x u16][y u16]` and supplies movement updates.
- S2C `0x0c` rich records identify player entities. Moving entities without a
  player record and with a repeating bounded route are monster candidates.
- On map `11013`, five non-player moving entities repeat fixed waypoint sets.
  Three occupy the overlapping region roughly `x=310..730, y=790..1110`, which
  contains configured train points `(590,1010)` and `(450,810)`. This confirms
  that a configured train point is a sample inside a roaming region, not the
  complete spawn definition.

`Ground.mmg` remains collision/passability data only. It is used to generate the
coverage route and validate chosen points, not as a source of monster spawns.

## User flow

1. Training mode reaches the selected map using the existing world router.
2. If a valid high-confidence cached scan exists, the bot skips scanning.
3. Otherwise the bot enters full-map scan mode.
4. Scan mode suppresses `combat_ready()` while scanning. If necessary it switches
   channel once so the server resets combat-active state and roaming monsters do
   not interrupt the scan.
5. The bot walks the coverage route, waits at observation stations until nearby
   monster routes stabilize, then continues.
6. After all reachable coverage cells are visited, observations are grouped into
   roaming areas and reduced to one validated center point per area. Only the
   center points and small scan-status metadata are saved; raw patrol traces and
   region geometry are discarded.
7. The bot moves to the best area's center point, restores
   combat-ready state, and starts normal training.

Relogin and app restart reuse the cache. A rescan is required only when the cache
is missing, incomplete, explicitly invalidated, or has a different map-data
fingerprint.

## Coverage route

The scanner derives a connected walkable-cell graph from `Ground.mmg` and limits
the scan to the connected component reachable from the map arrival position.
Tiny isolated components that cannot be reached in normal play are ignored.

Observation stations are selected with overlapping visibility coverage rather
than visiting every 20-pixel block. Candidate stations are walkable cells on a
coarse grid. The station spacing is conservative relative to the game viewport so
that neighboring observation areas overlap. Stations are ordered in a serpentine
coverage sweep, with existing smart A* navigation connecting each pair.

If a station cannot be reached, the scanner records it as unreachable and
continues. A scan is incomplete when a meaningful portion of the reachable map
was skipped; incomplete scans are cached for diagnostics but are not used as a
final high-confidence training result.

## Observation and completion rules

At each station the scanner records initial positions from `0x07` and movement
positions from `0x06`, scoped by map id and scan session. Entity ids must never be
joined across maps.

The selected full-accuracy mode waits for route stabilization:

- A monster candidate needs at least three valid position samples and at least
  two distinct coordinates.
- A route is stable when it has completed a repeat (a previously observed
  waypoint/edge is revisited after covering its current unique waypoint set) and
  no new waypoint has appeared during the quiet window.
- The station completes when every currently observed monster candidate is stable
  and no new candidate or waypoint appears during the quiet window.
- A hard per-station timeout prevents infinite waits caused by players, unusual
  NPCs, packet loss, or a monster that leaves visibility. Timed-out observations
  are retained with lower confidence.
- A second pass revisits stations that timed out or produced low-confidence edge
  areas. The whole scan finishes only after the second pass or when all stations
  are high confidence.

Timeout and quiet-window constants will be configurable in the shared config with
safe defaults. Full mode may take many minutes on a large map; correctness takes
priority over a fixed duration.

## Entity classification

The scanner maintains per-session entity state:

- Entities identified by rich `0x0c` player records are excluded.
- The bot's own entity and known party entities are excluded.
- Static entities are excluded because they do not provide a roaming route.
- A remaining entity becomes a monster candidate only after repeated bounded
  `0x06` movement or an initial `0x07` position followed by movement.
- Implausible coordinates, cross-map updates, one-off movement, and routes larger
  than a conservative maximum diameter are rejected or marked low confidence.

This intentionally avoids depending on a monster template id that has not yet
been confirmed in the protocol. Classification evidence and rejection reasons are
kept in diagnostic output so later packet discoveries can improve it safely.

## Center-point construction

Each candidate first produces an in-memory patrol trace. Traces are merged into
one training area when their buffered paths overlap or are separated by only a
small walkable gap. The merge operates in collision-grid space so walls prevent
two visually close patrols from becoming one area.

For each area, the scanner computes a medoid-like center from unique observed
positions so repeated dwell packets do not bias the result. If that geometric
center is blocked, it is projected to the nearest walkable cell in the same
reachable component. The final cached map result contains:

- one `[x, y]` center point per discovered monster area;
- map-level scan completion, confidence, fingerprint, and timestamp metadata.

Raw entity ids, waypoint sets, visit counts, bounding boxes, polygons, and cell
masks exist only in memory while scanning and are not written to the runtime
cache. Existing configured train points are optional validation seeds: closeness
to a computed center can raise confidence, but configured points neither create
nor move a discovered center.

## Center ranking

Centers are ranked primarily by observed monster density and completeness, then by
walkability and travel cost. Existing battle block statistics
may break ties, but lack of battle history must not prevent selection on a new
map.

The first implementation chooses the highest-ranked center automatically. The
cache retains every center so later UI work can allow manual bãi selection without
rescanning.

## Cache

Use a new versioned runtime file `mob_spots.json`, stored through the existing
app-data abstraction and seeded as an Android asset where applicable. Top-level
metadata includes schema version and map-data fingerprint. Each map entry includes
scan status, timestamps, coverage statistics, settings used, and the list of
center points. It must not persist patrol traces or region geometry.

Writes are atomic (`.tmp` then replace). New observations merge conservatively
with compatible cached data. A partial or interrupted scan remains resumable but
is never labeled complete. A Ground/map fingerprint change invalidates geometric
results for that map.

## Failure handling

- Missing `Ground.mmg`: report that full scan cannot cover the map; do not pretend
  a complete result. Existing configured points remain a fallback if available.
- Navigation failure: skip the station, mark coverage incomplete, and continue.
- Battle starts during scan: finish/exit the battle through existing behavior,
  keep collected data, and resume the current station.
- Relogin/disconnect: persist progress and resume from the first unfinished
  station after returning to the same map.
- No monsters observed after complete coverage: cache a valid empty result with
  evidence, but do not start a training loop at an arbitrary point.
- Ambiguous moving entities: exclude them from high-confidence center calculation;
  diagnostic traces may be logged but are not persisted.

## Verification

Tests will cover packet parsing, player exclusion, route stabilization, timeout,
second-pass behavior, wall-aware patrol grouping, center projection,
cache resume/invalidation, and best-point selection.

An offline capture regression for map `11013` must recover the two observed patrol
groups from the available capture segment. The lower-left computed center must be
walkable and lie near the configured points `(590,1010)` and `(450,810)`. A live
scan is considered valid only when its temporary diagnostic overlay shows coverage
stations, in-memory traces, and computed center points aligned with the decoded
Ground map. The overlay is a verification artifact and is not stored in the cache.

Both Windows and Android builds must run the same unit tests for shared logic and
ship the same cache schema/config defaults.
