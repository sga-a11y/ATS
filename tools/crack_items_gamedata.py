"""Sinh items_gamedata.json: ten + HP/SP hoi + co RESTRICT cua moi item.

Truong `restrict` (ItemData.lua:346 --[30] 限制) la BITMASK:
    0 co the vut | 1 vut la mat | 2 khong chuyen nhuong | 4 KHONG PHAI NGUYEN LIEU HOP
    8 KHONG THE BI HOP | 16 khong ban cho Npc | 32 khong gui ngan hang
Client loc item cho HOP VAT PHAM bang dung bit 4 (UICompound.lua:435):
    if bit.band(itemDatas[id].restrict, 4) ~= 0 then return false end
Nen bot phai dung cung dieu kien do, KHONG loc theo TEN (truoc day hardcode
_COMBINE_EXCLUDE = ("Huong Dung Ma Duoc", "Huong Dung Dai Duoc") -> sot "Bo Tay" va moi item
moi cua game).

Ghi them "restrict" vao MOI item co restrict != 0 (item binh thuong = 0 -> bo qua cho file gon).
Cac truong cu (name / hp / sp / battle) GIU NGUYEN de khong pha code dang doc file nay.

File .dat KHONG theo repo (gitignore) - copy tu client vao truoc khi chay.
Chay: python tools/crack_items_gamedata.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import _find          # noqa: E402
from crack_furnace_notify import read_items        # noqa: E402

OUT = os.path.join(ROOT, "items_gamedata.json")


def main():
    path = _find("gamedata_Item.dat", os.path.join("gamedata", "Data", "Item_C.dat"))
    if not path:
        raise SystemExit("Khong thay gamedata_Item.dat (hoac gamedata/Data/Item_C.dat)")
    items = read_items(path)

    # GIU nguyen cac truong dang co trong file cu (name/hp/sp/battle) - chi THEM restrict.
    try:
        with open(OUT, encoding="utf-8") as fh:
            old = json.load(fh)
    except Exception:
        old = {}

    # CHI THEM `restrict` vao cac item DA CO trong file. KHONG ghi de "name" va KHONG them item
    # moi: ten trong file cu bi LECH BAN GHI o ~1237 muc (vd 0x1f41 = "Trang Bi Cap 40<rac>" trong
    # khi .dat la "Tui Tinh Nhan Do") - sua ten la doi hanh vi cua nhieu cho khac (log tui, thong
    # bao, doi chieu theo ten) nen phai tach thanh viec RIENG, khong tron vao fix hop do.
    by_id = {d["id"]: d for d in items}
    out = dict(old)
    n_new = 0
    for key, rec in out.items():
        try:
            tid = int(key, 16) if key.lower().startswith("0x") else int(key)
        except ValueError:
            continue
        r = (by_id.get(tid) or {}).get("restrict", 0)
        rec = dict(rec)
        if r:
            rec["restrict"] = r
            n_new += 1
        else:
            rec.pop("restrict", None)
        out[key] = rec

    # THEM item MOI (id chua co trong file). KHONG dung vao muc da co -> ten cu giu nguyen,
    # khong doi hanh vi cho nao dang doi chieu theo ten. Khong co buoc nay thi MOI item game
    # them sau nay deu hien la "item 30558" (vd event Mung Quoc Khanh).
    n_add = 0
    for tid, d in sorted(by_id.items()):
        if ("0x%04x" % tid) in out or str(tid) in out:
            continue
        name = (d.get("name") or "").strip()
        if not name:
            continue
        rec = {"name": name}
        if d.get("restrict"):
            rec["restrict"] = d["restrict"]
        out["0x%04x" % tid] = rec
        n_add += 1

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    n_nocombine = sum(1 for v in out.values() if (v.get("restrict", 0) & 4))
    print("=> %s: %d item (+%d MOI, %d co restrict != 0, %d KHONG dung de hop duoc - bit 4)"
          % (os.path.basename(OUT), len(out), n_add, n_new, n_nocombine))


if __name__ == "__main__":
    main()
