# Team Dungeon Level 110 Design

## Goal

Add the level 110 team dungeon (`dungeon_id=0x0010`, completion mission
`0x30ae`) to both the PC and Android products. The dungeon is difficult, so its
checkbox is visible but **disabled by default** on both products. A party only
runs it after the user explicitly enables level 110.

The implementation must follow the verified MuMu capture
`captures/teamdungeon_lv110_mumu12_20260805_202150.pcap`. In particular, a
battle can temporarily have an empty/dead enemy slot and then replace that
enemy in the same slot. The replacement is accompanied by NPC dialogue such
as "khong ket thuc de the dau". That dialogue is part of the current battle;
it is not a battle-end signal.

## Capture Evidence

The capture contains five encounters. Encounters 3, 4, and 5 contain explicit
mid-battle replacements:

| Time (s) | Old enemy | New enemy |
| --- | --- | --- |
| 246.191 | Cao Thuan (`0x9d39`) | Ham Tran Binh (`0x9d3d`) |
| 264.061 | Nguy Tuc (`0x9d3b`) | Ham Tran Binh (`0x9d3d`) |
| 355.063 | Lu Bo (`0x9d3e`) | Hac Manh (`0x9d42`) |
| 355.063 | Lu Bo (`0x9d3e`) | Tao Tinh (`0x9d41`) |
| 428.595 | Lu Bo (`0x9d3e`) | Phi Tuong Binh (`0x9d40`) |
| 608.567 | Lu Bo (`0x9d43`) | Hau Thanh (`0x9d49`) |
| 608.567 | Lu Bo (`0x9d43`) | Nguy Tuc (`0x9d4a`) |
| 679.251 | Lu Bo (`0x9d43`) | Tong Hien (`0x9d4b`) |

Each replacement is announced by server packet `0x35/0600`. Its body is:

```text
[06 00] [01] [old entity: 8 bytes] [new entity: 8 bytes]
```

It is followed by a new-enemy `0x0b`, a same-slot `0x35/0300`, a full `0x33`
battle snapshot, and new offers/turn packets. There is no client
`0x14/0600` advance needed for the replacement.

The first four encounters end with server `0x14/0700`. The last encounter is
completed by mission update `0x18/0100`, mission `0x30ae`, step `1`, together
with the final `0x14/6400` summary. Temporary `enemy_slots == []`, an idle
timeout, `in_battle == False`, or the NPC replacement dialogue are not valid
PB110 encounter-end conditions.

## Considered Approaches

### A. Capture-specific state machine with explicit packet signals (chosen)

Implement the five known stages and captured movements/actions. Add a small
observer for `0x35/0600`, and wait for explicit end signals instead of the
generic combat-idle heuristic. This is the smallest safe change and matches
the evidence.

### B. Reuse the generic `in_combat()` / empty-enemy heuristic (rejected)

This can finish a stage during the short gap before a replacement is inserted,
causing route/dialog packets to be sent while the battle is still active. The
likely result is desynchronization or disconnection.

### C. Build a generic data-driven dungeon scripting engine (deferred)

A generic DSL could eventually describe levels 20, 50, 80, and 110, but it is
larger than this task and would increase regression risk in three working
dungeons. PB110 should first be implemented and verified as a focused script.

## Runtime State and Packet Handling

The client maintains two monotonic PB110 observations:

- an explicit normal-battle-end sequence incremented by server `0x14/0700`;
- a reinforcement sequence incremented by valid server `0x35/0600` enemy
  replacement packets.

When a valid replacement arrives during PB110:

1. Decode and log the old/new entity IDs and names when known.
2. Increment the reinforcement sequence.
3. Keep/restore battle-active state so generic idle inference cannot advance
   the dungeon script during the replacement gap.
4. Let the following normal battle snapshot and offers drive combat; send no
   scene-advance or NPC-confirm packet.

The first four stage waits snapshot the explicit end sequence before combat
and return only after that sequence advances. The final stage waits for PB110
completion (`0x30ae`, step `1`, or the existing equivalent dungeon-complete
state). Existing disconnect and party-relogin coordination remains in charge;
PB110 adds no independent reconnect loop.

## Five-Stage Script

The room flow reuses the existing team-dungeon room creation, four-member
invite, and start logic with dungeon ID `0x0010`.

### Encounter 1

- Send `0x14/0800` target `0x0008`, then `0x0c/0100`.
- Advance with the existing `0x14/0600` helper until battle begins.
- Wait for explicit `0x14/0700` end.

### Route to Encounter 2

- Run the captured post-battle heal/item step.
- Advance, then move through `(490,2410)`, `(222,2446)`, `(126,2459)`,
  `(50,2470)`.
- Interact `0x14/0800` target `0x0006`, advance once, interact target
  `0x0009`, then advance until encounter 2 begins.
- Wait for explicit `0x14/0700` end.

### Route to Encounter 3

- Run the captured post-battle heal/item step.
- Move through `(733,350)`, `(710,350)`, `(452,226)`, `(366,185)`,
  `(280,143)`, `(210,110)`.
- Interact target `0x0002`, advance once.
- Move through `(2796,2314)`, `(2721,2255)`, `(2647,2195)`, `(2590,2150)`.
- Interact target `0x000a`, then advance until encounter 3 begins.
- Accept all `0x35/0600` replacements as the same encounter and wait for the
  explicit `0x14/0700` end.

### Route to Encounter 4

- Run the captured post-battle heal/item step.
- Move through `(2623,2176)`, `(2796,2313)`, `(2871,2372)`, `(2946,2432)`,
  `(3020,2491)`, `(3070,2530)`.
- Interact target `0x0005`, advance once, move to `(430,370)`.
- Interact target `0x000b`, then advance until encounter 4 begins.
- Accept all replacements as the same encounter and wait for explicit
  `0x14/0700` end.

### Route to Encounter 5 and Completion

- Advance, move through `(430,370)`, `(228,459)`, `(141,498)`, `(70,530)`.
- Interact target `0x0003`, advance once.
- Move through `(2268,219)`, `(2181,258)`, `(2110,290)`.
- Preserve the captured preparation/heal step, interact target `0x000c`, and
  advance until encounter 5 begins.
- Accept all replacements as the same encounter.
- Finish only after PB110 mission completion (`0x30ae`, step `1`) or the
  existing equivalent final-completion state, then reuse normal team-dungeon
  cleanup/party-leave behavior.

Repeated final coordinates and bounded advance counts follow the conventions
already used by the level 50 and level 80 scripts. Each wait remains bounded
and reports a clear stage-specific timeout instead of silently advancing.

## PC and Android Configuration

- Add level 110 to the selectable team-dungeon level list on PC and Android.
- Preserve the current defaults for levels 20, 50, and 80.
- Set level 110 to `false` when the setting does not exist.
- Preserve an explicitly saved level-110 value on subsequent launches.
- Keep shared Python behavior synchronized into the Android package using the
  repository's existing sync mechanism.

## Tests

Implementation starts with failing regression tests covering:

1. Exact `0x35/0600` replacement bodies decode old/new enemy identities and
   keep PB110 in battle.
2. A temporary empty enemy list or false combat flag does not complete a
   PB110 encounter before a new explicit end packet.
3. A new `0x14/0700` completes each of encounters 1-4.
4. Mission `0x30ae`, step `1`, completes encounter 5.
5. `do_team_dungeon(110)` dispatches to the PB110 script.
6. PC and Android expose level 110 and default it to disabled.
7. Shared PC/Android PB110 methods remain synchronized.
8. A capture regression verifies five initial encounters, all eight captured
   replacement pairs, and final PB110 completion.

No release build is part of this design step. Product builds are performed
only after implementation and tests are complete and the user requests a
build/release.
