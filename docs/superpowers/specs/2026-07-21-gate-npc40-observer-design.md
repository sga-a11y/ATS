# Gate 40NPC Packet Observer Design

## Problem

`GameClient._dispatch()` calls `_observe_npc40_packet()` for every packet in every mode. The packet classified as the 40NPC repeat prompt (`0x41 0a0001`) also appears after ordinary train-map battles. The observer therefore clears `state.in_battle` before the normal `0x14 sub0800` end handler runs.

Because the normal handler then sees `in_battle_TRUOC=False`, it skips `reset_enemies()`. `BattleState._battle_counted` remains latched from the previous battle, so the next battle's first `0x33` snapshot does not return `start_enemy_slots` and `_record_train_block_stats()` is not called.

## Design

- `_observe_npc40_packet()` returns immediately unless `_npc40_started` is true.
- The guard applies before both battle-start sequence tracking and repeat-prompt processing.
- The active 40NPC loop keeps its existing behavior unchanged.
- Ordinary train battles never mutate `_npc40_prompt_seq`, `_npc40_last_defeated`, `state.in_battle`, or `_battle_end_grace_until` through the 40NPC observer.
- Apply the same source change to PC and APK through the existing sync script.

## Tests

- An inactive observer receiving `0x41 0a0001` preserves `state.in_battle=True`, `_battle_counted=True`, prompt sequence, defeat flag, and grace timestamp.
- An active observer still increments battle/prompt sequences and records defeat exactly as before.
- Existing train block stats, NPC40, and party policy tests pass.

## Release Scope

Do not build or publish a release until the dev/source tests and user testing are complete.
