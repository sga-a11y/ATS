"""Tim duong lien map qua cong dich chuyen (BFS tren do thi co huong MAP_GATES)."""
from collections import deque


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
