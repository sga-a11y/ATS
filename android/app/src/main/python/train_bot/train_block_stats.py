"""Train-map monster block statistics.

Counts the block shape of enemies seen at the start of each train-map battle,
grouped by map id and configured mob point.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Iterable

from ._appdir import app_dir


_LOCK = threading.Lock()
_FILE = "train_block_stats.json"
MAX_SPOT_BATTLES = 100_000   # toi da so tran ghi/diem (du thay ti le, file khoi phinh)


def _path() -> str:
    return os.path.join(app_dir(), _FILE)


def spot_key(spot) -> str:
    x, y = spot
    return f"{int(x)},{int(y)}"


def _load_unlocked() -> dict:
    path = _path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("version", 1)
            data.setdefault("maps", {})
            return data
    except Exception:
        pass
    # Android ships a seed copy in assets/train_bot_data. On first write, the
    # runtime file in app_dir() takes over and keeps accumulating.
    try:
        from .config import _read_asset
        data = json.loads(_read_asset(_FILE))
        if isinstance(data, dict):
            data.setdefault("version", 1)
            data.setdefault("maps", {})
            return data
    except Exception:
        pass
    return {"version": 1, "maps": {}}


def load_stats() -> dict:
    with _LOCK:
        return _load_unlocked()


def _save_unlocked(data: dict) -> None:
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _runs(cols: Iterable[int]) -> list[list[int]]:
    out = []
    cur = []
    for c in sorted(set(int(x) for x in cols)):
        if cur and c != cur[-1] + 1:
            out.append(cur)
            cur = []
        cur.append(c)
    if cur:
        out.append(cur)
    return out


def cells_from_enemy_slots(enemy_slots: Iterable[int]) -> list[tuple[int, int]]:
    """Convert internal enemy pos (row*10 + col) to (row, col).

    The game sends row 0/1 and position 0..4 separately. The bot stores that
    as row*10 + col for combat targeting.
    """
    cells = []
    for pos in enemy_slots:
        pos = int(pos)
        if pos >= 10:
            row, col = divmod(pos, 10)
        else:
            row, col = 0, pos
        if row in (0, 1) and 0 <= col <= 4:
            cell = (row, col)
            if cell not in cells:
                cells.append(cell)
    return sorted(cells)


def block_pattern_from_cells(cells: Iterable[tuple[int, int]]) -> str:
    """Return row-only block shape like '3x1 + 1x1'.

    Blocks are counted only by horizontal runs on each enemy row. Vertical
    alignment is intentionally ignored: two rows of 3 enemies become
    '3x1 + 3x1', not '3x2'.
    """
    rows = {0: set(), 1: set()}
    for row, col in cells:
        row = int(row)
        col = int(col)
        if row in rows and 0 <= col <= 4:
            rows[row].add(col)

    blocks = []
    for row in (0, 1):
        for run in _runs(rows[row]):
            blocks.append((run[0], row, len(run), 1))

    if not blocks:
        return "0"
    blocks.sort(key=lambda b: (b[0], b[1], -b[2], -b[3]))
    counts = {}
    order = []
    for _col, _row, width, _height in blocks:
        if width not in counts:
            counts[width] = 0
            order.append(width)
        counts[width] += 1
    return " + ".join(f"{w}x{counts[w]}" for w in order)


def block_pattern_from_slots(enemy_slots: Iterable[int]) -> str:
    return block_pattern_from_cells(cells_from_enemy_slots(enemy_slots))


def record_battle(map_id: int, spot, enemy_slots: Iterable[int]) -> dict | None:
    cells = cells_from_enemy_slots(enemy_slots)
    if not cells:
        return None
    pattern = block_pattern_from_cells(cells)
    mkey = str(int(map_id))
    skey = spot_key(spot)
    now = int(time.time())

    with _LOCK:
        data = _load_unlocked()
        spot_data = (data.setdefault("maps", {})
                         .setdefault(mkey, {})
                         .setdefault("spots", {})
                         .setdefault(skey, {"total": 0, "patterns": {}}))
        if int(spot_data.get("total", 0)) >= MAX_SPOT_BATTLES:
            return None
        spot_data["total"] = int(spot_data.get("total", 0)) + 1
        patterns = spot_data.setdefault("patterns", {})
        patterns[pattern] = int(patterns.get(pattern, 0)) + 1
        spot_data["last_slots"] = [f"{row}:{col}" for row, col in cells]
        spot_data["last_pattern"] = pattern
        spot_data["updated_at"] = now
        _save_unlocked(data)
        return {"total": spot_data["total"], "pattern": pattern, "count": patterns[pattern]}


def get_spot_summary(map_id: int, spot) -> dict:
    data = load_stats()
    return (data.get("maps", {})
                .get(str(int(map_id)), {})
                .get("spots", {})
                .get(spot_key(spot), {"total": 0, "patterns": {}}))


def format_patterns(patterns: dict, limit: int = 6) -> str:
    rows = sorted(((str(k), int(v)) for k, v in (patterns or {}).items()),
                  key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{k}: {v}" for k, v in rows[:limit])
