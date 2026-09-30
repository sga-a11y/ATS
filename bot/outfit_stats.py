"""Dong CHI SO + "Nếu mặc bộ này" cho tui do APK. Ban port 1-1 cua gui.py::BagDialog
(`_cong_cua_mon`, `_cong_cua_bo`, `_stats_line`, `_dong_delta`) - cung luat, cung thu tu hien.

Tach module rieng de APK dung duoc (APK khong co gui.py). Sua luat o day thi sua ca gui.py.
"""
from __future__ import annotations

from .client import _load_gamedata_items, _load_json_data_file

# Linh da: EStoneAttr -> ma chi so + tri so theo cap (bot/pet_login_stats.py, sao tu client).
_STONE_ATTR = {1: 212, 2: 210, 3: 211, 4: 218, 5: 219, 6: 214}
_STONE_VAL = (1, 2, 3, 4, 5, 7, 9, 11, 13, 15, 18, 21, 24, 27, 30)
# Ma chi so trong DU LIEU ITEM -> ma chi so cua NHAN VAT / khoa cua pet_stats.
_I2CHAR = {212: 27, 210: 28, 211: 29, 218: 31, 219: 32, 214: 30}
_I2PET = {212: "int", 210: "atk", 211: "def", 218: "hpx", 219: "spx", 214: "agi"}
_SAU = ((212, "INT"), (210, "ATK"), (211, "DEF"), (218, "HPx"), (219, "SPx"), (214, "AGI"))
# Controller_RoleController.lua EAttribute - THU TU user chot 26/08.
_ATTR = ((27, "INT"), (28, "ATK"), (29, "DEF"), (31, "HPx"), (32, "SPx"), (30, "AGI"),
         (88, "Hút HP"), (89, "Hút SP"), (90, "Kháng"), (87, "Cường hoá"))

_eq_db = None


def _eq():
    global _eq_db
    if _eq_db is None:
        _eq_db = _load_json_data_file("eq_affix.json") or {}
    return _eq_db


def _thing_cua_tid(c, tid):
    """ThingData cua mon `tid`: uu tien mon DANG MAC, khong thi ban xin nhat trong tui."""
    for x in (getattr(c, "equipped_items", None) or []):
        if int(x.get("id", 0)) == int(tid):
            return x
    try:
        slot = c._bag_slot_best(int(tid))
    except Exception:
        slot = None
    if slot is None:
        return None
    return (getattr(c, "bag_items", None) or {}).get(slot)


def cong_cua_mon(tid, info):
    """{ma chi so: cong} cua MOT mon: ban mau + linh da + cuong hoa + dong phu."""
    out = {}
    d = _load_gamedata_items().get(int(tid)) or {}
    eq = _eq()

    def _add(ma, v):
        if ma and v:
            out[int(ma)] = out.get(int(ma), 0) + int(v)
    for _k, _v in ((d.get("a1k"), d.get("a1v")), (d.get("a2k"), d.get("a2v"))):
        if _k and _v and int(_v) != 100:
            _add(_k, int(_v) - 100)
    if not info:
        return out
    _sa, _sl = int(info.get("stone_attr") or 0), int(info.get("stone_lv") or 0)
    if _sa in _STONE_ATTR and 1 <= _sl <= len(_STONE_VAL):
        _add(_STONE_ATTR[_sa], _STONE_VAL[_sl - 1])
    _rf = int(info.get("reinforced") or 0)
    if _rf:
        for row in (eq.get("reinforced") or []):
            if (int(row.get("ft", 0)) == int(d.get("ft") or 0)
                    and int(row.get("attr", 0)) == int(d.get("a1k") or 0)
                    and int(row.get("q", 0)) == int(d.get("q") or 0)):
                for _c in (row.get("c1"), row.get("c2")):
                    _v = (eq.get("value") or {}).get(str(int(_c or 0)))
                    if _v and 1 <= _rf <= len(_v.get("lv") or []):
                        _add(_v.get("attr"), _v["lv"][_rf - 1])
                break
    for _i, _id in enumerate((info.get("affix") or [])[:3], 1):
        _row = (eq.get("affix") or {}).get(str(int(_id or 0)))
        if _row:
            _lv = _row.get("lv") or []
            _add(_row.get("attr"), _lv[_i - 1] if _i <= len(_lv) else 0)
    return out


def cong_cua_bo(c, emap):
    out = {}
    for tid in (emap or {}).values():
        if not tid:
            continue
        for ma, v in cong_cua_mon(tid, _thing_cua_tid(c, tid)).items():
            out[ma] = out.get(ma, 0) + v
    return out


def _equip_map(c, who):
    if not who:
        return dict(getattr(c, "equip_by_fit", None) or {})
    return dict((getattr(c, "pet_equip_by_fit", None) or {}).get(int(who)) or {})


def stats_line(c, who, trung_thanh_canh_bao=40):
    """Dong chi so. CHI ghi cai bot THAT SU biet - thieu thi bo qua, khong doan."""
    st = getattr(c, "state", None)
    if not who:
        lv = getattr(c, "char_level", None)
        unit = getattr(st, "char", None) if st else None
        phan = ["Cấp %s" % (lv if lv is not None else "?")]
        try:
            full = c.char_stat_full() or {}
        except Exception:
            full = {}
        attrs = getattr(c, "char_attrs", None) or {}
        for _id, _ten in _ATTR:
            if _id in full:
                phan.append("%s %s" % (_ten, full[_id]))
            elif _id in attrs:
                phan.append("%s %s" % (_ten, attrs[_id]))
        if unit is not None and getattr(unit, "hp_max", 0):
            phan.append("HP %d/%d" % (unit.hp, unit.hp_max))
            if getattr(unit, "sp_max", 0):
                phan.append("SP %d/%d" % (unit.sp, unit.sp_max))
        return "Chỉ số:   " + "   •   ".join(phan)
    _active = int(getattr(c, "active_pet_slot", 0) or 0)
    try:
        ps = c.pet_stats(int(who))
    except Exception:
        ps = None
    if not ps:
        return "Chỉ số: chưa nhận được dữ liệu pet (gói 0x0f) — thử lại sau khi login xong."
    phan = ["Cấp %s" % (ps.get("level") if ps.get("level") is not None else "?")]
    for _k, _ten in (("int", "INT"), ("atk", "ATK"), ("def", "DEF"),
                     ("hpx", "HPx"), ("spx", "SPx"), ("agi", "AGI")):
        if ps.get(_k) is not None:
            phan.append("%s %s" % (_ten, ps[_k]))
    if ps.get("hp_max"):
        phan.append("HP %s/%s" % (ps.get("hp"), ps["hp_max"]))
    if ps.get("sp_max"):
        phan.append("SP %s/%s" % (ps.get("sp"), ps["sp_max"]))
    try:
        _pid = int((getattr(st, "carried_pets", None) or [])[int(who) - 1][0])
        _tt = (getattr(c, "pet_faith", None) or {}).get(_pid)
    except Exception:
        _tt = None
    if _tt is not None:
        phan.append("Trung thành %s%s" % (_tt, " ⚠" if int(_tt) < trung_thanh_canh_bao else ""))
    if int(who) == _active:
        phan.append("★ đang xuất chiến")
    return "Chỉ số:   " + "   •   ".join(phan)


def dong_delta(c, who, bo):
    """Chi so SAU KHI mac bo `bo` ({fit: tid}). User 26/08: ghi con so KET QUA, khong ghi +-."""
    moi = cong_cua_bo(c, {int(f): int(t) for f, t in (bo or {}).items()})
    cu = cong_cua_bo(c, _equip_map(c, who))
    d = {ma: moi.get(ma, 0) - cu.get(ma, 0) for ma in set(moi) | set(cu)}
    for _a, _b in ((25, 207), (26, 208)):
        if d.get(_a):
            d[_b] = d.get(_b, 0) + d.pop(_a)
    phan = []
    if not who:
        try:
            full = dict(c.char_stat_full() or {})
        except Exception:
            full = {}
        for _k, _v in (getattr(c, "char_attrs", None) or {}).items():
            full.setdefault(_k, _v)
        for _i, _ten in _SAU:
            _c = full.get(_I2CHAR[_i])
            if _c is not None:
                phan.append("%s %d" % (_ten, int(_c) + d.get(_i, 0)))
        _u = getattr(getattr(c, "state", None), "char", None)
        if _u is not None and getattr(_u, "hp_max", 0):
            phan.append("HP %d" % (int(_u.hp_max) + d.get(207, 0)))
            if getattr(_u, "sp_max", 0):
                phan.append("SP %d" % (int(_u.sp_max) + d.get(208, 0)))
    else:
        try:
            ps = c.pet_stats(int(who)) or {}
        except Exception:
            ps = {}
        for _i, _ten in _SAU:
            _c = ps.get(_I2PET[_i])
            if _c is not None:
                phan.append("%s %d" % (_ten, int(_c) + d.get(_i, 0)))
        if ps.get("hp_max"):
            phan.append("HP %d" % (int(ps["hp_max"]) + d.get(207, 0)))
        if ps.get("sp_max"):
            phan.append("SP %d" % (int(ps["sp_max"]) + d.get(208, 0)))
    if not phan:
        return "Mặc bộ này: chưa đủ dữ liệu chỉ số"
    return "Nếu mặc bộ này:   " + "   •   ".join(phan)
