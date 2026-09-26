"""Per-tick manual party route decisions and worker actions.

The party engine calls ``decide_route`` on its own thread. Travel happens on
the existing account workers; this module creates no threads or barriers.
"""

import time
from typing import NamedTuple


class RouteDecision(NamedTuple):
    actions: dict
    phase: str
    complete: bool
    lag_since: float | None


def decide_route(plan, accs, leader_user, *, channel_target=None,
                 joined_members=None, now=None, grace_seconds=30.0):
    """Choose the next route work from live maps, channels and leader roster.

    ``phase`` and ``lag_since`` are returned for the caller to save in its
    party plan. A missing account or unknown map cannot satisfy an arrival.
    """
    users = list(plan.get("users") or ())
    phase = plan.get("phase") or "gather"
    lag_since = plan.get("lag_since")
    seen = {a.username: a for a in accs if a.username in users}
    waiting = {u: "nghi" for u in users if u in seen and seen[u].song}
    source, dest, city = plan.get("source"), plan.get("dest"), plan.get("city")
    if (not users or leader_user not in users or source is None or dest is None or city is None
            or any(u not in seen or not seen[u].song or seen[u].map_id is None for u in users)):
        return RouteDecision(waiting, "gather", False, None)

    positions = {u: int(seen[u].map_id) for u in users}
    source, dest, city = int(source), int(dest), int(city)
    expected_members = len(users) - 1
    if all(m == dest for m in positions.values()):
        if plan.get("temporary_party"):
            if joined_members is None:
                return RouteDecision(waiting, "finish", False, None)
            if joined_members > 0:
                return RouteDecision({u: "route_finish" for u in users}, "finish", False, None)
        return RouteDecision(waiting, "finish", True, None)

    if phase == "gather":
        if all(m == source for m in positions.values()):
            phase = "sync_source"
        elif all(m == city for m in positions.values()):
            phase = "sync_city"
        else:
            return RouteDecision(
                {u: ("nghi" if positions[u] == city else "route_gather") for u in users},
                "gather", False, None)

    if phase in ("sync_city", "sync_source"):
        assembly = city if phase == "sync_city" else source
        if any(m != assembly for m in positions.values()):
            return RouteDecision(waiting, "gather", False, None)
        if expected_members:
            if any(seen[u].kenh is None for u in users):
                return RouteDecision(waiting, phase, False, None)
            if channel_target is None:
                channels = {int(seen[u].kenh) for u in users}
                if len(channels) != 1:
                    return RouteDecision(waiting, phase, False, None)
                channel_target = channels.pop()
            switching = {u: ("nghi" if int(seen[u].kenh) == int(channel_target)
                             and getattr(seen[u], "kenh_chac", True)
                             else "doi_kenh") for u in users}
            if "doi_kenh" in switching.values():
                return RouteDecision(switching, phase, False, None)
            if joined_members is None:
                return RouteDecision(waiting, phase, False, None)
            if joined_members < expected_members:
                return RouteDecision({u: "lap_party" for u in users}, phase, False, None)
        phase = "dest" if assembly == source else "source"

    if phase in ("source", "dest"):
        if expected_members and (joined_members is None or joined_members < expected_members):
            return RouteDecision(waiting, "gather", False, None)
        leader_map = positions[leader_user]
        different = any(m != leader_map for m in positions.values())
        if different:
            at = float(now if now is not None else time.time())
            if plan.get("leader_map", leader_map) != leader_map:
                lag_since = None
            lag_since = at if lag_since is None else float(lag_since)
            if at - lag_since > grace_seconds:
                return RouteDecision(waiting, "gather", False, None)
        else:
            lag_since = None
        if phase == "source":
            if all(m == source for m in positions.values()):
                phase = "dest"
            elif leader_map == source:
                return RouteDecision(waiting, phase, False, lag_since)
            else:
                waiting[leader_user] = "route_source"
                return RouteDecision(waiting, phase, False, lag_since)
        if phase == "dest":
            if leader_map != dest:
                waiting[leader_user] = "route_dest"
            return RouteDecision(waiting, phase, False, lag_since)

    return RouteDecision(waiting, "gather", False, None)


def execute_route_action(action, client, plan, *, abort=None, finish=None):
    """Execute one bounded route step on the already running account worker."""
    if abort is not None and abort():
        return False
    if action == "route_gather":
        if plan.get("city") is None or plan.get("flag") is None:
            return False
        client.pre_route_town_hop()
        if abort is not None and abort():
            return False
        return bool(client.go_to_town(int(plan["city"]), int(plan["flag"])))
    if action in ("route_source", "route_dest"):
        source, dest = plan.get("source"), plan.get("dest")
        if source is None or dest is None:
            return False
        solo = len(plan.get("users") or ()) <= 1
        if not solo:
            client.flee_mode = False
            try:
                client.combat_ready()
            except Exception:
                pass
        if action == "route_source":
            if getattr(client, "current_map", None) == int(source):
                return True
            return bool(client.follow_smart_route(int(source), None,
                                                  abort=abort, flee=solo))
        current = getattr(client, "current_map", None)
        if current is None:
            return False
        if int(current) == int(dest):
            return True
        return bool(client.follow_smart_scene_route(int(current), int(dest), None,
                                                    abort=abort, flee=solo))
    if action == "route_finish" and finish is not None:
        finish(client)
        return True
    return False
