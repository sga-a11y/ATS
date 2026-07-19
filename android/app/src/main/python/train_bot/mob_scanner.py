"""Learn bounded monster patrols and reduce each roaming area to one center."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import threading


Point = tuple[int, int]


@dataclass
class PatrolTrace:
    sample_count: int = 0
    unique_points: list[Point] = field(default_factory=list)
    edges: set[tuple[Point, Point]] = field(default_factory=set)
    repeated_edge_count: int = 0
    last_point: Point | None = None
    last_new_at: float = 0.0

    def add(self, point: Point, now: float) -> bool:
        self.sample_count += 1
        is_new = point not in self.unique_points
        if is_new:
            self.unique_points.append(point)
            self.last_new_at = float(now)
        if self.last_point is not None and point != self.last_point:
            edge = (self.last_point, point)
            if edge in self.edges:
                self.repeated_edge_count += 1
            else:
                self.edges.add(edge)
        self.last_point = point
        return is_new

    @property
    def diameter(self) -> float:
        if len(self.unique_points) < 2:
            return 0.0
        return max(math.dist(a, b) for i, a in enumerate(self.unique_points)
                   for b in self.unique_points[i + 1:])

    def stable(self, now: float, quiet_seconds: float, min_samples: int,
               max_patrol_diameter: float) -> bool:
        return (
            self.sample_count >= min_samples
            and len(self.unique_points) >= 2
            and self.repeated_edge_count >= 1
            and self.diameter <= max_patrol_diameter
            and float(now) - self.last_new_at >= quiet_seconds
        )


@dataclass(frozen=True)
class CenterCandidate:
    point: Point
    monster_count: int
    confidence: float


class MobScanSession:
    def __init__(self, map_id: int, self_entity: bytes | None = None,
                 party_entities=None, quiet_seconds: float = 8.0,
                 min_samples: int = 3, max_patrol_diameter: float = 800.0,
                 merge_distance: float = 200.0):
        self.map_id = int(map_id)
        self.self_entity = bytes(self_entity) if self_entity else None
        self.party_entities = {bytes(e) for e in (party_entities or ()) if e}
        self.quiet_seconds = float(quiet_seconds)
        self.min_samples = int(min_samples)
        self.max_patrol_diameter = float(max_patrol_diameter)
        self.merge_distance = float(merge_distance)
        self._lock = threading.RLock()
        self._traces: dict[bytes, PatrolTrace] = {}
        self._players: set[bytes] = set()
        self._station_entities: set[bytes] = set()
        self._station_started = 0.0
        self._station_last_change = 0.0

    def begin_station(self, now: float) -> None:
        with self._lock:
            self._station_entities.clear()
            self._station_started = float(now)
            self._station_last_change = float(now)

    def mark_player(self, entity: bytes) -> None:
        entity = bytes(entity)
        with self._lock:
            self._players.add(entity)
            self._traces.pop(entity, None)
            self._station_entities.discard(entity)

    def observe_spawn(self, entity: bytes, map_id: int, x: int, y: int,
                      now: float) -> None:
        self._observe(entity, map_id, x, y, now)

    def observe_move(self, entity: bytes, map_id: int, x: int, y: int,
                     now: float) -> None:
        self._observe(entity, map_id, x, y, now)

    def _observe(self, entity: bytes, map_id: int, x: int, y: int,
                 now: float) -> None:
        entity = bytes(entity)
        if int(map_id) != self.map_id or not (0 < int(x) < 20000 and 0 < int(y) < 20000):
            return
        with self._lock:
            if (entity == self.self_entity or entity in self.party_entities
                    or entity in self._players):
                return
            is_new_entity = entity not in self._traces
            trace = self._traces.setdefault(entity, PatrolTrace())
            is_new_point = trace.add((int(x), int(y)), float(now))
            self._station_entities.add(entity)
            if is_new_entity or is_new_point:
                self._station_last_change = float(now)

    def candidate_count(self) -> int:
        with self._lock:
            return len(self._traces)

    def station_stable(self, now: float) -> bool:
        with self._lock:
            now = float(now)
            if now - self._station_last_change < self.quiet_seconds:
                return False
            if not self._station_entities:
                return now - self._station_started >= self.quiet_seconds
            return all(self._traces[e].stable(
                now, self.quiet_seconds, self.min_samples,
                self.max_patrol_diameter,
            ) for e in self._station_entities if e in self._traces)

    def stable_traces(self, now: float) -> list[PatrolTrace]:
        with self._lock:
            return [trace for trace in self._traces.values() if trace.stable(
                float(now), self.quiet_seconds, self.min_samples,
                self.max_patrol_diameter,
            )]


def _closest_pair(a: PatrolTrace, b: PatrolTrace):
    return min(((math.dist(pa, pb), pa, pb)
                for pa in a.unique_points for pb in b.unique_points),
               key=lambda item: item[0])


def _can_merge(a: PatrolTrace, b: PatrolTrace, distance: float, ground,
               map_id: int) -> bool:
    gap, pa, pb = _closest_pair(a, b)
    if gap > distance:
        return False
    if ground is None:
        return True
    path = ground.find_world_path(map_id, pa, pb)
    if not path:
        return False
    walked = sum(math.dist(p, q) for p, q in zip(path, path[1:]))
    return walked <= distance * 1.5


def _medoid(points: list[Point]) -> Point:
    unique = list(dict.fromkeys(points))
    return min(unique, key=lambda point: (
        sum(math.dist(point, other) for other in unique), point[1], point[0]
    ))


def compute_centers(session: MobScanSession, ground, start: Point,
                    now: float | None = None) -> list[CenterCandidate]:
    if now is None:
        import time
        now = time.monotonic()
    traces = session.stable_traces(float(now))
    if not traces:
        return []

    parent = list(range(len(traces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, first in enumerate(traces):
        for j in range(i + 1, len(traces)):
            if _can_merge(first, traces[j], session.merge_distance,
                          ground, session.map_id):
                union(i, j)

    groups = {}
    for i, trace in enumerate(traces):
        groups.setdefault(find(i), []).append(trace)

    centers = []
    for group in groups.values():
        point = _medoid([point for trace in group for point in trace.unique_points])
        if ground is not None:
            point = ground.nearest_walkable_world(session.map_id, point, start)
            if point is None:
                continue
        confidence = min(1.0, 0.6 + 0.1 * sum(t.repeated_edge_count for t in group))
        centers.append(CenterCandidate(tuple(map(int, point)), len(group), confidence))
    return sorted(centers, key=lambda c: (-c.monster_count, -c.confidence,
                                          c.point[1], c.point[0]))
