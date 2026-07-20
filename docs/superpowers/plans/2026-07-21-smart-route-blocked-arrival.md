# Smart Route Blocked Arrival Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow automatic routing to Thái Lăng 2 when an inferred post-warp gate center is a blocked collision cell.

**Architecture:** Keep the stateful world graph unchanged and normalize only inferred post-warp arrivals through `GroundMapStore.nearest_walkable_world`. Use the normalized coordinate both for eager route validation and the runtime fallback, then mirror the implementation in Android.

**Tech Stack:** Python, unittest, Ground.mmg collision data

## Global Constraints

- Desktop and Android routing behavior must remain identical.
- Do not add a legacy hand-authored train route.
- Do not build release artifacts in this task.

---

### Task 1: Reproduce and fix blocked inferred arrivals

**Files:**
- Modify: `tests/test_smart_route.py`
- Modify: `bot/smart_route.py`
- Modify: `android/app/src/main/python/train_bot/smart_route.py`

**Interfaces:**
- Consumes: `GroundMapStore.nearest_walkable_world(map_id, point, reachable_from)`
- Produces: `SmartWorldRouter._arrival_after(edge)` returning a walkable `(x, y)` tuple or `None`

- [ ] **Step 1: Write the failing regression test**

Add a test that calls `build_route(14852, (470, 1950))`, asserts the route exists, asserts scenes are `[14001, 22000, 14523, 14534, 14522, 14533, 14521, 22000, 14851]`, and asserts the second scene-22000 leg contains a valid cached path.

- [ ] **Step 2: Run the regression test and verify RED**

Run: `python -m unittest tests.test_smart_route.TestSmartWorldRouter.test_builds_thai_lang_2_through_world_map_twice -v`

Expected: FAIL because `build_route` returns `None`.

- [ ] **Step 3: Implement the minimal normalization**

In `_arrival_after`, resolve the reverse gate, then call:

```python
return self.ground.nearest_walkable_world(
    reverse["scene"], tuple(gate["center"]), tuple(gate["center"])
)
```

Retain `None` when no reverse gate or walkable component is available. Mirror the same code in the Android router.

- [ ] **Step 4: Run focused and routing tests**

Run: `python -m unittest tests.test_smart_route tests.test_world_nav tests.test_pathfind -v`

Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `python -m unittest discover -s tests -v`

Expected: all modified-area tests pass; report any known unrelated baseline failure separately.

- [ ] **Step 6: Commit**

```text
fix: route through blocked warp arrivals
```
