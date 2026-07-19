# Train Map Packet Probe Design

## Goal

Replace the failed automatic full-map walk with a short, stationary packet probe that reaches an unconfigured train map automatically and captures the map entity snapshot needed to identify the real monster movement protocol.

## Confirmed constraints

- The user selects only the train map. No safe or mob coordinate input is required.
- Existing smart world routing still takes the whole party from the nearest city through the final warp.
- Capture is armed before routing so the target-map load packet is not missed.
- Once the leader reaches the learned warp safe, it remains stationary for 60 seconds.
- The probe records raw server packets only while `current_map` equals the target map.
- Random encounter combat positions are never used as monster evidence.
- Full-map coverage walking is disabled by default during this probe phase.
- Existing empty center caches are non-terminal: they must not suppress a new probe.
- An existing fingerprint-valid safe is never overwritten on later relogs.
- PC and Android source behavior remain synchronized, but no EXE, ZIP, or APK is built until the user tests the source version.

## Components and data flow

`GameClient` exposes a bounded raw packet capture lifecycle. The coordinator arms capture before train routing. The receive thread dispatches each packet normally, then records it if dispatch has established that the client is on the requested target map. Records are JSON Lines containing monotonic timestamp, map id, opcode, packet length, and full packet hex. The file is created in the normal app-data directory and its path is logged.

After arrival, `_resolve_train_mob_centers` checks cache and configured points. A non-empty learned cache remains usable. A configured mob list remains usable as a temporary fallback. When neither exists, the leader switches the current channel while capture is already armed, waits at the safe for 60 seconds, closes the capture, and returns no center. Members remain at the safe and combat training does not start at an invented point.

## Cache and safe rules

`status="empty"` is diagnostic evidence from a failed scanner, not a permanent completed result. It must not be returned as a valid learned-center cache. Safe data remains stored separately in the same runtime file, but `_capture_arrival_safe` first reuses a fingerprint-valid cached safe and only records the first arrival when no safe exists.

## Testing

- A packet capture test proves packets before the target map are ignored and the first target-map packet is retained after dispatch updates `current_map`.
- A coordinator policy test proves empty cache plus no configured mob starts the stationary probe and never calls `scan_full_map`.
- A fallback test proves configured mob points do not trigger coverage scanning.
- A cache test proves `status="empty"` does not load as a completed center list.
- A safe test proves a later routed login cannot overwrite an existing safe.
- Existing packet observer, routing, cache, PC/Android parity, and full Python tests remain green.

## Out of scope

- Decoding the captured unknown packet layout before a real probe file exists.
- Automatically deriving monster centers from random battles.
- EXE, ZIP, APK, Git push, or GitHub Release creation.
