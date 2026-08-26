# -*- coding: utf-8 -*-
"""Sinh `exchange.json` (bang DOI cua "the doi" / hop chon qua) tu `Data/Exchange_C.dat`.

Vi sao can: item co `specialAbility == EItemUseKind.Exchange (219)` KHONG dung goi dung item
thuong. Client mo bang cho user chon roi gui goi RIENG:

    C:090-001 <兌換> +兌換物品ID(2) +選取數量(1) <<+選取索引(1)>>   -> opcode 0x5a sub 01

So muc phai chon = `itemData.elementValue` (Logic_Item.lua:1999-2035). Danh sach muc nam trong
`exchangeDatas[itemId][index]` doc tu file nay - client KHONG gui danh sach do qua mang, nen bot
phai tu tra bang moi biet index nao ra item gi.

Cau truc (crack `Data_ExchangeData.lua` + `DataManager.OnLoadExchange`):
    [count i32] + moi ban ghi 6 byte: [groupId u16][itemId u16][count u16]
Ban ghi cung `groupId` nam lien nhau, index tinh theo THU TU xuat hien (bat dau tu 1).

Dung:
    python tools/crack_exchange.py
"""
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "exchange.json")


def _find(*names):
    for n in names:
        p = n if os.path.isabs(n) else os.path.join(ROOT, n)
        if os.path.exists(p):
            return p
    return None


def read_exchange(path):
    """{group_id: [(item_id, count), ...]} - thu tu trong list CHINH LA index (1-based)."""
    with open(path, "rb") as fh:
        data = fh.read()
    count = struct.unpack_from("<i", data, 0)[0]
    cur = 4
    out = {}
    for _ in range(count):
        gid, iid, cnt = struct.unpack_from("<HHH", data, cur)
        cur += 6
        out.setdefault(gid, []).append((iid, cnt))
    return out


def _item_names():
    try:
        with open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return {}
    out = {}
    for k, v in d.items():
        try:
            out[int(k, 16)] = (v or {}).get("name") or ""
        except (TypeError, ValueError):
            pass
    return out


def main():
    path = _find("gamedata/Data/Exchange_C.dat", "gamedata_Exchange.dat")
    if not path:
        print("khong tim thay Exchange_C.dat - keo tu may ao:")
        print("  adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/Exchange_C.dat "
              "gamedata/Data/")
        return 1
    groups = read_exchange(path)
    ten = _item_names()
    out = {}
    for gid, rows in groups.items():
        out["0x%04x" % gid] = [
            {"i": i, "id": "0x%04x" % iid, "n": cnt, "ten": ten.get(iid, "")}
            for i, (iid, cnt) in enumerate(rows, 1)
        ]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"groups": out}, fh, ensure_ascii=False, separators=(",", ":"))
    print("da ghi %s: %d the doi (%d muc)"
          % (os.path.basename(OUT), len(out), sum(len(v) for v in out.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
