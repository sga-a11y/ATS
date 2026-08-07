# Combat Phase HP Gate Design

## Behavior

Automatic crowd-control and ally-protection phases run only while at least one living enemy has
`current HP > 1500`. At exactly 1500 HP, that enemy does not keep either phase enabled.

Enemy-protection breaking remains enabled regardless of this threshold. Explicit user-configured
skill rules remain authoritative and are not filtered by the automatic phase gate.

## Implementation

Add one shared predicate in `bot/combat.py` based on `enemy_slots` and `enemy_hp`. Use it as a guard
inside `_try_cc` and `_try_protect`; do not add it to `_try_break_enemy_protect`. Sync the shared
Python files to APK and cover the 1500/1501 boundary plus break-protection behavior with tests.
