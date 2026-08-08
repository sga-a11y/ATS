# Train Party Whitelist-First Invite Design

## Goal

When a bot leader forms or reforms a normal train party, invite eligible
whitelisted human players before inviting bot members, matching the established
team-dungeon ordering.

## Behavior

- A whitelist candidate must be visible around the leader on the current map
  and channel. Existing nearby/entity validation remains authoritative.
- Every train-party invitation pass sends whitelist invitations first and bot
  invitations second.
- Whitelisted players remain optional: they do not increment or satisfy the bot
  member readiness/join count, and failure to accept does not block train flow.
- Bot members retain the existing live map/channel gate and retry/reform rules.
- The same behavior is shipped in the PC and APK Python runtimes.

## Implementation Boundary

Add a normal-party participant invitation helper parallel to the existing
team-dungeon helper. It calls the existing nearby-only whitelist invitation
method, then the existing bot-member invitation method. Train startup and train
reform/retry paths use this helper instead of calling bot invitation directly.
Unrelated event, stand-still, solo, and dungeon-room invitation behavior does
not change.

## Error Handling

A missing/unseen whitelist entity produces the existing throttled diagnostic
and then bot invitations continue. An exception while inviting optional
whitelist participants is logged and must not prevent bot invitations.

## Verification

- Regression test records invitation events and asserts whitelist invitation
  occurs before the first bot invitation.
- Regression test confirms bot invitations still occur when no whitelist entity
  is available or whitelist invitation fails.
- Run party-policy/channel tests, compile both runtimes, and verify mirrored PC
  and APK files are identical.
