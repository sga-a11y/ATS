"""Crack chi so TRANG BI tu gamedata/Data/Item_C.dat -> equip_stats.json.

Layout record = ItemData.New(reader) trong client (Data_ItemData.lua):
 [count i32] roi count record, moi record:
  name(u16len+utf16) kind(u8) Id(u16) iconId(u16) picId(u16*2)
  attr1{kind u16, attrItem u8, value i32} attr2{...}
  material(u8) level(u8) fitType(u8) specialAbility(u16) colorTints(i32*8)
  openUsed(u8) needLv(u8) price(i32) sellPrice(i32) gender(u8) restrict(u8)
  threshold(i32) element(u8) elementValue(i32) skillLink(u16) turn(u8)
  giftDot(u16) spare2(u8) spare3(u16) restrict2(u8) suitId(u16) spare5(u8)
  directUse(u8) roleCountIndex(u16) roleCountValue(i32) sort(u8)
  equipSwitch(u8*2) btnState(u8) durable(u8) furnaceKind(u8) furnaceCount(u32)
  quality(u8) auctionTag(u8) auctionSubTag(u8) description(u16len+utf16)

Chi xuat item TRANG BI (fitType 1-6, 100). Value thuoc tinh la dang GOC-100
(bonus that = value-100); elementValue tuong tu. Xuat GIA TRI GOC, hien thi tru 100.
"""
import struct, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAT = os.path.join(ROOT, "gamedata", "Data", "Item_C.dat")
OUT = os.path.join(ROOT, "equip_stats.json")
EQUIP_FIT = {1, 2, 3, 4, 5, 6, 100}   # mu/ao/vu khi/ho uyen/giay/dac biet/phong


def crack():
    data = open(DAT, "rb").read()
    p = 0
    def u8():
        nonlocal p; v = data[p]; p += 1; return v
    def u16():
        nonlocal p; v = struct.unpack_from("<H", data, p)[0]; p += 2; return v
    def i32():
        nonlocal p; v = struct.unpack_from("<i", data, p)[0]; p += 4; return v
    def u32():
        nonlocal p; v = struct.unpack_from("<I", data, p)[0]; p += 4; return v
    def s():
        nonlocal p; n = u16(); v = data[p:p+n].decode("utf-16-le", "replace"); p += n; return v

    count = i32()
    out = {}
    for _ in range(count):
        if p >= len(data):
            break
        name = s(); kind = u8(); Id = u16(); u16(); u16(); u16()
        a1 = (u16(), u8(), i32()); a2 = (u16(), u8(), i32())
        u8(); level = u8(); fitType = u8(); u16()
        for _c in range(8):
            i32()
        u8(); needLv = u8(); i32(); i32(); u8(); u8()
        i32(); element = u8(); elementValue = i32(); u16(); u8()
        u16(); u8(); u16(); u8(); suitId = u16(); u8()
        u8(); u16(); i32(); u8()
        u8(); u8(); u8(); u8(); u8(); u32()
        quality = u8(); u8(); u8()
        s()   # description
        if Id == 0 or fitType not in EQUIP_FIT:
            continue
        attrs = [[k, v] for (k, _ai, v) in (a1, a2) if k != 0]
        out["0x%04x" % Id] = {
            "n": name, "lv": needLv, "q": quality,
            "e": element, "ev": elementValue,
            "a": attrs, "fit": fitType, "kind": kind, "suit": suitId,
        }
    return out


def _max_bonus(v):
    return max([val - 100 for _k, val in v["a"]] or [0])


def merge_default_notify(equip):
    """Them item Trang Bi co chi so >= +40 vao furnace_default_notify.json (tab 'Trang Bi').
    Engine + UI da tu default nhung item trong file nay la 'Thong bao'. Chi lay item CO trong
    furnace_pool.json (Trang Bi)."""
    pool_path = os.path.join(ROOT, "furnace_pool.json")
    dn_path = os.path.join(ROOT, "furnace_default_notify.json")
    try:
        pool = json.load(open(pool_path, encoding="utf-8")).get("Trang Bi", {})
    except Exception:
        pool = {}
    try:
        dn = json.load(open(dn_path, encoding="utf-8"))
    except Exception:
        dn = {}
    tb = {}
    for idh, nm in pool.items():
        v = equip.get(idh)
        if v and _max_bonus(v) >= 40:
            tb[idh] = nm
    dn["Trang Bi"] = tb   # ghi de tab Trang Bi (giu Vo Tuong / Chuyen Sinh cua crack_furnace_notify)
    json.dump(dn, open(dn_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("furnace_default_notify.json: them %d Trang Bi >=+40 (default Thong bao)" % len(tb))


if __name__ == "__main__":
    d = crack()
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))
    print("equip_stats.json:", len(d), "trang bi ->", OUT)
    merge_default_notify(d)
