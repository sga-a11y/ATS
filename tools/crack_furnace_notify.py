"""Sinh furnace_default_notify.json: item lo MAC DINH "Thong bao" (thay vi "Bo qua").

Yeu cau user: vo tuong nao CO VU KHI CHUYEN DUNG (vkcd) thi mach cua no dang co gia tri ->
mac dinh phai BAO cho user quyet dinh, khong duoc am tham bo qua:
  - Lo VO TUONG   : cuon goi pet (Bi Cap) cua tuong co vkcd
  - Lo CHUYEN SINH: K.Toa + T.Tinh + Me cua tuong co vkcd

GHEP THEO ID (khong theo ten - ten trong pool bi CAT NGAN, vd "Trieu V. Khuong Me"):
  kind 38 (Bi Cap) : spare3           = npc GOC
  kind 37 (K.Toa)  : attribute[1].value (a1k==65) = npc GOC, a2v = npc CHUYEN SINH
  kind 51 (T.Tinh) : a1v = npc CHUYEN SINH  -> bac cau qua K.Toa ve npc GOC
  kind 58 (Me)     : a1v = npc CHUYEN SINH  -> nhu tren
Do phu do duoc: 1188/1192 muc trong furnace_pool.json (sot 4).

Nguon: gamedata_Item.dat (KHONG theo repo - copy tu client) + furnace_pool.json +
exclusive_weapons.json (tools/crack_exclusive_weapons.py).

Chay: python tools/crack_furnace_notify.py
Ghi:  furnace_default_notify.json  { "<pool tab>": { "<tid_hex>": "<ten item>" } }
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import Reader, _find          # noqa: E402  (dung chung Reader)

OUT = os.path.join(ROOT, "furnace_default_notify.json")
POOL = os.path.join(ROOT, "furnace_pool.json")
VKCD = os.path.join(ROOT, "exclusive_weapons.json")

KIND_SUMMON = 38        # Bi Cap - cuon goi pet
KIND_KIMTOA = 37        # K.Toa
KIND_TUONGTINH = 51     # T.Tinh
KIND_ME = 58            # Me
ATTR_KIND_NPC = 65      # attribute[1].kind == 65 -> value la npc id (o item K.Toa)

# Thu tu 54 truong cua ItemData.New() - xem tools/crack_exclusive_weapons.py
FIELDS = (
    [("name", "t"), ("kind", "b"), ("id", "H"), ("iconId", "H"), ("pic1", "H"), ("pic2", "H"),
     ("a1k", "H"), ("a1i", "b"), ("a1v", "i"), ("a2k", "H"), ("a2i", "b"), ("a2v", "i"),
     ("material", "b"), ("level", "b"), ("fitType", "b"), ("specialAbility", "H")]
    + [("tint%d" % i, "i") for i in range(1, 9)]
    + [("openUsed", "b"), ("needLv", "b"), ("price", "i"), ("sellPrice", "i"), ("gender", "b"),
       ("restrict", "b"), ("threshold", "i"), ("element", "b"), ("elementValue", "i"),
       ("skillLink", "H"), ("turn", "b"), ("giftDot", "H"), ("spare2", "b"), ("spare3", "H"),
       ("restrict2", "b"), ("suitId", "H"), ("spare5", "b"), ("directUse", "b"),
       ("roleCountIndex", "H"), ("roleCountValue", "i"), ("sort", "b"), ("eq1", "b"), ("eq2", "b"),
       ("btnState", "b"), ("durable", "b"), ("furnaceKind", "b"), ("furnaceCount", "I"),
       ("quality", "b"), ("auctionTag", "b"), ("auctionSubTag", "b"), ("desc", "t")]
)


def read_items(path):
    r = Reader(open(path, "rb").read())
    fn = {"t": r.text, "b": r.byte, "H": r.u16, "I": r.u32, "i": r.i32}
    return [{nm: fn[t]() for nm, t in FIELDS} for _ in range(r.u32())]


def main():
    item_path = _find("gamedata_Item.dat", os.path.join("gamedata", "Data", "Item_C.dat"))
    if not item_path:
        raise SystemExit("Khong thay gamedata_Item.dat (hoac gamedata/Data/Item_C.dat)")
    items = read_items(item_path)
    by_id = {d["id"]: d for d in items}

    # Cau noi npc CHUYEN SINH -> npc GOC, hoc tu chinh item K.Toa (mang ca hai id)
    reinc2base = {}
    for d in items:
        if d["kind"] == KIND_KIMTOA and d["a1k"] == ATTR_KIND_NPC and d["a1v"] and d["a2v"]:
            reinc2base.setdefault(d["a2v"], d["a1v"])

    def base_npc(d):
        if d["kind"] == KIND_SUMMON and d["spare3"]:
            return d["spare3"]
        if d["kind"] == KIND_KIMTOA and d["a1k"] == ATTR_KIND_NPC:
            return d["a1v"]
        if d["kind"] in (KIND_TUONGTINH, KIND_ME) and d["a1v"]:
            return reinc2base.get(d["a1v"], 0)
        return 0

    vkcd = json.load(open(VKCD, encoding="utf-8"))
    vk_npc = {int(v["npc_id"]) for v in vkcd.values() if v.get("npc_id")}
    pool = json.load(open(POOL, encoding="utf-8"))

    out = {}
    for tab in ("Vo Tuong", "Chuyen Sinh"):     # Trang Bi KHONG doi (khong gan vao vo tuong)
        sel = {}
        for tid_hex, nm in pool.get(tab, {}).items():
            d = by_id.get(int(tid_hex, 16))
            if d and base_npc(d) in vk_npc:
                sel[tid_hex] = nm
        out[tab] = dict(sorted(sel.items()))
        print("  %-12s %3d/%d item -> mac dinh THONG BAO" % (tab, len(sel), len(pool.get(tab, {}))))

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("=> %s (%d tab)" % (os.path.basename(OUT), len(out)))


if __name__ == "__main__":
    main()
