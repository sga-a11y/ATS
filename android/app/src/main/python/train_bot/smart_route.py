"""Build and persist collision-safe routes between teleport cities and train maps."""

import json
import math
import os
import tempfile


def _route_key(dest_map, safe):
    return f"{int(dest_map)}:{int(safe[0])},{int(safe[1])}"


def _start_key(start):
    return f"{math.ceil(start[0] / 20)},{math.ceil(start[1] / 20)}"


def _path_distance(path):
    return sum(math.dist(left, right) for left, right in zip(path, path[1:]))


class SmartRouteCache:
    def __init__(self, path):
        self.path = path
        try:
            with open(path, encoding="utf-8") as fh:
                self.data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.data = {}

    def get(self, dest_map, safe, fingerprint):
        entry = self.data.get(_route_key(dest_map, safe))
        if not entry or entry.get("fingerprint") != fingerprint:
            return None
        return entry.get("route")

    def put(self, dest_map, safe, fingerprint, route):
        self.data[_route_key(dest_map, safe)] = {
            "fingerprint": fingerprint,
            "route": route,
        }
        self._write()

    def invalidate(self, dest_map, safe):
        if self.data.pop(_route_key(dest_map, safe), None) is not None:
            self._write()

    def _write(self):
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        descriptor, temp_path = tempfile.mkstemp(
            prefix=".smart_routes.", suffix=".tmp", dir=directory
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, separators=(",", ":"))
                fh.write("\n")
            os.replace(temp_path, self.path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise


class SmartWorldRouter:
    def __init__(self, nav, ground, cache):
        self.nav = nav
        self.ground = ground
        self.cache = cache

    def build_route(self, dest_map, safe):
        dest_map = int(dest_map)
        safe = (int(safe[0]), int(safe[1]))
        cached = self.cache.get(dest_map, safe, self.nav.fingerprint)
        if cached is not None:
            return cached

        candidates = self.nav.rank_cities(dest_map)
        gate_counts = sorted({item["gate_count"] for item in candidates})
        for gate_count in gate_counts:
            viable = []
            for candidate in candidates:
                if candidate["gate_count"] != gate_count:
                    continue
                route = self._candidate_route(candidate, dest_map, safe)
                if route is not None:
                    viable.append(route)
            if viable:
                route = min(
                    viable,
                    key=lambda item: (item["total_distance"], item["city"]),
                )
                self.cache.put(dest_map, safe, self.nav.fingerprint, route)
                return route
        return None

    def _candidate_route(self, candidate, dest_map, safe):
        start = tuple(candidate["arrival"])
        total_distance = 0.0
        route_legs = []
        for index, edge in enumerate(candidate["legs"]):
            gate = self.nav.get_gate(edge["scene"], edge["door"])
            if gate is None:
                return None
            gate_center = tuple(gate["center"])
            path = self.ground.find_world_path(edge["scene"], start, gate_center)
            if path is None:
                return None
            total_distance += _path_distance(path)
            next_start = self._arrival_after(edge)
            route_leg = {
                "scene": edge["scene"],
                "target_scene": edge["target_scene"],
                "from_code": edge["from"],
                "to_code": edge["to"],
                "gate": edge["door"],
                "gate_center": list(gate_center),
                "paths": {_start_key(start): [list(point) for point in path]},
            }
            if next_start is not None:
                route_leg["target_arrival"] = list(next_start)
            route_legs.append(route_leg)
            start = next_start
            if start is None and index < len(candidate["legs"]) - 1:
                return None

        final_paths = {}
        if start is not None:
            path = self.ground.find_world_path(dest_map, start, safe)
            if path is None:
                return None
            total_distance += _path_distance(path)
            final_paths[_start_key(start)] = [list(point) for point in path]
        return {
            "dest_map": dest_map,
            "safe": list(safe),
            "city": candidate["city"],
            "flag": candidate["flag"],
            "arrival": list(candidate["arrival"]),
            "legs": route_legs,
            "final_paths": final_paths,
            "total_distance": round(total_distance, 3),
        }

    def _arrival_after(self, edge):
        reverse_edges = [
            candidate
            for candidate in self.nav.graph.get(edge["to"], ())
            if candidate["target_scene"] == edge["scene"]
        ]
        for reverse in reverse_edges:
            gate = self.nav.get_gate(reverse["scene"], reverse["door"])
            if gate is not None:
                return tuple(gate["center"])
        return None

    def get_leg_path(self, route, scene_id, start):
        leg = next(
            (item for item in route["legs"] if item["scene"] == int(scene_id)),
            None,
        )
        if leg is None:
            return None
        key = _start_key(start)
        cached = leg["paths"].get(key)
        if cached is not None:
            return [tuple(point) for point in cached]
        path = self.ground.find_world_path(
            scene_id, tuple(start), tuple(leg["gate_center"])
        )
        if path is None:
            return None
        self.record_leg_path(route, scene_id, start, path)
        return path

    def record_leg_path(self, route, scene_id, start, path):
        leg = next(
            (item for item in route["legs"] if item["scene"] == int(scene_id)),
            None,
        )
        if leg is None:
            return False
        leg["paths"][_start_key(start)] = [list(point) for point in path]
        self.cache.put(
            route["dest_map"],
            route["safe"],
            self.nav.fingerprint,
            route,
        )
        return True
