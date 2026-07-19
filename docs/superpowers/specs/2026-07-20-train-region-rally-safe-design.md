# Train Region Rally Safe Design

## Goal

For every learned monster patrol region, derive one nearby walkable rally-safe point outside
monster movement and persist the learned result directly in `train_maps.json`. The party rallies
at that safe, forms the party, then the leader pulls everyone to the corresponding monster center.

## Data model

The existing schema remains unchanged:

```json
{
  "safe": [[safe_x, safe_y]],
  "mobs": [[mob_x, mob_y]]
}
```

For automatically learned maps, `safe[i]` corresponds to `mobs[i]`. Existing hand-authored maps
remain compatible; the coordinator continues using nearest-safe selection when counts are not
aligned. The post-warp arrival safe is retained only as fallback when no regional safe can be
derived.

## Regional safe derivation

The scanner already groups bounded patrol traces to produce monster centers. It will retain each
group's observed points until the probe finishes, then derive one safe per group:

1. Enumerate walkable blocks in the same reachable component using `Ground.mmg`.
2. Reject any block within 200 world pixels of any observed monster point, including monsters in
   neighboring groups.
3. Among remaining blocks, choose the point with the shortest walkable path from that group's
   center. Tie-break deterministically by distance, Y, then X.
4. If no candidate exists within 600 world pixels of the center, use the post-warp safe for that
   group and log the fallback.

This defines "safe" only as outside observed monster movement, as requested. It does not claim
that random encounters are impossible there.

## Persistence

`train_maps.json` is updated atomically through a temporary file and `os.replace`. A successful
learn writes all center/safe pairs together; partial data is never committed. Existing `name` and
unrelated map entries are preserved.

Desktop uses the normal writable `train_maps.json`. Android materializes the bundled
`train_maps.json` into app files before Python starts and reads/writes that local copy. A packaged
baseline is merged on app update without replacing non-empty learned `safe`/`mobs` values.

`mob_spots.json` remains a capture/progress cache and backward-compatible fallback, but a complete
successful learn is promoted immediately into `train_maps.json`.

## Runtime flow

1. Route to the target map and capture the post-warp fallback safe.
2. Observe monster movement and build patrol groups.
3. Compute centers and regional safes.
4. Atomically write aligned `mobs` and `safe` arrays to `train_maps.json`.
5. Update the current in-memory train-map entry immediately.
6. Pick a monster center; rally at its paired safe; form party; pull to the center.
7. On relog, load the written map entry and skip learning.

## Failure handling

- Missing Ground data: keep the post-warp safe, do not write incomplete regional pairs.
- Interrupted/disconnected probe: retain progress cache, do not alter `train_maps.json`.
- Invalid or unwritable JSON: log an explicit error and continue using the complete in-memory
  result for the current session.
- Existing non-empty configured `mobs`: use them unchanged and skip automatic learning. Automatic
  persistence only fills entries whose `mobs` array was empty when the probe started.

## Verification

- Unit-test safe rejection inside patrol clearance and deterministic nearest valid selection.
- Test walls/path distance so Euclidean-near but unreachable points are not chosen.
- Test atomic preservation of map name and unrelated entries.
- Test aligned `safe`/`mobs` output and immediate coordinator use.
- Test Android local materialization/merge and PC/Android Python parity.
- Replay the map `20801` capture and verify every learned center receives a regional safe outside
  all 16 observed patrol traces.
