# Smart Route Blocked Arrival Design

## Problem

The route to map 14852 legitimately visits scene 22000 twice through different graph states. After returning from the cave loop, the router predicts the arrival from the reverse gate center `(580, 960)`. That coordinate is a blocked Ground.mmg cell, so eager local A* rejects the otherwise valid route before execution.

## Design

- Preserve the existing stateful world graph; `22000002` and `22000001` remain distinct.
- Normalize every inferred post-warp arrival to the nearest walkable coordinate in the same reachable component.
- Do not alter explicit city arrival coordinates or destination safe points.
- Runtime continues to prefer a real position supplied by the server. The normalized inferred arrival remains the fallback when the transition clears `client.pos`.
- Apply identical routing behavior to desktop and Android sources.

## Acceptance Criteria

- `build_route(14852, (470, 1950))` returns a route from Trường An.
- Its scene sequence contains scene 22000 twice and follows the cave loop before entering 14851 and 14852.
- The second scene-22000 leg starts from a walkable inferred coordinate and has a valid local path to gate 9.
- Existing smart-route tests continue to pass.

