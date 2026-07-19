"""Atomic writable storage for configured and learned train-map points."""
from __future__ import annotations

from copy import deepcopy
import json
import os
import threading


_LOCK = threading.RLock()


def _points(values):
    return [[int(point[0]), int(point[1])] for point in values or ()]


def _atomic_write(path: str, data: dict) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def merge_baseline(baseline: dict, local: dict | None) -> dict:
    result = deepcopy(baseline if isinstance(baseline, dict) else {"maps": {}})
    result.setdefault("maps", {})
    local_maps = (local or {}).get("maps", {}) if isinstance(local, dict) else {}
    for key, local_entry in local_maps.items():
        baseline_entry = result["maps"].get(key)
        if baseline_entry is None:
            result["maps"][key] = deepcopy(local_entry)
            continue
        if not isinstance(local_entry, dict) or not local_entry.get("mobs"):
            continue
        local_mobs = local_entry.get("mobs") or []
        local_safes = local_entry.get("safe") or []
        if (local_mobs == baseline_entry.get("mobs")
                and len(local_safes) != len(local_mobs)):
            continue
        merged = deepcopy(baseline_entry)
        merged.update(deepcopy(local_entry))
        if "name" in baseline_entry:
            merged["name"] = baseline_entry["name"]
        result["maps"][key] = merged
    return result


def materialize_train_maps(path: str, baseline: dict) -> dict:
    with _LOCK:
        local = None
        try:
            with open(path, encoding="utf-8") as fh:
                local = json.load(fh)
        except Exception:
            pass
        merged = merge_baseline(baseline, local)
        if local != merged:
            _atomic_write(path, merged)
        return merged


def save_learned_regions(path: str, map_id: int, safes, centers) -> bool:
    safe_points = _points(safes)
    center_points = _points(centers)
    if not center_points or len(safe_points) != len(center_points):
        return False
    with _LOCK:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return False
        maps = data.setdefault("maps", {})
        entry = maps.setdefault(str(int(map_id)), {"name": str(int(map_id))})
        if entry.get("mobs"):
            return False
        entry["safe"] = safe_points
        entry["mobs"] = center_points
        _atomic_write(path, data)
    return True
