"""Sinh donate_materials.json: TAT CA nguyen lieu (hop thanh) co the DONATE cho quan doan.

Dung cho tinh nang "Donate nguyen lieu cho quan doan": moi item co 2 trang thai GIU LAI / DONATE,
MAC DINH = DONATE HET (user doi sang GIU trong GUI/APK giong list phan giai cuon pet).

Nguyen lieu = item co KIND nam trong MATERIAL_KINDS (loai nguyen lieu hop thanh trong Item_C.dat):
  24 Sanh, 25 Go, 26 Vo, 27 Xuong, 28 Ngoc Sa, 29 Da quy/bang, 30 Da (leather), 31 Vai, 32 Giay,
  33 Truc, 34 Thao moc, 35 Hat Da, 36 Bang, 40 Kim Sa, 41 Ngan Phan, 42 Bot Dong, 43 Thiet Phan,
  44 Thiec Sa, 45 Tu Tinh, 46 Hong Tinh.
LOAI TRU (dtquy, KHONG phai nguyen lieu): 37 Kim Toa, 38 The chi so, 39 Cuoc/vu khi.
Client donate qua C:039-015 (opcode 0x27 sub0f) theo BAG INDEX; loc bag = ArmyFilter (material field).

Chay: python tools/crack_donate_materials.py   (-> ghi donate_materials.json)
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_furnace_notify import read_items        # noqa: E402

OUT = os.path.join(ROOT, "donate_materials.json")
MATERIAL_KINDS = {24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
                  40, 41, 42, 43, 44, 45, 46}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    item_path = os.path.join(ROOT, "gamedata", "Data", "Item_C.dat")
    if not os.path.exists(item_path):
        item_path = os.path.join(ROOT, "gamedata_Item.dat")
    items = read_items(item_path)
    out = {}
    for d in items:
        if d["kind"] not in MATERIAL_KINDS:
            continue
        if d["level"] <= 0:
            continue
        out["0x%04x" % d["id"]] = {"name": d["name"], "kind": d["kind"], "lv": d["level"]}
    out = dict(sorted(out.items(), key=lambda kv: (kv[1]["kind"], kv[1]["lv"], kv[1]["name"])))
    data = {
        "_note": "AUTO-SINH tu tools/crack_donate_materials.py (Item_C.dat). Nguyen lieu hop thanh co "
                 "the DONATE quan doan. tid_hex -> {name, kind, lv}. MAC DINH donate HET; user danh dau "
                 "GIU trong GUI (material_modes[tid]='keep'). Donate qua 0x27 sub0f theo slot.",
        "items": out,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=0)
    print("=> %s: %d nguyen lieu (%d kind)" % (os.path.basename(OUT), len(out), len(MATERIAL_KINDS)))


if __name__ == "__main__":
    main()
