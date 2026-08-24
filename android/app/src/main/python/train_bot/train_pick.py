"""Tu chon MAP + DIEM TRAIN theo level party, so quai va he quai.

Luong: level party -> level quai MONG MUON -> loc map chua level do -> chon diem.

Uu tien diem CHUA CO DU LIEU (de gom thong ke he/level), het diem trong moi loc theo cau hinh.
Khong ra diem nao thi ha level mong muon xuong 1 roi tim lai.

Level cua map doc tu TEN MAP (quy uoc user tu dat): '129-130', '126', '4x'.
Level/he cua quai doc tu train_block_stats.json + npc_table.json (KHONG chep lai vao dau).
"""
from __future__ import annotations

import random
import re

from . import train_block_stats

# Cach suy level quai mong muon tu level party. Khoa nay luu trong accounts.json.
PICK_MODES = [
    ("avg-20", "Tự chọn map: level TB -20"),
    ("avg-25", "Tự chọn map: level TB -25"),
    ("avg-30", "Tự chọn map: level TB -30"),
    ("min+29", "Tự chọn map: level thấp nhất +29"),
    ("max-29", "Tự chọn map: level cao nhất -29"),
]
PICK_KEYS = [k for k, _lbl in PICK_MODES]
DEFAULT_PICK = "avg-25"        # mac dinh khi doi sang mode train

# 7 he cua game + VO HE. So 6 (EElement.None) khong npc nao dung nen khong dua vao.
ELEMENTS = [(1, "Địa"), (2, "Thủy"), (3, "Hỏa"), (4, "Phong"),
            (5, "Tâm"), (7, "Quang"), (8, "Ám"), (0, "Vô hệ")]
ALL_ELEMENTS = [e for e, _n in ELEMENTS]
DEFAULT_MOB_MIN = 3
DEFAULT_MOB_MAX = 4


def map_level_range(name):
    """Ten map -> (level thap nhat, level cao nhat). Doc duoc ca 111 map hien co.

    '129-130' -> (129,130) | '126' -> (126,126) | '4x' -> (40,49). Khong doc duoc -> None.
    """
    s = str(name or "").strip()
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*$", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (lo, hi) if lo <= hi else (hi, lo)
    m = re.search(r"(\d+)\s*[xX]\s*$", s)
    if m:
        d = int(m.group(1)) * 10
        return d, d + 9
    m = re.search(r"(\d+)\s*$", s)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None


_SOUL_PREFIX = re.compile(r"^\s*LH\s*-")


def is_soul_map(name):
    """Map 'LH-...' = quai LINH HON, cuc khoe, phai reborn 2 lan moi danh duoc.

    BOT TU CHON thi bo qua han. User chon TAY van vao binh thuong (khong chan o day).
    """
    return bool(_SOUL_PREFIX.match(str(name or "")))


def desired_level(pick_mode, levels):
    """Level quai mong muon. levels = level CUA CA CHAR VA PET moi thanh vien.

    Trung binh lam tron giong _average_party_levels ben run_party_digioi (cong len len // 2).
    """
    nums = [int(x) for x in (levels or []) if isinstance(x, int) and x > 0]
    if not nums or pick_mode not in PICK_KEYS:
        return None
    if pick_mode == "min+29":
        return max(1, min(nums) + 29)
    if pick_mode == "max-29":
        return max(1, max(nums) - 29)
    avg = (sum(nums) + len(nums) // 2) // len(nums)
    return max(1, avg - int(pick_mode.split("-")[1]))


def spot_profile(spot_data):
    """Rut gon 1 diem train: level quai, he quai, so con hay gap nhat.

    Tra None o 'levels'/'elements' khi diem CHUA CO du lieu quai -> nhanh gom du lieu dung cai nay.
    """
    spot_data = spot_data or {}
    mobs = spot_data.get("mobs") or {}
    levels, elements = [], set()
    table = train_block_stats._npc_table()
    for tid in mobs:
        info = table.get(str(tid))
        if not info:
            continue
        lv = info.get("level")
        if isinstance(lv, int) and lv > 0:
            levels.append(lv)
        elements.add(int(info.get("element") or 0))
    patterns = spot_data.get("patterns") or {}
    top_count = 0
    if patterns:
        top = max(patterns.items(), key=lambda kv: int(kv[1]))[0]
        top_count = train_block_stats._mobs_in_pattern(top)
    return {
        "levels": (min(levels), max(levels)) if levels else None,
        "elements": elements or None,
        "top_count": top_count,
        "has_data": bool(levels),
    }


def spot_matches(prof, level, mob_min, mob_max, elements):
    """Diem co hop cau hinh khong (chi goi khi diem DA CO du lieu)."""
    lv = prof.get("levels")
    if not lv or not (lv[0] <= level <= lv[1]):
        return False
    top = prof.get("top_count") or 0
    if top and not (mob_min <= top <= mob_max):
        return False
    want = set(elements or ALL_ELEMENTS)
    got = prof.get("elements")
    # Diem phai TOAN quai thuoc he da tick: tick nghia la "chi danh nhung he nay".
    return not got or got <= want


def _spots_of_maps(maps, level):
    """[(map_id, spot_index, spot_xy)] cua moi map co chua `level` trong khoang ten map."""
    out = []
    for map_id, name, mobs in maps:
        if is_soul_map(name):
            continue
        rng = map_level_range(name)
        if not rng or not (rng[0] <= level <= rng[1]):
            continue
        for i, xy in enumerate(mobs or []):
            out.append((int(map_id), i, xy))
    return out


def pick_train_spot(pick_mode, levels, maps, mob_min=DEFAULT_MOB_MIN, mob_max=DEFAULT_MOB_MAX,
                    elements=None, stats=None, rng=None):
    """-> (map_id, spot_index, level_da_dung, ly_do) hoac None.

    maps = [(map_id, ten_map, [diem...])]. Ha dan level mong muon cho toi khi ra diem.
    """
    level = desired_level(pick_mode, levels)
    if level is None:
        return None
    rng = rng or random
    stats = stats if stats is not None else train_block_stats.load_stats()
    all_spots = stats.get("maps", {})
    start = level
    while level >= 1:
        cands = _spots_of_maps(maps, level)
        if cands:
            profs = []
            no_data = []
            for map_id, idx, xy in cands:
                sd = (all_spots.get(str(map_id), {}).get("spots", {})
                      .get(train_block_stats.spot_key(xy)))
                prof = spot_profile(sd)
                if not prof["has_data"]:
                    no_data.append((map_id, idx))
                else:
                    profs.append((map_id, idx, prof))
            if no_data:
                map_id, idx = rng.choice(no_data)
                return map_id, idx, level, "chua co du lieu quai (gom du lieu)"
            ok = [(m, i) for m, i, p in profs
                  if spot_matches(p, level, mob_min, mob_max, elements)]
            if ok:
                map_id, idx = rng.choice(ok)
                return map_id, idx, level, "khop level/so quai/he"
        level -= 1
    return None if start is None else None
