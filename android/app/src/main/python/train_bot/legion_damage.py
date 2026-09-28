"""THEO DOI DAME BOSS QUAN DOAN - xem documents/LEGION_DAMAGE.md + KNOWLEDGE.md muc
"BOSS QUAN DOAN - bang damage".

Server gui TONG dame tich luy cua tung member (client gan de, khong cong don):
  - S:039-002 (0x27 sub02) bang QD luc login  -> tang them = dame LUC OFFLINE (khong dem so lan)
  - S:039-116 (0x27 sub74) roleId(8)+tong(4)  -> acc dang online: +1 lan danh, delta = dame lan do
Chi ghi khi tong server > ban ghi => nhieu acc cung QD nhan cung 1 goi thi goi thu 2 tu bo qua.
Ban ghi CHUNG theo orgId, chia tuan 0h thu Hai gio VN, giu 2 tuan.
"""
from __future__ import annotations

import json
import os
import struct
import threading
import time

_VN_OFFSET = 7 * 3600
_WEEK = 7 * 86400
KEEP_WEEKS = 2
_FILE = "legion_damage.json"
_lock = threading.Lock()


def _path():
    try:
        from ._appdir import app_dir
        return os.path.join(app_dir(), _FILE)
    except Exception:
        return _FILE


def week_start(ts: float) -> int:
    """Epoch cua 0h thu Hai (gio VN) cua tuan chua ts."""
    local = int(ts) + _VN_OFFSET
    # 1970-01-01 la thu Nam -> dich 3 ngay de ngay 0 la thu Hai
    days = (local // 86400 + 3) // 7 * 7 - 3
    return days * 86400 - _VN_OFFSET


def week_key(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(week_start(ts) + _VN_OFFSET))


def _str(b: bytes, p: int):
    n = b[p]
    return b[p + 1:p + 1 + n].decode("utf-16-le", "replace"), p + 1 + n


def parse_org_data(body: bytes):
    """S:039-002 (body tinh tu sub). -> (ten QD, [(roleId hex, ten, tong dame)], bossCount)
    hoac None. bossCount = so boss DA HA (None neu doc duoi goi loi).

    Organization.SetData + PlayerInfo.New(readOrgData=true): moi member =
    roleId(8) ten(L) lv/element/turn3/turn/career(5) sex/head(2) colorTints(8)
    online(1) score(4) weekScore(4) dutyFlags(5) bossDamage(4)."""
    try:
        name, p = _str(body, 2)
        n = 1 + body[p] + body[p + 1]
        p += 2
        out = []
        for _ in range(n):
            rid = body[p:p + 8].hex()
            nm, p = _str(body, p + 8)
            p += 7 + 8 + 1 + 4 + 4 + 5
            dmg = struct.unpack_from("<I", body, p)[0]
            p += 4
            out.append((rid, nm, dmg))
    except (IndexError, struct.error):
        return None
    try:
        # quy che(L) giai tan(8) thanh lap(8) dong minh(1) co(1) hoat dong tuan(4)/tich luy(4)
        _decl, p = _str(body, p)
        count = struct.unpack_from("<H", body, p + 26)[0]
    except (IndexError, struct.error):
        count = None
    return name, out, count


def parse_boss_info(body: bytes):
    """S:039-115 -> bossCount (so boss DA HA). Boss dang danh = cap bossCount + 1
    (Organization.GetBossHp: HP = cap * 150000)."""
    if len(body) < 8:
        return None
    return struct.unpack_from("<H", body, 2)[0]


def parse_member_boss(body: bytes):
    """S:039-116 -> (roleId hex, tong dame) hoac None."""
    if len(body) < 14:
        return None
    return body[2:10].hex(), struct.unpack_from("<I", body, 10)[0]


def load():
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            d.setdefault("orgs", {})
            d.setdefault("accounts", {})
            return d
    except Exception:
        pass
    return {"orgs": {}, "accounts": {}}


def _save(d):
    p = _path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, p)


def _prune(org, now):
    keep = {week_key(now - i * _WEEK) for i in range(KEEP_WEEKS)}
    for k in list(org.get("weeks", {})):
        if k not in keep:
            del org["weeks"][k]


def _apply(d, org_id, rid, name, total, live, now, lv=None, allow_reset=True):
    """Ghi 1 member vao ban ghi. -> dict su kien (de log) hoac None neu khong doi gi."""
    org = d["orgs"].setdefault(str(org_id), {"name": "", "updated": 0, "weeks": {}})
    wk = org["weeks"].setdefault(week_key(now), {})
    m = wk.setdefault(rid, {"name": "", "total": 0, "hits": 0, "last": 0, "log": []})
    names = org.setdefault("names", {})
    if name:
        names[rid] = name
    m["name"] = names.get(rid, m["name"])
    old = int(m.get("total", 0))
    if total == old:
        return None
    if total < old:
        if not allow_reset:   # bang QD CU (nap bu khi tick giua chung) -> khong phai reset
            return None
        m["total"] = total
        m["log"].append({"ts": int(now), "dmg": 0, "off": 0, "reset": 1})
        return {"rid": rid, "name": m["name"], "reset": True, "total": total}
    delta = total - old
    m["total"] = total
    m["last"] = int(now)
    e = {"ts": int(now), "dmg": delta, "off": 0 if live else 1}
    if live and lv:
        e["lv"] = lv   # dame offline KHONG biet danh cap nao -> khong ghi
    m["log"].append(e)
    if live:
        m["hits"] = int(m.get("hits", 0)) + 1
        org["last_hit"] = [week_key(now), rid, len(m["log"]) - 1, int(now)]
    org["updated"] = int(now)
    return {"rid": rid, "name": m["name"], "delta": delta, "total": total, "live": live,
            "hits": m["hits"], "lv": lv if live else None}


def on_org_data(username, org_id, body, now=None, stale=False):
    """Goi 039-002 (acc vua vao game). -> list su kien.

    stale=True: bang giu tu luc login, nap bu khi user TICK luc acc dang chay (bang QD chi gui 1
    lan luc login). Van lay ten/cap boss; tong chi ghi neu LON HON, khong bao gio coi la reset."""
    now = time.time() if now is None else now
    r = parse_org_data(body)
    if r is None or not org_id:
        return []
    oname, members, count = r
    ev = []
    with _lock:
        d = load()
        d["accounts"][username] = str(org_id)
        for rid, nm, dmg in members:
            e = _apply(d, org_id, rid, nm, dmg, False, now, allow_reset=not stale)
            if e:
                ev.append(e)
        org = d["orgs"].setdefault(str(org_id), {"name": "", "updated": 0, "weeks": {}})
        org["name"] = oname
        if count is not None:
            org["boss_count"] = count
        org["updated"] = int(now)
        _prune(org, now)
        _save(d)
    return ev


def on_member_boss(username, org_id, body, now=None):
    """Goi 039-116 (acc dang online). -> su kien hoac None."""
    now = time.time() if now is None else now
    r = parse_member_boss(body)
    if r is None or not org_id:
        return None
    rid, total = r
    with _lock:
        d = load()
        d["accounts"][username] = str(org_id)
        org = d["orgs"].setdefault(str(org_id), {"name": "", "updated": 0, "weeks": {}})
        bc = org.get("boss_count")
        e = _apply(d, org_id, rid, "", total, True, now, None if bc is None else boss_level(bc))
        _prune(org, now)
        _save(d)
    return e


# Boss QD QUAY VONG Lv1 -> Lv7 -> Lv1 (user xac nhan 28/09). Client KHONG co vong nay
# (GetBossHp chi la bossCount + 1) -> server tu lam; chua biet server dua bossCount ve 0 hay de
# tang mai, nen dung % de dung ca hai.
BOSS_LEVELS = 7


def boss_level(count) -> int:
    """bossCount (so boss da ha) -> cap boss DANG danh (1..7)."""
    return int(count) % BOSS_LEVELS + 1


KILL_WINDOW = 30   # giay: 039-115 toi ngay sau 039-116 cua chinh lan danh do (capture: lien ke)


def on_boss_info(username, org_id, body, now=None):
    """Goi 039-115 (sau moi lan danh). bossCount tang -> lan danh vua ghi da HA boss.
    -> (lv boss vua ha, su kien lan danh) hoac None."""
    now = time.time() if now is None else now
    count = parse_boss_info(body)
    if count is None or not org_id:
        return None
    out = None
    with _lock:
        d = load()
        org = d["orgs"].setdefault(str(org_id), {"name": "", "updated": 0, "weeks": {}})
        old = org.get("boss_count")
        if old is not None and count == old:
            return None
        lh = org.get("last_hit")
        if old is not None and count != old and lh and now - lh[3] <= KILL_WINDOW:
            try:
                m = org["weeks"][lh[0]][lh[1]]
                hit = m["log"][lh[2]]
                hit["kill"] = 1
                out = (hit.get("lv") or "?", {"rid": lh[1], "name": m.get("name", "")})
            except (KeyError, IndexError):
                pass
            org["last_hit"] = None
        org["boss_count"] = count
        _save(d)
    return out


def info(username, org_id=None, now=None):
    """Du lieu cho UI. org_id None -> lay theo acc da ghi lan truoc (xem offline)."""
    now = time.time() if now is None else now
    d = load()
    oid = str(org_id) if org_id else d["accounts"].get(username)
    org = d["orgs"].get(oid) if oid else None
    if not org:
        return {"org_id": oid or "", "name": "", "updated": 0, "weeks": []}
    weeks = []
    for i in range(KEEP_WEEKS):
        k = week_key(now - i * _WEEK)
        ms = org.get("weeks", {}).get(k, {})
        rows = sorted(({"rid": rid, **m} for rid, m in ms.items()),
                      key=lambda x: (-int(x.get("total", 0)), x["rid"]))
        weeks.append({"week": k, "members": rows})
    return {"org_id": oid, "name": org.get("name", ""), "updated": org.get("updated", 0),
            "weeks": weeks}
