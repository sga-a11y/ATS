# Phúc Thần Priority Design

## Goal

Make Túi Đại Phúc Thần the third fallback in the protective-item flow instead of consuming it independently whenever it exists.

## Priority Flow

Each invocation of `use_phuc_than_items()` performs at most one protective action, using hardcoded template IDs in this order:

1. If `0x5aab` Ngọc Siêu Phúc Thần exists, equip one and stop the protective flow.
2. Otherwise, if `0x5a2d` Ngọc Đại Phúc Thần exists, equip one and stop the protective flow.
3. Otherwise, if `0xb5f4` Túi Đại Phúc Thần exists, consume at most one and stop the protective flow.
4. If none exists, perform no protective action.

After that selection, Đại Phúc Thần `0xb3d6` and Phúc Thần `0xb3d5` continue through the existing normal consumable flow and retain their configured limits. Túi Đại Phúc Thần is excluded from that normal loop so it cannot be consumed twice or consumed while either protective gem exists.

## Scope

- Implement identical behavior in desktop `bot/client.py` and Android `android/app/src/main/python/train_bot/client.py`.
- Keep the existing login invocation, 30-minute periodic invocation, no-combat guard, and Ngọc Hư cleanup unchanged.
- Keep `use_items.json` data and item quantity metadata unchanged; the priority TIDs are intentionally hardcoded in the client logic.

## Failure Behavior

“If unavailable” means the item is absent or has zero tracked quantity. If the selected equip/use command itself reports failure, the function does not fall through to a lower-priority item during the same invocation, matching the existing gem behavior.

## Testing

Add focused tests covering Ngọc Siêu priority, Ngọc Đại fallback, Túi fallback, no protective item, exclusion of Túi from normal consumption, and desktop/Android source parity. Run the complete Python test suite afterward.
