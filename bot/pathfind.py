"""Tim duong lien map qua cong dich chuyen (BFS tren do thi co huong MAP_GATES)."""
from collections import deque
import heapq
import math
import re
import struct


def find_path(graph, src_map, dst_map):
    """graph: {map_id -> [(x,y,to), ...]}. Tra:
      []   neu da o dst (src == dst)
      list [(gate_x, gate_y, next_map), ...] = chuoi cong NGAN nhat
      None neu khong co duong (hoac src khong co trong graph)."""
    if src_map == dst_map:
        return []
    if src_map not in graph:
        return None
    visited = {src_map}
    q = deque([(src_map, [])])   # (map_hien_tai, duong_di_toi_no)
    while q:
        cur, path = q.popleft()
        for (x, y, to) in graph.get(cur, []):
            if to in visited:
                continue
            np = path + [(x, y, to)]
            if to == dst_map:
                return np
            visited.add(to)
            q.append((to, np))
    return None


def _value(grid, width, height, x, y):
    if x < 1 or x > width or y < 1 or y > height:
        return None
    return grid[(x - 1) * height + (y - 1)]


def _blocked(grid, width, height, x, y):
    value = _value(grid, width, height, x, y)
    return value is None or value & 1 == 1 or value & 4 == 4


def is_line_clear(grid, width, height, start, target):
    """Port MapManager.IsLineWay: kiem tra ca ceil/floor sat hai mep duong."""
    sx, sy = start
    tx, ty = target
    vx = -1 if sx >= tx else 1
    vy = -1 if sy >= ty else 1
    dx, dy = abs(sx - tx), abs(sy - ty)
    if dx == 0 and dy == 0:
        return not _blocked(grid, width, height, sx, sy)
    slope = dy / (dx + 0.01) if dx >= dy else dx / (dy + 0.01)
    if dx >= dy:
        for i in range(1, dx + 1):
            x = sx + i * vx
            for y in (sy + math.ceil(i * slope * vy), sy + math.floor(i * slope * vy)):
                if _blocked(grid, width, height, x, y):
                    return False
    else:
        for i in range(1, dy + 1):
            y = sy + i * vy
            for x in (sx + math.ceil(i * slope * vx), sx + math.floor(i * slope * vx)):
                if _blocked(grid, width, height, x, y):
                    return False
    return True


def _empty_target(grid, width, height, target):
    x, y = target
    if not _blocked(grid, width, height, x, y):
        return target
    # Thu tu giong MapManager.GetNearEmpty: tren, duoi, trai, phai, bon goc.
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                   (-1, -1), (-1, 1), (1, -1), (1, 1)):
        if not _blocked(grid, width, height, x + dx, y + dy):
            return x + dx, y + dy
    return None


def _smooth(grid, width, height, path):
    if len(path) < 3:
        return path
    result = [path[0]]
    current = 0
    while current < len(path) - 1:
        farthest = current + 1
        for candidate in range(current + 2, len(path)):
            if is_line_clear(grid, width, height, path[current], path[candidate]):
                farthest = candidate
        result.append(path[farthest])
        current = farthest
    return result


def find_local_path(grid, width, height, start, target, smooth=True):
    """A* noi-map tren block 1-based, 4 huong, collision bit 1/4 nhu Lua game."""
    if _blocked(grid, width, height, *start):
        return None
    target = _empty_target(grid, width, height, target)
    if target is None:
        return None
    if start == target:
        return [start]
    if is_line_clear(grid, width, height, start, target):
        return [start, target]

    frontier = [(math.dist(start, target), 0, start)]
    came_from = {start: None}
    cost_so_far = {start: 0}
    serial = 0
    while frontier:
        _, _, current = heapq.heappop(frontier)
        if current == target:
            break
        x, y = current
        for nxt in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
            if _blocked(grid, width, height, *nxt):
                continue
            new_cost = cost_so_far[current] + 1
            if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                cost_so_far[nxt] = new_cost
                came_from[nxt] = current
                serial += 1
                heapq.heappush(frontier, (new_cost + math.dist(nxt, target), serial, nxt))
    if target not in came_from:
        return None

    path = []
    current = target
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return _smooth(grid, width, height, path) if smooth else path


class GroundMapStore:
    """Doc Ground.mmg mot lan va cap map collision theo scene id."""

    def __init__(self, path):
        with open(path, "rb") as fh:
            self.data = fh.read()
        self.index = {}
        pattern = re.compile(rb"([0-9]+\.map)(.{11})(.{4})(.{4})", re.DOTALL)
        for match in pattern.finditer(self.data):
            name = match.group(1)
            if match.start(1) == 0 or self.data[match.start(1) - 1] != len(name):
                continue
            offset, size = struct.unpack("<II", match.group(3) + match.group(4))
            self.index[int(name[:-4])] = (offset, size)

    def get(self, map_id):
        entry = self.index.get(int(map_id))
        if entry is None:
            return None
        offset, size = entry
        data = self.data
        if offset < 0 or size < 13 or offset + size > len(data):
            return None
        width, height = struct.unpack_from("<II", data, offset)
        chunk_count = data[offset + 8]
        p = offset + 9 + chunk_count * 6
        grid_w, grid_h = struct.unpack_from("<HH", data, p)
        p += 4
        grid_size = grid_w * grid_h
        if p + grid_size > offset + size:
            return None
        return {"width_px": width, "height_px": height, "grid_w": grid_w,
                "grid_h": grid_h, "grid": data[p:p + grid_size]}

    def find_world_path(self, map_id, start, target):
        m = self.get(map_id)
        if m is None:
            return None
        left = math.floor((800 - m["width_px"]) * 0.5 * 0.05) * 20 \
            if m["width_px"] < 800 else 0
        top = math.floor((600 - m["height_px"]) * 0.5 * 0.05) * 20 \
            if m["height_px"] < 600 else 0
        to_block = lambda p: (math.ceil((p[0] - left) * 0.05),
                              math.ceil((p[1] - top) * 0.05))
        blocks = find_local_path(m["grid"], m["grid_w"], m["grid_h"],
                                 to_block(start), to_block(target))
        if blocks is None:
            return None
        result = [(bx * 20 - 10 + left, by * 20 - 10 + top) for bx, by in blocks]
        target_block = to_block(target)
        if blocks and blocks[-1] == target_block and not _blocked(
                m["grid"], m["grid_w"], m["grid_h"], *target_block):
            result[-1] = tuple(target)
        return result
