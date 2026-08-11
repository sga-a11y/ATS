"""Sinh pet_scrolls.json: TAT CA cuon goi vo tuong (Bi Cap) co trong game.

Dung cho tinh nang "Tu phan giai cuon vo tuong rac" (Cai dat nang cao -> Tu don tui do):
moi cuon co 2 trang thai GIU LAI / PHAN GIAI, mac dinh cuon cua vo tuong CO VU KHI CHUYEN
DUNG (vkcd) = GIU LAI, con lai = PHAN GIAI.

  kind 38 (EItemKind, Bi Cap = cuon goi pet) : spare3 = npc id cua vo tuong duoc goi
  (xem tools/crack_exclusive_weapons.py - cung layout ItemData.New() 54 truong)

KHONG khoa cung: pet co vkcd nhieu con van lom, mac dinh "giu lai" chi la GOI Y - user
van doi sang "phan giai" duoc trong GUI/APK.

Nguon: gamedata_Item.dat + gamedata_Npc.dat (KHONG theo repo - copy tu client) +
exclusive_weapons.json (tools/crack_exclusive_weapons.py).

Chay: python tools/crack_pet_scrolls.py
Ghi:  pet_scrolls.json  { "<tid_hex>": {"name": ten cuon, "npc_id": id, "npc": ten tuong,
                                        "vkcd": true/false} }
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import _find, parse_npc_names        # noqa: E402
from crack_furnace_notify import read_items                       # noqa: E402

OUT = os.path.join(ROOT, "pet_scrolls.json")
VKCD = os.path.join(ROOT, "exclusive_weapons.json")
KIND_SUMMON = 38        # Bi Cap - cuon goi pet


def main():
    item_path = _find("gamedata_Item.dat", os.path.join("gamedata", "Data", "Item_C.dat"))
    npc_path = _find("gamedata_Npc.dat", os.path.join("gamedata", "Data", "Npc_C.dat"))
    if not item_path:
        raise SystemExit("Khong thay gamedata_Item.dat (hoac gamedata/Data/Item_C.dat)")
    items = read_items(item_path)
    npcs = parse_npc_names(npc_path) if npc_path else {}

    vk = json.load(open(VKCD, encoding="utf-8"))
    vk_npc = {int(v["npc_id"]) for v in vk.values() if v.get("npc_id")}

    out = {}
    for d in items:
        if d["kind"] != KIND_SUMMON:
            continue
        npc = d["spare3"]
        # kind 38 con om ca HOP QUA / PHIEU CHON ("Qua Tan Thu", "Phieu chon vu khi..."):
        # cung kind nhung spare3 = 0 vi khong goi ra vo tuong nao -> loai, neu khong list se
        # ra 5553 muc thay vi ~400 cuon that (va bot co the phan giai nham hop qua).
        if not npc:
            continue
        out["0x%04x" % d["id"]] = {
            "name": d["name"],
            "npc_id": npc,
            "npc": npcs.get(npc, ""),
            "vkcd": bool(npc and npc in vk_npc),
        }
    out = dict(sorted(out.items(), key=lambda kv: kv[1]["name"]))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    n_keep = sum(1 for v in out.values() if v["vkcd"])
    print("=> %s: %d cuon (%d co vkcd -> mac dinh GIU LAI, %d -> PHAN GIAI)"
          % (os.path.basename(OUT), len(out), n_keep, len(out) - n_keep))


if __name__ == "__main__":
    main()
