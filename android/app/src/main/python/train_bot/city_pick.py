"""Chon THANH XUAT PHAT gan nhat ma CA PARTY da mo teleport.

VI SAO CAN: truoc day bot co dinh gom o NGHIEP THANH roi di bo toi thanh gan bai train. Hai van
de user chi ra (25/08):
  1. Nghiep Thanh CUNG co the chua mo -> ke hoach chet han.
  2. Nghiep Thanh khong he "gan": di tu do toi Kien Nghiep mat 5 cong, trong khi tu Hoi Ke chi 2.

Cach lam moi: trong so cac thanh MA CA PARTY DEU DA MO, chon thanh GAN NHAT (theo so cong phai di)
toi thanh dich. Khoang cach do tren chinh do thi world_nav.json ma bot dung de di duong.

"Gan nhat" = KHOANG CACH, khong phai so `flag`. Vi du that: bai can Nghiep Thanh, ma Nghiep Thanh
chua mo -> Cu Loc (2 cong) la gan nhat, du flag cua Cu Loc (3) LON HON Nghiep Thanh (2).
"""
from __future__ import annotations

from collections import defaultdict, deque

_graph = None
_hops_cache = {}
HOP_CAP = 30      # xa hon nay coi nhu khong toi duoc (do thi co 3728 scene, 25 cong la thua)


def _load_graph():
    """{scene: set(scene ke}} tu world_nav.json. Chi can chieu di, khong can cong nao."""
    global _graph
    if _graph is not None:
        return _graph
    _graph = defaultdict(set)
    try:
        from .config import _base_dir
        import json
        import os
        with open(os.path.join(_base_dir(), "world_nav.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        for e in data.get("edges", ()):
            _graph[int(e["scene"])].add(int(e["target_scene"]))
    except Exception:
        pass
    return _graph


def city_hops(src, dest):
    """So CONG phai di tu `src` toi `dest`. None = khong toi duoc (trong gioi han HOP_CAP)."""
    src, dest = int(src), int(dest)
    if src == dest:
        return 0
    key = (src, dest)
    if key in _hops_cache:
        return _hops_cache[key]
    g = _load_graph()
    seen = {src}
    q = deque([(src, 0)])
    found = None
    while q:
        node, d = q.popleft()
        if d >= HOP_CAP:
            break
        for nxt in g.get(node, ()):
            if nxt in seen:
                continue
            if nxt == dest:
                found = d + 1
                q.clear()
                break
            seen.add(nxt)
            q.append((nxt, d + 1))
    _hops_cache[key] = found
    return found


def nearest_start_city(dest_city, unlocked, exclude=()):
    """Thanh XUAT PHAT gan `dest_city` nhat trong so `unlocked`. None neu khong co cai nao toi duoc.

    unlocked = danh sach city_id ma CA PARTY deu da mo.
    Tra (city_id, so_cong). dest_city co trong unlocked -> tra chinh no, 0 cong.
    """
    dest_city = int(dest_city)
    best = None
    for cid in unlocked:
        cid = int(cid)
        if cid in exclude:
            continue
        h = city_hops(cid, dest_city)
        if h is None:
            continue
        if best is None or h < best[1] or (h == best[1] and cid < best[0]):
            best = (cid, h)
    return best
